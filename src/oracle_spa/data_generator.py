"""Bounded-memory synthetic rows and stable, versioned dataset fingerprints."""

from datetime import datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from itertools import islice
import json
from pathlib import Path
import random

from oracle_spa.config import ConfigError

ROOT = Path(__file__).resolve().parents[2]
TABLES = ("CUSTOMERS", "PRODUCTS", "ORDERS", "ORDER_ITEMS")
REGIONS = ("NORTH", "SOUTH", "EAST", "WEST", "CENTRAL")
CATEGORIES = ("BOOKS", "HOME", "SPORT", "TECH", "TOYS")
STATUSES = ("NEW", "PAID", "SHIPPED", "CANCELLED")
VERSION = 1


def settings():
    try:
        value = json.loads((ROOT / "config/datasets.json").read_text())
        if set(value) != {"version", "default_seed", "reference_date", "batch_size", "profiles"}:
            raise ValueError
        if value["version"] != VERSION or set(value["profiles"]) != {"tiny", "small", "medium", "large"}:
            raise ValueError
        datetime.strptime(value["reference_date"], "%Y-%m-%d")
        if type(value["default_seed"]) is not int or not 0 <= value["default_seed"] < 2**63:
            raise ValueError
        if type(value["batch_size"]) is not int or not 1 <= value["batch_size"] <= 5000:
            raise ValueError
        for counts in value["profiles"].values():
            if set(counts) != {t.lower() for t in TABLES}:
                raise ValueError
            if any(type(n) is not int or not 1 <= n <= 1_000_000 for n in counts.values()):
                raise ValueError
            if counts["order_items"] < counts["orders"] or counts["order_items"] > 20 * counts["orders"]:
                raise ValueError
    except (OSError, ValueError, TypeError, KeyError):
        raise ConfigError("Invalid versioned dataset configuration.") from None
    return value


class Dataset:
    def __init__(self, profile="tiny", seed=None):
        self.settings = settings()
        if profile not in self.settings["profiles"]:
            raise ConfigError("Unknown dataset profile; use tiny, small, medium or large.")
        seed = self.settings["default_seed"] if seed is None else seed
        if type(seed) is not int or not 0 <= seed < 2**63:
            raise ConfigError("Seed must be an integer between 0 and 2^63-1.")
        self.profile, self.seed = profile, seed
        self.counts = self.settings["profiles"][profile]
        self.reference = datetime.strptime(self.settings["reference_date"], "%Y-%m-%d")
        self.batch_size = self.settings["batch_size"]

    def rng(self, stream):
        # Separate streams keep rows independent of fetch/insert batch boundaries.
        return random.Random(f"ospa:{VERSION}:{self.seed}:{stream}")

    def customers(self):
        rng = self.rng("customers")
        for identity in range(1, self.counts["customers"] + 1):
            yield (identity, f"Synthetic Customer {identity:08d}",
                   f"customer{identity:08d}@example.invalid", REGIONS[rng.randrange(5)],
                   self.reference - timedelta(days=730 + rng.randrange(365)))

    def price(self, identity):
        cents = 100 + (identity * 7919 + self.seed % 100000) % 99901
        return Decimal(cents) / 100

    def products(self):
        rng = self.rng("products")
        for identity in range(1, self.counts["products"] + 1):
            yield (identity, rng.choices(CATEGORIES, weights=(50, 20, 15, 10, 5))[0],
                   f"Synthetic Product {identity:08d}", self.price(identity),
                   int(rng.randrange(10) != 0))

    def order_groups(self):
        rng = self.rng("orders")
        base, extra = divmod(self.counts["order_items"], self.counts["orders"])
        item_id = 0
        for order_id in range(1, self.counts["orders"] + 1):
            limit = max(1, self.counts["customers"] // 10) if rng.randrange(10) < 8 else self.counts["customers"]
            customer_id = rng.randrange(1, limit + 1)
            status = rng.choices(STATUSES, weights=(10, 60, 25, 5))[0]
            age = rng.randrange(90) if rng.randrange(10) < 7 else rng.randrange(365)
            date = self.reference - timedelta(days=age, seconds=rng.randrange(1, 86401))
            items = []
            for _ in range(base + (order_id <= extra)):
                item_id += 1
                product_id = rng.randrange(1, self.counts["products"] + 1)
                items.append((item_id, order_id, product_id, rng.randrange(1, 6), self.price(product_id)))
            total = sum((item[3] * item[4] for item in items), Decimal(0))
            yield (order_id, customer_id, date, status, total), items

    def rows(self, table):
        if table == "CUSTOMERS":
            yield from self.customers()
        elif table == "PRODUCTS":
            yield from self.products()
        elif table == "ORDERS":
            for order, _ in self.order_groups():
                yield order
        elif table == "ORDER_ITEMS":
            for _, items in self.order_groups():
                yield from items
        else:
            raise ConfigError("Unknown dataset table.")

    def manifest(self):
        config_hash = sha256(json.dumps(self.settings, sort_keys=True).encode()).hexdigest()
        return {"version": VERSION, "profile": self.profile, "seed": self.seed,
                "reference_date": self.settings["reference_date"], "config_sha256": config_hash,
                "counts": self.counts, "checksums": {t: checksum(self.rows(t)) for t in TABLES}}


def batches(rows, size):
    if type(size) is not int or size < 1:
        raise ConfigError("Batch size must be positive.")
    iterator = iter(rows)
    while batch := list(islice(iterator, size)):
        yield batch


def canonical(row):
    def normalize(value):
        if isinstance(value, datetime):
            return value.isoformat(timespec="seconds")
        if isinstance(value, (Decimal, int, float)):
            return format(Decimal(str(value)).normalize(), "f")
        return value
    return json.dumps([normalize(v) for v in row], ensure_ascii=True, separators=(",", ":"))


def checksum(rows):
    digest = sha256()
    for row in rows:
        digest.update((canonical(row) + "\n").encode())
    return digest.hexdigest()

"""Atomic batch loading into a verified, exclusively locked laboratory schema."""

from datetime import datetime, timezone
import json
from time import perf_counter

from oracle_spa.data_generator import Dataset, TABLES, batches
from oracle_spa.db import DiagnosticError
from oracle_spa.schema import ALL_TABLES, COLUMNS, lock_tables
from oracle_spa.validation import read_manifest, validate_data


def load_data(connection, profile="tiny", seed=None):
    dataset = Dataset(profile, seed)
    start = perf_counter()
    manifest = dataset.manifest()
    generation_seconds = perf_counter() - start
    lock_tables(connection)
    try:
        with connection.cursor() as cursor:
            counts = {}
            for table in ALL_TABLES:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                counts[table] = cursor.fetchone()[0]
            if any(counts.values()):
                _, existing = read_manifest(connection)
                if existing != manifest:
                    raise DiagnosticError("Existing dataset differs; explicit authorized reset is required before another profile/seed.")
                result = validate_data(connection)
                connection.rollback()
                return {"load": "reused", "validation": result}
            start = perf_counter()
            for table in TABLES:
                columns = ", ".join(name for name, _ in COLUMNS[table])
                binds = ", ".join(f":{i}" for i in range(1, len(COLUMNS[table]) + 1))
                for batch in batches(dataset.rows(table), dataset.batch_size):
                    cursor.executemany(f"INSERT INTO {table} ({columns}) VALUES ({binds})", batch)
            cursor.execute("INSERT INTO ospa_dataset (dataset_id, profile, seed, manifest, loaded_at) VALUES (1,:profile,:seed,:manifest,:loaded_at)",
                           profile=dataset.profile, seed=dataset.seed, manifest=json.dumps(manifest, sort_keys=True),
                           loaded_at=datetime.now(timezone.utc).replace(tzinfo=None))
            load_seconds = perf_counter() - start
        result = validate_data(connection, dataset, manifest)
        connection.commit()
        return {"load": "committed", "generation_checksum_seconds": generation_seconds,
                "generation_and_insert_seconds": load_seconds, "validation": result}
    except BaseException:
        connection.rollback()
        raise

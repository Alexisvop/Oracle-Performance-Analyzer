"""Live SQL integrity checks and exact ordered comparison with regenerated rows."""

from collections import Counter
from itertools import zip_longest
import json

from oracle_spa.data_generator import Dataset, TABLES, canonical, checksum
from oracle_spa.db import DiagnosticError
from oracle_spa.schema import COLUMNS, inspect_schema


def read_manifest(connection):
    with connection.cursor() as cursor:
        cursor.execute("SELECT profile, seed, manifest FROM ospa_dataset WHERE dataset_id=1")
        rows = cursor.fetchall()
    if len(rows) != 1:
        raise DiagnosticError("No unique committed dataset manifest; load data or review partial state.")
    try:
        profile, seed, text = rows[0]
        manifest = json.loads(text)
        dataset = Dataset(profile, seed)
        if manifest != dataset.manifest():
            raise ValueError
    except (ValueError, TypeError, KeyError):
        raise DiagnosticError("Dataset metadata differs from versioned generator/configuration.") from None
    return dataset, manifest


def fetch_rows(connection, table, size=500):
    if table not in TABLES:
        raise DiagnosticError("Unknown validation table.")
    columns = ", ".join(name for name, _ in COLUMNS[table])
    with connection.cursor() as cursor:
        cursor.arraysize = size
        cursor.execute(f"SELECT {columns} FROM {table} ORDER BY {COLUMNS[table][0][0]}", fetch_decimals=True)
        while batch := cursor.fetchmany(size):
            yield from batch


def compare_rows(actual, expected):
    sentinel = object()
    for left, right in zip_longest(actual, expected, fillvalue=sentinel):
        if left is sentinel or right is sentinel or canonical(left) != canonical(right):
            raise DiagnosticError("Dataset rows differ from the recorded profile/seed; no data changed.")


def validate_data(connection, dataset=None, manifest=None, allowed_indexes=(), *, backup_permit=None):
    options = {"backup_permit": backup_permit} if backup_permit is not None else {}
    if inspect_schema(connection, allowed_indexes, **options) != "ready":
        raise DiagnosticError("Expected a complete initialized laboratory schema.")
    if dataset is None:
        dataset, manifest = read_manifest(connection)
    result = {"profile": dataset.profile, "seed": dataset.seed, "counts": {}, "checksums": {}, "distributions": {}}
    with connection.cursor() as cursor:
        for table in TABLES:
            pk = COLUMNS[table][0][0]
            cursor.execute(f"SELECT COUNT(*), COUNT(DISTINCT {pk}), MIN({pk}), MAX({pk}) FROM {table}")
            expected = dataset.counts[table.lower()]
            if cursor.fetchone() != (expected, expected, 1, expected):
                raise DiagnosticError("Row counts, duplicate keys or ID range failed validation.")
            result["counts"][table] = expected
            nulls = " OR ".join(f"{col} IS NULL" for col, _ in COLUMNS[table])
            cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE {nulls}")
            if cursor.fetchone() != (0,):
                raise DiagnosticError("Unexpected NULL values.")
        checks = [
            "SELECT COUNT(*) FROM orders o LEFT JOIN customers c ON c.customer_id=o.customer_id WHERE c.customer_id IS NULL",
            "SELECT COUNT(*) FROM order_items i LEFT JOIN orders o ON o.order_id=i.order_id WHERE o.order_id IS NULL",
            "SELECT COUNT(*) FROM order_items i LEFT JOIN products p ON p.product_id=i.product_id WHERE p.product_id IS NULL",
            "SELECT COUNT(*) FROM products WHERE unit_price<=0 OR is_active NOT IN (0,1)",
            "SELECT COUNT(*) FROM order_items WHERE quantity<=0 OR unit_price<=0",
            "SELECT COUNT(*) FROM orders WHERE total_amount<=0 OR status NOT IN ('NEW','PAID','SHIPPED','CANCELLED')",
            "SELECT COUNT(*) FROM orders o LEFT JOIN (SELECT order_id, SUM(quantity*unit_price) total FROM order_items GROUP BY order_id) i ON i.order_id=o.order_id WHERE i.total IS NULL OR o.total_amount<>i.total",
            "SELECT COUNT(*) FROM orders o JOIN customers c ON c.customer_id=o.customer_id WHERE o.order_date<c.created_at",
        ]
        for sql in checks:
            cursor.execute(sql)
            if cursor.fetchone() != (0,):
                raise DiagnosticError("Referential, domain, date or monetary integrity failed.")
        for table, column, index in (("CUSTOMERS", "REGION", 3), ("PRODUCTS", "CATEGORY", 1), ("ORDERS", "STATUS", 3)):
            cursor.execute(f"SELECT {column}, COUNT(*) FROM {table} GROUP BY {column} ORDER BY {column}")
            observed = dict(cursor.fetchall())
            expected = dict(Counter(row[index] for row in dataset.rows(table)))
            if observed != expected:
                raise DiagnosticError("Observed distribution differs from deterministic generation.")
            result["distributions"][column.lower()] = observed
        cursor.execute("SELECT COUNT(*) FROM orders WHERE customer_id<=:limit", limit=max(1, dataset.counts["customers"] // 10))
        result["distributions"]["orders_hot_customers"] = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM orders WHERE order_date>=:cutoff", cutoff=dataset.reference.replace(hour=0))
        # A fixed reference boundary is also checked by the exact row comparison below.
        if cursor.fetchone() != (0,):
            raise DiagnosticError("Orders must precede the fixed reference boundary.")
    for table in TABLES:
        actual = fetch_rows(connection, table, dataset.batch_size)
        try:
            compare_rows(actual, dataset.rows(table))
        finally:
            actual.close()
        result["checksums"][table] = checksum(fetch_rows(connection, table, dataset.batch_size))
        if result["checksums"][table] != manifest["checksums"][table]:
            raise DiagnosticError("Stored dataset checksum differs from regenerated data.")
    result["status"] = "PASS"
    return result

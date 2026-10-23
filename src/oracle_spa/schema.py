"""Explicit schema ownership, dictionary verification and transactional row reset."""

from hashlib import sha256
import re

from oracle_spa.data_generator import ROOT, TABLES
from oracle_spa.db import DiagnosticError

COLUMNS = {
    "CUSTOMERS": [("CUSTOMER_ID", "NUMBER(12)"), ("FULL_NAME", "VARCHAR2(100 CHAR)"),
                  ("EMAIL", "VARCHAR2(160 CHAR)"), ("REGION", "VARCHAR2(12 CHAR)"), ("CREATED_AT", "DATE")],
    "PRODUCTS": [("PRODUCT_ID", "NUMBER(12)"), ("CATEGORY", "VARCHAR2(20 CHAR)"),
                 ("PRODUCT_NAME", "VARCHAR2(100 CHAR)"), ("UNIT_PRICE", "NUMBER(12,2)"), ("IS_ACTIVE", "NUMBER(1)")],
    "ORDERS": [("ORDER_ID", "NUMBER(12)"), ("CUSTOMER_ID", "NUMBER(12)"), ("ORDER_DATE", "DATE"),
               ("STATUS", "VARCHAR2(12 CHAR)"), ("TOTAL_AMOUNT", "NUMBER(16,2)")],
    "ORDER_ITEMS": [("ORDER_ITEM_ID", "NUMBER(12)"), ("ORDER_ID", "NUMBER(12)"),
                    ("PRODUCT_ID", "NUMBER(12)"), ("QUANTITY", "NUMBER(5)"), ("UNIT_PRICE", "NUMBER(12,2)")],
    "OSPA_DATASET": [("DATASET_ID", "NUMBER(1)"), ("PROFILE", "VARCHAR2(10 CHAR)"),
                     ("SEED", "NUMBER(19)"), ("MANIFEST", "VARCHAR2(4000 CHAR)"), ("LOADED_AT", "DATE")],
}
ALL_TABLES = tuple(COLUMNS)
RESET_CONFIRMATION = "ORACLE_SPA/FREEPDB1/DELETE_DATA"
CHECKS = {
    "CUSTOMERS": {"CUSTOMERS_ID_CK": "CUSTOMER_ID > 0", "CUSTOMERS_REGION_CK": "REGION IN ('NORTH','SOUTH','EAST','WEST','CENTRAL')"},
    "PRODUCTS": {"PRODUCTS_ID_CK": "PRODUCT_ID > 0", "PRODUCTS_PRICE_CK": "UNIT_PRICE > 0", "PRODUCTS_ACTIVE_CK": "IS_ACTIVE IN (0,1)"},
    "ORDERS": {"ORDERS_ID_CK": "ORDER_ID > 0", "ORDERS_TOTAL_CK": "TOTAL_AMOUNT > 0", "ORDERS_STATUS_CK": "STATUS IN ('NEW','PAID','SHIPPED','CANCELLED')"},
    "ORDER_ITEMS": {"ITEMS_ID_CK": "ORDER_ITEM_ID > 0", "ITEMS_QTY_CK": "QUANTITY > 0", "ITEMS_PRICE_CK": "UNIT_PRICE > 0"},
    "OSPA_DATASET": {"DATASET_SINGLE_CK": "DATASET_ID = 1", "DATASET_SEED_CK": "SEED >= 0", "DATASET_PROFILE_CK": "PROFILE IN ('tiny','small','medium','large')"},
}
FOREIGN_KEYS = {"ORDERS": [("ORDERS_CUSTOMER_FK", "CUSTOMER_ID", "CUSTOMERS")],
                "ORDER_ITEMS": [("ITEMS_ORDER_FK", "ORDER_ID", "ORDERS"), ("ITEMS_PRODUCT_FK", "PRODUCT_ID", "PRODUCTS")]}


def create_statements():
    statements = []
    for table, columns in COLUMNS.items():
        parts = [f"{name} {kind} NOT NULL" for name, kind in columns]
        parts.append(f"CONSTRAINT {table}_PK PRIMARY KEY ({columns[0][0]})")
        parts += [f"CONSTRAINT {name} CHECK ({condition})" for name, condition in CHECKS[table].items()]
        parts += [f"CONSTRAINT {name} FOREIGN KEY ({column}) REFERENCES {parent} ({COLUMNS[parent][0][0]})"
                  for name, column, parent in FOREIGN_KEYS.get(table, [])]
        statements.append(f"CREATE TABLE {table} (\n    " + ",\n    ".join(parts) + "\n)")
    return statements


def marker():
    return "OSPA_PHASE2_V1:" + sha256(";\n".join(create_statements()).encode()).hexdigest()


def expected_columns():
    result = []
    for table, columns in COLUMNS.items():
        for position, (name, kind) in enumerate(columns, 1):
            numbers = [int(n) for n in re.findall(r"\d+", kind.partition("(")[2])]
            if kind.startswith("NUMBER"):
                result.append((table, name, position, "NUMBER", numbers[0], numbers[1] if len(numbers) > 1 else 0, None, None, "N"))
            elif kind.startswith("VARCHAR2"):
                result.append((table, name, position, "VARCHAR2", None, None, numbers[0], "C", "N"))
            else:
                result.append((table, name, position, "DATE", None, None, None, None, "N"))
    return sorted(result)


def normalize_check(value):
    return re.sub(r'[\s"()]', '', value or '')


def assert_identity(connection):
    with connection.cursor() as cursor:
        cursor.execute("SELECT USER, SYS_CONTEXT('USERENV','CON_NAME'), SYS_CONTEXT('USERENV','CURRENT_SCHEMA') FROM dual")
        if cursor.fetchone() != ("ORACLE_SPA", "FREEPDB1", "ORACLE_SPA"):
            raise DiagnosticError("Refusing operation: expected ORACLE_SPA current schema in FREEPDB1.")


def inspect_schema(connection, allowed_indexes=(), *, backup_permit=None):
    from oracle_spa.indexes import definitions, inspect_indexes
    experimental = definitions(allowed_indexes)
    backup = None
    backup_structure = None
    if backup_permit is not None:
        from oracle_spa.statistics_backup import BACKUP, verify_structure
        backup_structure = verify_structure(connection, backup_permit)['structure']
        backup = BACKUP
    assert_identity(connection)
    with connection.cursor() as cursor:
        cursor.execute("SELECT object_name, object_type, status FROM user_objects")
        objects = set(cursor.fetchall())
        if not objects:
            return "empty"
        expected = {(table, "TABLE", "VALID") for table in ALL_TABLES} | {(table + "_PK", "INDEX", "VALID") for table in ALL_TABLES}
        expected |= {(name, "INDEX", "VALID") for name in experimental}
        if backup:
            expected |= {tuple(row[:3]) for row in backup_structure['new_objects']['rows']}
        if objects != expected:
            raise DiagnosticError("Partial or unrecognized schema objects; no changes made. Review manually.")
        cursor.execute("SELECT table_name, comments FROM user_tab_comments")
        if {t: m for t, m in cursor.fetchall() if t != backup} != {table: marker() for table in ALL_TABLES}:
            raise DiagnosticError("Schema ownership markers differ; operation refused.")
        cursor.execute("SELECT table_name, column_name, column_id, data_type, data_precision, data_scale, "
                       "CASE WHEN data_type='VARCHAR2' THEN char_length END, char_used, nullable "
                       "FROM user_tab_columns ORDER BY table_name, column_id")
        if sorted(row for row in cursor.fetchall() if row[0] != backup) != expected_columns():
            raise DiagnosticError("Schema columns differ from the versioned contract.")
        cursor.execute("SELECT table_name, constraint_name, constraint_type, status, validated, "
                       "r_owner, r_constraint_name, delete_rule, search_condition_vc, generated, "
                       "deferrable, deferred FROM user_constraints")
        constraints = [row for row in cursor.fetchall() if row[0] != backup]
        cursor.execute("SELECT constraint_name, column_name FROM user_cons_columns ORDER BY constraint_name, position")
        columns = {}
        for name, column in cursor.fetchall():
            columns.setdefault(name, []).append(column)
        found = set()
        nulls = set()
        for table, name, kind, status, validated, owner, parent, rule, condition, generated, deferrable, deferred in constraints:
            if (status, validated, deferrable, deferred) != ("ENABLED", "VALIDATED", "NOT DEFERRABLE", "IMMEDIATE"):
                raise DiagnosticError("Disabled, deferred or unvalidated constraint; operation refused.")
            if kind == "C" and generated == "GENERATED NAME":
                values = columns.get(name, [])
                if len(values) != 1 or normalize_check(condition) != values[0] + "ISNOTNULL":
                    raise DiagnosticError("Unrecognized generated constraint.")
                nulls.add((table, values[0]))
                continue
            found.add((table, name))
            if kind == "P" and name == table + "_PK" and columns.get(name) == [COLUMNS[table][0][0]]:
                continue
            if kind == "C" and name in CHECKS[table] and normalize_check(condition) == normalize_check(CHECKS[table][name]):
                continue
            matches = [(n, col, ref) for n, col, ref in FOREIGN_KEYS.get(table, []) if n == name]
            if kind == "R" and matches:
                _, column, ref = matches[0]
                if (owner, parent, rule, columns.get(name)) == ("ORACLE_SPA", ref + "_PK", "NO ACTION", [column]):
                    continue
            raise DiagnosticError("Unrecognized constraint definition; operation refused.")
        expected_constraints = {(t, t + "_PK") for t in ALL_TABLES}
        expected_constraints |= {(t, n) for t in ALL_TABLES for n in CHECKS[t]}
        expected_constraints |= {(t, n) for t in ALL_TABLES for n, _, _ in FOREIGN_KEYS.get(t, [])}
        if found != expected_constraints or nulls != {(t, col) for t in ALL_TABLES for col, _ in COLUMNS[t]}:
            raise DiagnosticError("Missing schema constraints; operation refused.")
        cursor.execute("SELECT index_name, table_name, uniqueness, index_type FROM user_indexes")
        expected_indexes = {(t + "_PK", t, "UNIQUE", "NORMAL") for t in ALL_TABLES}
        expected_indexes |= {(n, spec.table, "NONUNIQUE", "NORMAL") for n, spec in experimental.items()}
        if backup:
            expected_indexes |= {(r[0],r[2],r[4],r[5]) for r in backup_structure['backup_index']['rows']}
        if set(cursor.fetchall()) != expected_indexes:
            raise DiagnosticError("Unexpected indexes; operation refused.")
    inspect_indexes(connection, allowed_indexes)
    return "ready"


def init_schema(connection):
    if inspect_schema(connection) == "ready":
        return {"schema": "reused", "tables": list(ALL_TABLES)}
    expected = ";\n\n".join(create_statements()) + ";\n"
    if (ROOT / "sql/01_schema.sql").read_text() != expected:
        raise DiagnosticError("Versioned SQL differs from schema contract; no DDL executed.")
    with connection.cursor() as cursor:
        cursor.execute("SELECT privilege FROM session_privs")
        if ("CREATE TABLE",) not in cursor.fetchall():
            raise DiagnosticError("CREATE TABLE is required; request an administrator-approved minimal grant in FREEPDB1.")
        for statement, table in zip(create_statements(), ALL_TABLES):
            cursor.execute(statement)
            cursor.execute(f"COMMENT ON TABLE {table} IS '{marker()}'")
    if inspect_schema(connection) != "ready":
        raise DiagnosticError("Schema verification failed after DDL; inspect partial creation manually.")
    return {"schema": "created", "tables": list(ALL_TABLES)}


def lock_tables(connection):
    if inspect_schema(connection) != "ready":
        raise DiagnosticError("Initialize the empty laboratory schema first.")
    with connection.cursor() as cursor:
        for table in ALL_TABLES:
            cursor.execute(f"LOCK TABLE {table} IN EXCLUSIVE MODE NOWAIT")
    # Reinspect after locking to close the gap between inspection and modification.
    if inspect_schema(connection) != "ready":
        raise DiagnosticError("Schema changed during locking; operation refused.")


def reset_data(connection, confirmation=None):
    if confirmation != RESET_CONFIRMATION:
        raise DiagnosticError("Reset requires --confirm " + RESET_CONFIRMATION + "; affected tables: " + ", ".join(ALL_TABLES))
    lock_tables(connection)
    try:
        with connection.cursor() as cursor:
            for table in ("ORDER_ITEMS", "ORDERS", "PRODUCTS", "CUSTOMERS", "OSPA_DATASET"):
                cursor.execute(f"DELETE FROM {table}")
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    return {"reset": "committed", "tables": list(ALL_TABLES), "ddl_used": False}

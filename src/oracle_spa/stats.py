"""Explicit full-scan statistics on verified own tables, without histograms."""

from datetime import datetime, timezone
from oracle_spa.data_generator import ROOT, TABLES
from oracle_spa.db import DiagnosticError
from oracle_spa.schema import inspect_schema
from oracle_spa.validation import validate_data


def gather_stats(connection):
    if inspect_schema(connection) != "ready":
        raise DiagnosticError("Initialize and load the laboratory first.")
    validate_data(connection)
    result = {"collected_at_utc": datetime.now(timezone.utc).isoformat(),
              "method": "DBMS_STATS.GATHER_TABLE_STATS; estimate_percent=NULL; degree=1; cascade=TRUE; FOR ALL COLUMNS SIZE 1", "tables": {}}
    with connection.cursor() as cursor:
        for table in TABLES:
            cursor.execute((ROOT / "sql/03_stats.sql").read_text(), table_name=table)
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            actual = cursor.fetchone()[0]
            cursor.execute("SELECT num_rows, last_analyzed, stale_stats FROM user_tab_statistics WHERE table_name=:name AND object_type='TABLE'", name=table)
            row = cursor.fetchone()
            if row is None or row[0] != actual or row[1] is None or row[2] != "NO":
                raise DiagnosticError("Statistics are missing, stale or differ from the observed count; inspect manually.")
            result["tables"][table] = {"observed_rows": actual, "statistics_rows": row[0],
                                       "last_analyzed_server_time": row[1].isoformat(), "stale_stats": row[2]}
    return result

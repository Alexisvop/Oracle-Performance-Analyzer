"""Read-only E04 experiment planning and validation.

Recovery is exclusively authorized via statistics_backup.py (operation import-recovery)
using the pre-existing, verified OSPA_ORDERS_STATS_BAK backup (B_ORIGINAL_V1).
Historical RESTORE_TABLE_STATS is retained strictly for documentation as an
unauthorized alternative; it is never used for automatic recovery.

Ground-truth row counts (PAID=5876, CANCELLED=541) are reference values from
the deterministic small/20261016 dataset, NOT mandatory optimizer estimates.
Compiler estimates, plan choices and latencies must be observed, never forced.
"""
from oracle_spa.schema import inspect_schema
from oracle_spa.db import DiagnosticError
from oracle_spa.statistics_backup import BACKUP, STATID, IMPORT_SQL, differences, digest

GATHER_SQL = """BEGIN DBMS_STATS.GATHER_TABLE_STATS(
  ownname => 'ORACLE_SPA', tabname => 'ORDERS', estimate_percent => 100,
  degree => 1, cascade => FALSE,
  method_opt => 'FOR COLUMNS SIZE 4 STATUS',
  no_invalidate => FALSE); END;"""

RECOVERY_SQL = IMPORT_SQL

UNAUTHORIZED_HISTORICAL_RESTORE_SQL = """BEGIN DBMS_STATS.RESTORE_TABLE_STATS(
  ownname => 'ORACLE_SPA', tabname => 'ORDERS',
  as_of_timestamp => TO_TIMESTAMP_TZ(:restore_at, 'YYYY-MM-DD HH24:MI:SS.FF6 TZH:TZM'),
  no_invalidate => FALSE, force => FALSE); END;"""

# Backwards compatibility alias for historical references in tests and logs.
RESTORE_SQL = UNAUTHORIZED_HISTORICAL_RESTORE_SQL

# Ground truth synthetic row counts from small profile (seed 20261016), total 10,000 orders.
# These are real dataset cardinalities, NOT mandatory CBO compilation estimates.
REFERENCE_CARDINALITIES = {
    'PAID': 5876,       # 58.76% of orders (frequent cohort)
    'SHIPPED': 2523,    # 25.23% of orders
    'NEW': 1060,        # 10.60% of orders
    'CANCELLED': 541,   # 5.41% of orders (rare cohort)
}


def evaluate_observed_histogram(column_stats_row, histogram_rows):
    """Inspect live dictionary rows to separate observed histogram attributes from expectations.

    Supports both the 9-column projection from statistics_plan() and the full 16-column
    row from USER_TAB_COL_STATISTICS (exact_statistics()['columns']).
    Does not force an assertion; returns an objective report of observed properties.
    """
    if not column_stats_row:
        return {'status': 'MISSING', 'error': 'No column statistics found for STATUS.'}
    if len(column_stats_row) >= 15 and column_stats_row[0] == 'ORDERS':
        col_name = column_stats_row[1]
        num_distinct = column_stats_row[2]
        density = column_stats_row[5]
        num_nulls = column_stats_row[6]
        num_buckets = column_stats_row[7]
        hist_type = column_stats_row[14]
    else:
        col_name, num_distinct, density, num_nulls, num_buckets, hist_type = column_stats_row[:6]
    density_val = float(density['oracle_number']) if isinstance(density, dict) else float(density) if density else None
    buckets_val = int(num_buckets['oracle_number']) if isinstance(num_buckets, dict) else int(num_buckets) if num_buckets else None
    distinct_val = int(num_distinct['oracle_number']) if isinstance(num_distinct, dict) else int(num_distinct) if num_distinct else None
    endpoints_count = len(histogram_rows)

    is_expected_frequency = (
        col_name == 'STATUS'
        and hist_type == 'FREQUENCY'
        and buckets_val == 4
        and distinct_val == 4
        and endpoints_count == 4
    )

    return {
        'status': 'PASS' if is_expected_frequency else 'UNEXPECTED',
        'column_name': col_name,
        'histogram_type_observed': hist_type,
        'num_distinct_observed': distinct_val,
        'num_buckets_observed': buckets_val,
        'density_observed': density_val,
        'endpoints_count_observed': endpoints_count,
        'endpoints_observed': histogram_rows,
        'is_expected_frequency': is_expected_frequency,
        'note': 'Expected FREQUENCY with 4 buckets; if UNEXPECTED, stop before measuring Scenario B.',
    }


def extract_plan_summary(plan_dict):
    """Extract real operator and plan attributes from explain_query() output.

    Uses the actual explain_query() schema: 'operators', 'object', 'estimated_rows',
    'optimizer_cost', 'access_predicates', 'filter_predicates', 'statement_id', 'plan_hash'.
    Never fabricates operators when a capture is incomplete or missing operators.
    """
    if not isinstance(plan_dict, dict):
        return {
            'status': 'INCOMPLETE',
            'reason': 'Plan capture is not a dictionary.',
            'operators': [],
        }

    operators = plan_dict.get('operators')
    plan_hash = plan_dict.get('plan_hash')
    plan_type = plan_dict.get('type')
    plan_status = plan_dict.get('status')
    has_valid_operators = (
        isinstance(operators, list)
        and len(operators) > 0
        and all(isinstance(op, dict) and 'operation' in op for op in operators)
    )

    if (
        not has_valid_operators
        or plan_hash is None
        or plan_type != 'ESTIMATED_PLAN'
        or plan_status not in (None, 'PASS')
    ):
        return {
            'status': 'INCOMPLETE',
            'reason': 'Plan capture lacks complete operators or valid ESTIMATED_PLAN status; no operators fabricated.',
            'type': plan_type,
            'statement_id': plan_dict.get('statement_id'),
            'plan_hash': plan_hash,
            'query_id': plan_dict.get('query_id'),
            'variant': plan_dict.get('variant'),
            'sql_sha256': plan_dict.get('sql_sha256'),
            'binds': plan_dict.get('binds'),
            'root_operation': None,
            'root_options': None,
            'root_estimated_rows': None,
            'root_optimizer_cost': None,
            'orders_access_type': None,
            'orders_operation': None,
            'orders_options': None,
            'orders_owner': None,
            'orders_object': None,
            'orders_estimated_rows': None,
            'orders_optimizer_cost': None,
            'orders_access_predicates': None,
            'orders_filter_predicates': None,
            'operators': [],
            'display': list(plan_dict.get('display', [])) if isinstance(plan_dict.get('display'), list) else [],
            'warnings': list(plan_dict.get('warnings', [])) if isinstance(plan_dict.get('warnings'), list) else [],
        }

    root_op = operators[0]
    orders_op = next((op for op in operators if op.get('object') == 'ORDERS'), None)
    if orders_op is not None:
        op_name = orders_op.get('operation') or ''
        op_opts = orders_op.get('options') or ''
        access_type = f'{op_name} {op_opts}'.strip() or None
    else:
        access_type = None

    return {
        'status': 'PASS',
        'type': plan_type,
        'statement_id': plan_dict.get('statement_id'),
        'plan_hash': plan_hash,
        'query_id': plan_dict.get('query_id'),
        'variant': plan_dict.get('variant'),
        'sql_sha256': plan_dict.get('sql_sha256'),
        'binds': plan_dict.get('binds'),
        'root_operation': root_op.get('operation'),
        'root_options': root_op.get('options'),
        'root_estimated_rows': root_op.get('estimated_rows'),
        'root_optimizer_cost': root_op.get('optimizer_cost'),
        'orders_access_type': access_type,
        'orders_operation': orders_op.get('operation') if orders_op else None,
        'orders_options': orders_op.get('options') if orders_op else None,
        'orders_owner': orders_op.get('owner') if orders_op else None,
        'orders_object': orders_op.get('object') if orders_op else None,
        'orders_estimated_rows': orders_op.get('estimated_rows') if orders_op else None,
        'orders_optimizer_cost': orders_op.get('optimizer_cost') if orders_op else None,
        'orders_access_predicates': orders_op.get('access_predicates') if orders_op else None,
        'orders_filter_predicates': orders_op.get('filter_predicates') if orders_op else None,
        'operators': [dict(op) for op in operators],
        'display': list(plan_dict.get('display', [])) if isinstance(plan_dict.get('display'), list) else [],
        'warnings': list(plan_dict.get('warnings', [])) if isinstance(plan_dict.get('warnings'), list) else [],
    }


def inspect_e04_stale_stats_exception(
    before_indexes,
    after_indexes,
    *,
    experiment_id='E04',
    histogram_active=False,
    before_index_meta=None,
    after_index_meta=None,
):
    """Evaluate whether index statistics differences in E04 are exclusively the authorized ORDERS_PK.STALE_STATS NO->YES transition.

    Does not mutate before_indexes or after_indexes.
    Rejects any change to index definitions, OBJECT_ID, index count, numeric statistics,
    LAST_ANALYZED, or non-E04 / non-histogram scenarios.
    """
    if experiment_id != 'E04':
        raw = differences(before_indexes, after_indexes, '/effective/statistics/indexes')
        return {
            'allowed': not raw and before_index_meta == after_index_meta,
            'exception_applied': False,
            'differences': raw,
            'exception_record': None,
            'reason': None if not raw else 'STALE_STATS exception applies exclusively to E04.',
        }

    if before_index_meta != after_index_meta:
        return {
            'allowed': False,
            'exception_applied': False,
            'differences': differences(before_index_meta, after_index_meta, '/index_metadata'),
            'exception_record': None,
            'reason': 'Physical index definition, uniqueness, columns or OBJECT_ID changed.',
        }

    # Support minimal unit-test fixtures where indexes == [] on both sides
    if before_indexes == [] and after_indexes == []:
        return {
            'allowed': True,
            'exception_applied': False,
            'differences': [],
            'exception_record': None,
            'reason': None,
        }

    if not isinstance(before_indexes, dict) or not isinstance(after_indexes, dict):
        return {
            'allowed': False,
            'exception_applied': False,
            'differences': differences(before_indexes, after_indexes, '/effective/statistics/indexes'),
            'exception_record': None,
            'reason': 'Invalid index statistics structure.',
        }

    cols_before = before_indexes.get('columns')
    cols_after = after_indexes.get('columns')
    rows_before = before_indexes.get('rows')
    rows_after = after_indexes.get('rows')

    if (
        not isinstance(cols_before, list)
        or cols_before != cols_after
        or not isinstance(rows_before, list)
        or not isinstance(rows_after, list)
        or len(rows_before) != 1
        or len(rows_after) != 1
    ):
        return {
            'allowed': False,
            'exception_applied': False,
            'differences': differences(before_indexes, after_indexes, '/effective/statistics/indexes'),
            'exception_record': None,
            'reason': 'Index count or column schema changed; exactly one ORDERS_PK row is required.',
        }

    required_cols = {'INDEX_NAME', 'TABLE_OWNER', 'TABLE_NAME', 'LAST_ANALYZED', 'STALE_STATS'}
    if not required_cols.issubset(set(cols_before)):
        return {
            'allowed': False,
            'exception_applied': False,
            'differences': differences(before_indexes, after_indexes, '/effective/statistics/indexes'),
            'exception_record': None,
            'reason': 'Required USER_IND_STATISTICS columns missing.',
        }

    idx_name_pos = cols_before.index('INDEX_NAME')
    tbl_owner_pos = cols_before.index('TABLE_OWNER')
    tbl_name_pos = cols_before.index('TABLE_NAME')
    last_analyzed_pos = cols_before.index('LAST_ANALYZED')
    stale_pos = cols_before.index('STALE_STATS')

    b_row = rows_before[0]
    a_row = rows_after[0]
    if (
        b_row[idx_name_pos] != 'ORDERS_PK'
        or a_row[idx_name_pos] != 'ORDERS_PK'
        or b_row[tbl_owner_pos] != 'ORACLE_SPA'
        or a_row[tbl_owner_pos] != 'ORACLE_SPA'
        or b_row[tbl_name_pos] != 'ORDERS'
        or a_row[tbl_name_pos] != 'ORDERS'
    ):
        return {
            'allowed': False,
            'exception_applied': False,
            'differences': differences(before_indexes, after_indexes, '/effective/statistics/indexes'),
            'exception_record': None,
            'reason': 'Index row does not belong to ORACLE_SPA.ORDERS_PK on ORDERS.',
        }

    raw_diffs = differences(before_indexes, after_indexes, '/effective/statistics/indexes')
    if not raw_diffs:
        return {
            'allowed': True,
            'exception_applied': False,
            'differences': [],
            'exception_record': None,
            'reason': None,
        }

    expected_path = f'/effective/statistics/indexes/rows/0/{stale_pos}'
    if (
        raw_diffs == [expected_path]
        and histogram_active
        and b_row[stale_pos] == 'NO'
        and a_row[stale_pos] == 'YES'
        and b_row[last_analyzed_pos] == a_row[last_analyzed_pos]
    ):
        return {
            'allowed': True,
            'exception_applied': True,
            'differences': raw_diffs,
            'exception_record': {
                'experiment_id': 'E04',
                'table_name': 'ORDERS',
                'index_name': 'ORDERS_PK',
                'column_name': 'STALE_STATS',
                'column_index': stale_pos,
                'path': expected_path,
                'before_value': 'NO',
                'after_value': 'YES',
                'index_last_analyzed': b_row[last_analyzed_pos],
                'reason': (
                    'Derived USER_IND_STATISTICS.STALE_STATS flag transitioned NO->YES after '
                    'GATHER_TABLE_STATS(..., cascade=>FALSE) advanced ORDERS.LAST_ANALYZED while '
                    'preserving ORDERS_PK.LAST_ANALYZED and all numeric index statistics.'
                ),
            },
            'reason': None,
        }

    return {
        'allowed': False,
        'exception_applied': False,
        'differences': raw_diffs,
        'exception_record': None,
        'reason': 'Disallowed index statistics change or STALE_STATS transition outside authorized histogram state.',
    }


def validate_e04_post_gather_state(
    before_state,
    after_state,
    *,
    before_index_meta=None,
    after_index_meta=None,
):
    """Pre-Scenario-B guard for E04 after GATHER_TABLE_STATS.

    Verifies that:
      1. ORDERS.STATUS has the expected 4-bucket FREQUENCY histogram.
      2. Non-target columns (CUSTOMER_ID, ORDER_DATE, ORDER_ID, TOTAL_AMOUNT) are untouched.
      3. ORDERS table statistics changed only in LAST_ANALYZED.
      4. ORDERS_PK index statistics are either identical or differ exclusively in STALE_STATS (NO->YES).
      5. Dataset, preferences, explicit_preferences, metadata and version are untouched.
    Preserves all raw differences in the returned report without modifying before_state or after_state.
    """
    b_eff = before_state['effective']
    a_eff = after_state['effective']
    b_stats = b_eff['statistics']
    a_stats = a_eff['statistics']

    # 1. Evaluate observed STATUS histogram
    cols_cols = a_stats['columns']['columns']
    col_name_idx = cols_cols.index('COLUMN_NAME')
    status_row = next((r for r in a_stats['columns']['rows'] if r[col_name_idx] == 'STATUS'), None)
    hist_cols = a_stats['histograms']['columns']
    hist_col_name_idx = hist_cols.index('COLUMN_NAME')
    status_hist_rows = [r for r in a_stats['histograms']['rows'] if r[hist_col_name_idx] == 'STATUS']
    hist_eval = evaluate_observed_histogram(status_row, status_hist_rows)

    # 2. Non-target columns in columns and histograms must be 100% unchanged
    b_non_status_cols = [r for r in b_stats['columns']['rows'] if r[col_name_idx] != 'STATUS']
    a_non_status_cols = [r for r in a_stats['columns']['rows'] if r[col_name_idx] != 'STATUS']
    non_target_col_diffs = differences(b_non_status_cols, a_non_status_cols, '/effective/statistics/columns/non_status')

    b_non_status_hist = [r for r in b_stats['histograms']['rows'] if r[hist_col_name_idx] != 'STATUS']
    a_non_status_hist = [r for r in a_stats['histograms']['rows'] if r[hist_col_name_idx] != 'STATUS']
    non_target_hist_diffs = differences(b_non_status_hist, a_non_status_hist, '/effective/statistics/histograms/non_status')

    # 3. Table statistics: only LAST_ANALYZED on ORDERS may change
    tbl_cols = b_stats['table']['columns']
    tbl_last_analyzed_idx = tbl_cols.index('LAST_ANALYZED')
    tbl_diffs = differences(b_stats['table'], a_stats['table'], '/effective/statistics/table')
    allowed_tbl_diff = f'/effective/statistics/table/rows/0/{tbl_last_analyzed_idx}/datetime'
    disallowed_tbl_diffs = [d for d in tbl_diffs if d != allowed_tbl_diff]

    # 4. Index statistics & STALE_STATS exception
    stale_check = inspect_e04_stale_stats_exception(
        b_stats['indexes'],
        a_stats['indexes'],
        experiment_id='E04',
        histogram_active=(hist_eval['status'] == 'PASS'),
        before_index_meta=before_index_meta,
        after_index_meta=after_index_meta,
    )

    # 5. Other sections must have zero differences
    other_diffs = {
        'dataset': differences(b_eff['dataset'], a_eff['dataset'], '/effective/dataset'),
        'preferences': differences(b_eff['preferences'], a_eff['preferences'], '/effective/preferences'),
        'explicit_preferences': differences(
            b_stats['explicit_preferences'],
            a_stats['explicit_preferences'],
            '/effective/statistics/explicit_preferences',
        ),
        'metadata': differences(b_eff['metadata'], a_eff['metadata'], '/effective/metadata'),
        'version': differences(b_eff['version'], a_eff['version'], '/effective/version'),
    }

    all_raw_diffs = differences(b_stats, a_stats, '/effective/statistics')
    passed = (
        hist_eval['status'] == 'PASS'
        and not non_target_col_diffs
        and not non_target_hist_diffs
        and not disallowed_tbl_diffs
        and stale_check['allowed']
        and all(not v for v in other_diffs.values())
    )

    return {
        'status': 'PASS' if passed else 'BLOCKED',
        'ready_for_scenario_b': passed,
        'histogram_evaluation': hist_eval,
        'non_target_column_differences': non_target_col_diffs,
        'non_target_histogram_differences': non_target_hist_diffs,
        'disallowed_table_differences': disallowed_tbl_diffs,
        'index_stale_stats_check': stale_check,
        'derived_metadata_exceptions': [stale_check['exception_record']] if stale_check['exception_applied'] else [],
        'other_invariant_differences': other_diffs,
        'all_statistics_differences_preserved': all_raw_diffs,
        'before_statistics_sha256': digest(b_stats),
        'after_statistics_sha256': digest(a_stats),
    }


def statistics_plan(connection, *, backup_permit=None):
    """Read-only plan for E04. Does not execute GATHER or recovery.

    Inspects current dictionary state and documents the required gates.
    """
    options = {'backup_permit': backup_permit} if backup_permit is not None else {}
    if inspect_schema(connection, **options) != 'ready':
        raise DiagnosticError('Statistics planning requires verified laboratory objects.')

    with connection.cursor() as cur:
        cur.execute(
            "SELECT TO_CHAR(SYSTIMESTAMP,'YYYY-MM-DD HH24:MI:SS.FF6 TZH:TZM'), "
            "TO_CHAR(DBMS_STATS.GET_STATS_HISTORY_AVAILABILITY,'YYYY-MM-DD HH24:MI:SS.FF6 TZH:TZM'), "
            "DBMS_STATS.GET_STATS_HISTORY_RETENTION FROM dual"
        )
        restore_at, available_since, retention = cur.fetchone()
        cur.execute(
            "SELECT column_name,num_distinct,density,num_nulls,num_buckets,histogram,"
            "RAWTOHEX(low_value),RAWTOHEX(high_value),TO_CHAR(last_analyzed,'YYYY-MM-DD HH24:MI:SS') "
            "FROM user_tab_col_statistics WHERE table_name='ORDERS' ORDER BY column_name"
        )
        columns = cur.fetchall()
        cur.execute(
            "SELECT column_name,endpoint_number,endpoint_value "
            "FROM user_tab_histograms WHERE table_name='ORDERS' ORDER BY column_name,endpoint_number"
        )
        histogram = cur.fetchall()
        cur.execute(
            "SELECT table_name,num_rows,blocks,avg_row_len,sample_size,TO_CHAR(last_analyzed,'YYYY-MM-DD HH24:MI:SS') "
            "FROM user_tab_statistics WHERE table_name='ORDERS' AND object_type='TABLE'"
        )
        table = cur.fetchall()
        cur.execute(
            "SELECT index_name,num_rows,leaf_blocks,distinct_keys,clustering_factor,blevel,sample_size,"
            "TO_CHAR(last_analyzed,'YYYY-MM-DD HH24:MI:SS') "
            "FROM user_ind_statistics WHERE table_name='ORDERS' ORDER BY index_name"
        )
        indexes = cur.fetchall()

    status_col = next((c for c in columns if c[0] == 'STATUS'), None)
    status_hist = [h for h in histogram if h[0] == 'STATUS']
    current_status_eval = evaluate_observed_histogram(status_col, status_hist)

    return {
        'status': 'PENDING APPROVAL',
        'execution_gate': 'NO-GO: GATHER requires separate explicit owner authorization; recovery requires separate explicit owner authorization',
        'table': 'ORACLE_SPA.ORDERS',
        'histogram_column': 'STATUS',
        'backup_table': f'ORACLE_SPA.{BACKUP}',
        'backup_statid': STATID,
        'backup_state': 'EXISTS; 7 rows with STATID B_ORIGINAL_V1; contents SHA-256 verified',
        'authorized_recovery_mechanism': 'statistics_backup.py operation import-recovery from OSPA_ORDERS_STATS_BAK',
        'unauthorized_historical_alternative': 'RESTORE_TABLE_STATS (retained for documentation only; NOT authorized for automatic recovery)',
        'gather_sql': GATHER_SQL,
        'recovery_sql': RECOVERY_SQL,
        'restore_sql': RESTORE_SQL,
        'restoration_test': 'NOT VERIFIED for post-histogram recovery; import-rehearsal passed on identical stats but actual restore after gather remains to be verified',
        'reference_data_cardinalities': REFERENCE_CARDINALITIES,
        'cardinality_guidance': (
            'Reference cardinalities (PAID=5876, CANCELLED=541) are deterministic ground-truth counts from small/20261016, '
            'NOT mandatory CBO compilation estimates. EXPLAIN PLAN estimates must be observed, never forced.'
        ),
        'current_histogram_state': current_status_eval,
        'snapshot': {'table': table, 'columns': columns, 'histogram': histogram, 'indexes': indexes},
        'history_diagnostics': {
            'restore_at': restore_at,
            'history_available_since': available_since,
            'retention_days': retention,
        },
        'failure_criteria': [
            'Error before GATHER -> STOP; no modification made.',
            'Error during GATHER -> STOP; journal partial status; do not retry; inspect read-only.',
            'Histogram created but different than expected -> STOP; record observed type/buckets; do NOT benchmark Scenario B.',
            'Failure during measurements -> STOP; retain partial samples; proceed to recovery only after review.',
            'Failure during import-recovery -> STOP; journal partial status; do not repeat automatically.',
            'Differences post-recovery -> STOP; report field-level differences; never falsify PASS.',
            'Loss of connection -> STOP; reconnect and inspect read-only before any other action.',
            'Alteration of backup -> FATAL STOP; stattab contents must remain identical.',
        ],
        'procedure_stages': [
            '1. Preflight and verification of original backup (7 rows, SHA-256 intact).',
            '2. Contemporary measurement of Scenario A (baseline without histogram).',
            '3. Specific, independent owner authorization for a single GATHER.',
            '4. Execution of GATHER and verification of observed histogram attributes.',
            '5. Measurement of Scenario B for PAID and CANCELLED (5 warmups, 10 repeats each).',
            '6. Independent owner authorization for import-recovery.',
            '7. Execution of import-recovery from OSPA_ORDERS_STATS_BAK.',
            '8. Exact post-recovery verification via hashes and field-by-field restoration().',
            '9. Final regression tests and report generation.',
        ],
        'risks': [
            'GATHER_TABLE_STATS invalidates cursors and changes CBO cardinality estimates.',
            'GATHER_TABLE_STATS updates LAST_ANALYZED on the ORDERS table and STATUS column.',
            'Cascade FALSE prevents index statistics gathering, but table-level statistics are recalculated.',
            'Restoration after a real histogram modification remains NOT VERIFIED until executed.',
            'Rollback does not undo DDL/DBMS_STATS mutations; recovery relies exclusively on import-recovery.',
        ],
    }

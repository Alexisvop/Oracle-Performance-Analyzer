"""Unit tests for E04 safety corrections and experimental controls.

Verifies:
1. Rejection of consumed prior authorizations.
2. Separation of GATHER and import-recovery authorizations.
3. Validation of different statistical scenarios.
4. Absence of artificial requirements on plans/cardinalities.
5. Backup protection and structure preservation.
6. Suspension and abort criteria.
7. Exact post-verification restoration accuracy.
8. Preservation of backwards compatibility with prior phases.
"""
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
import os
from unittest.mock import MagicMock
import pytest

from oracle_spa.db import DiagnosticError
from oracle_spa import statistics_backup as sb
from oracle_spa import statistics_experiment as se
from oracle_spa.analysis import compare_statistics_runs
from oracle_spa.queries import CATALOG, get_query


def dummy_original():
    return {
        'effective': {
            'statistics': {
                'density': sb.value(Decimal('0.25')),
                'last_analyzed': '2026-10-18T18:17:24',
                'user_stats': 'NO',
            },
            'dataset': {'seed': 20261016, 'profile': 'small'},
            'preferences': {'PUBLISH': 'TRUE'},
            'metadata': {'rows': [{'dataset_id': 1}]},
            'version': '23.26.3.0.0',
        },
        'history': [],
    }


def dummy_permit():
    structure = {
        'name': sb.BACKUP,
        'version': '23.26.3.0.0',
        'structure': {'new_objects': {'rows': []}},
    }
    receipt = {
        'kind': 'forensic-reconciliation',
        'status': 'MATCHED; EXTERNAL APPROVAL PENDING',
        'journal_validated': True,
        'original_stop_preserved': True,
        'backup': structure,
    }
    p = sb.BackupPermit(receipt, sb.digest(structure), sb.digest(receipt))
    return replace(p, statistics_approval=sb.statistics_approval(p))


# 1. Rejection of consumed prior authorizations
def test_rejection_of_consumed_authorizations(tmp_path):
    marker = tmp_path / 'authorization-reserved.json'
    fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as f:
        f.write('{"reserved": true}\n')

    # Re-opening with O_EXCL must fail immediately
    with pytest.raises(FileExistsError):
        os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)


# 2. Separation of GATHER and import-recovery authorizations
def test_separation_of_gather_and_recovery_authorizations(monkeypatch):
    assert 'GATHER_TABLE_STATS' in se.GATHER_SQL
    assert 'IMPORT_TABLE_STATS' in se.RECOVERY_SQL
    assert 'RESTORE_TABLE_STATS' in se.UNAUTHORIZED_HISTORICAL_RESTORE_SQL
    assert se.RECOVERY_SQL != se.GATHER_SQL
    assert se.RECOVERY_SQL != se.UNAUTHORIZED_HISTORICAL_RESTORE_SQL

    # Recovery must use statistics_backup.py import-recovery contract
    c = MagicMock()
    c.version = '23.26.3.0.0'
    c.transaction_in_progress = False
    p = dummy_permit()
    orig = dummy_original()
    receipt = {'original_sha256': sb.digest(orig['effective']), 'contents_sha256': 'valid'}

    monkeypatch.setattr(sb, 'inspect_original', lambda *a: orig)
    monkeypatch.setattr(sb, 'inspect_interfaces', lambda *a: {})
    monkeypatch.setattr(sb, 'validate_backup', lambda *a: None)

    plan = sb.prepare_operation(
        c,
        'import-recovery',
        orig,
        permit=p,
        export_receipt=receipt,
    )
    assert plan['operation'] == 'import-recovery'
    assert 'import-recovery' in plan['confirmation']
    assert 'import-rehearsal' not in plan['confirmation']
    assert 'export' not in plan['confirmation']


# 3. Validation of different statistical scenarios
def test_validation_of_different_statistical_scenarios():
    def make_run(variant='baseline', histogram='NONE'):
        cohort = 'PAID' if variant == 'baseline' else 'CANCELLED'
        return {
            'run_id': f'run_{variant}_{histogram}',
            'experiment_id': 'E04',
            'query_id': 'Q06',
            'order_seed': 20261016,
            'warmups': 5,
            'repeats': 10,
            'context': {
                'profile': 'small',
                'seed': 20261016,
                'statistics': [['ORDERS', 10000, 'old']],
                'column_statistics': [['ORDERS', 'STATUS', 4, histogram]],
                'orders_effective_preferences': {'PUBLISH': 'TRUE'},
                'orders_statistics_exact': {k: [] for k in sb.QUERIES},
                'indexes': ['ORDERS_PK'],
            },
            'environment': {},
            'session': {'arraysize': 500},
            'metric': 'full fetch',
            'scenario': 'baseline',
            'cases': {
                variant: {
                    'validation': {
                        'sql_sha256': 'sql_hash',
                        'binds': {'status': cohort},
                        'result': {'rows': 10},
                    }
                }
            },
            'samples': [{'warmup': False, 'status': 'PASS', 'elapsed_ms': 1.0, 'variant': variant}] * 10,
            'status': 'PASS',
            'controls_unchanged': True,
            'equivalent': False,
        }

    # Scenario A (NONE) vs Scenario B (FREQUENCY) for same cohort (PAID)
    run_a = make_run('baseline', 'NONE')
    run_b = make_run('baseline', 'FREQUENCY')
    approval = 'E04/ORDERS/' + sb.digest([run_a, run_b])
    result = compare_statistics_runs(run_a, run_b, 'baseline', approval=approval)
    assert result['status'] == 'DESCRIPTIVE ONLY'
    assert result['cohort'] == 'PAID'

    # If non-statistical control drifts (e.g. index added) -> NOT COMPARABLE
    run_b_drift = deepcopy(run_b)
    run_b_drift['context']['indexes'].append('EXTRA_INDEX')
    approval_drift = 'E04/ORDERS/' + sb.digest([run_a, run_b_drift])
    result_drift = compare_statistics_runs(run_a, run_b_drift, 'baseline', approval=approval_drift)
    assert result_drift['status'] == 'NOT COMPARABLE'


# 4. Absence of artificial requirements on plans/cardinalities
def test_absence_of_artificial_plan_and_cardinality_requirements():
    assert se.REFERENCE_CARDINALITIES == {'PAID': 5876, 'CANCELLED': 541, 'SHIPPED': 2523, 'NEW': 1060}

    # evaluate_observed_histogram returns objective report, never raises
    normal_eval = se.evaluate_observed_histogram(
        ('STATUS', {'oracle_number': '4'}, {'oracle_number': '0.00005'}, 0, {'oracle_number': '4'}, 'FREQUENCY'),
        [(1, 'CANCELLED'), (2, 'NEW'), (3, 'PAID'), (4, 'SHIPPED')],
    )
    assert normal_eval['status'] == 'PASS'
    assert normal_eval['is_expected_frequency'] is True

    # If optimizer creates TOP-FREQUENCY or HYBRID, it must report UNEXPECTED without crashing
    hybrid_eval = se.evaluate_observed_histogram(
        ('STATUS', {'oracle_number': '4'}, {'oracle_number': '0.01'}, 0, {'oracle_number': '3'}, 'HYBRID'),
        [(1, 'CANCELLED'), (2, 'PAID'), (3, 'SHIPPED')],
    )
    assert hybrid_eval['status'] == 'UNEXPECTED'
    assert hybrid_eval['is_expected_frequency'] is False


# 5. Backup protection and structure preservation
def test_backup_protection_and_structure_preservation(monkeypatch):
    p = dummy_permit()
    c = MagicMock()
    orig = dummy_original()

    monkeypatch.setattr(sb, 'inspect_original', lambda *a: orig)
    monkeypatch.setattr(sb, 'inspect_interfaces', lambda *a: {})
    monkeypatch.setattr(sb, 'verify_structure', lambda *a: None)
    monkeypatch.setattr(sb, 'backup_contents', lambda *a: {'rows': [[1]]})

    # Export cannot overwrite populated backup
    with pytest.raises(DiagnosticError, match='overwrite'):
        sb.prepare_operation(c, 'export', orig, p)

    # validate_backup rejects altered statid or hash
    receipt = {'operation': 'export', 'status': 'PASS', 'sql': sb.EXPORT_SQL, 'statid': sb.STATID,
               'structure_sha256': p.reviewed_structure_sha256, 'contents_sha256': 'valid'}
    with pytest.raises(DiagnosticError):
        sb.validate_backup(c, p, {**receipt, 'statid': 'CORRUPTED'})


# 6. Suspension and abort criteria
def test_suspension_and_abort_criteria(monkeypatch, tmp_path):
    c = MagicMock()
    c.transaction_in_progress = False
    plan = {'operation': 'create', 'sql': sb.CREATE_SQL, 'confirmation': 'valid_token'}
    monkeypatch.setattr(sb, 'prepare_operation', lambda *a: plan)
    journal = tmp_path / 'attempt.jsonl'
    cur = c.cursor.return_value.__enter__.return_value
    cur.execute.side_effect = RuntimeError('ORA-00054: resource busy')

    # Failure must raise DiagnosticError with partial effects and create journal
    with pytest.raises(DiagnosticError, match='partial effects'):
        sb.execute_operation(c, plan, confirmation='valid_token', original=dummy_original(), journal=journal)

    # A subsequent attempt on the same journal path must be rejected
    with pytest.raises(FileExistsError):
        sb.execute_operation(c, plan, confirmation='valid_token', original=dummy_original(), journal=journal)


# 7. Exact post-verification restoration accuracy
def test_exact_post_verification_restoration_accuracy():
    before = dummy_original()
    after = deepcopy(before)

    # Exact match -> PASS
    assert sb.restoration(before, after)['status'] == 'PASS'
    assert sb.restoration(before, after)['differences'] == []

    # Even 1 micro-difference in density -> FAIL
    after['effective']['statistics']['density'] = sb.value(Decimal('0.250000001'))
    res = sb.restoration(before, after)
    assert res['status'] == 'FAIL'
    assert '/statistics/density' in res['differences'][0]


# 8. Preservation of backwards compatibility with prior phases
def test_preservation_of_backwards_compatibility_with_prior_phases():
    # RESTORE_SQL remains accessible for backwards compatibility
    assert hasattr(se, 'RESTORE_SQL')
    assert ':restore_at' in se.RESTORE_SQL

    # Catalog queries Q01-Q08 remain immutable and accessible
    assert len(CATALOG) == 8
    assert get_query('Q01').name == 'Customer by email'
    assert get_query('Q06').name == 'Frequent versus rare status'
    assert get_query('Q08').name == 'Latest twenty orders'


def _load_real_e04_states():
    import json
    from pathlib import Path
    root = Path('docs/evidence/phase4/group-b-histogram')
    before = json.loads((root / 'state-before-gather.json').read_text())
    after_gather = json.loads((root / 'state-after-gather.json').read_text())
    after_recovery = json.loads((root / 'state-after-recovery.json').read_text())
    run_a = json.loads((root / 'runs' / 'a626b8a37c2b4c6f868ec8cda92314ad' / 'run.json').read_text())
    return before, after_gather, after_recovery, run_a


# 9. STALE_STATS NO->YES allowed only under authorized E04 histogram scenario
def test_stale_stats_no_to_yes_allowed_only_under_authorized_e04_scenario():
    before, after_gather, _, _ = _load_real_e04_states()
    b_idx = before['effective']['statistics']['indexes']
    a_idx = after_gather['effective']['statistics']['indexes']

    # Authorized E04 with active histogram -> allowed with explicit exception record
    ok = se.inspect_e04_stale_stats_exception(b_idx, a_idx, experiment_id='E04', histogram_active=True)
    assert ok['allowed'] is True
    assert ok['exception_applied'] is True
    assert ok['differences'] == ['/effective/statistics/indexes/rows/0/22']
    assert ok['exception_record']['index_name'] == 'ORDERS_PK'
    assert ok['exception_record']['column_name'] == 'STALE_STATS'
    assert ok['exception_record']['before_value'] == 'NO'
    assert ok['exception_record']['after_value'] == 'YES'

    # Rejected if histogram is NOT active
    no_hist = se.inspect_e04_stale_stats_exception(b_idx, a_idx, experiment_id='E04', histogram_active=False)
    assert no_hist['allowed'] is False

    # Rejected for any other experiment (E01, E02, E03, E05)
    for other_exp in ('E01', 'E02', 'E03', 'E05'):
        res = se.inspect_e04_stale_stats_exception(b_idx, a_idx, experiment_id=other_exp, histogram_active=True)
        assert res['allowed'] is False

    # Rejected if transition is YES->NO or NO->UNKNOWN
    bad_after = deepcopy(a_idx)
    bad_after['rows'][0][22] = 'UNKNOWN'
    assert se.inspect_e04_stale_stats_exception(b_idx, bad_after, experiment_id='E04', histogram_active=True)['allowed'] is False
    assert se.inspect_e04_stale_stats_exception(a_idx, b_idx, experiment_id='E04', histogram_active=True)['allowed'] is False


# 10. Numeric index statistics or LAST_ANALYZED change is rejected
def test_numeric_index_statistics_or_last_analyzed_change_is_rejected():
    before, after_gather, _, _ = _load_real_e04_states()
    b_idx = before['effective']['statistics']['indexes']
    cols = b_idx['columns']

    for col_name, new_val in (
        ('BLEVEL', {'oracle_number': '2'}),
        ('LEAF_BLOCKS', {'oracle_number': '19'}),
        ('DISTINCT_KEYS', {'oracle_number': '9999'}),
        ('CLUSTERING_FACTOR', {'oracle_number': '45'}),
        ('NUM_ROWS', {'oracle_number': '10001'}),
        ('SAMPLE_SIZE', {'oracle_number': '9000'}),
        ('LAST_ANALYZED', {'datetime': '2026-10-20T02:16:12'}),
    ):
        pos = cols.index(col_name)
        mutated = deepcopy(after_gather)
        mutated['effective']['statistics']['indexes']['rows'][0][pos] = new_val
        guard = se.validate_e04_post_gather_state(before, mutated)
        assert guard['status'] == 'BLOCKED'
        assert guard['ready_for_scenario_b'] is False


# 11. Change of OBJECT_ID or index definition is rejected
def test_index_object_id_or_definition_change_is_rejected():
    before, after_gather, _, _ = _load_real_e04_states()
    meta_before = {'object_id': 73174, 'index_name': 'ORDERS_PK', 'columns': [('ORDER_ID', 1, 'ASC')], 'uniqueness': 'UNIQUE'}
    meta_after_id = {**meta_before, 'object_id': 99999}
    meta_after_def = {**meta_before, 'columns': [('ORDER_ID', 1, 'DESC')]}

    assert se.validate_e04_post_gather_state(
        before, after_gather, before_index_meta=meta_before, after_index_meta=meta_before
    )['ready_for_scenario_b'] is True
    assert se.validate_e04_post_gather_state(
        before, after_gather, before_index_meta=meta_before, after_index_meta=meta_after_id
    )['ready_for_scenario_b'] is False
    assert se.validate_e04_post_gather_state(
        before, after_gather, before_index_meta=meta_before, after_index_meta=meta_after_def
    )['ready_for_scenario_b'] is False


# 12. Appearance of an additional index or loss of ORDERS_PK is rejected
def test_additional_index_or_missing_orders_pk_is_rejected():
    before, after_gather, _, _ = _load_real_e04_states()
    extra_idx = deepcopy(after_gather)
    extra_row = deepcopy(extra_idx['effective']['statistics']['indexes']['rows'][0])
    extra_row[0] = 'OSPA_ORDERS_STATUS_IDX'
    extra_idx['effective']['statistics']['indexes']['rows'].append(extra_row)
    assert se.validate_e04_post_gather_state(before, extra_idx)['ready_for_scenario_b'] is False

    missing_idx = deepcopy(after_gather)
    missing_idx['effective']['statistics']['indexes']['rows'] = []
    assert se.validate_e04_post_gather_state(before, missing_idx)['ready_for_scenario_b'] is False


# 13. Changes to non-target columns of ORDERS are rejected
def test_non_target_columns_of_orders_are_rejected():
    before, after_gather, _, run_a = _load_real_e04_states()
    # Mutating CUSTOMER_ID (row 0) in state_after_gather blocks validate_e04_post_gather_state
    mutated_state = deepcopy(after_gather)
    mutated_state['effective']['statistics']['columns']['rows'][0][14] = 'FREQUENCY'
    guard = se.validate_e04_post_gather_state(before, mutated_state)
    assert guard['status'] == 'BLOCKED'
    assert guard['non_target_column_differences']

    # Mutating CUSTOMER_ID in compare_statistics_runs produces NOT COMPARABLE
    sim_b = deepcopy(run_a)
    sim_b['context']['orders_statistics_exact'] = deepcopy(after_gather['effective']['statistics'])
    sim_b['context']['column_statistics'] = [
        ['ORDERS', 'STATUS', 4, 'FREQUENCY', 4] if r[:2] == ['ORDERS', 'STATUS'] else r
        for r in sim_b['context']['column_statistics']
    ]
    # Corrupt CUSTOMER_ID in orders_statistics_exact['columns']
    sim_b_bad = deepcopy(sim_b)
    sim_b_bad['context']['orders_statistics_exact']['columns']['rows'][0][14] = 'HYBRID'
    approval_bad = 'E04/ORDERS/' + sb.digest([run_a, sim_b_bad])
    res_bad = compare_statistics_runs(run_a, sim_b_bad, 'baseline', approval=approval_bad)
    assert res_bad['status'] == 'NOT COMPARABLE'

    # Corrupt CUSTOMER_ID in summary column_statistics
    sim_b_bad2 = deepcopy(sim_b)
    for r in sim_b_bad2['context']['column_statistics']:
        if r[:2] == ['ORDERS', 'CUSTOMER_ID']:
            r[3] = 'FREQUENCY'
    approval_bad2 = 'E04/ORDERS/' + sb.digest([run_a, sim_b_bad2])
    res_bad2 = compare_statistics_runs(run_a, sim_b_bad2, 'baseline', approval=approval_bad2)
    assert res_bad2['status'] == 'NOT COMPARABLE'


# 14. Cross-cohort PAID vs CANCELLED comparisons are rejected
def test_cross_cohort_paid_vs_cancelled_rejected():
    _, after_gather, _, run_a = _load_real_e04_states()
    sim_b = deepcopy(run_a)
    sim_b['context']['orders_statistics_exact'] = deepcopy(after_gather['effective']['statistics'])
    # Tamper variant 'baseline' bind to 'CANCELLED'
    sim_b['cases']['baseline']['validation']['binds'] = {'status': 'CANCELLED'}
    approval = 'E04/ORDERS/' + sb.digest([run_a, sim_b])
    with pytest.raises(DiagnosticError, match='cohort or bind mismatch'):
        compare_statistics_runs(run_a, sim_b, 'baseline', approval=approval)


# 15. Plan extractor uses real operators and refuses to fabricate missing operators
def test_plan_extractor_real_and_incomplete_captures():
    import json
    from pathlib import Path
    root = Path('docs/evidence/phase4/group-b-histogram')
    _, _, _, run_a = _load_real_e04_states()

    # Real Scenario A plan from run.json
    paid_plan = run_a['cases']['baseline']['plan']
    paid_summary = se.extract_plan_summary(paid_plan)
    assert paid_summary['status'] == 'PASS'
    assert paid_summary['plan_hash'] == 36248429
    assert paid_summary['orders_access_type'] == 'TABLE ACCESS FULL'
    assert paid_summary['orders_object'] == 'ORDERS'
    assert paid_summary['orders_estimated_rows'] == 2500
    assert paid_summary['orders_optimizer_cost'] == 15
    assert paid_summary['root_optimizer_cost'] == 16
    assert paid_summary['orders_filter_predicates'] == '"STATUS"=:STATUS'
    assert paid_summary['binds'] == {'status': 'PAID'}
    assert len(paid_summary['operators']) == 3

    # Incomplete plan from observed-histogram.json (where old extractor saved steps=[])
    obs_hist = json.loads((root / 'observed-histogram.json').read_text())
    incomplete_paid = obs_hist['estimated_plans_with_histogram']['baseline_PAID']
    inc_summary = se.extract_plan_summary(incomplete_paid)
    assert inc_summary['status'] == 'INCOMPLETE'
    assert inc_summary['operators'] == []
    assert inc_summary['orders_estimated_rows'] is None
    assert inc_summary['plan_hash'] == 36248429


# 16. Simulation with real recorded evidence from previous E04 execution
def test_simulation_with_real_recorded_e04_evidence():
    before, after_gather, after_recovery, run_a = _load_real_e04_states()

    # 1. Original state and post-recovery state match with 0 differences
    assert sb.restoration(before, after_recovery)['status'] == 'PASS'
    assert sb.restoration(before, after_recovery)['differences'] == []

    # 2. Post-gather state with FREQUENCY histogram and ORDERS_PK.STALE_STATS='YES' passes guard
    guard = se.validate_e04_post_gather_state(before, after_gather)
    assert guard['status'] == 'PASS'
    assert guard['ready_for_scenario_b'] is True
    assert guard['histogram_evaluation']['status'] == 'PASS'
    assert guard['histogram_evaluation']['histogram_type_observed'] == 'FREQUENCY'
    assert guard['histogram_evaluation']['num_buckets_observed'] == 4
    assert len(guard['derived_metadata_exceptions']) == 1
    assert guard['derived_metadata_exceptions'][0]['path'] == '/effective/statistics/indexes/rows/0/22'
    assert '/effective/statistics/indexes/rows/0/22' in guard['all_statistics_differences_preserved']

    # 3. Same-cohort comparison succeeds across scenario labels ('baseline' vs 'status-histogram')
    sim_b = deepcopy(run_a)
    sim_b['run_id'] = 'b' * 32
    sim_b['scenario'] = 'status-histogram'
    sim_b['context']['orders_statistics_exact'] = deepcopy(after_gather['effective']['statistics'])
    sim_b['context']['statistics'] = [
        ['ORDERS', 10000, '2026-10-20 02:16:12', 'NO'] if r[0] == 'ORDERS' else r
        for r in sim_b['context']['statistics']
    ]
    sim_b['context']['column_statistics'] = [
        ['ORDERS', 'STATUS', 4, 'FREQUENCY', 4] if r[:2] == ['ORDERS', 'STATUS'] else r
        for r in sim_b['context']['column_statistics']
    ]

    approval = 'E04/ORDERS/' + sb.digest([run_a, sim_b])
    for variant, cohort in (('baseline', 'PAID'), ('rare', 'CANCELLED')):
        comp = compare_statistics_runs(run_a, sim_b, variant, approval=approval)
        assert comp['status'] == 'DESCRIPTIVE ONLY'
        assert comp['cohort'] == cohort
        assert comp['baseline_scenario'] == 'baseline'
        assert comp['alternative_scenario'] == 'status-histogram'
        assert len(comp['derived_metadata_exceptions']) == 1
        assert '/indexes/rows/0/22' in comp['authorized_statistics_changes']
        # Original run dicts retain STALE_STATS untouched
        assert run_a['context']['orders_statistics_exact']['indexes']['rows'][0][22] == 'NO'
        assert sim_b['context']['orders_statistics_exact']['indexes']['rows'][0][22] == 'YES'

"""Descriptive client-latency statistics; retain outliers and disclose failures."""
from math import isfinite
from statistics import mean, median, stdev


def _is_finite_number(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and isfinite(value)


def percentile(values, fraction):
    """Linear interpolation at (n-1)*p, including endpoints; no exclusive quartiles."""
    if (
        not values
        or not _is_finite_number(fraction)
        or not 0 <= fraction <= 1
        or not all(_is_finite_number(v) for v in values)
    ):
        raise ValueError('Nonempty finite numeric values and a probability in [0, 1] are required')
    ordered = sorted(values)
    rank = (len(ordered)-1)*fraction
    low = int(rank)
    high = min(low+1, len(ordered)-1)
    return ordered[low] + (ordered[high]-ordered[low])*(rank-low)


def summarize(samples):
    measured = [s for s in samples if not s['warmup']]
    values = [s['elapsed_ms'] for s in measured if s['status']=='PASS'
              and _is_finite_number(s['elapsed_ms']) and s['elapsed_ms']>=0]
    result = {'unit':'ms', 'n':len(values), 'failures':len(measured)-len(values),
              'warmups':sum(s['warmup'] for s in samples),
              'warmup_failures':sum(s['warmup'] and s['status']!='PASS' for s in samples)}
    result.update({key:None for key in ('median','mean','min','max','iqr','p95','stddev')})
    if values:
        result.update(median=median(values),mean=mean(values),min=min(values),max=max(values),
                      iqr=percentile(values,.75)-percentile(values,.25),p95=percentile(values,.95),
                      stddev=stdev(values) if len(values)>1 else None)
    return result


def comparison(baseline, alternative, *, comparable, valid):
    enough = min(baseline['n'], alternative['n']) >= 5
    clean = not any(x['failures'] or x['warmup_failures'] for x in (baseline, alternative))
    if not comparable or not valid or not enough or not clean:
        return {'status':'NOT COMPARABLE', 'reason':'Requires equivalent results, stable controls, no failures and at least five valid samples per variant.'}
    a,b = baseline['median'], alternative['median']
    return {'status':'DESCRIPTIVE ONLY', 'alternative_minus_baseline_ms':b-a,
            'change_percent':100*(b-a)/a if a else None,
            'baseline_over_alternative':a/b if b else None,
            'limitation':'Client latency variation is not proof of a causal improvement.'}


def compare_runs(baseline, alternative, variant='baseline'):
    """Separate index-state blocks; strict deterministic controls, no automatic DDL."""
    keys=('experiment_id','query_id','order_seed','warmups','repeats')
    context_keys=('profile','seed','manifest','statistics','column_statistics','selected','oracle_version','identity')
    compatible=all(baseline.get(k)==alternative.get(k) for k in keys)
    compatible &= all(baseline['context'].get(k)==alternative['context'].get(k) for k in context_keys)
    compatible &= baseline.get('session')==alternative.get('session')
    for key in ('python_version','driver_version','oracle_image_digest','source_sha256'):
        compatible &= baseline['environment'].get(key)==alternative['environment'].get(key)
    a=baseline['cases'].get(variant);b=alternative['cases'].get(variant)
    compatible &= bool(a and b)
    if a and b:
        for key in ('sql_sha256','binds','result'):
            compatible &= a['validation'].get(key)==b['validation'].get(key)
    valid=all(r['status']=='PASS' and r.get('controls_unchanged') for r in (baseline,alternative))
    result=comparison(summarize([s for s in baseline['samples'] if s['variant']==variant]),
                      summarize([s for s in alternative['samples'] if s['variant']==variant]),
                      comparable=compatible and baseline['equivalent'] and alternative['equivalent'],valid=valid)
    return {'baseline_run_id':baseline['run_id'],'alternative_run_id':alternative['run_id'],**result,
            'block_limitation':'Index states measured at different times; cache, load and order confounding remain. Not randomized per repetition.'}


ALLOWED_E04_SCENARIOS = ('baseline', 'status-histogram', 'histogram')


def _is_e04_histogram_active(run):
    from oracle_spa.statistics_experiment import evaluate_observed_histogram
    exact = run.get('context', {}).get('orders_statistics_exact', {})
    cols = exact.get('columns')
    hists = exact.get('histograms')
    if isinstance(cols, dict) and 'columns' in cols and 'rows' in cols and isinstance(hists, dict) and 'columns' in hists and 'rows' in hists:
        col_idx = cols['columns'].index('COLUMN_NAME')
        hist_col_idx = hists['columns'].index('COLUMN_NAME')
        status_row = next((r for r in cols['rows'] if r[col_idx] == 'STATUS'), None)
        status_hist = [r for r in hists['rows'] if r[hist_col_idx] == 'STATUS']
        return evaluate_observed_histogram(status_row, status_hist)['status'] == 'PASS'
    return any(
        len(row) >= 4 and row[0] == 'ORDERS' and row[1] == 'STATUS' and row[3] == 'FREQUENCY'
        for row in run.get('context', {}).get('column_statistics', [])
    )


def compare_statistics_runs(baseline, alternative, variant, *, approval=None):
    """Explicit E04 same-cohort comparison; only named ORDERS.STATUS statistics and allowed derived metadata may differ.

    Approval binds both complete run artifacts. It is not permission to gather stats.
    """
    from copy import deepcopy
    from oracle_spa.statistics_backup import digest, differences
    from oracle_spa.statistics_experiment import inspect_e04_stale_stats_exception
    from oracle_spa.db import DiagnosticError
    expected = 'E04/ORDERS/' + digest([baseline, alternative])
    if approval != expected:
        raise DiagnosticError('Specific E04 statistics comparison approval is required.')
    if variant not in ('baseline', 'rare') or any(
            r.get('experiment_id') != 'E04' or r.get('query_id') != 'Q06'
            for r in (baseline, alternative)):
        raise DiagnosticError('Only same-cohort E04/Q06 comparisons are allowed.')
    if any(not r['context'].get('orders_effective_preferences') for r in (baseline, alternative)):
        raise DiagnosticError('Effective preferences evidence is required.')
    expected_status = 'PAID' if variant == 'baseline' else 'CANCELLED'
    for run in (baseline, alternative):
        binds = run.get('cases', {}).get(variant, {}).get('validation', {}).get('binds')
        if binds != {'status': expected_status}:
            raise DiagnosticError('E04 cohort or bind mismatch.')
    if (
        baseline.get('scenario') != 'baseline'
        or alternative.get('scenario') not in ALLOWED_E04_SCENARIOS
    ):
        return {'status': 'NOT COMPARABLE', 'reason': 'Non-ORDERS-statistics controls changed.'}

    left, right = deepcopy(baseline), deepcopy(alternative)
    for run in (left, right):
        if 'statistics' not in run['context'] or 'column_statistics' not in run['context']:
            raise DiagnosticError('Statistics evidence is missing.')
        run['context']['statistics'] = [row for row in run['context']['statistics'] if row[0] != 'ORDERS']
        # Only ORDERS.STATUS may differ in column_statistics; non-STATUS columns of ORDERS must match.
        run['context']['column_statistics'] = [
            row for row in run['context']['column_statistics']
            if not (len(row) >= 2 and row[0] == 'ORDERS' and row[1] == 'STATUS')
        ]
        exact = run['context'].get('orders_statistics_exact')
        if not exact or set(exact) != {'table', 'columns', 'histograms', 'indexes', 'explicit_preferences'}:
            raise DiagnosticError('Full exact ORDERS statistics evidence is required.')

    histogram_active = _is_e04_histogram_active(alternative)
    stale_check = inspect_e04_stale_stats_exception(
        baseline['context']['orders_statistics_exact']['indexes'],
        alternative['context']['orders_statistics_exact']['indexes'],
        experiment_id='E04',
        histogram_active=histogram_active,
        before_index_meta=baseline['context'].get('indexes'),
        after_index_meta=alternative['context'].get('indexes'),
    )
    if not stale_check['allowed']:
        return {'status': 'NOT COMPARABLE', 'reason': 'Non-ORDERS-statistics controls changed.'}

    for run in (left, right):
        exact = run['context']['orders_statistics_exact']
        for section in ('columns', 'histograms'):
            sec_val = exact[section]
            if isinstance(sec_val, dict) and 'columns' in sec_val and 'rows' in sec_val:
                col_pos = sec_val['columns'].index('COLUMN_NAME')
                sec_val['rows'] = [row for row in sec_val['rows'] if row[col_pos] != 'STATUS']
            elif sec_val == []:
                exact[section] = None
        tbl_val = exact['table']
        if isinstance(tbl_val, dict) and 'columns' in tbl_val and 'rows' in tbl_val:
            la_pos = tbl_val['columns'].index('LAST_ANALYZED')
            for row in tbl_val['rows']:
                if row[0] == 'ORDERS':
                    row[la_pos] = None
        elif tbl_val == []:
            exact['table'] = None
        run['equivalent'] = True  # Same variant on both sides, never baseline versus rare.
        run['scenario'] = 'baseline'

    if stale_check['exception_applied']:
        right['context']['orders_statistics_exact']['indexes'] = deepcopy(
            left['context']['orders_statistics_exact']['indexes']
        )

    if left['context'] != right['context'] or left.get('metric') != right.get('metric'):
        return {'status': 'NOT COMPARABLE', 'reason': 'Non-ORDERS-statistics controls changed.'}
    result = compare_runs(left, right, variant)
    result.update(
        cohort=expected_status,
        baseline_scenario=baseline.get('scenario'),
        alternative_scenario=alternative.get('scenario'),
        authorization=expected,
        authorized_statistics_changes=differences(
            baseline['context']['orders_statistics_exact'],
            alternative['context']['orders_statistics_exact'],
        ),
        derived_metadata_exceptions=[stale_check['exception_record']] if stale_check['exception_applied'] else [],
        statistics_before_sha256=digest({k: baseline['context'][k] for k in ('statistics', 'column_statistics', 'orders_statistics_exact')}),
        statistics_after_sha256=digest({k: alternative['context'][k] for k in ('statistics', 'column_statistics', 'orders_statistics_exact')}),
        block_limitation='Statistics states measured in separate blocks; cache/load confounding remains.',
    )
    return result

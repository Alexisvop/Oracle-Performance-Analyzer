"""Regression checks for defects found in the final Phase 3 audit; mocks are not evidence."""
import sqlite3
from unittest.mock import MagicMock
import pytest
from oracle_spa.db import DiagnosticError
from oracle_spa.execution import compare_results,run_query
from oracle_spa.plans import explain_query,actual_cursor_plan,metric_availability

@pytest.mark.parametrize('mismatch',[False,True])
def test_multiset_closes_sqlite_on_success_and_failure(monkeypatch,mismatch):
    original=sqlite3.connect;connections=[]
    def capture(*args,**kwargs):
        c=original(*args,**kwargs);connections.append(c);return c
    monkeypatch.setattr('oracle_spa.execution.sqlite3.connect',capture)
    if mismatch:
        with pytest.raises(DiagnosticError):compare_results([(1,)],[(2,)],False)
    else:compare_results([(1,)],[(1,)],False)
    assert len(connections)==1
    with pytest.raises(sqlite3.ProgrammingError,match='closed'):
        connections[0].execute('SELECT 1')

@pytest.mark.parametrize('operation',[run_query,explain_query,actual_cursor_plan])
def test_reused_context_cannot_skip_live_identity(operation):
    c=MagicMock();cur=c.cursor.return_value.__enter__.return_value
    cur.fetchone.return_value=('SYSTEM','FREEPDB1','ORACLE_SPA')
    with pytest.raises(DiagnosticError,match='expected ORACLE_SPA'):
        operation(c,'Q01',context=(None,{}))
    assert len(cur.execute.call_args_list)==1
    assert 'SYS_CONTEXT' in cur.execute.call_args.args[0]

def test_partial_operator_metrics_are_not_all_observed():
    metrics=metric_availability([{'starts':1,'actual_rows':None,'consistent_gets':0,'current_gets':None,'physical_reads':0}])
    assert metrics['starts']=='OBSERVED'
    assert metrics['actual_rows']=='NOT AVAILABLE'
    assert metrics['physical_reads']=='OBSERVED'  # Real zero differs from missing.
    assert metric_availability([{'starts':1},{'starts':None}])['starts']=='NOT VERIFIED'
    assert set(metric_availability([]).values())=={'NOT AVAILABLE'}

@pytest.mark.parametrize('fault',[None,'header','hash','missing_metric','multiple_children'])
def test_cursor_association_and_metric_labels(monkeypatch,fault):
    # Synthetic fixture: validates control flow only; no server metrics are claimed.
    import oracle_spa.plans as plans
    monkeypatch.setattr(plans,'assert_identity',lambda c:None)
    monkeypatch.setattr(plans,'cursor_availability',lambda c:{v:'accessible' for v in plans.CURSOR_VIEWS})
    sql='SELECT /*+ gather_plan_statistics */ /* OSPA_fixture */ customer_id FROM customers'
    monkeypatch.setattr('oracle_spa.execution.run_query',lambda *a,**k:{'sql':sql})
    c=MagicMock();cur=c.cursor.return_value.__enter__.return_value
    identities=[('123456789abcd',2,sql)]*(2 if fault=='multiple_children' else 1)
    cur.fetchall.side_effect=[identities]
    sid='123456789abcf' if fault=='header' else '123456789abcd'
    calls=iter([
        [(f'SQL_ID {sid}, child number 2',),('Plan hash value: 321',)],
        [(0,'SELECT STATEMENT',None,1,None if fault=='missing_metric' else 1,0,0,0,999 if fault=='hash' else 321)]
    ])
    cur.__iter__.side_effect=lambda:iter(next(calls))
    result=plans.actual_cursor_plan(c,'Q01')
    if fault in ('header','hash','multiple_children'):
        assert result['type']=='NOT AVAILABLE' and result['status']=='NOT VERIFIED'
    else:
        assert result['type']=='ACTUAL_CURSOR_PLAN'
        assert result['metrics_status']==('NOT VERIFIED' if fault=='missing_metric' else 'OBSERVED')
        lookup=cur.execute.call_args_list[0]
        assert lookup.kwargs['sql']==sql
        display=cur.execute.call_args_list[1]
        assert display.kwargs=={'sid':'123456789abcd','child':2}

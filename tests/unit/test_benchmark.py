from copy import deepcopy
from unittest.mock import MagicMock
import json
import pytest
from oracle_spa.analysis import percentile, summarize, comparison
from oracle_spa.benchmark import schedule, timed_fetch, run_benchmark
from oracle_spa.db import DiagnosticError
from oracle_spa.experiments import EXPERIMENTS, get_experiment
from oracle_spa.indexes import INDEXES, definitions, operation_plan, apply_index, inspect_indexes
from oracle_spa.report import write_run, render_report, run_directory


def test_catalog_and_index_definitions_are_closed():
    assert {e.id for e in EXPERIMENTS.values()}=={'E01','E02','E03','E04','E05'}
    assert not EXPERIMENTS['status-skew'].equivalent
    for e in EXPERIMENTS.values():
        for names in e.scenarios.values():definitions(names)
    for bad in ('CUSTOMERS_PK','BAD; DROP TABLE CUSTOMERS','OSPA_UNKNOWN'):
        with pytest.raises(DiagnosticError):operation_plan('drop',bad)
    with pytest.raises(DiagnosticError):definitions(('OSPA_ORDERS_DATE',)*2)
    with pytest.raises(DiagnosticError):get_experiment('email-index','unexpected')


def test_ddl_confirmation_is_checked_before_connection_use():
    c=MagicMock()
    for action in ('create','drop'):
        with pytest.raises(DiagnosticError,match='approval'):
            apply_index(c,action,'OSPA_ORDERS_DATE',None)
        assert not c.cursor.called
    plan=operation_plan('create','OSPA_ORDERS_CUST_DATE')
    assert plan['sql']=='CREATE INDEX ORACLE_SPA.OSPA_ORDERS_CUST_DATE ON ORACLE_SPA.ORDERS (CUSTOMER_ID, ORDER_DATE) TABLESPACE USERS'
    assert plan['implicit_commit'] and not plan['rollback_restores_index']


def test_index_conflict_and_constraint_are_refused():
    c=MagicMock();cur=c.cursor.return_value.__enter__.return_value
    cur.fetchall.return_value=[]
    with pytest.raises(DiagnosticError,match='definition'):inspect_indexes(c,('OSPA_ORDERS_DATE',))
    cur.fetchall.side_effect=[ [('ORACLE_SPA','ORDERS','NONUNIQUE','NORMAL','VALID','VISIBLE','NO')], [('ORDER_DATE',1,'ASC')], [('PK',)] ]
    with pytest.raises(DiagnosticError,match='Constraint'):inspect_indexes(c,('OSPA_ORDERS_DATE',))


def test_drop_requires_creation_receipt_and_no_active_transaction(monkeypatch):
    c=MagicMock();c.transaction_in_progress=False
    monkeypatch.setattr('oracle_spa.schema.inspect_schema',lambda *args:'ready')
    monkeypatch.setattr('oracle_spa.indexes.inspect_indexes',lambda *args:[{'object_id':100}])
    p=operation_plan('drop','OSPA_ORDERS_DATE')
    with pytest.raises(DiagnosticError,match='receipt'):
        apply_index(c,'drop','OSPA_ORDERS_DATE',p['confirmation'],('OSPA_ORDERS_DATE',),101)
    assert not c.cursor.called
    c.transaction_in_progress=True
    with pytest.raises(DiagnosticError,match='transaction'):
        apply_index(c,'drop','OSPA_ORDERS_DATE',p['confirmation'],('OSPA_ORDERS_DATE',),100)


def test_schedule_reproducible_balanced_and_bounded():
    a=list(schedule(('baseline','range'),5,10,19))
    assert a==list(schedule(('baseline','range'),5,10,19))
    assert a!=list(schedule(('baseline','range'),5,10,20))
    assert len(a)==30 and sum(w for w,_,_ in a)==10
    assert {v for _,_,v in a[:2]}=={'baseline','range'}
    for w,r in ((-1,10),(1,0),(1,101),(True,1)):
        with pytest.raises(DiagnosticError):list(schedule(('baseline',),w,r))


def test_timer_wraps_only_execute_and_complete_fetch():
    events=[]
    class Cursor:
        def execute(self,*a,**kw):events.append('execute')
        def fetchmany(self,n):
            events.append('fetch')
            return [(1,)] if events.count('fetch')==1 else []
    times=iter((1_000_000,3_000_000))
    def clock():events.append('clock');return next(times)
    rows,ms=timed_fetch(Cursor(),'SELECT 1',{},clock)
    assert rows==[(1,)] and ms==2
    assert events==['clock','execute','fetch','fetch','clock']


def test_timer_finalizes_on_execute_error():
    c=MagicMock();c.execute.side_effect=RuntimeError('private-value')
    clock=MagicMock(side_effect=[0,100])
    with pytest.raises(RuntimeError):timed_fetch(c,'SELECT 1',{},clock)
    assert clock.call_count==2


def sample(ms, warmup=False, status='PASS'):
    return {'elapsed_ms':ms,'warmup':warmup,'status':status,'variant':'baseline'}


def test_analysis_keeps_outliers_and_excludes_warmups():
    s=summarize([sample(x) for x in [1,2,3,4,100]]+[sample(900,True),sample(None,status='FAIL')])
    assert s['n']==5 and s['failures']==1 and s['median']==3 and s['iqr']==2
    assert s['p95']==pytest.approx(80.8) and s['max']==100 and s['warmups']==1
    assert percentile([1],.95)==1
    assert summarize([])['median'] is None


def test_no_speedup_for_cohorts_failures_or_insufficient_samples():
    good=summarize([sample(1)]*10)
    assert comparison(good,good,comparable=True,valid=True)['change_percent']==0
    assert comparison(good,good,comparable=False,valid=True)['status']=='NOT COMPARABLE'
    assert comparison(good,good,comparable=True,valid=False)['status']=='NOT COMPARABLE'
    assert comparison(good,summarize([sample(1)]),comparable=True,valid=True)['status']=='NOT COMPARABLE'


def test_report_rejects_paths_and_preserves_raw_samples(tmp_path):
    for bad in ('../.env','A'*32,'run-1'):
        with pytest.raises(DiagnosticError):run_directory(bad,tmp_path)
    run={'run_id':'a'*32,'status':'PASS','experiment_id':'E01','scenario':'baseline',
         'metric':'query-only','cases':{'baseline':{}},'samples':[sample(1),sample(2,True)],
         'equivalent':True,'controls_unchanged':True,'environment_notes':['No server CPU inference.']}
    path=write_run(run,tmp_path)
    summary=render_report(run['run_id'],tmp_path)
    assert summary['summaries']['baseline']['n']==1
    assert len((path/'samples.csv').read_text().splitlines())==3
    assert 'ms' in (path/'latency.svg').read_text()
    assert json.loads((path/'run.json').read_text())==run
    assert render_report(run['run_id'],tmp_path)==summary
    (tmp_path/('b'*32)).symlink_to(path,target_is_directory=True)
    with pytest.raises(DiagnosticError):run_directory('b'*32,tmp_path)


def test_cli_offline_plan_and_invalid_counts(capsys,monkeypatch):
    from oracle_spa.cli import main
    monkeypatch.setattr('oracle_spa.cli.Config.from_env',lambda:pytest.fail('must validate before credentials'))
    assert main(['index-plan','--index','OSPA_ORDERS_DATE','--action','create'])==0
    assert 'CREATE INDEX' in capsys.readouterr().out
    assert main(['run','--query','Q01','--repeats','0'])==1
    assert main(['compare','--experiment','email-index','--scenario','bad'])==1


def test_failed_sample_preserved_without_driver_secret_or_retry(monkeypatch):
    import oracledb
    context=(MagicMock(profile='small',seed=20261016),{'selected':{}})
    c=MagicMock();c.version='23.26.3.0.0'
    monkeypatch.setattr('oracle_spa.benchmark.prepare',lambda *a:context)
    monkeypatch.setattr('oracle_spa.benchmark.environment',lambda:{k:None for k in ('git_commit','oracle_image_digest','python_version','driver_version')})
    checked={'sql_sha256':'hash','binds':{},'result':{}}
    plan={'sql_sha256':'hash','binds':{},'type':'ESTIMATED_PLAN','plan_hash':10}
    monkeypatch.setattr('oracle_spa.benchmark.run_query',lambda *a:checked)
    monkeypatch.setattr('oracle_spa.benchmark.explain_query',lambda *a:plan)
    monkeypatch.setattr('oracle_spa.benchmark.session_settings',lambda *a:{})
    monkeypatch.setattr('oracle_spa.benchmark.binds_for',lambda *a:{})
    failing=MagicMock(side_effect=oracledb.DatabaseError('password=private-value'))
    monkeypatch.setattr('oracle_spa.benchmark.timed_fetch',failing)
    saved=[]
    with pytest.raises(DiagnosticError,match='retained failed sample'):
        run_benchmark(c,'email-index',warmups=0,repeats=10,sink=lambda r:saved.append(deepcopy(r)))
    assert failing.call_count==1
    final=saved[-1]
    assert final['status']=='FAIL' and len(final['samples'])==1
    assert final['samples'][0]['status']=='FAIL' and final['samples'][0]['elapsed_ms'] is None
    assert 'private-value' not in json.dumps(final)


def test_session_configuration_uses_supported_sql_and_declared_read_only_mode():
    from oracle_spa.benchmark import session_settings
    c=MagicMock();cur=c.cursor.return_value.__enter__.return_value
    cur.fetchall.return_value=[('NLS_DATE_FORMAT','DD-MON-RR')]
    cur.fetchone.return_value=('+00:00','+00:00')
    s=session_settings(c)
    assert s['transaction_mode'].startswith('SET TRANSACTION READ ONLY')
    assert 'ISOLATION_LEVEL' not in str(cur.execute.call_args_list)


def test_schema_extension_is_explicit_and_keeps_other_contract_checks():
    from test_dataset import schema_fixture
    from oracle_spa.schema import inspect_schema
    c,replies=schema_fixture()
    replies[0].append(('OSPA_ORDERS_DATE','INDEX','VALID'))
    with pytest.raises(DiagnosticError,match='unrecognized'):inspect_schema(c)
    c,replies=schema_fixture()
    replies[0].append(('OSPA_ORDERS_DATE','INDEX','VALID'))
    replies[5].append(('OSPA_ORDERS_DATE','ORDERS','NONUNIQUE','NORMAL'))
    replies.extend([[('ORACLE_SPA','ORDERS','NONUNIQUE','NORMAL','VALID','VISIBLE','NO')], [('ORDER_DATE',1,'ASC')], []])
    cur=c.cursor.return_value.__enter__.return_value
    cur.fetchone.side_effect=[('ORACLE_SPA','FREEPDB1','ORACLE_SPA'),(123,),(65536,)]
    assert inspect_schema(c,('OSPA_ORDERS_DATE',))=='ready'
    c,replies=schema_fixture()
    replies[0].extend([('OSPA_ORDERS_DATE','INDEX','VALID'),('UNKNOWN','TABLE','VALID')])
    with pytest.raises(DiagnosticError,match='unrecognized'):inspect_schema(c,('OSPA_ORDERS_DATE',))


def test_cross_block_comparison_rejects_control_drift():
    from oracle_spa.analysis import compare_runs
    run={'run_id':'a'*32,'experiment_id':'E01','query_id':'Q01','order_seed':1,'warmups':5,'repeats':10,
         'context':{'manifest':{'seed':1}},'environment':{'source_sha256':{'benchmark.py':'abc'}},
         'session':{'arraysize':500},'cases':{'baseline':{'validation':{'sql_sha256':'abc','binds':{},'result':{'rows':1}}}},
         'samples':[sample(1)]*10,'status':'PASS','controls_unchanged':True,'equivalent':True}
    other=deepcopy(run);other['run_id']='b'*32
    assert compare_runs(run,other)['status']=='DESCRIPTIVE ONLY'
    other['context']['manifest']['seed']=2
    assert compare_runs(run,other)['status']=='NOT COMPARABLE'


def test_statistics_planning_is_read_only_and_has_explicit_restore_risk(monkeypatch):
    from oracle_spa.statistics_experiment import statistics_plan
    c=MagicMock();cur=c.cursor.return_value.__enter__.return_value
    cur.fetchone.return_value=('now','old',31);cur.fetchall.return_value=[]
    monkeypatch.setattr('oracle_spa.statistics_experiment.inspect_schema',lambda *a:'ready')
    plan=statistics_plan(c)
    assert all(call.args[0].startswith('SELECT ') for call in cur.execute.call_args_list)
    assert plan['status']=='PENDING APPROVAL'
    assert 'NOT VERIFIED' in plan['restoration_test']
    assert ':restore_at' in plan['restore_sql']

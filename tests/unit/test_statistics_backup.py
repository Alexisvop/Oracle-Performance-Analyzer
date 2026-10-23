from copy import deepcopy
from decimal import Decimal
from unittest.mock import MagicMock
from dataclasses import replace
from pathlib import Path
import json
import pytest
from oracle_spa import statistics_backup as sb
from oracle_spa.db import DiagnosticError
from oracle_spa.schema import inspect_schema
from oracle_spa.analysis import compare_statistics_runs


def original():
    return {'effective': {'statistics': {'density': sb.value(Decimal('.25'))},
                          'dataset': {'seed':20261016}, 'preferences': {'PUBLISH':'TRUE'}},
            'history': []}


def observed_structure():
    return {'name':sb.BACKUP, 'version':'23.26.3.0.0', 'structure':json.loads(
        Path('docs/evidence/phase4/group-b-create-stat-table/observed-structure.json').read_text())}


def permit():
    observation=observed_structure()
    proof={'kind':'forensic-reconciliation','status':'MATCHED; EXTERNAL APPROVAL PENDING',
           'journal_validated':True,'original_stop_preserved':True,'backup':observation}
    return sb.BackupPermit(proof,sb.digest(observation),sb.digest(proof))


def expanded_schema_fixture():
    from test_dataset import schema_fixture
    c,replies=schema_fixture();structure=observed_structure()['structure']
    replies[0].extend(tuple(row[:3]) for row in structure['new_objects']['rows'])
    replies[1].append((sb.BACKUP,None))
    replies[2].append((sb.BACKUP,'STATID',1,'VARCHAR2',None,None,128,'B','Y'))
    replies[5].extend((r[0],r[2],r[4],r[5]) for r in structure['backup_index']['rows'])
    return c,replies


def test_exact_serialization_and_history_are_separate():
    before=original();after=deepcopy(before);after['history'].append('new entry')
    assert sb.restoration(before,after)['status']=='PASS'
    assert sb.restoration(before,after)['history_changed']
    after['effective']['statistics']['density']=sb.value(Decimal('.25000000000000001'))
    report=sb.restoration(before,after)
    assert report['status']=='FAIL' and report['differences']==['/statistics/density/oracle_number']
    assert report['before_sha256'] != report['after_sha256']
    assert sb.value(b'\x00\xff')=={'raw_hex':'00FF'}
    assert sb.differences({'date':None},{'date':'today'})==['/date']


def test_closed_sql_and_missing_authorization_before_database_access(tmp_path):
    c=MagicMock()
    for bad in ('gather','restore','drop','export; DELETE FROM ORDERS'):
        with pytest.raises(DiagnosticError):sb.prepare_operation(c,bad,original())
    with pytest.raises(DiagnosticError):
        sb.execute_operation(c,{'operation':'create'},confirmation=None,original=original(),journal=tmp_path/'attempt')
    assert not c.cursor.called
    assert set(sb.OPERATIONS)=={'create','export','import-rehearsal','import-recovery'}
    for sql in sb.OPERATIONS.values():
        assert sb.BACKUP in sql and 'force=>TRUE' not in sql and 'DROP' not in sql
    assert 'cascade=>TRUE' in sb.EXPORT_SQL and 'force=>FALSE' in sb.IMPORT_SQL


def test_structure_needs_review_and_rejects_replacement(monkeypatch):
    p=permit();c=MagicMock()
    monkeypatch.setattr(sb,'observe_structure',lambda c:p.creation_receipt['backup'])
    assert sb.verify_structure(c,p)==p.creation_receipt['backup']
    with pytest.raises(DiagnosticError):sb.verify_structure(c,None)
    with pytest.raises(DiagnosticError):sb.verify_structure(c,sb.BackupPermit(p.creation_receipt,'not-approved',p.reviewed_provenance_sha256))
    different=deepcopy(p.creation_receipt['backup']);different['structure']['new_objects']['rows'][-1][3]={'oracle_number':'124'}
    monkeypatch.setattr(sb,'observe_structure',lambda c:different)
    with pytest.raises(DiagnosticError,match='object ID'):sb.verify_structure(c,p)


def test_backup_opt_in_does_not_relax_original_schema(monkeypatch):
    from test_dataset import schema_fixture
    p=permit()
    monkeypatch.setattr(sb,'observe_structure',lambda c:p.creation_receipt['backup'])
    c,replies=expanded_schema_fixture()
    with pytest.raises(DiagnosticError):inspect_schema(c)
    c,replies=expanded_schema_fixture()
    assert inspect_schema(c,backup_permit=p)=='ready'
    for bad in ('unknown','columns','constraints','indexes','marker'):
        c,replies=expanded_schema_fixture()
        if bad=='unknown':replies[0].append(('OTHER_BACKUP','TABLE','VALID'))
        if bad=='columns':replies[2].pop(0)
        if bad=='constraints':replies[3].pop()
        if bad=='indexes':replies[5].pop(0)
        if bad=='marker':replies[1].pop(0)
        with pytest.raises(DiagnosticError):inspect_schema(c,backup_permit=p)


def test_backup_fingerprint_and_provenance(monkeypatch):
    p=permit();c=MagicMock();contents={'columns':['opaque'],'rows':[['data']]}
    monkeypatch.setattr(sb,'observe_structure',lambda c:p.creation_receipt['backup'])
    monkeypatch.setattr(sb,'backup_contents',lambda c:contents)
    receipt={'operation':'export','status':'PASS','sql':sb.EXPORT_SQL,'statid':sb.STATID,
             'structure_sha256':p.reviewed_structure_sha256,'contents_sha256':sb.digest(contents)}
    assert sb.validate_backup(c,p,receipt)==contents
    for key in ('statid','contents_sha256','structure_sha256','sql','operation','status'):
        bad={**receipt,key:'wrong'}
        with pytest.raises(DiagnosticError):sb.validate_backup(c,p,bad)


def test_export_never_overwrites_and_import_requires_original(monkeypatch):
    p=permit();p=replace(p,statistics_approval=sb.statistics_approval(p));c=MagicMock();before=original()
    monkeypatch.setattr(sb,'inspect_original',lambda *a:before)
    monkeypatch.setattr(sb,'inspect_interfaces',lambda *a:{})
    monkeypatch.setattr(sb,'verify_structure',lambda *a:None)
    monkeypatch.setattr(sb,'backup_contents',lambda *a:{'rows':[[1]]})
    with pytest.raises(DiagnosticError,match='overwrite'):sb.prepare_operation(c,'export',before,p)
    monkeypatch.setattr(sb,'validate_backup',lambda *a:None)
    with pytest.raises(DiagnosticError,match='different original'):
        sb.prepare_operation(c,'import-rehearsal',before,p,{'original_sha256':'wrong'})
    changed=deepcopy(before);changed['effective']['dataset']['seed']=1
    monkeypatch.setattr(sb,'inspect_original',lambda *a:changed)
    with pytest.raises(DiagnosticError):sb.prepare_operation(c,'import-recovery',before,p)


def test_partial_failure_logged_redacted_and_never_retried(monkeypatch,tmp_path):
    c=MagicMock();c.transaction_in_progress=False
    plan={'operation':'create','sql':sb.CREATE_SQL,'confirmation':'specific'}
    monkeypatch.setattr(sb,'prepare_operation',lambda *a:plan)
    cur=c.cursor.return_value.__enter__.return_value
    cur.execute.side_effect=RuntimeError('password=secret')
    journal=tmp_path/'attempt.jsonl'
    with pytest.raises(DiagnosticError,match='partial effects'):
        sb.execute_operation(c,plan,confirmation='specific',original=original(),journal=journal)
    assert cur.execute.call_count==1
    assert 'secret' not in journal.read_text() and 'POSSIBLE PARTIAL' in journal.read_text()
    with pytest.raises(FileExistsError):
        sb.execute_operation(c,plan,confirmation='specific',original=original(),journal=journal)
    assert cur.execute.call_count==1 and not c.rollback.called


def test_plan_drift_or_active_transaction_prevents_mutation(monkeypatch,tmp_path):
    c=MagicMock();plan={'operation':'export','confirmation':'x'}
    monkeypatch.setattr(sb,'prepare_operation',lambda *a:{**plan,'changed':True})
    with pytest.raises(DiagnosticError):sb.execute_operation(c,plan,confirmation='x',original=original(),journal=tmp_path/'j')
    assert not c.cursor.called and not (tmp_path/'j').exists()


def run(cohort='PAID'):
    variant='baseline' if cohort=='PAID' else 'rare'
    return {'run_id':'a','experiment_id':'E04','query_id':'Q06','order_seed':20261016,
            'warmups':5,'repeats':10,'context':{'profile':'small','seed':20261016,
            'statistics':[['ORDERS',10000,'old']], 'column_statistics':[['ORDERS','STATUS',4,'NONE']],
            'orders_effective_preferences':{'PUBLISH':'TRUE'},
            'orders_statistics_exact':{k:[] for k in sb.QUERIES}, 'indexes':['ORDERS_PK']},
            'environment':{},'session':{'arraysize':500},'metric':'full fetch', 'scenario':'baseline',
            'cases':{variant:{'validation':{'sql_sha256':'sql','binds':{'status':cohort},'result':{'rows':10}}}},
            'samples':[{'warmup':False,'status':'PASS','elapsed_ms':1,'variant':variant}]*10,
            'status':'PASS','controls_unchanged':True,'equivalent':False}


@pytest.mark.parametrize('cohort,variant',[('PAID','baseline'),('CANCELLED','rare')])
def test_e04_same_cohort_only(cohort,variant):
    a=run(cohort);b=deepcopy(a);b['context']['column_statistics'][0][-1]='FREQUENCY'
    approval=lambda:'E04/ORDERS/'+sb.digest([a,b])
    with pytest.raises(DiagnosticError):compare_statistics_runs(a,b,variant)
    assert compare_statistics_runs(a,b,variant,approval=approval())['status']=='DESCRIPTIVE ONLY'
    b['cases'][variant]['validation']['binds']['status']='SHIPPED'
    with pytest.raises(DiagnosticError):compare_statistics_runs(a,b,variant,approval=approval())


@pytest.mark.parametrize('drift',['index','histogram-index','profile','result','sql','bind','metric','other-table'])
def test_e04_non_statistics_drift_is_rejected(drift):
    a=run();b=deepcopy(a)
    if drift=='index':b['context']['indexes'].append('EXPERIMENTAL')
    if drift=='histogram-index':b['context']['orders_statistics_exact']['indexes']=['changed']
    if drift=='profile':b['context']['profile']='tiny'
    if drift in ('result','sql','bind'):
        key={'result':'result','sql':'sql_sha256','bind':'binds'}[drift]
        b['cases']['baseline']['validation'][key]='changed'
    if drift=='metric':b['metric']='partial fetch'
    if drift=='other-table':b['context']['statistics'].append(['CUSTOMERS',1])
    approval='E04/ORDERS/'+sb.digest([a,b])
    if drift=='bind':
        with pytest.raises(DiagnosticError):compare_statistics_runs(a,b,'baseline',approval=approval)
    else:assert compare_statistics_runs(a,b,'baseline',approval=approval)['status']=='NOT COMPARABLE'


def test_published_snapshot_contract_is_unchanged():
    from pathlib import Path
    record=json.loads(Path('docs/evidence/phase4/group-b-preflight/statistics-original-exact.json').read_text())
    assert sb.QUERIES==record['queries']
    assert sb.digest(record['snapshot'])==record['snapshot_sha256']


def test_import_rehearsal_mismatch_is_failure_not_success(monkeypatch,tmp_path):
    c=MagicMock();c.transaction_in_progress=False
    before=original();after=deepcopy(before);after['effective']['statistics']['last_analyzed']='changed'
    plan={'operation':'import-rehearsal','sql':sb.IMPORT_SQL,'confirmation':'specific'}
    monkeypatch.setattr(sb,'prepare_operation',lambda *a:plan)
    monkeypatch.setattr(sb,'inspect_original',lambda *a:after)
    monkeypatch.setattr(sb,'validate_backup',lambda *a:None)
    with pytest.raises(DiagnosticError,match='partial effects'):
        sb.execute_operation(c,plan,confirmation='specific',original=before,journal=tmp_path/'attempt')
    assert c.cursor.return_value.__enter__.return_value.execute.call_count==1
    evidence=[json.loads(line) for line in (tmp_path/'attempt').read_text().splitlines()]
    assert any(row.get('verification',{}).get('status')=='FAIL' for row in evidence)
    assert not c.rollback.called


def test_interfaces_are_read_only_and_missing_signature_blocks(monkeypatch):
    c=MagicMock();c.cursor.return_value.__enter__.return_value.fetchone.return_value=('ORACLE_SPA','FREEPDB1','ORACLE_SPA')
    monkeypatch.setattr(sb,'query',lambda *a,**kw:{'columns':[],'rows':[]})
    with pytest.raises(DiagnosticError,match='signature'):sb.inspect_interfaces(c)
    assert all(call.args[0].startswith('SELECT ') for call in c.cursor.return_value.__enter__.return_value.execute.call_args_list)


def test_history_dates_provenance_and_endpoint_changes_never_pass():
    for field in ('last_analyzed','user_stats','global_stats','endpoint_actual_value','num_distinct','density'):
        before=original();after=deepcopy(before)
        after['effective']['statistics'][field]='changed'
        assert sb.restoration(before,after)['status']=='FAIL'

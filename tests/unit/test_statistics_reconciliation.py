"""Observed Oracle fixture plus adversarial mutations; no live writes."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest
import oracledb
from oracle_spa import statistics_backup as sb
from oracle_spa.db import DiagnosticError
from test_statistics_backup import observed_structure,permit,original

EVIDENCE=Path('docs/evidence/phase4/group-b-create-stat-table')


def dictionary_mock(monkeypatch,structure):
    c=MagicMock();c.version='23.26.3.0.0'
    c.cursor.return_value.__enter__.return_value.fetchone.return_value=('ORACLE_SPA','FREEPDB1','ORACLE_SPA')
    def read(c,sql,**binds):
        if sql.startswith('SELECT table_name,tablespace_name,temporary'):
            return {'rows':[[sb.BACKUP,'USERS','N','NO',None,'NO']]}
        key=next(k for k,v in sb.STRUCTURE_QUERIES.items() if v==sql)
        return deepcopy(structure[key])
    monkeypatch.setattr(sb,'query',read)
    return c


def test_homonymous_index_and_dictionary_lob_graph(monkeypatch):
    observation=observed_structure();c=dictionary_mock(monkeypatch,observation['structure'])
    assert sb.observe_structure(c)==observation
    assert all(call.args[0].startswith('SELECT ') for call in c.cursor.return_value.__enter__.return_value.execute.call_args_list)


@pytest.mark.parametrize('mutation',['normal_columns','normal_direction','normal_position','uniqueness',
 'normal_owner','lob_table','lob_column','lob_index','lob_segment','extra_sys_index','extra_object',
 'column_type','table_owner','missing_lob','missing_lob_index','constraint','duplicate_id'])
def test_only_exact_relationships_are_accepted(monkeypatch,mutation):
    s=observed_structure()['structure']
    if mutation=='normal_columns':s['backup_index_columns']['rows'][0][1]='C6'
    if mutation=='normal_direction':s['backup_index_columns']['rows'][0][3]='DESC'
    if mutation=='normal_position':s['backup_index_columns']['rows'][0][2]={'oracle_number':'2'}
    if mutation=='uniqueness':s['backup_index']['rows'][0][4]='UNIQUE'
    if mutation=='normal_owner':s['backup_index']['rows'][0][1]='OTHER_SCHEMA'
    if mutation=='lob_table':s['lob_links']['rows'][0][0]='ANOTHER_TABLE'
    if mutation=='lob_column':s['lob_links']['rows'][0][1]='CL1'
    if mutation=='lob_index':s['lob_links']['rows'][0][3]='SYS_FAKE_INDEX'
    if mutation=='lob_segment':s['lob_links']['rows'][0][2]='SYS_FAKE_LOB'
    if mutation=='extra_sys_index':s['backup_index']['rows'].append(['SYS_FAKE','ORACLE_SPA',sb.BACKUP,'USERS','UNIQUE','LOB','VALID','VISIBLE','NO'])
    if mutation=='extra_object':s['new_objects']['rows'].append(['SYS_FAKE','LOB','VALID',{'oracle_number':'90000'},{'datetime':'today'}])
    if mutation=='column_type':s['columns']['rows'][0][2]='NUMBER'
    if mutation=='table_owner':s['backup_table']['rows'][0][0]='OTHER_SCHEMA'
    if mutation=='missing_lob':s['lob_links']['rows'].pop()
    if mutation=='missing_lob_index':s['backup_index']['rows'].pop()
    if mutation=='constraint':s['constraints']['rows'].append(['BAD','C','ENABLED','VALIDATED','1=1'])
    if mutation=='duplicate_id':s['new_objects']['rows'][0][3]=s['new_objects']['rows'][1][3]
    c=dictionary_mock(monkeypatch,s)
    with pytest.raises(DiagnosticError):sb.observe_structure(c)


def test_other_pdb_or_schema_rejected_before_metadata(monkeypatch):
    c=dictionary_mock(monkeypatch,observed_structure()['structure'])
    c.cursor.return_value.__enter__.return_value.fetchone.return_value=('SYSTEM','FREEPDB1','ORACLE_SPA')
    with pytest.raises(DiagnosticError,match='identity|expected'):sb.observe_structure(c)


def test_object_id_or_provenance_tampering_invalidates_permit(monkeypatch):
    p=permit();current=deepcopy(p.creation_receipt['backup'])
    current['structure']['new_objects']['rows'][0][3]={'oracle_number':'99999'}
    monkeypatch.setattr(sb,'observe_structure',lambda c:current)
    with pytest.raises(DiagnosticError,match='object ID'):sb.verify_structure(MagicMock(),p)
    monkeypatch.setattr(sb,'observe_structure',lambda c:p.creation_receipt['backup'])
    p.creation_receipt['original_stop_preserved']=False
    with pytest.raises(DiagnosticError,match='provenance'):sb.verify_structure(MagicMock(),p)


def reconciliation_fixture(monkeypatch,tmp_path):
    for name in ('manifest.json','create-attempt.jsonl','plan.json','preflight.json','result.json',
                 'observed-structure.json','observational-creation-receipt.json','executed.sql'):
        (tmp_path/name).write_bytes((EVIDENCE/name).read_bytes())
    c=MagicMock();c.cursor.return_value.__enter__.return_value.fetchone.return_value=('ORACLE_SPA','FREEPDB1','ORACLE_SPA')
    monkeypatch.setattr(sb,'observe_structure',lambda c:observed_structure())
    before=json.loads((EVIDENCE/'preflight.json').read_text())['original_observed']
    monkeypatch.setattr(sb,'inspect_original',lambda c,p:deepcopy(before))
    monkeypatch.setattr(sb,'query',lambda c,sql:{'rows':[[{'oracle_number':'0'}]]})
    return c,sb.sha256((tmp_path/'manifest.json').read_bytes()).hexdigest()


def test_original_stop_reconciles_without_success_receipt_or_mutations(monkeypatch,tmp_path):
    c,pin=reconciliation_fixture(monkeypatch,tmp_path)
    before=(tmp_path/'create-attempt.jsonl').read_bytes()
    result=sb.reconcile_existing(c,tmp_path,reviewed_manifest_sha256=pin)
    proof=result['reconciliation']
    assert proof['kind']=='forensic-reconciliation' and proof['original_stop_preserved']
    assert proof['original_journal'][-1]['status']=='STOP; POSSIBLE PARTIAL EFFECTS'
    assert 'operation' not in proof and 'sql' not in proof
    assert result['permit_proposal']['statistics_approval'] is None
    assert (tmp_path/'create-attempt.jsonl').read_bytes()==before
    assert not c.commit.called and not c.rollback.called
    for operation in ('export','import-rehearsal','import-recovery'):
        with pytest.raises(DiagnosticError,match='external approval'):
            sb.prepare_operation(c,operation,original(),sb.BackupPermit(**result['permit_proposal']))


@pytest.mark.parametrize('problem',['manifest','journal_hash','stop','sql','attempts','effective_state','nonempty','object_id'])
def test_bad_reconciliation_is_refused(monkeypatch,tmp_path,problem):
    c,pin=reconciliation_fixture(monkeypatch,tmp_path)
    if problem=='manifest':pin='wrong'
    if problem=='journal_hash':(tmp_path/'create-attempt.jsonl').write_text('altered')
    if problem in ('stop','sql','attempts'):
        name='result.json' if problem=='attempts' else 'create-attempt.jsonl'
        if problem=='attempts':
            v=json.loads((tmp_path/name).read_text());v['ddl_attempts']=2
            content=json.dumps(v)
        else:
            events=[json.loads(x) for x in (tmp_path/name).read_text().splitlines()]
            if problem=='stop':events[-1]['status']='PASS'
            if problem=='sql':events[0]['sql']='BEGIN NULL; END;'
            content='\n'.join(json.dumps(e) for e in events)+'\n'
        (tmp_path/name).write_text(content)
        m=json.loads((tmp_path/'manifest.json').read_text())
        m['sha256']['docs/evidence/phase4/group-b-create-stat-table/'+name]=sb.sha256((tmp_path/name).read_bytes()).hexdigest()
        (tmp_path/'manifest.json').write_text(json.dumps(m))
        pin=sb.sha256((tmp_path/'manifest.json').read_bytes()).hexdigest()
    if problem=='effective_state':
        monkeypatch.setattr(sb,'inspect_original',lambda *a:original())
    if problem=='nonempty':monkeypatch.setattr(sb,'query',lambda *a:{'rows':[[{'oracle_number':'1'}]]})
    if problem=='object_id':
        changed=observed_structure();changed['structure']['new_objects']['rows'][0][3]={'oracle_number':'99999'}
        monkeypatch.setattr(sb,'observe_structure',lambda c:changed)
    with pytest.raises(DiagnosticError):sb.reconcile_existing(c,tmp_path,reviewed_manifest_sha256=pin)
    assert not c.commit.called


@pytest.mark.parametrize('stage',['plsql','post-validation','dictionary','interrupted-during-plsql','interrupted-after-plsql'])
def test_phase_and_safe_oracle_code_are_recorded(monkeypatch,tmp_path,stage):
    c=MagicMock();c.transaction_in_progress=False
    plan={'operation':'create','sql':sb.CREATE_SQL,'confirmation':'specific'}
    monkeypatch.setattr(sb,'prepare_operation',lambda *a:plan)
    execute=c.cursor.return_value.__enter__.return_value.execute
    if stage=='plsql':execute.side_effect=oracledb.DatabaseError(SimpleNamespace(full_code='ORA-00955',message='password=secret dsn=private'))
    if stage=='interrupted-during-plsql':execute.side_effect=KeyboardInterrupt()
    def inspect(c):
        if stage=='dictionary':raise sb.InspectionError('ORA-00942')
        if stage=='interrupted-after-plsql':raise KeyboardInterrupt()
        raise DiagnosticError('Unexpected structure')
    monkeypatch.setattr(sb,'observe_structure',inspect)
    exception=KeyboardInterrupt if stage.startswith('interrupted') else DiagnosticError
    journal=tmp_path/'attempt'
    with pytest.raises(exception):
        sb.execute_operation(c,plan,confirmation='specific',original=original(),journal=journal)
    events=[json.loads(x) for x in journal.read_text().splitlines()]
    completed=stage not in ('plsql','interrupted-during-plsql')
    assert events[-1]['plsql_completed']==completed
    assert any(e['status']=='PLSQL COMPLETED' for e in events)==completed
    expected={'plsql':'PLSQL ERROR','post-validation':'POST_VALIDATION_FAILED','dictionary':'DICTIONARY INSPECTION ERROR',
              'interrupted-during-plsql':'INTERRUPTED; OUTCOME NOT VERIFIED','interrupted-after-plsql':'INTERRUPTED; OUTCOME NOT VERIFIED'}[stage]
    assert events[-1]['outcome']==expected
    if stage=='plsql':assert events[-1]['code']=='ORA-00955'
    if stage=='dictionary':assert events[-1]['code']=='ORA-00942'
    assert 'secret' not in journal.read_text() and 'private' not in journal.read_text()
    assert execute.call_count==1 and not c.rollback.called


def test_dictionary_driver_message_is_redacted():
    c=MagicMock();c.cursor.return_value.__enter__.return_value.execute.side_effect=oracledb.DatabaseError(SimpleNamespace(full_code='ORA-00942',message='private password=secret'))
    with pytest.raises(sb.InspectionError) as raised:sb.query(c,'SELECT 1 FROM dual')
    assert raised.value.code=='ORA-00942'
    assert 'secret' not in str(raised.value) and 'private' not in str(raised.value)


@pytest.mark.parametrize('operation',['init','reset'])
def test_backup_inspection_does_not_authorize_other_ddl_or_data_reset(operation):
    from test_statistics_backup import expanded_schema_fixture
    from oracle_spa.schema import init_schema,reset_data,RESET_CONFIRMATION
    c,_=expanded_schema_fixture()
    with pytest.raises(DiagnosticError):
        if operation=='init':init_schema(c)
        else:reset_data(c,RESET_CONFIRMATION)
    assert all(call.args[0].startswith('SELECT ') for call in c.cursor.return_value.__enter__.return_value.execute.call_args_list)
    assert not c.commit.called

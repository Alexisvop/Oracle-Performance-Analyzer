"""Fail-closed, separately authorized ORDERS statistics backup operations.

No entry point runs on import. A creation receipt is NOT a structure approval.
Oracle's private stattab layout is observed, never guessed or edited.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
import os
from pathlib import Path

from oracle_spa.db import DiagnosticError
from oracle_spa.schema import assert_identity, inspect_schema

BACKUP = 'OSPA_ORDERS_STATS_BAK'
STATID = 'B_ORIGINAL_V1'
CREATE_SQL = """BEGIN DBMS_STATS.CREATE_STAT_TABLE(
 ownname=>'ORACLE_SPA', stattab=>'OSPA_ORDERS_STATS_BAK',
 tblspace=>'USERS', global_temporary=>FALSE); END;"""
EXPORT_SQL = """BEGIN DBMS_STATS.EXPORT_TABLE_STATS(
 ownname=>'ORACLE_SPA', tabname=>'ORDERS', partname=>NULL,
 stattab=>'OSPA_ORDERS_STATS_BAK', statid=>'B_ORIGINAL_V1',
 cascade=>TRUE, statown=>'ORACLE_SPA', stat_category=>'OBJECT_STATS'); END;"""
IMPORT_SQL = """BEGIN DBMS_STATS.IMPORT_TABLE_STATS(
 ownname=>'ORACLE_SPA', tabname=>'ORDERS', partname=>NULL,
 stattab=>'OSPA_ORDERS_STATS_BAK', statid=>'B_ORIGINAL_V1',
 cascade=>TRUE, statown=>'ORACLE_SPA', no_invalidate=>FALSE,
 force=>FALSE, stat_category=>'OBJECT_STATS'); END;"""
DIFF_SQL = """SELECT report,maxdiffpct FROM TABLE(DBMS_STATS.DIFF_TABLE_STATS_IN_STATTAB(
 ownname=>'ORACLE_SPA', tabname=>'ORDERS', stattab1=>'OSPA_ORDERS_STATS_BAK',
 stattab2=>NULL, pctthreshold=>0, statid1=>'B_ORIGINAL_V1', stattab1own=>'ORACLE_SPA'))"""
OPERATIONS = {'create': CREATE_SQL, 'export': EXPORT_SQL,
              'import-rehearsal': IMPORT_SQL, 'import-recovery': IMPORT_SQL}
QUERIES = {
 'table': "SELECT * FROM user_tab_statistics WHERE table_name='ORDERS' AND object_type='TABLE' ORDER BY table_name",
 'columns': "SELECT * FROM user_tab_col_statistics WHERE table_name='ORDERS' ORDER BY column_name",
 'histograms': "SELECT * FROM user_tab_histograms WHERE table_name='ORDERS' ORDER BY column_name,endpoint_number",
 'indexes': "SELECT * FROM user_ind_statistics WHERE table_name='ORDERS' ORDER BY index_name,partition_name,subpartition_name",
 'explicit_preferences': "SELECT * FROM user_tab_stat_prefs WHERE table_name='ORDERS' ORDER BY preference_name",
}
PREFERENCES = ('PUBLISH', 'PREFERENCE_OVERRIDES_PARAMETER', 'METHOD_OPT', 'CASCADE',
               'ESTIMATE_PERCENT', 'DEGREE', 'NO_INVALIDATE', 'INCREMENTAL', 'GRANULARITY')


def value(v):
    if isinstance(v, Decimal): return {'oracle_number': str(v)}
    if isinstance(v, bytes): return {'raw_hex': v.hex().upper()}
    if isinstance(v, datetime): return {'datetime': v.isoformat()}
    if hasattr(v, 'read'): return value(v.read())
    return v


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def digest(obj):
    return sha256(canonical(obj).encode()).hexdigest()


def query(connection, sql, **binds):
    try:
        with connection.cursor() as cur:
            cur.execute(sql, binds, fetch_decimals=True)
            return {'columns': [d[0] for d in cur.description],
                    'rows': [[value(v) for v in row] for row in cur.fetchall()]}
    except Exception as exc:
        from oracle_spa.plans import safe_code
        raise InspectionError(safe_code(exc)) from None


class InspectionError(DiagnosticError):
    """Safe code only; never retain or display the driver's raw message."""
    def __init__(self, code):
        self.code = code
        super().__init__('Read-only inspection failed: ' + code)


def exact_statistics(connection):
    """Identical serialization and query ordering to the published original snapshot."""
    assert_identity(connection)
    return {key: query(connection, sql) for key, sql in QUERIES.items()}


def differences(before, after, path=''):
    """Field-level differences, including dates/provenance; never use a tolerance."""
    if isinstance(before, dict) and isinstance(after, dict):
        result = []
        for key in sorted(before.keys() | after.keys()):
            where = path + '/' + key
            if key not in before or key not in after:
                result.append(where)
            else:
                result.extend(differences(before[key], after[key], where))
        return result
    if isinstance(before, list) and isinstance(after, list) and len(before) == len(after):
        return [d for i, (a, b) in enumerate(zip(before, after))
                for d in differences(a, b, path + '/' + str(i))]
    return [] if type(before) is type(after) and before == after else [path or '/']


def restoration(original, observed):
    changed = differences(original['effective'], observed['effective'])
    return {'status': 'PASS' if not changed else 'FAIL', 'differences': changed,
            'before_sha256': digest(original['effective']),
            'after_sha256': digest(observed['effective']),
            'history_changed': original['history'] != observed['history']}


STRUCTURE_QUERIES = {
        'backup_table': "SELECT owner,table_name,tablespace_name,temporary,partitioned,iot_type,nested FROM all_tables WHERE owner=USER AND table_name='OSPA_ORDERS_STATS_BAK'",
        'columns': "SELECT column_name,column_id,data_type,data_type_owner,data_length,data_precision,data_scale,nullable,char_used,char_length,hidden_column,virtual_column,data_default FROM user_tab_cols WHERE table_name='OSPA_ORDERS_STATS_BAK' ORDER BY internal_column_id",
        'comments': "SELECT comments FROM user_tab_comments WHERE table_name='OSPA_ORDERS_STATS_BAK'",
        'constraints': "SELECT constraint_name,constraint_type,status,validated,search_condition_vc FROM user_constraints WHERE table_name='OSPA_ORDERS_STATS_BAK' ORDER BY constraint_name",
        'lob_links': "SELECT table_name,column_name,segment_name,index_name,tablespace_name,securefile,in_row,partitioned FROM user_lobs WHERE table_name='OSPA_ORDERS_STATS_BAK' ORDER BY column_name",
        'backup_index': "SELECT index_name,table_owner,table_name,tablespace_name,uniqueness,index_type,status,visibility,partitioned FROM user_indexes WHERE table_name='OSPA_ORDERS_STATS_BAK' ORDER BY index_name",
        'backup_index_columns': "SELECT index_name,column_name,column_position,descend FROM user_ind_columns WHERE table_name='OSPA_ORDERS_STATS_BAK' ORDER BY index_name,column_position",
        'new_objects': "SELECT object_name,object_type,status,object_id,created FROM user_objects WHERE object_name NOT IN ('CUSTOMERS','PRODUCTS','ORDERS','ORDER_ITEMS','OSPA_DATASET','CUSTOMERS_PK','PRODUCTS_PK','ORDERS_PK','ORDER_ITEMS_PK','OSPA_DATASET_PK') ORDER BY object_type,object_name",
    }


def expected_backup_columns():
    """Version-specific layout observed from Oracle 23.26.3, not a guessed stattab."""
    specs = [('STATID','VARCHAR2',128), ('TYPE','CHAR',1), ('VERSION','NUMBER',22), ('FLAGS','NUMBER',22)]
    specs += [(f'C{i}','VARCHAR2',128) for i in range(1,7)]
    specs += [(f'N{i}','NUMBER',22) for i in range(1,14)]
    specs += [('D1','DATE',7), ('T1','TIMESTAMP(6) WITH TIME ZONE',13)]
    specs += [(f'R{i}','RAW',1000) for i in range(1,4)]
    specs += [('CH1','VARCHAR2',1000), ('CL1','CLOB',4000), ('BL1','BLOB',4000)]
    number = lambda n: {'oracle_number': str(n)}
    return [[name,number(i),kind,None,number(size),None,number(6) if name=='T1' else None,
             'Y','B' if kind in ('VARCHAR2','CHAR') else None,
             number(size if kind in ('VARCHAR2','CHAR') else 0),'NO','NO',None]
            for i,(name,kind,size) in enumerate(specs,1)]


def observe_structure(connection):
    """Verify the six-object graph through dictionary relationships, never SYS_* names."""
    assert_identity(connection)
    result = {key: query(connection, sql) for key, sql in STRUCTURE_QUERIES.items()}
    own_table = query(connection,"SELECT table_name,tablespace_name,temporary,partitioned,iot_type,nested FROM user_tables WHERE table_name='OSPA_ORDERS_STATS_BAK'")
    if (result['backup_table']['rows'] != [['ORACLE_SPA',BACKUP,'USERS','N','NO',None,'NO']]
            or own_table['rows'] != [[BACKUP,'USERS','N','NO',None,'NO']]
            or result['columns']['rows'] != expected_backup_columns()
            or result['constraints']['rows'] or result['comments']['rows'] != [[None]]):
        raise DiagnosticError('Backup table layout differs from the observed Oracle contract.')
    links = result['lob_links']['rows']
    if (len(links)!=2 or [row[1] for row in links]!=['BL1','CL1']
            or any(row[0]!=BACKUP or row[4:]!=['USERS','YES','YES','NO'] for row in links)):
        raise DiagnosticError('Backup LOB relationships differ from the contract.')
    expected = {(BACKUP,'TABLE'), (BACKUP,'INDEX')}
    indexes = [[BACKUP,'ORACLE_SPA',BACKUP,'USERS','NONUNIQUE','NORMAL','VALID','VISIBLE','NO']]
    for _,_,segment,index,*_ in links:
        expected |= {(segment,'LOB'), (index,'INDEX')}
        indexes.append([index,'ORACLE_SPA',BACKUP,'USERS','UNIQUE','LOB','VALID','VISIBLE','NO'])
    objects = result['new_objects']['rows']
    if (len(expected)!=6 or len(objects)!=6 or {(r[0],r[1]) for r in objects}!=expected
            or any(r[2]!='VALID' or not r[4] for r in objects)
            or any(not isinstance(r[3],dict) or not r[3].get('oracle_number','').isdigit() or int(r[3]['oracle_number'])<=0 for r in objects)
            or len({canonical(r[3]) for r in objects})!=6
            or result['backup_index']['rows'] != sorted(indexes)):
        raise DiagnosticError('Unknown, replaced or invalid backup auxiliary objects.')
    columns = ['STATID','TYPE','C5','C1','C2','C3','C4','VERSION']
    if result['backup_index_columns']['rows'] != [[BACKUP,col,{'oracle_number':str(i)},'ASC'] for i,col in enumerate(columns,1)]:
        raise DiagnosticError('Normal backup index columns, order or positions differ.')
    return {'name': BACKUP, 'version': connection.version, 'structure': result}


@dataclass(frozen=True)
class BackupPermit:
    creation_receipt: dict
    reviewed_structure_sha256: str
    reviewed_provenance_sha256: str
    statistics_approval: str | None = None


def verify_structure(connection, permit):
    if not isinstance(permit, BackupPermit):
        raise DiagnosticError('A separately reviewed backup creation receipt is required.')
    receipt = permit.creation_receipt
    created = receipt.get('operation')=='create' and receipt.get('status')=='OBSERVED; REVIEW REQUIRED' and receipt.get('sql')==CREATE_SQL
    reconciled = (receipt.get('kind')=='forensic-reconciliation' and receipt.get('status')=='MATCHED; EXTERNAL APPROVAL PENDING'
                  and receipt.get('journal_validated') is True and receipt.get('original_stop_preserved') is True)
    if not (created or reconciled) or digest(receipt)!=permit.reviewed_provenance_sha256:
        raise DiagnosticError('Unrecognized backup provenance.')
    observed = observe_structure(connection)
    if (observed != receipt.get('backup')
            or digest(observed) != permit.reviewed_structure_sha256):
        raise DiagnosticError('Backup object ID, structure or version changed; no replacement allowed.')
    return observed


def statistics_approval(permit):
    """Independent approval of the backup, separate from each operation confirmation."""
    return 'APPROVE_STATISTICS_BACKUP/' + permit.reviewed_provenance_sha256 + '/' + permit.reviewed_structure_sha256


def reconcile_existing(connection, evidence_directory, *, reviewed_manifest_sha256):
    """Read-only reconciliation of the original STOP, not a historical CREATE receipt.

    The caller pins a previously reviewed manifest. This function cannot approve
    statistics operations; its proposed permit has statistics_approval=None.
    """
    try:
        return _reconcile_existing(connection,evidence_directory,reviewed_manifest_sha256)
    except (OSError,ValueError,KeyError,TypeError,IndexError):
        raise DiagnosticError('Original creation evidence is incomplete or malformed; reconciliation refused.') from None


def _reconcile_existing(connection, evidence_directory, reviewed_manifest_sha256):
    assert_identity(connection)
    root = Path(evidence_directory)
    manifest_bytes = (root/'manifest.json').read_bytes()
    if sha256(manifest_bytes).hexdigest() != reviewed_manifest_sha256:
        raise DiagnosticError('Original creation manifest differs from the reviewed evidence.')
    hashes = json.loads(manifest_bytes)['sha256']
    names = ('create-attempt.jsonl','plan.json','preflight.json','result.json',
             'observed-structure.json','observational-creation-receipt.json','executed.sql')
    contents = {}
    for name in names:
        content = (root/name).read_bytes()
        expected = hashes.get('docs/evidence/phase4/group-b-create-stat-table/' + name)
        if sha256(content).hexdigest() != expected:
            raise DiagnosticError('Original creation evidence was altered; reconciliation refused.')
        contents[name] = content
    entries = [json.loads(line) for line in contents['create-attempt.jsonl'].splitlines()]
    plan = json.loads(contents['plan.json'])
    original = json.loads(contents['preflight.json'])
    result = json.loads(contents['result.json'])
    recorded = json.loads(contents['observed-structure.json'])
    receipt = json.loads(contents['observational-creation-receipt.json'])
    base_plan = {k:v for k,v in plan.items() if k!='confirmation'}
    confirmation = 'ORACLE_SPA/FREEPDB1/create/' + digest(base_plan)
    if (len(entries)!=2 or entries[0]!={**plan,'status':'ATTEMPTED; OUTCOME UNKNOWN UNTIL VERIFIED'}
            or entries[1].get('status')!='STOP; POSSIBLE PARTIAL EFFECTS'
            or entries[1].get('operation')!='create' or plan.get('sql')!=CREATE_SQL
            or plan.get('operation')!='create' or plan.get('confirmation')!=confirmation
            or contents['executed.sql'].decode().strip()!=CREATE_SQL+'\n/'
            or result.get('status')!='STOP' or result.get('ddl_attempts')!=1 or result.get('module_invocations')!=1
            or original.get('status')!='PASS' or original['backup_objects']['rows']
            or receipt.get('status')!='OBSERVED CREATED; NOT ACCEPTED BY MODULE; EXTERNAL REVIEW REQUIRED'
            or receipt.get('observed_structural_sha256')!=digest(recorded)
            or receipt.get('new_objects')!=recorded['new_objects']
            or receipt.get('table_object_id')!=next(r[3] for r in recorded['new_objects']['rows'] if r[1]=='TABLE')
            or receipt.get('backup_rows')!=0 or receipt.get('column_count')!=31
            or plan.get('observed_sha256')!=plan.get('original_sha256')
            or plan.get('original_sha256')!=digest(original['original_observed']['effective'])):
        raise DiagnosticError('Original one-attempt CREATE journal/provenance is inconsistent.')
    observed = observe_structure(connection)
    if observed['structure']!=recorded:
        raise DiagnosticError('Existing backup IDs, creation dates or structure differ from the original observation.')
    rows = query(connection,'SELECT COUNT(*) FROM ORACLE_SPA.OSPA_ORDERS_STATS_BAK')['rows']
    if rows!=[[{'oracle_number':'0'}]]:
        raise DiagnosticError('Reconciliation requires the existing backup to be empty.')
    proof = {'kind':'forensic-reconciliation','status':'MATCHED; EXTERNAL APPROVAL PENDING',
             'journal_validated':True,'original_stop_preserved':True,'backup':observed,
             'original_manifest_sha256':reviewed_manifest_sha256,
             'original_journal_sha256':sha256(contents['create-attempt.jsonl']).hexdigest(),
             'original_journal':entries,'original_execution':'One attempt; PL/SQL completion acknowledgement not recorded.',
             'original_validation':'STOP preserved; not relabeled as successful CREATE.',
             'backup_rows':0,'external_approval':'PENDING'}
    # This transient permit authorizes only the requested read-only inspection.
    inspection = BackupPermit(proof,digest(observed),digest(proof))
    comparison = restoration(original['original_observed'],inspect_original(connection,inspection))
    if comparison['status']!='PASS':
        raise DiagnosticError('Original data, statistics, preferences or metadata changed.')
    proof['effective_state_comparison'] = comparison
    return {'reconciliation':proof,
            'permit_proposal':{'creation_receipt':proof,'reviewed_structure_sha256':digest(observed),
                               'reviewed_provenance_sha256':digest(proof),'statistics_approval':None},
            'external_approval':'PENDING; no EXPORT/IMPORT enabled'}



def effective_preferences(connection):
    return {name: query(connection,
            "SELECT DBMS_STATS.GET_PREFS(:pref,'ORACLE_SPA','ORDERS') FROM dual", pref=name)
            for name in PREFERENCES}

def inspect_original(connection, permit=None):
    from oracle_spa.validation import validate_data
    if inspect_schema(connection, backup_permit=permit) != 'ready':
        raise DiagnosticError('Complete laboratory schema required.')
    data = validate_data(connection, backup_permit=permit)
    if (data['profile'], data['seed']) != ('small', 20261016):
        raise DiagnosticError('Expected small/20261016.')
    prefs = effective_preferences(connection)
    return {'effective': {'statistics': exact_statistics(connection), 'preferences': prefs,
            'dataset': data, 'metadata': query(connection, 'SELECT * FROM ospa_dataset ORDER BY dataset_id'),
            'version': connection.version},
            'history': query(connection, "SELECT * FROM user_tab_stats_history WHERE table_name='ORDERS' ORDER BY stats_update_time")}


def backup_contents(connection):
    # Internal columns are opaque. Preserve duplicates and all values, independent of row order.
    result = query(connection, 'SELECT * FROM ORACLE_SPA.OSPA_ORDERS_STATS_BAK')
    result['rows'].sort(key=canonical)
    return result


def validate_backup(connection, permit, export_receipt):
    verify_structure(connection, permit)
    if (export_receipt.get('operation') != 'export' or export_receipt.get('status') != 'PASS'
            or export_receipt.get('sql') != EXPORT_SQL
            or export_receipt.get('structure_sha256') != permit.reviewed_structure_sha256
            or export_receipt.get('statid') != STATID):
        raise DiagnosticError('Incorrect backup receipt; import refused.')
    contents = backup_contents(connection)
    if not contents['rows'] or digest(contents) != export_receipt.get('contents_sha256'):
        raise DiagnosticError('Backup empty or changed; import refused.')
    return contents



def inspect_interfaces(connection):
    """Read installed signatures; documentation alone is not runtime compatibility."""
    assert_identity(connection)
    required = {
        'CREATE_STAT_TABLE': {'OWNNAME','STATTAB','TBLSPACE','GLOBAL_TEMPORARY'},
        'EXPORT_TABLE_STATS': {'OWNNAME','TABNAME','PARTNAME','STATTAB','STATID','CASCADE','STATOWN','STAT_CATEGORY'},
        'IMPORT_TABLE_STATS': {'OWNNAME','TABNAME','PARTNAME','STATTAB','STATID','CASCADE','STATOWN','STAT_CATEGORY','NO_INVALIDATE','FORCE'},
        'DIFF_TABLE_STATS_IN_STATTAB': {'OWNNAME','TABNAME','STATTAB1','STATTAB2','PCTTHRESHOLD','STATID1','STATTAB1OWN'},
        'GATHER_TABLE_STATS': {'OWNNAME','TABNAME','ESTIMATE_PERCENT','DEGREE','CASCADE','METHOD_OPT','NO_INVALIDATE'},
    }
    results = {}
    for name, names in required.items():
        found = query(connection, "SELECT argument_name,data_type,in_out,defaulted,position,overload FROM all_arguments WHERE owner='SYS' AND package_name='DBMS_STATS' AND object_name=:name ORDER BY overload,sequence", name=name)
        # Do not combine parameters from incompatible overloads.
        groups = {}
        for row in found['rows']:
            groups.setdefault(canonical(row[5]), set()).add(row[0])
        if not any(names <= group for group in groups.values()):
            raise DiagnosticError('Required DBMS_STATS signature unavailable; no mutation allowed.')
        results[name] = found
    return results

def prepare_operation(connection, operation, original, permit=None, export_receipt=None):
    """Read-only plan; exact approval string binds the operation to its observed state."""
    if operation not in OPERATIONS:
        raise DiagnosticError('Unknown statistics operation.')
    if operation != 'create' and (not isinstance(permit,BackupPermit) or permit.statistics_approval != statistics_approval(permit)):
        raise DiagnosticError('Independent external approval of the backup is required before EXPORT/IMPORT.')
    observed = inspect_original(connection, permit)
    inspect_interfaces(connection)
    if operation != 'import-recovery' and restoration(original, observed)['status'] != 'PASS':
        raise DiagnosticError('Original effective state differs; operation refused.')
    if operation == 'import-recovery':
        # Recovery may change only ORDERS statistics; data, preferences and engine stay fixed.
        for key in original['effective'].keys() - {'statistics'}:
            if original['effective'][key] != observed['effective'].get(key):
                raise DiagnosticError('Non-statistics controls changed; recovery requires manual review.')
    if operation == 'create' and permit is not None:
        raise DiagnosticError('Never replace or recreate a backup.')
    contents_hash = None
    if operation == 'export':
        verify_structure(connection, permit)
        if backup_contents(connection)['rows']:
            raise DiagnosticError('Never overwrite a populated backup.')
    if operation.startswith('import-'):
        validate_backup(connection, permit, export_receipt)
        if export_receipt.get('original_sha256') != digest(original['effective']):
            raise DiagnosticError('Backup belongs to a different original snapshot.')
        contents_hash = export_receipt['contents_sha256']
    plan = {'operation': operation, 'sql': OPERATIONS[operation],
            'original_sha256': digest(original['effective']),
            'observed_sha256': digest(observed['effective']),
            'structure_sha256': permit.reviewed_structure_sha256 if permit else None,
            'contents_sha256': contents_hash}
    return {**plan, 'confirmation': 'ORACLE_SPA/FREEPDB1/' + operation + '/' + digest(plan)}


def execute_operation(connection, plan, *, confirmation, original, journal,
                      permit=None, export_receipt=None):
    """One attempt per exclusive journal. No rollback claim or implicit retry/cleanup.

    Caller must establish an exclusive maintenance window before explicit approval.
    Keep the journal permanently, including interrupted/failed attempts.
    """
    if confirmation != plan.get('confirmation') or not confirmation:
        raise DiagnosticError('Specific operation approval is required.')
    current = prepare_operation(connection, plan.get('operation'), original, permit, export_receipt)
    if current != plan or connection.transaction_in_progress:
        raise DiagnosticError('Plan changed or transaction active; no mutation attempted.')
    # Exclusive creation and fsync precede the mutation. Never replace an attempt record.
    descriptor = os.open(journal,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(descriptor,'w',encoding='utf-8') as log:
        def record(event):
            log.write(canonical({'recorded_at_utc':datetime.now(timezone.utc).isoformat(),**event}) + '\n')
            log.flush(); os.fsync(log.fileno())
        record({'status': 'ATTEMPTED; OUTCOME UNKNOWN UNTIL VERIFIED', **plan})
        completed = False
        phase = 'PLSQL'
        try:
            with connection.cursor() as cur:
                cur.execute(plan['sql'])
                completed = True
                record({'status':'PLSQL COMPLETED','operation':plan['operation']})
            phase = 'POST_VALIDATION'
            operation = plan['operation']
            if operation == 'create':
                receipt = {**plan, 'status': 'OBSERVED; REVIEW REQUIRED',
                           'backup': observe_structure(connection),
                           'creation_ddl': query(connection, "SELECT DBMS_METADATA.GET_DDL('TABLE','OSPA_ORDERS_STATS_BAK',USER) FROM dual")}
                # Review the actual Oracle layout before any export/import.
                record({'status':'STRUCTURE OBSERVED','backup':receipt['backup']})
                review = BackupPermit(receipt, digest(receipt['backup']), digest(receipt))
                inspect_schema(connection, backup_permit=review)
                receipt['verification'] = restoration(original, inspect_original(connection, review))
                if receipt['verification']['status'] != 'PASS':
                    record(receipt)
                    raise DiagnosticError('State changed during creation; stop for review.')
            else:
                if operation == 'export':
                    connection.commit()
                    contents = backup_contents(connection)
                    diff = query(connection, DIFF_SQL)
                    if not contents['rows'] or len(diff['rows']) != 1 or diff['rows'][0][1] != {'oracle_number': '0'}:
                        raise DiagnosticError('Export comparison failed; retain backup and stop.')
                    receipt = {**plan, 'status': 'PASS', 'statid': STATID,
                               'contents_sha256': digest(contents), 'diff': diff}
                else:
                    receipt = dict(plan)
                if operation.startswith('import-'):
                    validate_backup(connection, permit, export_receipt)
                after = inspect_original(connection, permit)
                verified = restoration(original, after)
                receipt['verification'] = verified
                receipt['status'] = verified['status']
                if receipt['status'] != 'PASS':
                    record(receipt)
                    raise DiagnosticError('Effective statistics differ; recovery NOT VERIFIED. Stop.')
            record(receipt)
            return receipt
        except BaseException as exc:
            from oracle_spa.plans import safe_code
            outcome = ('INTERRUPTED; OUTCOME NOT VERIFIED' if not isinstance(exc,Exception)
                       else 'DICTIONARY INSPECTION ERROR' if isinstance(exc,InspectionError)
                       else 'POST_VALIDATION_FAILED' if completed else 'PLSQL ERROR')
            code = exc.code if isinstance(exc,InspectionError) else safe_code(exc)
            record({'status': 'STOP; POSSIBLE PARTIAL EFFECTS', 'outcome':outcome,
                    'phase':phase,'plsql_completed':completed,'code':code,'operation': plan['operation'],
                    'next': 'Read-only inspection; preserve backup and journal; request new specific approval.'})
            if not isinstance(exc,Exception):
                raise
            raise DiagnosticError('Statistics operation stopped; possible partial effects. No retry or cleanup performed.') from None

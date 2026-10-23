"""One functional execution, streaming correctness checks, no benchmark loop."""
from contextlib import closing
from datetime import datetime,timezone
from decimal import Decimal
from hashlib import sha256
from itertools import zip_longest
import json
import sqlite3
import tempfile
from oracle_spa.db import DiagnosticError
from oracle_spa.data_generator import canonical
from oracle_spa.schema import inspect_schema
from oracle_spa.validation import read_manifest,validate_data
from oracle_spa.queries import get_query,sql_for,binds_for,choose_binds,expected_rows,validate_binds

def json_value(value):
    if isinstance(value,datetime):return value.isoformat(timespec='seconds')
    if isinstance(value,Decimal):return str(value)
    raise TypeError('Unsupported evidence value')

def compare_results(actual,expected,ordered=True):
    digest=sha256();count=0
    if ordered:
        sentinel=object()
        for a,b in zip_longest(actual,expected,fillvalue=sentinel):
            if a is sentinel or b is sentinel or canonical(a)!=canonical(b):raise DiagnosticError('Query rows or ordering differ from independent expectation.')
            digest.update((canonical(a)+'\n').encode());count+=1
    else:
        # Disk-backed multiset preserves duplicates without retaining all rows in RAM.
        with tempfile.TemporaryDirectory(prefix='ospa-results-') as directory:
            with closing(sqlite3.connect(directory+'/rows.sqlite')) as db:
                db.execute('CREATE TABLE counts (row TEXT PRIMARY KEY, balance INTEGER, actual_count INTEGER)')
                for rows,delta in ((actual,1),(expected,-1)):
                    for row in rows:
                        db.execute('INSERT INTO counts VALUES (?,?,?) ON CONFLICT(row) DO UPDATE SET balance=balance+excluded.balance, actual_count=actual_count+excluded.actual_count',(canonical(row),delta,int(delta==1)))
                        if delta==1:count+=1
                if db.execute('SELECT 1 FROM counts WHERE balance<>0 LIMIT 1').fetchone():raise DiagnosticError('Query result multiset differs; duplicates are significant.')
                # Hash sorted rows with actual multiplicities after exact balance validation.
                for row,multiplicity in db.execute('SELECT row,actual_count FROM counts ORDER BY row'):
                    digest.update((row+'\t'+str(multiplicity)+'\n').encode())
        # Include total row count in the fingerprint.
        digest.update(str(count).encode())
    return {'rows':count,'result_sha256':digest.hexdigest(),'comparison':'ordered full rows' if ordered else 'exact multiset including duplicates'}

def prepare(connection, allowed_indexes=(), *, backup_permit=None):
    connection.rollback()
    with connection.cursor() as cur:cur.execute('SET TRANSACTION READ ONLY')
    options = {'backup_permit': backup_permit} if backup_permit is not None else {}
    if inspect_schema(connection, allowed_indexes, **options)!='ready':raise DiagnosticError('Expected known Phase 2 schema.')
    dataset,manifest=read_manifest(connection)
    if (dataset.profile,dataset.seed)!=('small',20261016):raise DiagnosticError('Phase 3 baseline requires small/20261016; no data changed.')
    validation=validate_data(connection, allowed_indexes=allowed_indexes, **options)
    selected,observed=choose_binds(connection,dataset)
    with connection.cursor() as cur:
        cur.execute("SELECT table_name,num_rows,TO_CHAR(last_analyzed,'YYYY-MM-DD HH24:MI:SS'),stale_stats FROM user_tab_statistics WHERE object_type='TABLE' ORDER BY table_name")
        stats=cur.fetchall()
        for table,rows,analyzed,stale in stats:
            if table in validation['counts'] and (rows!=validation['counts'][table] or not analyzed or stale!='NO'):
                raise DiagnosticError('Business-table statistics require review; no automatic collection.')
        cur.execute('SELECT index_name,table_name,uniqueness FROM user_indexes ORDER BY index_name');indexes=cur.fetchall()
        cur.execute("SELECT table_name,column_name,num_distinct,histogram,num_buckets FROM user_tab_col_statistics ORDER BY table_name,column_name");column_stats=cur.fetchall()
    extra = {}
    if backup_permit is not None:
        from oracle_spa.statistics_backup import exact_statistics, effective_preferences
        extra['orders_statistics_exact'] = exact_statistics(connection)
        extra['orders_effective_preferences'] = effective_preferences(connection)
    return dataset, {**extra, 'profile':dataset.profile,'seed':dataset.seed,'manifest':manifest,'statistics':stats,'column_statistics':column_stats,'indexes':indexes,'bind_observations':observed,'selected':selected,'oracle_version':connection.version,'identity':['ORACLE_SPA','FREEPDB1','ORACLE_SPA'],'baseline':'without experimental indexes' if not allowed_indexes else 'authorized experimental index scenario','authorized_indexes':list(allowed_indexes), **({'backup_permit': {'creation_receipt': backup_permit.creation_receipt, 'reviewed_structure_sha256': backup_permit.reviewed_structure_sha256, 'reviewed_provenance_sha256': backup_permit.reviewed_provenance_sha256}} if backup_permit is not None else {})}

def run_query(connection,query_id,variant='baseline',context=None,instrument=False):
    q=get_query(query_id,variant)
    if context is not None and inspect_context_schema(connection, context[1])!='ready':
        raise DiagnosticError('Reused context requires the verified laboratory schema.')
    dataset,metadata=prepare(connection) if context is None else context
    binds=binds_for(query_id,variant,metadata['selected']);validate_binds(query_id,variant,binds)
    sql=sql_for(query_id,variant)
    if instrument:
        from uuid import uuid4
        sql=sql.replace('SELECT ', 'SELECT /*+ gather_plan_statistics */ /* OSPA_'+uuid4().hex+' */ ',1)
    import oracledb
    with connection.cursor() as cur:
        cur.arraysize=500
        cur.execute(sql,binds,fetch_decimals=True)
        types={'number':oracledb.DB_TYPE_NUMBER,'text':oracledb.DB_TYPE_VARCHAR,'date':oracledb.DB_TYPE_DATE}
        if len(cur.description)!=len(q.columns) or any(col[1]!=types[kind] for col,kind in zip(cur.description,q.columns)):
            raise DiagnosticError('Query column count or Oracle types differ from contract.')
        def rows():
            while batch:=cur.fetchmany(500):
                for row in batch:
                    if len(row)!=len(q.columns):raise DiagnosticError('Invalid result shape.')
                    yield row
        result=compare_results(rows(),expected_rows(query_id,binds,dataset),q.ordered)
    if not result['rows']:raise DiagnosticError('Selected baseline unexpectedly returned no rows.')
    return {'query_id':query_id,'variant':variant,'sql_version':1,'sql':sql,'sql_sha256':sha256(sql.encode()).hexdigest(),'binds':binds,'timestamp_utc':datetime.now(timezone.utc).isoformat(),'context':metadata,'result':result,'status':'PASS'}


def inspect_context_schema(connection, metadata):
    options = {}
    if 'backup_permit' in metadata:
        from oracle_spa.statistics_backup import BackupPermit
        options['backup_permit'] = BackupPermit(**metadata['backup_permit'])
    return inspect_schema(connection, metadata.get('authorized_indexes', ()), **options)

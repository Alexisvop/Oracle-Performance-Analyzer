"""Estimated plan capture with existing Oracle session-private PLAN_TABLE only."""
from hashlib import sha256
from datetime import datetime, timezone
import re
from uuid import uuid4
from oracle_spa.db import DiagnosticError
from oracle_spa.queries import sql_for,binds_for
from oracle_spa.execution import prepare, inspect_context_schema
from oracle_spa.schema import assert_identity, inspect_schema

CURSOR_VIEWS=('V$SQL','V$SQL_PLAN','V$SESSION','V$SQL_PLAN_STATISTICS_ALL')

def new_statement_id():
    return 'OSPA_'+uuid4().hex[:25]

def safe_code(exc):
    code=getattr(exc.args[0],'full_code','') if exc.args else ''
    return code if re.fullmatch(r'(?:ORA|DPY)-\d+',code) else 'NOT AVAILABLE'

def cursor_availability(connection):
    import oracledb
    result={}
    with connection.cursor() as cur:
        for name in CURSOR_VIEWS:
            try:cur.execute('SELECT 1 FROM '+name+' WHERE 1=0');result[name]='accessible'
            except oracledb.Error as exc:result[name]=safe_code(exc)
    return result

def parse_display(lines):
    text='\n'.join(lines)
    found=re.search(r'Plan hash value:\s*(\d+)',text)
    return {'plan_hash':int(found.group(1)) if found else None,'display':lines,'warnings':[line for line in lines if re.search(r'warning|dynamic statistics|adaptive|could not|error|note',line,re.I)]}

def inspect_plan_table(connection):
    with connection.cursor() as cur:
        cur.execute("SELECT object_name FROM user_objects WHERE object_name='PLAN_TABLE'")
        if cur.fetchone():raise DiagnosticError('Local PLAN_TABLE requires explicit review; no objects created.')
        cur.execute("SELECT table_owner,table_name FROM all_synonyms WHERE owner='PUBLIC' AND synonym_name='PLAN_TABLE'")
        if cur.fetchone()!=('SYS','PLAN_TABLE$'):raise DiagnosticError('Expected Oracle public PLAN_TABLE synonym; request review before creating any object.')
        cur.execute("SELECT temporary,duration FROM all_tables WHERE owner='SYS' AND table_name='PLAN_TABLE$'")
        if cur.fetchone()!=('Y','SYS$SESSION'):raise DiagnosticError('PLAN_TABLE storage is not verified session-private.')
        cur.execute('SELECT statement_id FROM PLAN_TABLE WHERE 1=0')

def explain_query(connection,query_id,variant='baseline',context=None):
    if context is not None and inspect_context_schema(connection, context[1])!='ready':
        raise DiagnosticError('Reused context requires the verified laboratory schema.')
    dataset,metadata=prepare(connection) if context is None else context
    sql=sql_for(query_id,variant);binds=binds_for(query_id,variant,metadata['selected'])
    access=cursor_availability(connection)
    result={'timestamp_utc':datetime.now(timezone.utc).isoformat(),'query_id':query_id,'variant':variant,'sql':sql,'sql_sha256':sha256(sql.encode()).hexdigest(),'binds':binds,'context':metadata,'type':'ESTIMATED_PLAN','cursor_plan':{'type':'NOT AVAILABLE','access':access,'reason':'Required fixed views inaccessible; no grants applied.','operator_metrics':'NOT AVAILABLE'}}
    import oracledb
    connection.rollback()  # End read-only snapshot before temporary plan DML.
    try:
        inspect_plan_table(connection)
        statement_id=new_statement_id()
        result['statement_id']=statement_id
        with connection.cursor() as cur:
            # Only generated hex ID and closed catalog SQL enter this statement.
            cur.execute("EXPLAIN PLAN SET STATEMENT_ID = '"+statement_id+"' FOR "+sql,binds)
            cur.execute("SELECT plan_table_output FROM TABLE(DBMS_XPLAN.DISPLAY('PLAN_TABLE',:sid,'TYPICAL +PREDICATE +ALIAS +NOTE'))",sid=statement_id)
            result.update(parse_display([row[0] for row in cur]))
            cur.execute('SELECT id,parent_id,operation,options,object_owner,object_name,cardinality,cost,access_predicates,filter_predicates FROM PLAN_TABLE WHERE statement_id=:sid ORDER BY id',sid=statement_id)
            names=('id','parent_id','operation','options','owner','object','estimated_rows','optimizer_cost','access_predicates','filter_predicates')
            result['operators']=[dict(zip(names,row)) for row in cur]
        if not result['operators'] or result['plan_hash'] is None:raise DiagnosticError('Estimated plan capture incomplete; no fabricated fallback.')
        result['status']='PASS'
        result['limitations']=['Compilation estimate, not executed cursor statistics. Bind values recorded but EXPLAIN PLAN does not prove bind peeking.','Cost is not milliseconds; A-Rows/Starts/Buffers/Reads not observed.','PLAN_TABLE rows are session-private temporary DML, rolled back; no objects created.']
    except (oracledb.Error,DiagnosticError) as exc:
        result.update(type='NOT AVAILABLE',status='NOT VERIFIED',reason=safe_code(exc) if isinstance(exc,oracledb.Error) else str(exc))
    finally:connection.rollback()
    result['cursor_plan']=actual_cursor_plan(connection,query_id,variant,(dataset,metadata))
    return result

def verify_cursor_identity(rows,sql):
    if len(rows)!=1:raise DiagnosticError('Cursor association is absent or ambiguous.')
    sql_id,child,text=rows[0]
    if hasattr(text,'read'):text=text.read()
    if text!=sql or not re.fullmatch('[0-9a-z]{13}',sql_id) or type(child) is not int or child<0:
        raise DiagnosticError('Cursor SQL text or child identity mismatch.')
    return sql_id,child

def actual_cursor_plan(connection,query_id,variant='baseline',context=None):
    from oracle_spa.execution import run_query
    assert_identity(connection)
    access=cursor_availability(connection)
    if any(v!='accessible' for v in access.values()):
        return {'type':'NOT AVAILABLE','status':'NOT VERIFIED','access':access,'reason':'Required fixed views inaccessible; no grants applied.','operator_metrics':'NOT AVAILABLE'}
    import oracledb
    try:
        executed=run_query(connection,query_id,variant,context,instrument=True)
        with connection.cursor() as cur:
            cur.execute("SELECT sql_id,child_number,sql_fulltext FROM v$sql WHERE sql_text=:sql AND parsing_schema_name=USER AND executions>0",sql=executed['sql'])
            sql_id,child=verify_cursor_identity(cur.fetchall(),executed['sql'])
            cur.execute("SELECT plan_table_output FROM TABLE(DBMS_XPLAN.DISPLAY_CURSOR(:sid,:child,'ALLSTATS LAST +PREDICATE'))",sid=sql_id,child=child)
            display=parse_display([r[0] for r in cur])
            if display['plan_hash'] is None:raise DiagnosticError('Cursor plan not returned.')
            header=re.search(r'SQL_ID\s+([0-9a-z]{13}),\s*child number\s+(\d+)', '\n'.join(display['display']))
            if not header or (header.group(1),int(header.group(2)))!=(sql_id,child):
                raise DiagnosticError('Displayed cursor identity differs from the executed SQL.')
            cur.execute('SELECT id,operation,options,last_starts,last_output_rows,last_cr_buffer_gets,last_cu_buffer_gets,last_disk_reads,plan_hash_value FROM v$sql_plan_statistics_all WHERE sql_id=:sid AND child_number=:child ORDER BY id',sid=sql_id,child=child)
            names=('id','operation','options','starts','actual_rows','consistent_gets','current_gets','physical_reads','plan_hash')
            operators=[dict(zip(names,r)) for r in cur]
        if any(row['plan_hash']!=display['plan_hash'] for row in operators):
            raise DiagnosticError('Cursor statistics plan hash differs from displayed plan.')
        availability=metric_availability(operators)
        return {'type':'ACTUAL_CURSOR_PLAN','status':'PASS','sql_id':sql_id,'child_number':child,'executed':executed,**display,'operators':operators,'metric_availability':availability,'metrics_status':'OBSERVED' if all(v=='OBSERVED' for v in availability.values()) else 'NOT VERIFIED'}
    except (oracledb.Error,DiagnosticError) as exc:
        return {'type':'NOT AVAILABLE','status':'NOT VERIFIED','reason':safe_code(exc) if isinstance(exc,oracledb.Error) else str(exc)}


def metric_availability(operators):
    result = {}
    for metric in ('starts','actual_rows','consistent_gets','current_gets','physical_reads'):
        values = [row.get(metric) for row in operators]
        result[metric] = ('NOT AVAILABLE' if not values or all(v is None for v in values)
                          else 'NOT VERIFIED' if any(v is None for v in values) else 'OBSERVED')
    return result

"""Bounded small-dataset, full-fetch client latency. No index/statistics mutations."""
from datetime import datetime, timezone
from hashlib import sha256
import platform
from pathlib import Path
import random
import subprocess
import time
from uuid import uuid4
from oracle_spa.db import DiagnosticError
from oracle_spa.execution import prepare, run_query, compare_results
from oracle_spa.queries import get_query, sql_for, binds_for, expected_rows
from oracle_spa.plans import explain_query, safe_code
from oracle_spa.experiments import get_experiment, Experiment

FETCH_SIZE = 500
MAX_ROWS = 30000


def schedule(variants, warmups=5, repeats=10, order_seed=20261016):
    if type(warmups) is not int or not 0 <= warmups <= 100 or type(repeats) is not int or not 1 <= repeats <= 100:
        raise DiagnosticError('Warmups must be 0..100 and repeats 1..100.')
    if type(order_seed) is not int or not 0 <= order_seed <= 2**63-1:
        raise DiagnosticError('Order seed must be a nonnegative 63-bit integer.')
    rng=random.Random(order_seed)
    for warmup, count in ((True,warmups),(False,repeats)):
        for repetition in range(1,count+1):
            order=list(variants)
            rng.shuffle(order)
            for variant in order:
                yield warmup,repetition,variant


def timed_fetch(cursor, sql, binds, clock=None):
    """Cursor/arraysize configured by caller. Timing stops before any validation."""
    clock=clock or time.perf_counter_ns
    rows=[]
    start=clock()
    try:
        cursor.execute(sql,binds,fetch_decimals=True)
        while batch:=cursor.fetchmany(FETCH_SIZE):
            rows.extend(batch)
            if len(rows)>MAX_ROWS:
                raise DiagnosticError('Bounded small-profile result limit exceeded.')
    finally:
        elapsed=(clock()-start)/1_000_000
    return rows,elapsed


def session_settings(connection):
    with connection.cursor() as cur:
        cur.execute("SELECT parameter,value FROM nls_session_parameters ORDER BY parameter")
        nls=cur.fetchall()
        cur.execute("SELECT SESSIONTIMEZONE,DBTIMEZONE FROM dual")
        zone=cur.fetchone()
    return {'nls':nls,'timezones':zone,'transaction_mode':'SET TRANSACTION READ ONLY explicitly executed','arraysize':FETCH_SIZE,
            'prefetchrows':2,'call_timeout_ms':connection.call_timeout,
            'optimizer_session_parameters':'NOT AVAILABLE without additional privileges; no parameters changed'}


def environment():
    import oracledb
    def command(args):
        try:
            result=subprocess.run(args,capture_output=True,text=True,timeout=5,check=True)
            return result.stdout.strip()
        except (OSError,subprocess.SubprocessError):return None
    commit=command(['git','rev-parse','HEAD'])
    dirty=command(['git','status','--porcelain'])
    # Only immutable digest from the associated image; never inspect container environment.
    image_id=command(['podman','inspect','oracle-spa','--format','{{.Image}}'])
    digest=command(['podman','image','inspect',image_id,'--format','{{.Digest}}']) if image_id else None
    from oracle_spa.data_generator import ROOT
    sources=sorted((ROOT/'src/oracle_spa').glob('*.py'))+sorted((ROOT/'config').glob('*.json'))+sorted((ROOT/'sql/queries').glob('*.sql'))
    source_hashes={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in sources}
    return {'source_sha256':source_hashes,'git_commit':commit,'git_dirty':bool(dirty) if dirty is not None else None,
            'python_version':platform.python_version(),'driver_version':oracledb.__version__,
            'oracle_image_digest':digest,'clock_resolution_seconds':time.get_clock_info('perf_counter').resolution}


def run_benchmark(connection, experiment_name, scenario='baseline', warmups=5, repeats=10,
                  order_seed=20261016, query_variant=None, sink=None, query_id=None, *, backup_permit=None):
    if query_id is not None:
        get_query(query_id,query_variant or "baseline")
        if scenario != "baseline":raise DiagnosticError("Single-query measurements require baseline indexes.")
        experiment=Experiment("QUERY",query_id,(query_variant or "baseline",),{"baseline":()},True,"Single-query measurement")
    else:
        experiment=get_experiment(experiment_name,scenario)
    variants=experiment.variants if query_variant is None else (query_variant,)
    if any(v not in experiment.variants for v in variants):
        raise DiagnosticError('Variant is not registered for this experiment.')
    order=list(schedule(variants,warmups,repeats,order_seed))
    allowed=experiment.scenarios[scenario]
    options = {'backup_permit': backup_permit} if backup_permit is not None else {}
    context=prepare(connection,allowed, **options)
    dataset,metadata=context
    run={'run_id':uuid4().hex,'timestamp_utc':datetime.now(timezone.utc).isoformat(),
         'experiment_id':experiment.id,'experiment':experiment_name,'scenario':scenario,
         'query_id':experiment.query,'equivalent':experiment.equivalent,'warmups':warmups,
         'repeats':repeats,'order_seed':order_seed,'context':metadata,'environment':environment(),
         'metric':'client query-only execute + full fetch (including Python row collection)',
         'environment_notes':['Warm-cache tendency, cache state not controlled.',
                              'One index state per run; DDL states are separate blocks, not per-repetition alternation.',
                              'No server CPU or actual operator counters inferred from client elapsed time.'],
         'status':'RUNNING','cases':{},'samples':[]}
    def save():
        if sink:sink(run)
    save()
    try:
        # Validate complete typed results and capture plans before warmups/timing.
        for variant in variants:
            checked=run_query(connection,experiment.query,variant,context)
            plan=explain_query(connection,experiment.query,variant,context)
            if plan['sql_sha256']!=checked['sql_sha256'] or plan['binds']!=checked['binds']:
                raise DiagnosticError('Plan SQL/binds do not match the measured query.')
            run['cases'][variant]={'validation':checked,'plan':plan}
        if experiment.equivalent and len(variants)>1:
            results=[case['validation']['result'] for case in run['cases'].values()]
            if any(r!=results[0] for r in results):
                raise DiagnosticError('Alternative results are not equivalent.')
        # Plans roll back temporary DML; begin one consistent read-only measurement snapshot.
        context=prepare(connection,allowed, **options)
        if context[1]!=metadata:
            raise DiagnosticError('Controls changed during preparation.')
        run['session']=session_settings(connection)
        import oracledb
        for sequence,(warmup,repetition,variant) in enumerate(order,1):
            q=get_query(experiment.query,variant)
            sql=sql_for(experiment.query,variant)
            binds=binds_for(experiment.query,variant,metadata['selected'])
            plan=run['cases'][variant]['plan']
            sample={key:run['environment'][key] for key in ('git_commit','oracle_image_digest','python_version','driver_version')}
            sample.update(run_id=run['run_id'],sample_id=f"{run['run_id']}-{sequence}",timestamp_utc=datetime.now(timezone.utc).isoformat(),
                          oracle_version=connection.version,dataset_profile=dataset.profile,seed=dataset.seed,
                          experiment_id=experiment.id,query_id=experiment.query,variant=variant,scenario=scenario,
                          sequence=sequence,repetition=repetition,warmup=warmup,elapsed_ms=None,returned_rows=None,
                          result_checksum=None,plan_hash_or_id=plan.get('plan_hash'),plan_capture_type=plan['type'],
                          sql_sha256=sha256(sql.encode()).hexdigest(),sql_error=None,status='FAIL',environment_notes=run['environment_notes'])
            try:
                with connection.cursor() as cur:
                    cur.arraysize=FETCH_SIZE;cur.prefetchrows=2
                    rows,elapsed=timed_fetch(cur,sql,binds)
                    sample['elapsed_ms']=elapsed
                    types={'number':oracledb.DB_TYPE_NUMBER,'text':oracledb.DB_TYPE_VARCHAR,'date':oracledb.DB_TYPE_DATE}
                    if len(cur.description)!=len(q.columns) or any(col[1]!=types[kind] for col,kind in zip(cur.description,q.columns)):
                        raise DiagnosticError('Measured Oracle result types differ.')
                result=compare_results(rows,expected_rows(experiment.query,binds,dataset),q.ordered)
                if result!=run['cases'][variant]['validation']['result']:
                    raise DiagnosticError('Measured result differs from prevalidated result.')
                sample.update(status='PASS',returned_rows=result['rows'],result_checksum=result['result_sha256'])
            except BaseException as exc:
                sample['sql_error']=safe_code(exc) if isinstance(exc,oracledb.Error) else 'RESULT_VALIDATION_FAILED' if isinstance(exc,DiagnosticError) else 'INTERRUPTED_OR_UNEXPECTED_ERROR'
                run['samples'].append(sample);save()
                # No repeated authentication or execution attempts after any failure.
                if not isinstance(exc,(oracledb.Error,DiagnosticError)):raise
                raise DiagnosticError('Benchmark failed; retained failed sample, no automatic retries.') from None
            run['samples'].append(sample);save()
        after=prepare(connection,allowed, **options)[1]
        if after!=metadata or session_settings(connection)!=run['session']:
            raise DiagnosticError('Dataset, statistics, indexes or session controls changed during measurement.')
        run['controls_unchanged']=True
        run['status']='PASS'
    except BaseException as exc:
        run['status']='FAIL';run['failure']='Execution/preparation/control check failed or interrupted; no retry.'
        run['error_code']=safe_code(exc)
        save()
        raise
    save()
    return run

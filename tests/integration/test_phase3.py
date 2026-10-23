"""Opt-in functional baseline; no grants, schema DDL, data loads or stats gathering."""
import json
import os
from pathlib import Path
import pytest
from oracle_spa.config import Config
from oracle_spa.db import laboratory_session
from oracle_spa.execution import prepare,run_query,json_value
from oracle_spa.plans import explain_query
from oracle_spa.queries import CATALOG,variants
from oracle_spa.validation import validate_data,read_manifest

pytestmark=[pytest.mark.oracle,pytest.mark.skipif(os.environ.get('OSPA_PHASE3_INTEGRATION')!='1',reason='Explicit Phase 3 Oracle opt-in required')]

def test_phase3_all_queries_plans_and_reconnection(backup_options):
    results=[]
    output=Path('docs/evidence/phase3') if os.environ.get('OSPA_WRITE_PHASE3_EVIDENCE')=='1' else None
    with laboratory_session(Config.from_env()) as c:
        context=prepare(c,**backup_options)
        with c.cursor() as cur:
            cur.execute("SELECT TO_CHAR(loaded_at,'YYYY-MM-DD HH24:MI:SS') FROM ospa_dataset");loaded_at=cur.fetchall()
        before=validate_data(c,**backup_options)
        for qid in CATALOG:
            for variant in variants(qid):
                run=run_query(c,qid,variant,context)
                with c.cursor() as cur:
                    cur.execute('SELECT COUNT(*) FROM PLAN_TABLE')
                    plan_rows_before=cur.fetchone()[0]
                plan=explain_query(c,qid,variant,context)
                actual=plan['cursor_plan']
                assert plan['status']=='PASS', plan.get('reason')
                assert plan['type']=='ESTIMATED_PLAN' and plan['operators'] and plan['plan_hash'] is not None
                assert (plan['sql'],plan['sql_sha256'],plan['binds'])==(run['sql'],run['sql_sha256'],run['binds'])
                with c.cursor() as cur:
                    cur.execute('SELECT COUNT(*) FROM PLAN_TABLE WHERE statement_id=:sid',sid=plan['statement_id'])
                    assert cur.fetchone()==(0,)
                    cur.execute('SELECT COUNT(*) FROM PLAN_TABLE')
                    assert cur.fetchone()==(plan_rows_before,)
                assert run['status']=='PASS' and run['result']['rows']>0
                if qid=='Q08':assert run['result']['rows']==20
                result={'run':run,'estimated_plan':plan,'cursor_plan':actual}
                results.append(result)
                if output:
                    output.mkdir(exist_ok=True,parents=True)
                    (output/(qid+'-'+variant+'.json')).write_text(json.dumps(result,indent=2,default=json_value)+'\n')
        q7=[r['run']['result'] for r in results if r['run']['query_id']=='Q07']
        assert q7[0]==q7[1]
    with laboratory_session(Config.from_env()) as c:
        context2=prepare(c,**backup_options)
        for result in results:
            run=result['run'];repeated=run_query(c,run['query_id'],run['variant'],context2)
            assert repeated['result']==run['result']
        assert validate_data(c,**backup_options)==before
        assert context2[1]['manifest']==context[1]['manifest']
        assert context2[1]['statistics']==context[1]['statistics']
        assert context2[1]['indexes']==context[1]['indexes']
        with c.cursor() as cur:
            cur.execute("SELECT TO_CHAR(loaded_at,'YYYY-MM-DD HH24:MI:SS') FROM ospa_dataset")
            assert cur.fetchall()==loaded_at
        if output:
            (output/'integration-summary.json').write_text(json.dumps({'status':'PASS','queries':8,'cases':len(results),'all_results_rechecked_after_reconnection':True,'unchanged':['dataset rows/checksums','manifest','loaded_at','schema/indexes','statistics'],'baseline':'without experimental indexes','estimated_plan_cases':sum(r['estimated_plan']['status']=='PASS' for r in results),'actual_cursor_cases':sum(r['cursor_plan']['type']=='ACTUAL_CURSOR_PLAN' for r in results)},indent=2)+'\n')

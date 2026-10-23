"""Opt-in baseline measurement only. Never creates indexes or gathers statistics."""
import json
import os
from pathlib import Path
import pytest
from oracle_spa.benchmark import run_benchmark
from oracle_spa.config import Config
from oracle_spa.db import laboratory_session
from oracle_spa.execution import prepare,json_value
from oracle_spa.report import write_run,render_report
from oracle_spa.schema import inspect_schema

pytestmark=[pytest.mark.oracle,pytest.mark.skipif(os.environ.get('OSPA_PHASE4_INTEGRATION')!='1',reason='Explicit non-destructive Phase 4 opt-in required')]


def test_phase4_baseline_measurement_plans_exports_and_invariance(tmp_path,backup_options):
    with laboratory_session(Config.from_env()) as c:
        before=prepare(c,**backup_options)[1]
        assert inspect_schema(c,**backup_options)=='ready'
        run=run_benchmark(c,'sargability',warmups=1,repeats=2,sink=lambda r:write_run(r,tmp_path),**backup_options)
        assert run['status']=='PASS' and run['controls_unchanged']
        assert len(run['samples'])==6
        assert sum(not s['warmup'] for s in run['samples'])==4
        assert len({s['result_checksum'] for s in run['samples']})==1
        assert all(s['status']=='PASS' and s['returned_rows']==113 and s['elapsed_ms']>=0 for s in run['samples'])
        for case in run['cases'].values():
            assert case['plan']['status']=='PASS'
            assert case['plan']['sql_sha256']==case['validation']['sql_sha256']
            assert case['plan']['binds']==case['validation']['binds']
        report=render_report(run['run_id'],tmp_path)
        assert report['comparisons'][0]['status']=='NOT COMPARABLE' # only two measured samples
        assert len((tmp_path/run['run_id']/'samples.csv').read_text().splitlines())==7
    with laboratory_session(Config.from_env()) as c:
        assert prepare(c,**backup_options)[1]==before
        assert inspect_schema(c,**backup_options)=='ready'
    if os.environ.get('OSPA_WRITE_PHASE4_EVIDENCE')=='1':
        write_run(run,Path('docs/evidence/phase4/integration'))
        render_report(run['run_id'],Path('docs/evidence/phase4/integration'))

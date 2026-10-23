"""Auditable raw JSON/CSV and descriptive Markdown/SVG reports, no credentials."""
import csv
import json
from pathlib import Path
import re
from oracle_spa.analysis import summarize, comparison
from oracle_spa.data_generator import ROOT
from oracle_spa.db import DiagnosticError
from oracle_spa.execution import json_value

RESULTS = ROOT / 'results' / 'phase4'


def run_directory(run_id, root=RESULTS):
    if not isinstance(run_id,str) or not re.fullmatch(r'[a-f0-9]{32}',run_id):
        raise DiagnosticError('Invalid run ID; expected 32 lowercase hex characters.')
    root=Path(root)
    path=root/run_id
    if root.is_symlink() or path.is_symlink():
        raise DiagnosticError('Result paths must not be symbolic links.')
    return path


def write_run(run, root=RESULTS):
    path=run_directory(run['run_id'],root)
    path.mkdir(parents=True,exist_ok=True)
    # Atomic snapshots preserve completed and failed samples across interruption.
    target=path/'run.json';temp=path/'run.json.tmp'
    if target.is_symlink() or temp.is_symlink():
        raise DiagnosticError('Result files must not be symbolic links.')
    with temp.open('w',encoding='utf-8') as stream:
        json.dump(run,stream,indent=2,default=json_value,allow_nan=False)
        stream.write('\n')
    temp.replace(target)
    return path


def _reject_nonfinite_constant(_token):
    raise DiagnosticError('Benchmark evidence must not contain NaN or Infinity constants.')


def _load_run_payload(source, expected_run_id):
    if source.is_symlink() or not source.is_file() or source.stat().st_size>30_000_000:
        raise DiagnosticError('Missing, unsafe or oversized benchmark evidence.')
    try:
        run=json.loads(source.read_text(encoding='utf-8'),parse_constant=_reject_nonfinite_constant)
    except DiagnosticError:
        raise
    except (OSError,UnicodeError,json.JSONDecodeError):
        raise DiagnosticError('Corrupted or invalid JSON in benchmark evidence.') from None
    required={'run_id','status','samples','cases','equivalent','experiment_id','scenario','metric','environment_notes'}
    if not isinstance(run,dict) or not required<=run.keys():
        raise DiagnosticError('Benchmark evidence is missing required schema fields.')
    if run['run_id']!=expected_run_id:
        raise DiagnosticError('Run identity differs from directory.')
    if (
        not isinstance(run['samples'],list)
        or not isinstance(run['cases'],dict)
        or not isinstance(run['environment_notes'],list)
        or not all(isinstance(s,dict) and {'variant','warmup','status','elapsed_ms'}<=s.keys() for s in run['samples'])
    ):
        raise DiagnosticError('Benchmark evidence contains invalid collection or sample structure.')
    return run


def render_report(run_id, root=RESULTS):
    path=run_directory(run_id,root)
    source=path/'run.json'
    run=_load_run_payload(source,run_id)
    summaries={v:summarize([s for s in run['samples'] if s['variant']==v]) for v in run['cases']}
    variants=list(summaries)
    comparisons=[]
    for v in variants[1:]:
        comparisons.append({'baseline':variants[0],'alternative':v,**comparison(summaries[variants[0]],summaries[v],
                           comparable=run['equivalent'],valid=run['status']=='PASS' and run.get('controls_unchanged',False))})
    result={'run_id':run_id,'status':run['status'],'summaries':summaries,'comparisons':comparisons,
            'scope':'One scenario only; no cross-index-state causal conclusion.',
            'failed_samples_retained':True,'percentile_method':'linear interpolation at (n-1)*p'}
    for name in ('summary.json','samples.csv','summary.md','latency.svg'):
        if (path/name).is_symlink():raise DiagnosticError('Unsafe report output path.')
    (path/'summary.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    fields=list(run['samples'][0]) if run['samples'] else ['run_id','status']
    with (path/'samples.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for sample in run['samples']:
            writer.writerow({k:json.dumps(v) if isinstance(v,(list,dict)) else v for k,v in sample.items()})
    lines=[f"# {run['experiment_id']} / {run['scenario']} — {run_id}", '',f"Status: {run['status']}. Metric: {run['metric']}.",
           '', '| Variant | n | failures | Median ms | IQR ms | p95 ms |', '| --- | ---: | ---: | ---: | ---: | ---: |']
    for variant,s in summaries.items():
        lines.append(f"| {variant} | {s['n']} | {s['failures']} | {s['median']} | {s['iqr']} | {s['p95']} |")
    lines += ['', 'Warmups excluded from summaries, retained in raw samples. No outliers removed.',
              'Comparisons are descriptive, not proof of causation. Different status cohorts are not equivalent answers.',
              'Only this index/statistics scenario is represented; other scenarios remain pending.',
              '', '```json', json.dumps(comparisons,indent=2), '```', '', '![Observed median and p95 client latency](latency.svg)',
              '', *run['environment_notes']]
    (path/'summary.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    plot_latency(run, summaries, path/'latency.svg')
    return result


def plot_latency(run, summaries, target):
    """Standalone scientific figure; lazy imports never enter query timing."""
    import os
    os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.local'/'matplotlib'))
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib import pyplot as plt
    observed=[(v,s) for v,s in summaries.items() if s['n']]
    with plt.rc_context({'svg.hashsalt':'ospa-phase4','svg.fonttype':'none'}):
        fig,ax=plt.subplots(figsize=(9,3+len(observed)*.3),layout='constrained')
        try:
            labels=[f"{v} (n={s['n']})" for v,s in observed]
            ax.barh(labels,[s['median'] for _,s in observed],label='Median',color='#246aaf')
            ax.scatter([s['p95'] for _,s in observed],labels,label='p95',marker='|',color='black',s=160)
            ax.set_xlabel('Client execute + full fetch latency (ms)')
            ax.set_title(f"{run['experiment_id']} / {run['scenario']} / {run['status']}\nsmall, seed 20261016; warmups excluded; uncontrolled warm cache")
            ax.set_xlim(left=0)
            ax.legend()
            fig.savefig(target,format='svg',metadata={'Date':None,'Creator':'OSPA Phase 4 / Matplotlib'})
        finally:
            plt.close(fig)


def render_phase5_bundle(output_dir=ROOT / 'results' / 'phase5', evidence_root=ROOT / 'docs' / 'evidence' / 'phase4'):
    """Offline Phase 5 Stage B report, CSV, SVG/PNG chart, and manifest generator."""
    from oracle_spa.phase5_report import render_phase5_bundle as _render_phase5_bundle
    return _render_phase5_bundle(output_dir=output_dir, evidence_root=evidence_root)

"""Phase 1 connectivity and Phase 2 guarded schema/data commands."""

import argparse
import json
import sys

from oracle_spa.config import Config, ConfigError
from oracle_spa.db import DiagnosticError, diagnose, laboratory_session


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Oracle SPA local laboratory")
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("doctor", "init-schema", "validate-data", "gather-stats"):
        commands.add_parser(command)
    commands.add_parser('list-queries', help='List closed read-only catalog; no database needed')
    for name in ('run','explain'):
        command=commands.add_parser(name, help='Functional query/plan, or measured run with --repeats/--warmups')
        command.add_argument('--query', required=True, choices=[f'Q{i:02d}' for i in range(1,9)])
        command.add_argument('--variant', default='baseline', help='baseline; Q06 also rare, Q07 also range. Binds selected from observed data.')
        if name == 'run':
            command.add_argument('--warmups', type=int)
            command.add_argument('--repeats', type=int)
            command.add_argument('--order-seed', type=int, default=20261016)
    from oracle_spa.experiments import EXPERIMENTS
    from oracle_spa.indexes import INDEXES
    compare = commands.add_parser('compare', help='Measure one existing scenario; never performs DDL')
    compare.add_argument('--experiment', choices=EXPERIMENTS, required=True)
    compare.add_argument('--profile', choices=['small'], default='small')
    compare.add_argument('--scenario', default='baseline')
    compare.add_argument('--warmups', type=int, default=5)
    compare.add_argument('--repeats', type=int, default=10)
    compare.add_argument('--order-seed', type=int, default=20261016)
    report = commands.add_parser('report', help='Render single Phase 4 run report offline')
    report.add_argument('--run-id', required=True)
    report_all = commands.add_parser(
        'report-all',
        help='Offline Phase 5 reproducible report, CSV, chart, and manifest generator; no Oracle connection needed',
    )
    report_all.add_argument(
        '--output',
        default='results/phase5',
        help='Safe output directory for generated Phase 5 artifacts (default: results/phase5)',
    )
    index = commands.add_parser('index-plan', help='Offline DDL simulation only; no connection or mutation')
    index.add_argument('--index', choices=INDEXES, required=True)
    index.add_argument('--action', choices=['create','drop'], required=True)
    load = commands.add_parser("load-data")
    load.add_argument("--profile", choices=("tiny", "small", "medium", "large"), default="tiny")
    load.add_argument("--seed", type=int)
    reset = commands.add_parser("reset-data", help="delete only rows in the verified laboratory tables")
    reset.add_argument("--confirm", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'index-plan':
            from oracle_spa.indexes import operation_plan
            print(json.dumps(operation_plan(args.action,args.index),indent=2))
            return 0
        if args.command == 'report':
            from oracle_spa.report import render_report
            print(json.dumps(render_report(args.run_id),indent=2))
            return 0
        if args.command == 'report-all':
            from oracle_spa.report import render_phase5_bundle
            print(json.dumps(render_phase5_bundle(output_dir=args.output),indent=2))
            return 0
        measured = args.command == 'compare' or (args.command == 'run' and (args.warmups is not None or args.repeats is not None))
        if measured:
            from oracle_spa.benchmark import run_benchmark, schedule
            from oracle_spa.report import write_run, render_report
            from oracle_spa.experiments import get_experiment
            from oracle_spa.queries import get_query
            warmups = args.warmups if args.warmups is not None else 5
            repeats = args.repeats if args.repeats is not None else 10
            list(schedule(('baseline',),warmups,repeats,args.order_seed))
            if args.command == 'compare':
                get_experiment(args.experiment,args.scenario)
                options={'experiment_name':args.experiment,'scenario':args.scenario}
            else:
                get_query(args.query,args.variant)
                options={'experiment_name':'single-query','query_id':args.query,'query_variant':args.variant}
            with laboratory_session(Config.from_env()) as connection:
                result=run_benchmark(connection,**options,warmups=warmups,repeats=repeats,order_seed=args.order_seed,sink=write_run)
            render_report(result['run_id'])
            print(json.dumps({'status':result['status'],'run_id':result['run_id'],'evidence':'results/phase4/'+result['run_id']},indent=2))
            return 0
        if args.command == 'list-queries':
            from dataclasses import asdict
            from oracle_spa.queries import CATALOG, variants
            print(json.dumps({key:asdict(q)|{'variants':variants(key),'observed_result':None,'bind_types':{b:('datetime (naive midnight for day)' if b in ('start_date','end_date','day') else 'positive int' if b=='customer_id' else 'str') for b in q.binds}} for key,q in CATALOG.items()},indent=2))
            return 0
        if args.command in ('run','explain'):
            from oracle_spa.queries import get_query
            get_query(args.query,args.variant)
            from oracle_spa.execution import run_query,json_value
            from oracle_spa.plans import explain_query
            with laboratory_session(Config.from_env()) as connection:
                result=(run_query if args.command=='run' else explain_query)(connection,args.query,args.variant)
                print(json.dumps(result,indent=2,default=json_value))
            return 0 if result['status']=='PASS' else 1
        config = Config.from_env()
        if args.command == "doctor":
            result = diagnose(config)
            print("PASS connection: python-oracledb Thin mode")
            print(f"PASS session: {result.user} in {result.pdb}")
            print(f"PASS SELECT 1 FROM dual: {result.probe}")
            print(f"PASS Oracle server version: {result.version}")
        else:
            from oracle_spa.schema import ALL_TABLES, init_schema, reset_data
            from oracle_spa.loader import load_data
            from oracle_spa.validation import validate_data
            from oracle_spa.stats import gather_stats
            if args.command == "reset-data":
                print("Affected ORACLE_SPA tables: " + ", ".join(ALL_TABLES))
            with laboratory_session(config) as connection:
                if args.command == "init-schema":
                    result = init_schema(connection)
                elif args.command == "load-data":
                    result = load_data(connection, args.profile, args.seed)
                elif args.command == "validate-data":
                    # One read-consistent snapshot across all validation queries.
                    connection.rollback()
                    with connection.cursor() as cursor:
                        cursor.execute("SET TRANSACTION READ ONLY")
                    result = validate_data(connection)
                elif args.command == "gather-stats":
                    result = gather_stats(connection)
                else:
                    result = reset_data(connection, args.confirm)
                print(json.dumps(result, indent=2))
    except ConfigError as exc:
        print(f"FAIL configuration: {exc}", file=sys.stderr)
        return 2
    except DiagnosticError as exc:
        print(f"FAIL {args.command}: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print(f"FAIL {args.command}: interrupted; inspect state before retrying DDL.", file=sys.stderr)
        return 130
    except Exception:
        print(f"FAIL {args.command}: unexpected error; inspect state without logging credentials.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

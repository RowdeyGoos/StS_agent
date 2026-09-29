"""Installed entry point for bounded reference-policy combat evaluation."""
import argparse
import json


def main(argv=None):
    parser = argparse.ArgumentParser(description='Measure random-legal and heuristic combat baselines.')
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--audit-dir', help='Disjoint owner-only private replay directory')
    parser.add_argument('--cases-per-scenario', type=int, default=4)
    parser.add_argument('--split', choices=('train', 'validation', 'test'), default='validation')
    parser.add_argument('--start-index', type=int, default=0)
    parser.add_argument('--encounter', action='append', dest='encounters')
    parser.add_argument('--max-decisions', type=int, default=256)
    parser.add_argument('--time-limit', type=float, default=30.0)
    parser.add_argument('--config', help='Validated combat training JSON (mode, scenario_set, reward)')
    parser.add_argument('--checkpoint', help='Frozen imitation or PPO bundle to compare with reference policies')
    parser.add_argument('--hybrid', action='store_true', help='Compare ordinary-HP campaigns with learned combat/heuristic routing')
    parser.add_argument('--full-run', action='store_true', help='Pair heuristic, combat hybrid and fully learned genuine campaigns')
    parser.add_argument('--act1', action='store_true', help='Stop at Act 1 completion and compare Act 1 clear rates')
    parser.add_argument('--combat-checkpoint', help='Frozen combat comparison bundle for --full-run')
    parser.add_argument('--reference-checkpoint', help='Frozen campaign initializer to compare with --checkpoint')
    parser.add_argument('--campaign-cases', type=int, default=2)
    parser.add_argument('--freeze-suite', metavar='CONFIG', help='Freeze benchmark settings, cases and private snapshots before tuning')
    parser.add_argument('--suite', help='Frozen suite.json for paired evaluation or checkpoint selection')
    parser.add_argument('--candidate', action='append', default=[], help='Named inference bundle: imitation=PATH or ppo_NAME=PATH')
    parser.add_argument('--select-development', help='Complete benchmark.json from development; write selection.json')
    parser.add_argument('--selection', help='Locked selection.json required for --suite with --split test')
    args = parser.parse_args(argv)
    try:
        from game.agent.training.evaluation import evaluate_baselines
    except ModuleNotFoundError as error:
        if error.name not in ('gymnasium', 'numpy'):
            raise
        parser.error("Combat evaluation requires the optional 'sts-agent[gym]' dependencies")
    try:
        from game.agent.training.config import TrainingConfig
        config = TrainingConfig.load(args.config) if args.config else TrainingConfig()
        if args.checkpoint or args.suite or args.freeze_suite:
            try:
                import torch
            except ModuleNotFoundError as error:
                if error.name != 'torch':
                    raise
                parser.error("Checkpoint evaluation requires the optional 'sts-agent[train]' dependencies")
            torch.set_num_threads(1)
        if args.full_run or args.act1:
            if (args.full_run and args.act1 or not args.checkpoint or
                    (args.combat_checkpoint is None)==(args.reference_checkpoint is None) or
                    args.hybrid or args.config or args.encounters or
                    args.suite or args.freeze_suite or args.candidate or args.selection or args.select_development or args.audit_dir):
                parser.error('Choose --act1 or --full-run, --checkpoint, and one --combat-checkpoint or --reference-checkpoint; omit combat-only/suite options')
            import signal
            import threading
            from game.agent.training.run_evaluation import evaluate_full_run
            stopped = threading.Event()
            previous = {sig:signal.getsignal(sig) for sig in (signal.SIGINT,signal.SIGTERM)}
            for sig in previous: signal.signal(sig,lambda *_:stopped.set())
            try:
                path, report = evaluate_full_run(checkpoint=args.checkpoint, combat_checkpoint=args.combat_checkpoint,
                    reference_checkpoint=args.reference_checkpoint, goal='act1' if args.act1 else 'full_run',
                    output_dir=args.output_dir, cases=args.campaign_cases, split=args.split, start_index=args.start_index,
                    max_decisions=args.max_decisions, time_limit_seconds=args.time_limit, cancel=stopped)
            finally:
                for sig, handler in previous.items(): signal.signal(sig,handler)
            print(json.dumps({'report':str(path), 'status':report['status'], 'summary':report['summary'],
                'paired_vs_heuristic':report['paired_vs_heuristic'],
                **({'paired_vs_reference':report['paired_vs_reference']} if 'paired_vs_reference' in report else {})},indent=2))
            return 130 if report['status']=='interrupted' else 0 if report['status']=='complete' else 1
        if args.combat_checkpoint or args.reference_checkpoint:
            parser.error('Campaign comparison checkpoints require --act1 or --full-run')
        if args.freeze_suite or args.suite:
            from pathlib import Path
            if (args.config or args.hybrid or args.checkpoint or args.encounters or args.start_index or
                    args.max_decisions!=256 or args.time_limit!=30 or args.cases_per_scenario!=4 or args.audit_dir):
                parser.error('Frozen benchmarks use their stored limits, populations and private directories')
            if args.freeze_suite:
                if args.suite or args.candidate or args.selection or args.select_development or args.split!='validation':
                    parser.error('Freeze the complete suite before evaluation or selection')
                from game.agent.training.benchmark_suite import BenchmarkConfig, freeze_suite
                path, report = freeze_suite(args.output_dir, BenchmarkConfig.load(args.freeze_suite))
                print(json.dumps({'suite':str(path),'cases':len(report['cases'])}))
                return 0
            from game.agent.training.benchmark import evaluate_benchmark, select_checkpoint
            if args.select_development:
                if args.candidate or args.selection or args.split!='validation':
                    parser.error('Selection accepts only a complete development report and its suite')
                path, report = select_checkpoint(args.suite,args.select_development,Path(args.output_dir)/'selection.json')
                print(json.dumps({'selection':str(path),'selected':report['selected']}))
                return 0
            checkpoints={}
            for value in args.candidate:
                name, sep, bundle=value.partition('=')
                if not sep or not bundle or name in checkpoints:
                    parser.error('Use distinct --candidate NAME=PATH arguments')
                checkpoints[name]=bundle
            import signal
            import threading
            stopped=threading.Event()
            previous={sig:signal.getsignal(sig) for sig in (signal.SIGINT,signal.SIGTERM)}
            for sig in previous:
                signal.signal(sig,lambda *_:stopped.set())
            try:
                path, report=evaluate_benchmark(suite_path=args.suite,output_dir=args.output_dir,
                    checkpoints=checkpoints,split=args.split,selection_path=args.selection,cancel=stopped)
            finally:
                for sig, handler in previous.items(): signal.signal(sig,handler)
            print(json.dumps({'report':str(path),'status':report['status'],'summary':report['summary'],
                              'primary_conclusion':report.get('primary_conclusion')},indent=2))
            return 130 if report['status']=='interrupted' else 0 if report['status']=='complete' else 1
        if args.candidate or args.select_development or args.selection:
            parser.error('Named candidates and selection require --suite')
        if args.hybrid:
            if not args.checkpoint or args.config or args.encounters:
                parser.error('--hybrid requires --checkpoint and uses its objective; omit --config/--encounter')
            from game.agent.training.hybrid import evaluate_hybrid
            path, report = evaluate_hybrid(checkpoint=args.checkpoint, output_dir=args.output_dir,
                cases=args.campaign_cases, split=args.split, start_index=args.start_index,
                max_decisions=args.max_decisions, time_limit_seconds=args.time_limit, audit_dir=args.audit_dir)
            print(json.dumps({'report':str(path), 'status':report['status'], 'episodes':report['episodes']}, indent=2))
            return 0 if report['status'] == 'complete' else 1
        path, report = evaluate_baselines(output_dir=args.output_dir, audit_dir=args.audit_dir,
            cases_per_scenario=args.cases_per_scenario, split=args.split, start_index=args.start_index,
            encounters=args.encounters, max_decisions=args.max_decisions, time_limit_seconds=args.time_limit,
            config=config, checkpoint=args.checkpoint)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(json.dumps({'report': str(path), 'status': report['status'], 'summary': report['summary']}, indent=2))
    return 0 if report['status'] == 'complete' else 1


if __name__ == '__main__':
    raise SystemExit(main())

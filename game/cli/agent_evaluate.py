"""Installed entry point for bounded reference-policy combat evaluation."""
import argparse
import json
from game.agent import performance


def main(argv=None):
    parser = argparse.ArgumentParser(description='Measure random-legal and heuristic combat baselines.')
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--audit-dir', help='Disjoint owner-only private replay directory')
    parser.add_argument('--cases-per-scenario', type=int, default=4)
    parser.add_argument('--split', choices=('train', 'validation', 'test'), default='validation')
    parser.add_argument('--start-index', type=int, default=0)
    parser.add_argument('--encounter', action='append', dest='encounters')
    parser.add_argument('--max-decisions', type=int, help='Default 1024 for search campaigns, otherwise 256')
    parser.add_argument('--time-limit', type=float, help='Episode wall-clock ceiling; default 3600s for search campaigns, 600s for search fights, otherwise 30s')
    parser.add_argument('--config', help='Validated combat training JSON (mode, scenario_set, reward)')
    parser.add_argument('--checkpoint', help='Frozen imitation or PPO bundle to compare with reference policies')
    parser.add_argument('--hybrid', action='store_true', help='Compare ordinary-HP campaigns with learned combat/heuristic routing')
    parser.add_argument('--full-run', action='store_true', help='Pair heuristic, combat hybrid and fully learned genuine campaigns')
    parser.add_argument('--act1', action='store_true', help='Stop at Act 1 completion and compare Act 1 clear rates')
    parser.add_argument('--combat-checkpoint', help='Frozen combat comparison bundle for --full-run')
    parser.add_argument('--reference-checkpoint', help='Frozen campaign initializer to compare with --checkpoint')
    parser.add_argument('--campaign-cases', type=int, default=2)
    parser.add_argument('--workers', type=int,
        help=f'1–16 game workers for campaign or combat-corpus evaluation; defaults to min(16, CPUs), currently {performance.game_workers()}; other modes use 1')
    parser.add_argument('--combat-corpus', help='Matched genuine Act 1 combat starts in corpus.json')
    parser.add_argument('--combat-starts', choices=('opening', 'continuation', 'all'), default='opening',
                        help='Whole fights by default; continuations are separate tactical diagnostics')
    parser.add_argument('--freeze-suite', metavar='CONFIG', help='Freeze benchmark settings, cases and private snapshots before tuning')
    parser.add_argument('--suite', help='Frozen suite.json for paired evaluation or checkpoint selection')
    parser.add_argument('--candidate', action='append', default=[], help='Named inference bundle: imitation=PATH or ppo_NAME=PATH')
    parser.add_argument('--select-development', help='Complete benchmark.json from development; write selection.json')
    parser.add_argument('--selection', help='Locked selection.json required for --suite with --split test')
    from game.cli.search_args import add_search_arguments
    add_search_arguments(parser)
    parser.add_argument('--search-benchmark', help='Public developed-inventory JSON for balanced search evaluation')
    parser.add_argument('--search-critic-baseline-simulations', type=int,
                        help='Also compare critic-only Gumbel and root search at this fixed budget')
    parser.add_argument('--search-skip-root-baseline', action='store_true',
                        help='Compare network and Gumbel only after the root baseline is established')
    parser.add_argument('--search-cases', type=int, default=8, help='Paired combat starts for --search; Act 1 uses --campaign-cases')
    from game.cli.agent_track import add_tracking_arguments, cli_session
    add_tracking_arguments(parser)
    args = parser.parse_args(argv)
    with cli_session(args, parser):
        return _run(args, parser)


def _run(args, parser):
    if args.time_limit is None:
        args.time_limit = (3600. if args.act1 else 600.) if args.search else 30.
    if args.max_decisions is None:
        args.max_decisions = 1024 if args.search and args.act1 else 256
    if args.search_benchmark and (not args.search or args.act1 or args.combat_corpus or args.encounters):
        parser.error('--search-benchmark requires --search combats; omit --act1, --combat-corpus and --encounter')
    if args.combat_starts != 'opening' and not args.combat_corpus:
        parser.error('--combat-starts requires --combat-corpus')
    parallel = bool(args.act1 or args.full_run or args.combat_corpus or args.search)
    if args.workers is None:
        args.workers = performance.game_workers() if parallel else 1
    if not 1 <= args.workers <= performance.GAME_WORKER_LIMIT or args.workers != 1 and not parallel:
        parser.error('--workers accepts 1–16 and parallel workers require --act1, --full-run or --combat-corpus')
    try:
        from game.agent.training.evaluation import evaluate_baselines
    except ModuleNotFoundError as error:
        if error.name not in ('gymnasium', 'numpy'):
            raise
        parser.error("Combat evaluation requires the optional 'sts-agent[gym]' dependencies")
    try:
        from game.agent.training.config import TrainingConfig
        config = TrainingConfig.load(args.config) if args.config else TrainingConfig()
        if args.checkpoint or args.suite or args.freeze_suite or args.combat_corpus:
            try:
                import torch
            except ModuleNotFoundError as error:
                if error.name != 'torch':
                    raise
                parser.error("Checkpoint evaluation requires the optional 'sts-agent[train]' dependencies")
            torch.set_num_threads(1)
        if args.search:
            if (not args.checkpoint or args.full_run or args.hybrid or args.suite or args.freeze_suite or
                    args.selection or args.select_development or args.candidate or args.config or
                    args.audit_dir or args.combat_checkpoint or args.reference_checkpoint or
                    args.combat_starts != 'opening' or args.cases_per_scenario != 4 or
                    args.combat_corpus and args.encounters):
                parser.error('--search compares one --checkpoint on opening combats or --act1; omit other comparison modes')
            from game.cli.search_args import search_config
            from game.agent.training.search_run import run_search
            import signal
            import threading
            stopped = threading.Event()
            previous = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
            for sig in previous:
                signal.signal(sig, lambda *_: stopped.set())
            try:
                path, report = run_search(checkpoint=args.checkpoint, output_dir=args.output_dir,
                    search=search_config(args), corpus_path=args.combat_corpus,
                    cases=args.campaign_cases if args.act1 else args.search_cases, split=args.split,
                    start_index=args.start_index, max_decisions=args.max_decisions,
                    time_limit_seconds=args.time_limit, workers=args.workers, act1=args.act1,
                    encounters=tuple(args.encounters or ('overgrowth_vantom',)),
                    benchmark_path=args.search_benchmark,
                    critic_baseline_simulations=args.search_critic_baseline_simulations,
                    include_root=not args.search_skip_root_baseline, cancel=stopped)
            finally:
                for sig, handler in previous.items():
                    signal.signal(sig, handler)
            print(json.dumps({'report': str(path), 'status': report['status'], 'summary': report['summary'],
                              'paired_vs_network': report.get('paired_vs_network')}, indent=2))
            return 130 if report['status'] == 'interrupted' else 0 if report['status'] == 'complete' else 1
        if args.combat_corpus:
            if (args.act1 or args.full_run or args.hybrid or args.suite or args.freeze_suite or
                    args.selection or args.select_development or args.config or args.encounters or
                    args.start_index or args.cases_per_scenario != 4 or args.audit_dir or
                    args.combat_checkpoint or args.reference_checkpoint or args.checkpoint and args.candidate):
                parser.error('Combat corpus evaluation uses its frozen cases; choose --candidate or --checkpoint and limits/workers')
            from game.agent.training.combat_benchmark import evaluate_corpus
            checkpoints = {'learned':args.checkpoint} if args.checkpoint else {}
            for value in args.candidate:
                name, sep, bundle = value.partition('=')
                if not sep or not bundle or name in checkpoints:
                    parser.error('Use distinct --candidate NAME=PATH arguments')
                checkpoints[name] = bundle
            import signal
            import threading
            stopped = threading.Event()
            previous = {sig:signal.getsignal(sig) for sig in (signal.SIGINT,signal.SIGTERM)}
            for sig in previous: signal.signal(sig,lambda *_:stopped.set())
            try:
                path, report = evaluate_corpus(corpus_path=args.combat_corpus, output_dir=args.output_dir,
                    checkpoints=checkpoints, split=args.split, max_decisions=args.max_decisions,
                    time_limit_seconds=args.time_limit, workers=args.workers, cancel=stopped,
                    start_kind=args.combat_starts)
            finally:
                for sig, handler in previous.items(): signal.signal(sig,handler)
            print(json.dumps({'report':str(path), 'status':report['status'], 'summary':report['summary'],
                              'coverage':report['coverage'], 'total_seconds':report['total_seconds']},indent=2))
            return 130 if report['status']=='interrupted' else 0 if report['status']=='complete' else 1
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
                    max_decisions=args.max_decisions, time_limit_seconds=args.time_limit, cancel=stopped,
                    workers=args.workers)
            finally:
                for sig, handler in previous.items(): signal.signal(sig,handler)
            print(json.dumps({'report':str(path), 'status':report['status'], 'summary':report['summary'],
                'total_seconds':report['total_seconds'], 'execution':report['execution'],
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

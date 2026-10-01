"""Build and inspect a local public-recording analysis report."""
import argparse
import json
import sys
import time


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    compress = commands.add_parser('compress', help='Preview or verify lossless compression of public trajectories')
    compress.add_argument('--input', action='append', required=True, help='Public roots; private trees and partials are excluded')
    compress.add_argument('--apply', action='store_true', help='Replace verified plain copies with gzip containers')
    compress.add_argument('--workers', type=int, default=1)
    compress.add_argument('--report', help='New JSONL migration report, required with --apply')
    summary = commands.add_parser('summary', help='Quick reported metrics; no canonical recording validation or viewer export')
    summary.add_argument('--input', action='append', required=True, help='Public experiment directory; repeat to combine roots')
    build = commands.add_parser('build', help='Verify recordings and export compressed decision data')
    build.add_argument('--input', action='append', required=True, help='Public artifact file/directory; repeat to combine roots')
    build.add_argument('--output-dir', required=True, help='New analysis directory (never overwritten)')
    build.add_argument('--goal', choices=('act1', 'full_run'), help='Goal for unlabelled recordings; checks existing goal labels')
    build.add_argument('--title', default='Act 1 · Decision lab')
    build.add_argument('--workers', type=int, default=1, help='Parallel episode exporters, 1–8 (default: 1)')
    serve = commands.add_parser('serve', help='Open a read-only viewer on 127.0.0.1; Ctrl-C stops it')
    serve.add_argument('report_dir')
    serve.add_argument('--port', type=int, default=8765)
    serve.add_argument('--checkpoint', action='append', default=[], metavar='LABEL=PATH',
                       help='Explicit inference bundle for same-state comparison (max four)')
    inspect = commands.add_parser('inspect', help='Emit a decision or checkpoint comparison as JSON')
    inspect.add_argument('report_dir')
    inspect.add_argument('--episode', required=True)
    inspect.add_argument('--step', required=True, type=int, help='Zero-based recorded decision index')
    inspect.add_argument('--checkpoint', action='append', default=[], metavar='LABEL=PATH')
    args = parser.parse_args(argv)
    try:
        if args.command == 'compress':
            from game.agent.trace_compression import compress_traces
            last = time.monotonic()
            def progress(done, total, summary):
                nonlocal last
                if done == total or time.monotonic()-last >= 10:
                    print(json.dumps({'done': done, 'total': total, **summary}), file=sys.stderr, flush=True)
                    last = time.monotonic()
            result = compress_traces(args.input, apply=args.apply, workers=args.workers,
                                     report=args.report, progress=progress)
            print(json.dumps(result, sort_keys=True))
            return 1 if result['failed_groups'] else 0
        elif args.command == 'summary':
            from game.agent.analysis.summary import quick_summary
            print(json.dumps(quick_summary(args.input), indent=2, allow_nan=False))
        elif args.command == 'build':
            from game.agent.analysis.report import build_report
            started = time.perf_counter()
            def progress(done, count, row):
                print(json.dumps({'verified': done, 'total': count, 'episode': row['id']}), file=sys.stderr, flush=True)
            result = build_report(args.input, args.output_dir, title=args.title, goal=args.goal,
                                  progress=progress, workers=args.workers)
            print(json.dumps({'status': 'complete', 'report_dir': args.output_dir, 'runs': len(result['runs']),
                              'decisions': sum(r['steps'] for r in result['runs']),
                              'seconds': time.perf_counter()-started, 'export': result['export']}))
        else:
            from game.agent.analysis.server import AnalysisStore, make_server
            checkpoints = []
            for value in args.checkpoint:
                label, separator, path = value.partition('=')
                if not separator or not label or not path:
                    raise ValueError('Use --checkpoint LABEL=PATH')
                checkpoints.append((label, path))
            store = AnalysisStore(args.report_dir, checkpoints)
            if args.command == 'inspect':
                result = store.compare(args.episode, args.step) if checkpoints else store.decision(args.episode, args.step)
                print(json.dumps(result, indent=2, allow_nan=False))
            else:
                if not 0 <= args.port <= 65535:
                    raise ValueError('Invalid port')
                with make_server(store, args.port) as server:
                    print(json.dumps({'status': 'serving', 'url': f'http://127.0.0.1:{server.server_port}',
                                      'runs': len(store.runs), 'checkpoints': len(checkpoints)}), flush=True)
                    try:
                        server.serve_forever()
                    except KeyboardInterrupt:
                        pass
        return 0
    except KeyboardInterrupt:
        print(json.dumps({'status': 'cancelled', 'reason': 'Interrupted; unfinished exports have no report.json'}), file=sys.stderr)
        return 130
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, ModuleNotFoundError) as error:
        print(json.dumps({'status': 'failed', 'category': type(error).__name__, 'reason': str(error)}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

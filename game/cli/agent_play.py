"""Run the public-only demonstration policy and record complete headless trajectories."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import signal
import sys
import threading

from game.agent.runner import RunCancelled, RunConfig, RunFailure
from game.agent.workers import run_batch
from game.agent import performance


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True, help='Public trajectory directory.')
    parser.add_argument('--audit-dir', type=Path, help='Separate owner-only private replay directory; defaults to OUTPUT-private beside OUTPUT.')
    parser.add_argument('--character', choices=('ironclad', 'silent', 'regent', 'necrobinder', 'defect'), default='ironclad')
    parser.add_argument('--first-act', choices=('overgrowth', 'underdocks'), default='overgrowth')
    parser.add_argument('--act1', action='store_true', help='Stop successfully at the Act 1 task boundary.')
    parser.add_argument('--ascension', type=int, choices=range(11), default=0)
    parser.add_argument('--seed', type=int, default=0, help='Private base seed; episode i uses seed+i regardless of worker count.')
    parser.add_argument('--episodes', type=int, default=1)
    parser.add_argument('--workers', type=int, default=performance.game_workers(),
        help=f'1–32 game workers; defaults to min(16, CPUs), currently {performance.game_workers()}, limited by episode count')
    parser.add_argument('--max-decisions', type=int, default=4096)
    parser.add_argument('--time-limit', type=float, help='Seconds per episode; default 3600 with search, otherwise 300. Expiration is a cutoff.')
    parser.add_argument('--scenario', default='generated_campaign_all_unlocked_v1', help='Public scenario reference, without private replay data.')
    parser.add_argument('--split', choices=('train', 'validation', 'test'), default='train')
    policy = parser.add_mutually_exclusive_group()
    policy.add_argument('--combat-checkpoint', type=Path, help='Frozen combat model; heuristic handles other run decisions')
    policy.add_argument('--checkpoint', type=Path, help='Frozen full-run model handles every public decision')
    from game.cli.search_args import add_search_arguments, search_config
    add_search_arguments(parser)
    args = parser.parse_args(argv)
    if args.time_limit is None:
        args.time_limit = 3600. if args.search else 300.
    output = args.output_dir.resolve()
    audit = args.audit_dir or output.with_name(output.name + '-private')
    config = RunConfig(seed=args.seed, character=args.character, first_act=args.first_act,
                       ascension=args.ascension, max_decisions=args.max_decisions,
                       time_limit_seconds=args.time_limit, scenario=args.scenario, split=args.split,
                       goal='act1' if args.act1 else 'full_run')
    stopped = threading.Event()
    previous = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
    def interrupt(*_):
        stopped.set()
    for sig in previous:
        signal.signal(sig, interrupt)
    try:
        result = run_batch(config, output_dir=output, audit_dir=audit,
                           episodes=args.episodes, workers=args.workers, cancel=stopped,
                           combat_checkpoint=args.combat_checkpoint, run_checkpoint=args.checkpoint,
                           search=search_config(args))
    except (KeyboardInterrupt, RunCancelled):
        print(json.dumps({'status': 'cancelled', 'unfinished': 'partial'}), file=sys.stderr)
        return 130
    except ModuleNotFoundError as error:
        if (not (args.checkpoint or args.combat_checkpoint) or
                error.name not in ('torch', 'numpy', 'gymnasium')):
            raise
        print(json.dumps({'status': 'failed', 'category': type(error).__name__,
                          'reason': "Checkpoint playback requires the optional 'sts-agent[train]' dependencies"}),
              file=sys.stderr)
        return 1
    except (ValueError, OSError, RunFailure) as error:
        print(json.dumps({'status': 'failed', 'category': type(error).__name__,
                          'reason': str(error)}), file=sys.stderr)
        return 1
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    print(json.dumps({'status': 'complete', **asdict(result),
        **({'goal':'act1', 'act1_clears':sum(e.outcome.kind=='truncated' and e.outcome.reason=='external_stop'
                                          for e in result.episodes)} if args.act1 else {})}, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

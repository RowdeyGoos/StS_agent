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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True, help='Public trajectory directory.')
    parser.add_argument('--audit-dir', type=Path, help='Separate owner-only private replay directory; defaults to OUTPUT-private beside OUTPUT.')
    parser.add_argument('--character', choices=('ironclad', 'silent', 'regent', 'necrobinder', 'defect'), default='ironclad')
    parser.add_argument('--first-act', choices=('overgrowth', 'underdocks'), default='overgrowth')
    parser.add_argument('--ascension', type=int, choices=range(11), default=0)
    parser.add_argument('--seed', type=int, default=0, help='Private base seed; episode i uses seed+i regardless of worker count.')
    parser.add_argument('--episodes', type=int, default=1)
    parser.add_argument('--workers', type=int, default=1)
    parser.add_argument('--max-decisions', type=int, default=4096)
    parser.add_argument('--time-limit', type=float, default=300.0, help='Seconds per episode; expiration is an explicit cutoff.')
    parser.add_argument('--scenario', default='generated_campaign_all_unlocked_v1', help='Public scenario reference, without private replay data.')
    parser.add_argument('--split', choices=('train', 'validation', 'test'), default='train')
    args = parser.parse_args(argv)
    output = args.output_dir.resolve()
    audit = args.audit_dir or output.with_name(output.name + '-private')
    config = RunConfig(seed=args.seed, character=args.character, first_act=args.first_act,
                       ascension=args.ascension, max_decisions=args.max_decisions,
                       time_limit_seconds=args.time_limit, scenario=args.scenario, split=args.split)
    stopped = threading.Event()
    previous = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
    def interrupt(*_):
        stopped.set()
    for sig in previous:
        signal.signal(sig, interrupt)
    try:
        result = run_batch(config, output_dir=output, audit_dir=audit,
                           episodes=args.episodes, workers=args.workers, cancel=stopped)
    except (KeyboardInterrupt, RunCancelled):
        print(json.dumps({'status': 'cancelled', 'unfinished': 'partial'}), file=sys.stderr)
        return 130
    except (ValueError, OSError, RunFailure) as error:
        print(json.dumps({'status': 'failed', 'category': type(error).__name__,
                          'reason': str(error)}), file=sys.stderr)
        return 1
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    print(json.dumps({'status': 'complete', **asdict(result)}, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

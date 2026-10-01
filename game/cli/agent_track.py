"""Import, compare and serve local experiment records through MLflow."""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sys

from game.agent.tracking import TrackingConfig, tracking_session


def add_tracking_arguments(parser):
    parser.add_argument('--tracking-dir', help='Opt in to local MLflow logging at this directory')
    parser.add_argument('--tracking-experiment', default='StS experiments')
    parser.add_argument('--tracking-name', help='Display name for a new learner; exact resumes keep its name')
    parser.add_argument('--inspector-url', help='Optional loopback decision-inspector link')


@contextmanager
def cli_session(args, parser):
    directory = getattr(args, 'tracking_dir', None)
    if not directory:
        if getattr(args, 'tracking_name', None) or getattr(args, 'inspector_url', None):
            parser.error('--tracking-name/--inspector-url require --tracking-dir')
        yield
        return
    config = TrackingConfig(directory, args.tracking_experiment, args.tracking_name, args.inspector_url)
    # Configuration/dependency errors are detected before training starts.
    try:
        context = tracking_session(config)
        store = context.__enter__()
    except (ImportError, ValueError, OSError) as error:
        parser.error(str(error)+"; install sts-agent[tracking] for the optional dashboard")
    try:
        yield store
    finally:
        context.__exit__(None, None, None)


def import_reports(store, inputs):
    from game.agent.tracking import records as r
    supported, skipped, failed, results = [], [], [], []
    for path in r.discover(inputs, exclude=store.path):
        try:
            report = r.read_json(path)
            schema = report.get('schema')
            training = schema in ('sts_ppo_report_v1', 'sts_imitation_report_v1')
            diagnostic = path.name in ('diagnosis.json', 'tiny.json', 'smoke.json') and 'stage_sha256' in report
            if not training and schema not in r.EVALUATION_SCHEMAS and not diagnostic:
                skipped.append({'path': str(path), 'reason': 'unsupported schema', 'schema': schema})
                continue
            supported.append((0 if training else 1,
                report.get('start_decisions', report.get('start_update', 0)), path))
        except (ValueError, OSError) as error:
            failed.append({'path': str(path), 'error': str(error)})
    # Parents before continuations, all learners before their evaluations.
    for _, _, path in sorted(supported):
        try:
            results.append(store.import_report(path))
        except (ValueError, OSError, KeyError) as error:
            failed.append({'path': str(path), 'error': str(error)})
    return {'reports': results, 'skipped': skipped, 'failed': failed,
            'counts': {'tracked': sum(row['status'] == 'tracked' for row in results),
                       'unchanged': sum(row['status'] == 'unchanged' for row in results),
                       'skipped': len(skipped), 'failed': len(failed)}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    ingest = sub.add_parser('import', help='Import public reports without restoring or retraining models')
    ingest.add_argument('inputs', nargs='+')
    ingest.add_argument('--store', default='runs/experiment-tracking')
    ingest.add_argument('--experiment', default='StS experiments')
    ingest.add_argument('--name')
    ingest.add_argument('--inspector-url')
    ingest.add_argument('--report', help='Write the import inventory and explicit skip/failure reasons')
    serve = sub.add_parser('serve', help='Start MLflow on loopback only; telemetry disabled')
    serve.add_argument('--store', default='runs/experiment-tracking')
    serve.add_argument('--port', type=int, default=5000)
    catalog = sub.add_parser('catalog', help='Curate Models while preserving recovery files and metrics')
    catalog.add_argument('--store', default='runs/experiment-tracking')
    catalog.add_argument('--experiment', default='StS experiments')
    catalog.add_argument('--keep-checkpoint', action='append', default=[], help='Retain an imported checkpoint as a candidate')
    catalog.add_argument('--release-checkpoint', action='append', default=[], help='Remove an explicit candidate retention')
    args = parser.parse_args(argv)
    try:
        from game.agent.tracking.store import TrackingStore, local_store
        if args.command == 'serve':
            if not 1 <= args.port <= 65535:
                raise ValueError('Choose a port between 1 and 65535')
            store = local_store(args.store)
            env = {**os.environ, 'MLFLOW_DISABLE_TELEMETRY': 'true', 'MLFLOW_DISABLE_AGENT_HINT': 'true'}
            os.execve(sys.executable, [sys.executable, '-m', 'mlflow', 'server', '--host', '127.0.0.1',
                '--port', str(args.port), '--backend-store-uri', 'sqlite:///'+str(store/'mlflow.db'),
                '--default-artifact-root', (store/'artifacts').as_uri(), '--no-serve-artifacts'], env)
        if args.command == 'catalog':
            with TrackingStore(args.store, experiment=args.experiment) as store:
                print(json.dumps(store.curate_models(keep=args.keep_checkpoint, release=args.release_checkpoint), indent=2))
            return 0
        with TrackingStore(args.store, experiment=args.experiment, name=args.name,
                           inspector_url=args.inspector_url) as store:
            result = import_reports(store, args.inputs)
        if args.report:
            Path(args.report).write_text(json.dumps(result, indent=2, sort_keys=True)+'\n')
        print(json.dumps(result['counts'] if args.report else result, indent=2))
        return 1 if result['failed'] else 0
    except ImportError:
        parser.error("Install the optional sts-agent[tracking] dependencies")
    except (ValueError, OSError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    raise SystemExit(main())

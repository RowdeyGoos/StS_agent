"""Collect public demonstrations or run bounded CPU imitation, PPO and curriculum."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import time
from game.agent.action_policy import ALL_LEGAL, POLICIES


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    collect = sub.add_parser('collect', help='Record the current public heuristic on controlled combat starts')
    collect.add_argument('--output-dir', required=True)
    collect.add_argument('--split', choices=('train', 'validation', 'test'), default='train')
    collect.add_argument('--cases-per-scenario', type=int, default=1)
    collect.add_argument('--start-index', type=int, default=0)
    collect.add_argument('--max-decisions', type=int, default=96)
    collect.add_argument('--time-limit', type=float, default=30)
    collect.add_argument('--config')
    collect_run = sub.add_parser('collect-run', help='Record genuine campaigns and optional declared assisted demonstrations')
    collect_run.add_argument('--output-dir', required=True)
    collect_run.add_argument('--split', choices=('train','validation','test'), default='train')
    collect_run.add_argument('--cases', type=int, default=4)
    collect_run.add_argument('--start-index', type=int, default=0)
    collect_run.add_argument('--max-decisions', type=int, default=1024)
    collect_run.add_argument('--time-limit', type=float, default=120)
    collect_run.add_argument('--include-fixtures', action='store_true')
    imitate = sub.add_parser('imitate', help='Fit one public training corpus; keep validation separate')
    imitate.add_argument('--train-dir', required=True)
    imitate.add_argument('--validation-dir', required=True)
    imitate.add_argument('--output-dir', required=True)
    imitate.add_argument('--updates', type=int, default=128)
    imitate.add_argument('--batch-size', type=int, help='Defaults to 8; resume preserves the saved setting')
    imitate.add_argument('--learning-rate', type=float, help='Defaults to .003; resume preserves the saved setting')
    imitate.add_argument('--hidden-size', type=int, help='Defaults to 48')
    imitate.add_argument('--message-layers', type=int, help='Defaults to 2')
    imitate.add_argument('--seed', type=int, help='Private learner RNG seed; defaults to 0 for a new learner')
    imitate.add_argument('--resume-bundle')
    imitate.add_argument('--resume-state')
    imitate.add_argument('--full-run', action='store_true', help='Read canonical full-run demonstration manifests')
    imitate.add_argument('--initialize-combat', help='Explicit actor transfer; train-only vocabulary expansion and fresh run critic')
    imitate.add_argument('--action-policy', choices=POLICIES,
        help='Policy-action version; new learners default to all_legal_v1, resume keeps its saved version')
    ppo = sub.add_parser('ppo', help='Collect frozen task rollouts and run bounded masked PPO')
    ppo.add_argument('--checkpoint', required=True, help='Initial inference bundle, or PPO bundle to resume')
    ppo.add_argument('--config', required=True, help='Complete resolved PPO experiment JSON')
    ppo.add_argument('--output-dir', required=True)
    ppo.add_argument('--decisions', type=int, default=256, help='Additional decisions, at most 20,000')
    ppo.add_argument('--time-limit', type=float, default=3600, help='Wall budget, at most one hour')
    ppo.add_argument('--seed', type=int, help='Private learner RNG seed; defaults to 0 for a new learner')
    ppo.add_argument('--start-index', type=int, help='Private training episode cursor; defaults to 0')
    ppo.add_argument('--resume-state', help='Owner-only PPO state matching --checkpoint')
    ppo.add_argument('--reset-objective', action='store_true',
        help='Start a different full-run reward objective: keep actor, reset critic/optimizer; incompatible with resume')
    ppo.add_argument('--reset-action-policy', action='store_true',
        help='Adopt the config action policy in a new experiment; keep weights, start a fresh optimizer')
    ppo.add_argument('--workers', type=int, help='1–8 persistent collectors; defaults to 1, or saved count on resume')
    curriculum = sub.add_parser('curriculum', help='Run three or more learners through five fixed combat stages')
    curriculum.add_argument('--checkpoint', required=True)
    curriculum.add_argument('--config', required=True)
    curriculum.add_argument('--output-dir', required=True)
    curriculum.add_argument('--seeds', nargs='+', type=int, default=[17,23,41], help='Three to five private learner seeds')
    args = parser.parse_args(argv)
    try:
        import torch
        from game.agent.training.config import TrainingConfig
        from game.agent.training.demonstrations import collect_demonstrations, corpus_pairs
        from game.agent.training.checkpoint import publish, save_checkpoint, restore_learner, load_policy, runtime
        from game.agent.training.learner import load_corpus, ImitationLearner, LearnerConfig, evaluate_imitation
        from game.agent.training.model import ActorCritic, Architecture
        from game.agent.runner import prepare_directories
    except ModuleNotFoundError as error:
        if error.name not in ('torch', 'numpy', 'gymnasium'):
            raise
        parser.error("Install the optional 'sts-agent[train]' dependencies")
    torch.set_num_threads(1)
    try:
        if args.command in ('ppo','curriculum','collect-run'):
            import signal
            import threading
            from game.agent.training.ppo_config import PPOExperiment
            from game.agent.training.ppo_run import run_ppo
            stopped = threading.Event()
            previous = {sig:signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
            def interrupt(*_):
                stopped.set()
            for sig in previous:
                signal.signal(sig, interrupt)
            try:
                if args.command == 'collect-run':
                    from game.agent.training.run_demonstrations import collect_run_demonstrations
                    path, report = collect_run_demonstrations(output_dir=args.output_dir, split=args.split,
                        cases=args.cases, start_index=args.start_index, max_decisions=args.max_decisions,
                        time_limit_seconds=args.time_limit, include_fixtures=args.include_fixtures, cancel=stopped)
                elif args.command == 'curriculum':
                    from game.agent.training.curriculum_run import CurriculumConfig, run_curriculum
                    path, report = run_curriculum(checkpoint=args.checkpoint,config=CurriculumConfig.load(args.config),
                        output_dir=args.output_dir,seeds=tuple(args.seeds),cancel=stopped)
                else:
                    path, report = run_ppo(checkpoint=args.checkpoint, experiment=PPOExperiment.load(args.config),
                        output_dir=args.output_dir, decisions=args.decisions, time_limit_seconds=args.time_limit,
                        resume_state=args.resume_state, seed=args.seed, start_index=args.start_index, cancel=stopped,
                        workers=args.workers, reset_objective=args.reset_objective,
                        reset_action_policy=args.reset_action_policy)
            finally:
                for sig, handler in previous.items():
                    signal.signal(sig, handler)
            print(json.dumps({'report':str(path), 'status':report['status'], 'summary':report.get('summary'),
                              'last_complete_checkpoint':report.get('last_complete_checkpoint'),
                              'replicates':report.get('replicates')}, indent=2))
            return 130 if report['status']=='cancelled' else 1 if report['status']=='failed' else 0
        if args.command == 'collect':
            path, report = collect_demonstrations(output_dir=args.output_dir, split=args.split,
                cases_per_scenario=args.cases_per_scenario, start_index=args.start_index,
                max_decisions=args.max_decisions, time_limit_seconds=args.time_limit,
                config=TrainingConfig.load(args.config) if args.config else TrainingConfig())
            print(json.dumps({'report': str(path), 'status': report['status'],
                              'episodes': len(report['episodes'])}))
            return 0 if report['status'] == 'complete' else 1
        if not 1 <= args.updates <= 10000:
            raise ValueError('Choose 1–10,000 bounded updates')
        if bool(args.resume_bundle) != bool(args.resume_state):
            raise ValueError('Resume requires both the inference bundle and its private state')
        if args.initialize_combat and (not args.full_run or args.resume_bundle):
            raise ValueError('Combat transfer requires a new --full-run learner, not exact resume')
        started = time.perf_counter()
        output = Path(args.output_dir).resolve()
        output, private = prepare_directories(output, output.with_name(output.name+'-private'))
        report_path = output/'imitation.json'
        if report_path.exists() or (output/'initial.sts-model').exists() or (output/'final.sts-model').exists():
            raise FileExistsError(output)
        task = 'full_run' if args.full_run else 'combat'
        resumed = load_policy(args.resume_bundle, task=task) if args.resume_bundle else None
        frozen = resumed.model.vocabulary if resumed else None
        action_policy = args.action_policy or (resumed.model.action_policy if resumed else ALL_LEGAL)
        if resumed and action_policy != resumed.model.action_policy:
            raise ValueError('Exact resume cannot change its policy-action version')
        source = load_policy(args.initialize_combat, task='combat') if args.initialize_combat else None
        lineage = None
        if args.full_run:
            from game.agent.training.run_corpus import load_run_corpus, transfer_combat
            from game.agent.training.run_demonstrations import corpus_paths
            train = load_run_corpus(corpus_paths(args.train_dir, split='train', retain=True), split='train', vocabulary=frozen,
                base_vocabulary=source.model.vocabulary if source else None, action_policy=action_policy)
            validation = load_run_corpus(corpus_paths(args.validation_dir, split='validation', retain=True),
                split='validation', vocabulary=train.vocabulary, action_policy=action_policy)
        else:
            train = load_corpus(corpus_pairs(args.train_dir, split='train'), split='train', vocabulary=frozen,
                                action_policy=action_policy)
            validation = load_corpus(corpus_pairs(args.validation_dir, split='validation'), split='validation',
                                     vocabulary=train.vocabulary, action_policy=action_policy)
        if train.reward_spec != validation.reward_spec:
            raise ValueError('Training and validation objectives differ')
        if args.resume_bundle:
            learner = restore_learner(args.resume_bundle, args.resume_state, train)
            for name, expected in (('batch_size', learner.config.batch_size),
                                   ('learning_rate', learner.config.learning_rate),
                                   ('hidden_size', learner.model.architecture.hidden_size),
                                   ('message_layers', learner.model.architecture.message_layers)):
                if getattr(args, name) is not None and getattr(args, name) != expected:
                    raise ValueError('Exact resume cannot change '+name)
            if args.seed is not None:
                raise ValueError('Exact resume restores learner RNG state; omit --seed')
        else:
            seed = args.seed if args.seed is not None else 0
            architecture = Architecture(args.hidden_size if args.hidden_size is not None else 48,
                                        args.message_layers if args.message_layers is not None else 2)
            settings = LearnerConfig(args.batch_size if args.batch_size is not None else 8,
                                     args.learning_rate if args.learning_rate is not None else .003)
            if source:
                for name in ('hidden_size','message_layers'):
                    if getattr(args,name) is not None and getattr(args,name) != getattr(source.model.architecture,name):
                        raise ValueError('Actor transfer cannot change '+name)
                model, lineage = transfer_combat(source, train.vocabulary, seed=seed, action_policy=action_policy)
            else:
                model = ActorCritic(train.vocabulary, architecture, seed=seed, action_policy=action_policy)
            learner = ImitationLearner(model, train, settings, seed=seed)
        report = {'schema': 'sts_imitation_report_v1', 'status': 'running', 'runtime': runtime(),
                  'architecture': asdict(learner.model.architecture), 'learner_config': asdict(learner.config),
                  'reward_spec': train.reward_spec.to_dict(), 'feature_identity': train.vocabulary.identity,
                  'corpus_identity': train.identity, 'validation_identity': validation.identity,
                  'train_decisions': len(train.examples), 'validation_decisions': len(validation.examples),
                  'packed_corpus_bytes': train.nbytes, 'corpus_encoding_seconds': train.encoding_seconds,
                  'start_update': learner.updates, 'updates': [], 'task':task, 'transfer':lineage}
        report['action_policy'] = action_policy
        report['before'] = {'train': evaluate_imitation(learner.model, train),
                            'validation': evaluate_imitation(learner.model, validation)}
        report['initial_sha256'] = save_checkpoint(output/'initial.sts-model', learner,
                                                   resume_path=private/'initial.resume.pt')
        try:
            for _ in range(args.updates):
                report['updates'].append(learner.step())
            report['after'] = {'train': evaluate_imitation(learner.model, train),
                               'validation': evaluate_imitation(learner.model, validation)}
            report['final_sha256'] = save_checkpoint(output/'final.sts-model', learner,
                                                     resume_path=private/'final.resume.pt')
            report['status'] = 'complete'
        except (Exception, KeyboardInterrupt) as error:
            report['status'], report['failure'] = 'failed', type(error).__name__
        report['total_seconds'] = time.perf_counter()-started
        publish(report_path, (json.dumps(report, indent=2, sort_keys=True, allow_nan=False)+'\n').encode())
        print(json.dumps({'report': str(report_path), 'status': report['status'],
                          'before': report['before'], 'after': report.get('after')}, indent=2))
        return 0 if report['status'] == 'complete' else 1
    except (ValueError, OSError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    raise SystemExit(main())

"""Frozen sequential 24 + 8 configuration experiment; no teacher or preview."""
from dataclasses import asdict, replace
from datetime import datetime, timezone
import json
from pathlib import Path
from random import Random
import time
import torch

from game.agent.contracts import full as f
from game.agent.provenance import implementation
from ..benchmark_suite import data
from ..checkpoint import publish, save_ppo_checkpoint, load_policy
from ..combat_corpus import CorpusEnvironment
from ..config import TrainingConfig
from ..features import Vocabulary
from ..ppo import PPOLearner
from ..ppo_config import PPOConfig, PPOExperiment
from ..ppo_run import run_ppo
from ..rewards import RewardSpec
from .evaluate import evaluate
from .model import StudyActorCritic, match_capacity
from .projection import StudyEncoder, study_catalog
from .source import StudySource, prepare_source, reserve_test, _read, _sha_file
from .spec import ARCHITECTURES, RICHNESS, ABLATIONS, FeatureSpec, StudyArchitecture, digest

SCHEMA = 'sts_vantom_feature_study_v1'
MILESTONES = (0, 10000, 25000, 50000, 75000, 100000)
# All configurations use the same bounded invocations. These short final
# rollouts are part of the frozen schedule, not a response to observed reward.
CHUNKS = (10000, 20000, 25000, 35000, 45000, 50000, 60000, 70000, 75000, 85000, 95000, 100000)
LIMITS = dict(max_decisions=512, time_limit_seconds=120.)
ALPHA_REVISION = '9774eca833588cae88dea01f34422a8b0758cf14'


def rng_seed(seed, stream):
    return int(digest([seed, stream])[:15], 16)


def load_config(path):
    value = _read(Path(path))
    fields = {'schema', 'corpus', 'prefix_manifest', 'prefix_dir', 'reference_crosswalk', 'seeds', 'collectors', 'learner_threads'}
    if (set(value) != fields or value['schema'] != SCHEMA or len(value['seeds']) != 3
            or len(set(value['seeds'])) != 3
            or any(type(s) is not int or not 0 <= s < 2**31 for s in value['seeds'])
            or type(value['collectors']) is not int or not 1 <= value['collectors'] <= 16
            or value['learner_threads'] != 4):
        raise ValueError('Expected the complete three-seed Vantom study configuration')
    for key in ('corpus', 'prefix_manifest', 'prefix_dir', 'reference_crosswalk'):
        value[key] = str(Path(value[key]).expanduser().resolve())
    return value


def experiment(source):
    return PPOExperiment(TrainingConfig(reward=RewardSpec({'combat_win': 1., 'win_hp_fraction': .1}),
            action_policy='commit_decisions_v1'),
        PPOConfig(rollout_steps=4096, episode_decisions=512, episode_seconds=120.,
                  batch_size=16, epochs=2),
        tuple(sorted({r['room_kind'] for r in source.split('train')})), source.identity,
        'sts_ppo_experiment_v2')


def schedule(configurations, seeds):
    configurations = tuple(configurations)
    result = []
    for seed in seeds:
        order = sorted(configurations)
        Random(rng_seed(seed, 'configuration-order')).shuffle(order)
        result.extend((name, seed) for name in order)
    return result


def freeze(config, output, *, progress=None):
    path = output/'manifest.json'
    if path.exists():
        manifest = _read(path)
        if manifest['configuration'] != config or manifest['implementation'] != asdict(implementation()):
            raise ValueError('Frozen study configuration or implementation changed')
        return manifest
    source_path = output/'source'/'source.json'
    if not source_path.exists():
        prepare_source(corpus_path=config['corpus'], prefix_manifest=config['prefix_manifest'],
            prefix_dir=config['prefix_dir'], output_dir=source_path.parent, progress=progress)
    source = StudySource(source_path)
    crosswalk = _read(Path(config['reference_crosswalk']))
    if crosswalk.get('revision') != ALPHA_REVISION:
        raise ValueError('Feature reference must use the approved AlphaSpire revision')
    populations = {split: dict(starts=len(source.split(split)),
        openings=sum(r['start_kind'] == 'opening' for r in source.split(split)),
        fights=len({r['combat_id'] for r in source.split(split)})) for split in ('train', 'validation', 'test')}
    if (populations['train'] != dict(starts=668, openings=101, fights=101)
            or populations['validation']['openings'] != 42 or populations['test']['openings'] != 57):
        raise ValueError('Vantom population differs from the approved design')
    catalog = study_catalog().to_dict()
    probe = StudyEncoder(Vocabulary(()), StudyArchitecture(8, 'graph',
        FeatureSpec(entities=2048).to_dict(), catalog), action_policy='commit_decisions_v1')
    names, max_entities, max_candidates, train_slices = set(), 0, 0, {}
    # Only verified TRAIN public prefixes inform capacities, identities and slices.
    # No development or held-out observations participate in fitting.
    for row in source.split('train'):
        from game.agent.headless import HeadlessAdapter
        public = HeadlessAdapter(source.restore(row['case_id'],split='train'),decision_profile=f.PROFILE).observe().decision
        probe.history.restore(source.history_start(row['case_id'], split='train'), public)
        entries, _ = probe._rows(public)
        max_entities, max_candidates = max(max_entities, len(entries)), max(max_candidates, len(public.candidates))
        names.update(n.definition_id for _, n, role in entries
                     if role in ('card', 'enemy', 'potion', 'relic') and n.definition_id)
        if row['start_kind'] == 'opening':
            train_slices[row['case_id']] = dict(hp=public.context.get('hp'), max_hp=public.context.get('max_hp'),
                deck_size=sum(n.get('count', 0) for n in public.context.children if n.kind == 'pile'),
                potions=sum(n.kind == 'potion' for n in f.walk(public.run)))
    # The public candidate schema bounds candidates at 2,048. Reserve twice
    # observed entity use, rounded up, with a 128-slot floor. Overflow fails.
    capacity = max(128, 1 << (2*max_entities-1).bit_length())
    configurations, pairs = {}, []
    for architecture in ARCHITECTURES:
        for identities in (True, False):
            for richness in RICHNESS:
                name = f'{architecture}-{"ids" if identities else "mechanical"}-{richness}'
                spec = FeatureSpec(richness, identities, entities=capacity)
                vocabulary = Vocabulary(tuple(sorted(names)) if identities else ())
                model = StudyArchitecture(8, architecture, spec.to_dict(), catalog)
                configurations[name] = dict(architecture=asdict(model), vocabulary=vocabulary.to_dict())
                pairs.append((model, vocabulary))
    target, matched = match_capacity(pairs)
    for row, (architecture, parameters) in zip(configurations.values(), matched):
        row.update(architecture=asdict(architecture), parameters=parameters)
    manifest = dict(schema=SCHEMA, configuration=config, implementation=asdict(implementation()),
        frozen_at=datetime.now(timezone.utc).isoformat(), source=str(source_path), source_identity=source.identity,
        populations=populations, alpha_revision=ALPHA_REVISION, configurations=configurations,
        reference_crosswalk=crosswalk, reference_crosswalk_sha256=_sha_file(config['reference_crosswalk']),
        target_parameters=target, parameter_tolerance=.05,
        capacities=dict(entities=capacity, candidates=2048, max_train_entities=max_entities,
                        max_train_candidates=max_candidates, fit_split='train'),
        train_slices=train_slices, training_content=sorted(names),
        ppo=experiment(source).to_dict(), milestones=MILESTONES, chunks=CHUNKS,
        schedule=schedule(configurations, config['seeds']), decisions_per_learner=100000,
        total_learners=96, total_training_decisions=9600000,
        initialization='random; zero updates; no demonstrations, transfer or warmup',
        followups=dict(parent='best context no-vocabulary architecture at 100k', removals=ABLATIONS,
                       dimensions='retain parent', fresh_initialization=True),
        selection=['mean_greedy_wins', 'mean_sampled_wins', 'fewer_cutoffs', 'lower_inference_seconds', 'configuration_id'])
    publish(path, data(manifest))
    return _read(path)


def initialize(configuration, seed, manifest, folder):
    path, private = folder/'initial.sts-model', folder.with_name(folder.name+'-private')
    if path.exists():
        policy = load_policy(path)
        if policy.manifest['updates'] != 0 or not (private/'initial.resume.pt').is_file():
            raise ValueError('Random initialization is incomplete or has prior updates')
        return path, private/'initial.resume.pt'
    folder.mkdir(parents=True, exist_ok=True)
    model = StudyActorCritic(Vocabulary.from_dict(configuration['vocabulary']),
        StudyArchitecture(**configuration['architecture']), seed=rng_seed(seed, 'initialization'),
        action_policy='commit_decisions_v1')
    settings = PPOExperiment.from_dict(manifest['ppo'])
    factory = CorpusEnvironment(manifest['source'], manifest['source_identity'])
    learner = PPOLearner(model, settings, seed=rng_seed(seed, 'action-sampling'),
        cursor=rng_seed(seed, 'environment') % 2**40, env_factory=factory,
        workers=manifest['configuration']['collectors'])
    learner.update_generator.manual_seed(rng_seed(seed, 'minibatches'))
    try:
        if learner.updates or learner.decisions or learner.iterations:
            raise ValueError('Random learner has prior training')
        save_ppo_checkpoint(path, learner, resume_path=private/'initial.resume.pt')
    finally:
        learner.close()
    return path, private/'initial.resume.pt'


def train_one(name, configuration, seed, manifest, output, *, smoke=False, progress=None):
    folder = output/('smoke' if smoke else 'learners')/name/str(seed)
    result_path = folder/'learner.json'
    if result_path.exists():
        result = _read(result_path)
        if result['configuration'] != configuration or result['seed'] != seed:
            raise ValueError('Completed learner has a different binding')
        return result
    started = time.perf_counter()
    checkpoint, resume = initialize(configuration, seed, manifest, folder/'initialization')
    reports, evaluations, accepted = [], {}, 0
    settings = PPOExperiment.from_dict(manifest['ppo'])
    factory = CorpusEnvironment(manifest['source'], manifest['source_identity'])
    workers = manifest['configuration']['collectors']
    def evaluate_at(step, path):
        destination = folder/'evaluation'/f'{step:06}'
        report = evaluate(source_path=manifest['source'], output_dir=destination,
            checkpoints={name: str(path)}, split='validation', modes=[('greedy', 0)], workers=workers, seed=seed,
            training_content=manifest['training_content'])
        evaluations[str(step)] = str(destination/'evaluation.json')
        if progress:
            progress(dict(configuration=name, seed=seed, decisions=step,
                          development_wins=sum((r.get('combat') or {}).get('outcome') == 'victory' for r in report['episodes'])))
        (output/'progress.json').write_text(json.dumps(dict(configuration=name,seed=seed,decisions=step,
            evaluation=str(destination/'evaluation.json'),updated_at=datetime.now(timezone.utc).isoformat())))
    if not smoke:
        evaluate_at(0, checkpoint)
    for endpoint in ((128,) if smoke else CHUNKS):
        segment = folder/'training'/f'{endpoint:06}'
        report_path = segment/'ppo.json'
        if report_path.exists():
            report = _read(report_path)
            if report['initialization']['checkpoint'] != 'ppo_v1:'+_sha_file(checkpoint):
                raise ValueError('Bounded continuation does not follow its preceding checkpoint')
        else:
            _, report = run_ppo(checkpoint=checkpoint, resume_state=resume, experiment=settings,
                output_dir=segment, decisions=endpoint-accepted, time_limit_seconds=3600,
                env_factory=factory, workers=workers)
        if (report['status'] != 'complete' or report['summary']['accepted_decisions'] != endpoint-accepted
                or report['summary']['processed_decisions'] != endpoint-accepted
                or report['start_decisions'] != accepted):
            raise ValueError('Bounded study segment did not complete; retain evidence and stop, without extending budget')
        accepted = endpoint
        reports.append(str(report_path))
        checkpoint = segment/'final.sts-model'
        resume = segment.with_name(segment.name+'-private')/'final.resume.pt'
        if not smoke and endpoint in MILESTONES:
            evaluate_at(endpoint, checkpoint)
    if not smoke:
        for split, modes, label in (
            ('validation', [('sampled', 0), ('sampled', 1)], 'sampled'),
            ('train', [('greedy', 0)], 'training')):
            destination = folder/'evaluation'/label
            evaluate(source_path=manifest['source'], output_dir=destination, checkpoints={name: str(checkpoint)},
                     split=split, modes=modes, workers=workers, seed=seed, training_content=manifest['training_content'])
            evaluations[label] = str(destination/'evaluation.json')
    result = dict(schema='sts_feature_study_learner_v1', configuration_id=name, configuration=configuration,
        seed=seed, status='complete', collected_decisions=accepted, checkpoint=str(checkpoint),
        checkpoint_sha256=_sha_file(checkpoint), reports=reports, evaluations=evaluations,
        seconds=time.perf_counter()-started, smoke=smoke)
    publish(result_path, data(result))
    return result


def endpoint_key(name, learners):
    from .report import metrics
    greedy = [metrics(_read(Path(r['evaluations']['100000']))) for r in learners]
    sampled = [metrics(_read(Path(r['evaluations']['sampled']))) for r in learners]
    mean = lambda key, rows: sum(r[key] for r in rows)/len(rows)
    return (-mean('win_rate', greedy), -mean('win_rate', sampled),
            mean('cutoff_rate', greedy), mean('inference_seconds', greedy), name)


def choose(configurations, learners, predicate):
    eligible = [name for name, c in configurations.items() if predicate(c['architecture']['features'])]
    return min(eligible, key=lambda name: endpoint_key(name, learners[name]))


def run(config_path, output_dir, *, phase='all', progress=print):
    if _read(Path(config_path)).get('schema') == 'sts_vantom_shared_ppo_study_v1':
        from .hyperparameters import run as run_hyperparameters
        return run_hyperparameters(config_path, output_dir, phase=phase, progress=progress)
    if _read(Path(config_path)).get('schema') in ('sts_vantom_flat_width_study_v1','sts_vantom_entity_encoding_study_v1'):
        from .flat_width import run as run_flat_width
        return run_flat_width(config_path, output_dir, phase=phase, progress=progress)
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    config = load_config(config_path)
    torch.set_num_threads(config['learner_threads'])
    torch.use_deterministic_algorithms(True)
    manifest = freeze(config, output, progress=lambda i, n: progress(dict(verified_starts=i, total=n)))
    if phase == 'prepare':
        return manifest
    configurations = manifest['configurations']
    if phase in ('smoke', 'all'):
        results = [train_one(name, row, 193, manifest, output, smoke=True, progress=progress)
                   for name, row in configurations.items() if row['architecture']['features']['richness'] == 'context']
        smoke_path = output/'smoke.json'
        if not smoke_path.exists():
            publish(smoke_path, data(dict(status='complete', implementation=manifest['implementation'], learners=results)))
        if phase == 'smoke':
            return _read(smoke_path)
    if phase == 'report':
        from .report import build_report
        return build_report(output)
    if phase not in ('run', 'confirm', 'all'):
        raise ValueError('Unknown study phase')
    for file in ('smoke.json', 'semantic-review.json'):
        gate = _read(output/file)
        if gate.get('status') != 'complete' or gate.get('implementation') != manifest['implementation']:
            raise ValueError('Full training requires current-source smoke and independent semantic review: '+file)
    learners = {}
    if phase != 'confirm':
        for name, seed in manifest['schedule']:
            learners.setdefault(name, []).append(train_one(name, configurations[name], seed, manifest, output, progress=progress))
            from .report import build_report
            build_report(output)
        parent = choose(configurations, learners, lambda spec: not spec['identities'] and spec['richness'] == 'context')
        followups = {}
        for group in ABLATIONS:
            name = parent+'-without-'+group
            row = json.loads(json.dumps(configurations[parent]))
            row['architecture']['features']['ablations'] = [group]
            followups[name] = row
        followup_path = output/'followups.json'
        choice = dict(parent=parent, configurations=followups, schedule=schedule(followups, config['seeds']))
        if followup_path.exists():
            if _read(followup_path) != json.loads(json.dumps(choice)):
                raise ValueError('Development selection changed')
        else:
            publish(followup_path, data(choice))
        configurations = {**configurations, **followups}
        for name, seed in choice['schedule']:
            learners.setdefault(name, []).append(train_one(name, configurations[name], seed, manifest, output, progress=progress))
            build_report(output)
        winners = {kind: choose(configurations, learners, lambda spec, enabled=enabled: spec['identities'] == enabled)
                   for kind, enabled in (('identity', True), ('no_vocabulary', False))}
        policies = {'heuristic': dict(kind='heuristic'), 'random_legal': dict(kind='random_legal')}
        for kind, name in winners.items():
            for row in learners[name]:
                policies[f'{kind}-{row["seed"]}'] = dict(checkpoint=row['checkpoint'],
                    sha256=row['checkpoint_sha256'], learner_seed=row['seed'], configuration_id=name)
        selection_path = output/'selection.json'
        selection = dict(winners=winners, policies=policies, manifest_sha256=_sha_file(output/'manifest.json'))
        if selection_path.exists():
            if _read(selection_path) != selection:
                raise ValueError('Finalist selection changed')
        else:
            publish(selection_path, data(selection))
        from .report import build_report
        build_report(output)
        if phase == 'run':
            return selection
    selection = _read(output/'selection.json')
    reservation = output/'test-reservation.json'
    if not reservation.exists():
        reserve_test(StudySource(manifest['source']), reservation, policies=selection['policies'],
            manifest_sha256=selection['manifest_sha256'], limits=LIMITS, execution_output=output/'test')
    evaluate(source_path=manifest['source'], output_dir=output/'test', checkpoints={}, split='test',
        modes=[('greedy', 0), ('sampled', 0), ('sampled', 1)], workers=config['collectors'], reservation=str(reservation),
        training_content=manifest['training_content'])
    from .report import build_report
    return build_report(output)

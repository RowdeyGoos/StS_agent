"""Real-engine combat corpus, exact matched starts and split-safe consumers."""
from dataclasses import replace
import json
import multiprocessing
from pathlib import Path
import pickle
import threading

import pytest
torch = pytest.importorskip('torch')
pytest.importorskip('gymnasium')

from game.agent.action_policy import COMMIT_DECISIONS
from game.agent.headless.adapter import HeadlessAdapter
from game.agent.recording import load_trajectory
from game.agent.training.benchmark_suite import data, digest
from game.agent.training.checkpoint import save_checkpoint, restore_ppo
from game.agent.training.combat_benchmark import evaluate_corpus
from game.agent.training.combat_corpus import (CombatCorpus, CorpusConfig, build_corpus,
    collect_corpus_demonstrations, public_digest, training_factory, elite_route)
from game.agent.training.demonstrations import corpus_pairs
from game.agent.training.features import Vocabulary
from game.agent.training.learner import ImitationLearner, load_corpus
from game.agent.training.model import ActorCritic, Architecture
from game.agent.training.ppo import PPOLearner
from game.agent.training.ppo_config import PPOExperiment
from game.agent.training.ppo_run import run_ppo
from game.agent.training.rollout import collect
from game.headless.run.engine import RunEngine
from .test_full_run_training import bundles
from .test_ppo import comparable
from .test_training_model import cpu_threads


@pytest.fixture
def corpus(tmp_path):
    path, report = build_corpus(tmp_path / 'corpus', CorpusConfig(1, 1, 1, max_decisions=32))
    assert report['status'] == 'complete'
    return CombatCorpus(path)


def test_genuine_campaign_roots_are_split_before_combat_capture(corpus):
    report = corpus.report
    assert len(report['campaigns']) == 6
    assert {r['region'] for r in report['cases']} == {'overgrowth', 'underdocks'}
    assert any(g['combats'] > 1 for g in report['campaigns'])
    assert all(g['status'] in ('cutoff', 'defeat', 'act1_cleared') for g in report['campaigns'])
    groups = [{r['source_group'] for r in corpus.split(s)} for s in ('train', 'validation', 'test')]
    assert not groups[0] & groups[1] and not groups[0] & groups[2] and not groups[1] & groups[2]
    assert 'start_index' not in json.dumps(report) and 'campaign_seeds' not in json.dumps(report)
    assert 'snapshot' not in json.dumps(report['cases'])
    assert corpus.private.stat().st_mode & 0o777 == 0o700
    assert all(p.stat().st_mode & 0o777 == 0o600 for p in corpus.private.iterdir())
    row = corpus.split('train')[0]
    a = corpus.restore(row['case_id'], split='train')
    b = corpus.restore(row['case_id'], split='train')
    original = b.snapshot()
    assert a is not b and a.snapshot() == original
    adapter = HeadlessAdapter(a, decision_profile='full_run_v2')
    frame = adapter.observe()
    assert public_digest(frame.decision) == row['public_state_sha256']
    adapter.step(frame.binding, frame.decision.candidates[0].ref)
    assert b.snapshot() == original
    assert a.state.current_node_id is not None


def test_generated_ppo_preset_uses_minibatch_64(corpus):
    ppo = PPOExperiment.load(corpus.path.parent / 'combat-ppo.json').ppo
    assert (ppo.batch_size, ppo.rollout_steps, ppo.epochs, ppo.episode_decisions) == (64, 4096, 2, 512)


def test_train_factory_never_opens_heldout_snapshots_and_is_spawn_safe(corpus, monkeypatch):
    experiment = PPOExperiment.load(corpus.path.parent / 'combat-ppo.json')
    factory = pickle.loads(pickle.dumps(training_factory(corpus.path, experiment)))
    forbidden = {r['case_id'] + '.start.json' for s in ('validation', 'test') for r in corpus.split(s)}
    original = Path.read_bytes
    def guarded(path):
        assert path.name not in forbidden
        return original(path)
    monkeypatch.setattr(Path, 'read_bytes', guarded)
    for name in experiment.encounters:
        with factory(encounter=name, reward_spec=experiment.training.reward) as env:
            env.reset(seed=17)
            first = env.public_state
            case = env.corpus_case
            env.reset(seed=17)
            assert env.public_state == first and env.corpus_case == case
            assert case['split'] == 'train'
    with pytest.raises(ValueError, match='bound'):
        training_factory(corpus.path, replace(experiment, source='wrong-source'))
    with pytest.raises(ValueError, match='another split'):
        corpus.restore(corpus.split('test')[0]['case_id'], split='train')


def test_public_case_relabelling_and_snapshot_tampering_are_rejected(corpus):
    original = corpus.path.read_bytes()
    report = json.loads(original)
    row = report['cases'][0]
    row['hp'] += 1
    corpus.path.write_bytes(data(report))
    with pytest.raises(ValueError, match='mapping'):
        CombatCorpus(corpus.path)
    corpus.path.write_bytes(original)
    key = corpus.split('train')[0]['case_id']
    path = corpus.private / (key + '.start.json')
    original = path.read_bytes()
    path.write_bytes(original + b' ')
    with pytest.raises(ValueError, match='digest'):
        corpus.restore(key, split='train')
    path.write_bytes(original)
    path.chmod(0o644)
    with pytest.raises(ValueError, match='owner-only'):
        corpus.restore(key, split='train')


def test_learner_and_direct_collection_cannot_relabel_the_corpus(corpus):
    experiment = PPOExperiment.load(corpus.path.parent / 'combat-ppo.json')
    factory = training_factory(corpus.path, experiment)
    model = ActorCritic(Vocabulary(()), Architecture(16,1), action_policy=COMMIT_DECISIONS)
    wrong = replace(experiment, source=experiment.source + '0')
    with pytest.raises(ValueError, match='bound'):
        PPOLearner(model, wrong, env_factory=factory)
    with pytest.raises(ValueError, match='bound'):
        PPOLearner(model, experiment, env_factory=lambda **_: None)
    with pytest.raises(ValueError, match='bound'):
        collect(model, wrong, torch.Generator(), cursor=0, iteration=0, env_factory=factory)


def test_restored_hidden_root_must_match_the_declared_campaign_group(corpus):
    row = corpus.split('train')[0]
    registry_path = corpus.private / 'registry.json'
    registry = json.loads(registry_path.read_bytes())
    registry['campaign_seeds'][row['source_group']] += 30_000
    registry_path.write_bytes(data(registry))
    report = corpus.report
    report['registry_sha256'] = digest(registry)
    corpus.path.write_bytes(data(report))
    rebound = CombatCorpus(corpus.path)
    with pytest.raises(ValueError, match='Frozen combat state'):
        rebound.restore(row['case_id'], split='train')


def test_interruption_keeps_predeclared_sources_without_retry(tmp_path):
    stopped = threading.Event()
    def progress(group, total):
        stopped.set()
    path, report = build_corpus(tmp_path / 'cancelled', CorpusConfig(1,1,1,max_decisions=4),
                                cancel=stopped, progress=progress)
    assert report['status'] == 'interrupted'
    assert len(report['campaigns']) == 6
    assert sum(g['status'] == 'unattempted' for g in report['campaigns']) == 4
    assert not (path.parent / 'combat-ppo.json').exists()
    with pytest.raises(ValueError, match='complete collection'):
        CombatCorpus(path)
    with pytest.raises(FileExistsError):
        build_corpus(path.parent, CorpusConfig(1,1,1,max_decisions=4))


def _collection_shape(report):
    order = {g['source_group']: i for i, g in enumerate(report['campaigns'])}
    campaigns = [{k: v for k, v in g.items() if k != 'source_group'} for g in report['campaigns']]
    cases = [dict({k: v for k, v in r.items() if k not in ('source_group', 'case_id', 'combat_id')},
                  campaign=order[r['source_group']]) for r in report['cases']]
    return campaigns, cases


@pytest.mark.parametrize('learned', [False, True])
def test_parallel_collection_matches_serial_campaigns(tmp_path, bundles, learned):
    config = CorpusConfig(2, 1, 1, max_decisions=32, route_policy='mixed_elites', capture_turns=3,
                          start_index=5000, record_planning=True)
    collector = bundles[1] if learned else None
    serial_path, serial = build_corpus(tmp_path / 'serial', config, checkpoint=collector)
    seen = []
    parallel_path, parallel = build_corpus(tmp_path / 'parallel', config, checkpoint=collector, workers=3,
                                           progress=lambda group, total: seen.append((group['source_group'], total)))
    assert serial['status'] == parallel['status'] == 'complete'
    assert serial['execution'] == {'workers': 1, 'schedule': 'serial_v1'}
    assert parallel['execution'] == {'workers': 3, 'schedule': 'parallel_campaigns_v1'}
    assert serial['collector'] == parallel['collector']
    assert _collection_shape(serial) == _collection_shape(parallel)
    assert serial['coverage'] == parallel['coverage']
    assert sorted(seen) == sorted((g['source_group'], 8) for g in parallel['campaigns'])
    left, right = CombatCorpus(serial_path), CombatCorpus(parallel_path)
    assert ([left.registry[r['case_id']]['snapshot_sha256'] for r in serial['cases']] ==
            [right.registry[r['case_id']]['snapshot_sha256'] for r in parallel['cases']])
    assert all(p.stat().st_mode & 0o777 == 0o600 for p in right.private.iterdir())
    assert not list(right.private.glob('*.partial')) and not list(right.path.parent.glob('*.partial'))
    assert not [p for p in multiprocessing.active_children() if p.name.startswith('sts-')]


def test_parallel_cancellation_keeps_predeclared_sources_without_retry(tmp_path):
    stopped = threading.Event()
    path, report = build_corpus(tmp_path / 'cancelled', CorpusConfig(1, 1, 1, max_decisions=4), cancel=stopped,
                                progress=lambda group, total: stopped.set(), workers=2)
    assert report['status'] == 'interrupted'
    assert len(report['campaigns']) == 6
    assert sum(g['status'] == 'unattempted' for g in report['campaigns']) >= 3
    assert sum(g['starts'] for g in report['campaigns']) == len(report['cases'])
    assert not (path.parent / 'combat-ppo.json').exists()
    with pytest.raises(ValueError, match='complete collection'):
        CombatCorpus(path)
    assert not [p for p in multiprocessing.active_children() if p.name.startswith('sts-')]


def test_collector_changed_after_planning_stops_parallel_collection(tmp_path, bundles, monkeypatch):
    from game.agent.training import checkpoint
    collector = bundles[1]
    original = checkpoint.publish
    def publish(path, value, **kwargs):
        sha = original(path, value, **kwargs)
        if Path(path).name == 'campaigns.json':
            collector.write_bytes(collector.read_bytes() + b'changed')
        return sha
    monkeypatch.setattr(checkpoint, 'publish', publish)
    path, report = build_corpus(tmp_path / 'changed', CorpusConfig(1, 1, 1, max_decisions=4),
                                checkpoint=collector, workers=2)
    assert report['status'] == 'failed'
    assert all(g['status'] == 'unattempted' for g in report['campaigns']) and not report['cases']
    with pytest.raises(ValueError, match='complete collection'):
        CombatCorpus(path)
    with pytest.raises(ValueError, match='workers'):
        build_corpus(tmp_path / 'too-many', CorpusConfig(1, 1, 1, max_decisions=4), workers=17)
    assert not [p for p in multiprocessing.active_children() if p.name.startswith('sts-')]


def test_room_kind_filter_is_reported_and_bound_to_the_test_lock(corpus, tmp_path):
    arguments = dict(corpus_path=corpus.path, max_decisions=2)
    with pytest.raises(ValueError, match='room kinds'):
        evaluate_corpus(output_dir=tmp_path/'bad', room_kinds=('hallway',), **arguments)
    with pytest.raises(ValueError, match='room kinds'):
        evaluate_corpus(output_dir=tmp_path/'repeated', room_kinds=('boss', 'boss'), **arguments)
    with pytest.raises(ValueError, match='No combat cases'):
        evaluate_corpus(output_dir=tmp_path/'empty', room_kinds=('boss',), **arguments)
    _, report = evaluate_corpus(output_dir=tmp_path/'combat', room_kinds=('combat',), **arguments)
    assert report['status'] == 'complete' and report['room_kinds'] == ['combat']
    assert {r['room_kind'] for r in report['episodes']} == {'combat'}
    assert 'combat' not in report['balanced'] and report['balanced']['draws'] == 2000
    _, test = evaluate_corpus(output_dir=tmp_path/'test', split='test', room_kinds=('combat',), **arguments)
    assert test['status'] == 'complete'
    with pytest.raises(ValueError, match='locked'):
        evaluate_corpus(output_dir=tmp_path/'test-all-kinds', split='test', **arguments)


def test_balanced_win_rates_weight_encounters_equally_with_paired_campaign_resampling():
    from game.agent.training.comparison import balanced
    rows = []
    def add(policy, case, group, encounter, outcome, status='terminated'):
        rows.append({'policy': policy, 'case_id': case, 'source_group': group, 'room_kind': 'boss',
                     'encounter': encounter, 'status': status,
                     'combat': {'outcome': outcome} if outcome else None})
    for index in range(4):
        add('learned', f'c{index}', f'g{index}', 'common_boss', 'victory')
        add('heuristic', f'c{index}', f'g{index}', 'common_boss', 'defeat')
    add('learned', 'rare', 'g4', 'rare_boss', 'defeat')
    add('heuristic', 'rare', 'g4', 'rare_boss', 'victory')
    add('learned', 'failed', 'g5', 'rare_boss', None, status='failed')
    add('heuristic', 'failed', 'g5', 'rare_boss', 'victory')
    result = balanced(rows, ['heuristic', 'learned'])
    assert result == balanced(rows, ['heuristic', 'learned'])
    boss = result['boss']
    assert boss['encounters']['common_boss'] == {'fights': 4, 'win_rate': {'heuristic': 0., 'learned': 1.}}
    assert boss['encounters']['rare_boss'] == {'fights': 2, 'win_rate': {'heuristic': 1., 'learned': 0.}}
    assert boss['win_rate']['learned']['estimate'] == boss['win_rate']['heuristic']['estimate'] == .5
    assert 'elite' not in result
    forward, backward = boss['paired']['learned']['heuristic'], boss['paired']['heuristic']['learned']
    assert forward['difference'] == backward['difference'] == 0.
    assert forward['interval_95'] == pytest.approx([-b for b in reversed(backward['interval_95'])])
    low, high = boss['win_rate']['learned']['interval_95']
    assert 0 <= low <= .5 <= high <= 1
    json.loads(data(result))


def _public(run):
    return public_digest(HeadlessAdapter(run, decision_profile='full_run_v2').observe().decision)


def _exact(run):
    return json.dumps(run.snapshot(), ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode()


def test_hidden_resampling_keeps_public_state_and_a_restorable_engine(tactical_corpus):
    from game.headless.run.hidden import resample_hidden_combat
    from game.headless.run.snapshots import restore_run
    from game.agent.training.rewards import strict_json
    corpus = tactical_corpus
    rows = corpus.split('train')
    assert {r['start_kind'] for r in rows} == {'opening', 'continuation'}
    for row in rows:
        original = _exact(corpus.restore(row['case_id'], split='train'))
        variants = set()
        for seed in range(3):
            run = corpus.restore(row['case_id'], split='train')
            before = sorted(c.instance_id for c in run.combat.player.deck.draw_pile)
            resample_hidden_combat(run, seed)
            assert sorted(c.instance_id for c in run.combat.player.deck.draw_pile) == before
            assert _public(run) == row['public_state_sha256']
            raw = _exact(run)
            assert _exact(restore_run(strict_json(raw))) == raw
            repeated = corpus.restore(row['case_id'], split='train')
            resample_hidden_combat(repeated, seed)
            assert _exact(repeated) == raw
            variants.add(raw)
        assert original not in variants and len(variants) == 3
    row = next(r for r in rows if r['start_kind'] == 'opening')
    successors = set()
    for seed in range(8):
        run = corpus.restore(row['case_id'], split='train')
        resample_hidden_combat(run, seed)
        adapter = HeadlessAdapter(run, decision_profile='full_run_v2')
        frame = adapter.observe()
        end = next(a for a in frame.decision.candidates if a.kind == 'end_turn')
        assert adapter.step(frame.binding, end.ref).status == 'reconciled'
        successors.add(_exact(run))
    assert len(successors) > 1
    with pytest.raises(ValueError, match='active native combat'):
        resample_hidden_combat(RunEngine.campaign(character='ironclad', seed=3), 1)
    with pytest.raises(ValueError, match='nonnegative'):
        resample_hidden_combat(corpus.restore(row['case_id'], split='train'), -1)


def test_hidden_resampling_keeps_enchantment_owned_draw_positions(corpus):
    from game.headless.enchantments.base import EnchantmentInstance
    from game.headless.run.hidden import resample_hidden_combat
    row = next(r for r in corpus.split('train') if r['start_kind'] == 'opening')
    run = corpus.restore(row['case_id'], split='train')
    pile = run.combat.player.deck.draw_pile
    assert len(pile) >= 4
    pile[0].enchantment = EnchantmentInstance('imbued')
    pile[2].enchantment = EnchantmentInstance('perfect_fit')
    pinned = {0: pile[0], 2: pile[2]}
    orders = set()
    for seed in range(6):
        resample_hidden_combat(run, seed)
        assert all(pile[index] is card for index, card in pinned.items())
        orders.add(tuple(c.instance_id for c in pile))
    assert len(orders) > 1


def test_resampled_corpus_training_is_bound_and_reproducible(corpus):
    from game.agent.training.combat_corpus import validate_factory
    from game.agent.training.ppo_config import RESAMPLED_HIDDEN_STATE
    base = PPOExperiment.load(corpus.path.parent / 'combat-ppo.json')
    resampled = replace(base, hidden_state=RESAMPLED_HIDDEN_STATE)
    assert 'hidden_state' not in base.to_dict() and PPOExperiment.from_dict(base.to_dict()) == base
    assert resampled.to_dict()['hidden_state'] == RESAMPLED_HIDDEN_STATE and resampled.identity != base.identity
    assert PPOExperiment.from_dict(resampled.to_dict()) == resampled
    with pytest.raises(ValueError, match='Omit hidden_state'):
        PPOExperiment.from_dict(dict(base.to_dict(), hidden_state='frozen'))
    with pytest.raises(ValueError, match='Invalid'):
        replace(base, hidden_state='shuffled')
    with pytest.raises(ValueError, match='Hidden-state'):
        PPOExperiment(hidden_state=RESAMPLED_HIDDEN_STATE)
    frozen = training_factory(corpus.path, base)
    factory = pickle.loads(pickle.dumps(training_factory(corpus.path, resampled)))
    assert factory.hidden_state == RESAMPLED_HIDDEN_STATE
    for experiment, owner in ((resampled, frozen), (base, factory), (resampled, None)):
        with pytest.raises(ValueError, match='hidden-state'):
            validate_factory(experiment, owner)
    for name in base.encounters:
        starts = {}
        for label, owner in (('frozen', frozen), ('resampled', factory)):
            snapshots = []
            for _ in range(2):
                with owner(encounter=name, reward_spec=base.training.reward) as env:
                    env.reset(seed=23)
                    case = env.corpus_case
                    assert public_digest(env.public_state) == case['public_state_sha256']
                    snapshots.append(_exact(env._adapter._engine))
            assert snapshots[0] == snapshots[1]
            starts[label] = snapshots[0]
        assert starts['frozen'] == _exact(corpus.restore(case['case_id'], split='train'))
        assert starts['resampled'] != starts['frozen']


def test_resampled_ppo_records_its_treatment_and_rejects_a_changed_resume(tactical_corpus, tmp_path):
    corpus = tactical_corpus
    bundle = make_model(corpus, tmp_path)
    experiment = PPOExperiment.load(corpus.path.parent / 'combat-ppo.json')
    experiment = replace(experiment, hidden_state='resampled_v1', ppo=replace(
        experiment.ppo, rollout_steps=8, episode_decisions=2, batch_size=4, epochs=1))
    factory = training_factory(corpus.path, experiment)
    _, report = run_ppo(checkpoint=bundle, experiment=experiment, env_factory=factory,
                        output_dir=tmp_path/'ppo', decisions=8, workers=2)
    assert report['status'] == 'complete', report
    audits = list((tmp_path/'ppo-private').rglob('*.audit.json'))
    assert audits and all(json.loads(p.read_text())['experiment']['hidden_state'] == 'resampled_v1' for p in audits)
    frozen = replace(experiment, hidden_state='frozen')
    with pytest.raises(ValueError):
        restore_ppo(tmp_path/'ppo/final.sts-model', tmp_path/'ppo-private/final.resume.pt',
                    experiment=frozen, env_factory=training_factory(corpus.path, frozen))
    assert not [p for p in multiprocessing.active_children() if p.name.startswith('sts-')]


def make_model(corpus, tmp_path):
    root = tmp_path / 'demonstrations'
    _, report = collect_corpus_demonstrations(corpus_path=corpus.path, output_dir=root,
                                              max_decisions=2)
    assert report['status'] == 'complete'
    pairs = corpus_pairs(root, split='train')
    training = load_corpus(pairs, split='train', action_policy=COMMIT_DECISIONS)
    learner = ImitationLearner(ActorCritic(training.vocabulary, Architecture(16,1),
                                         action_policy=COMMIT_DECISIONS), training)
    bundle = tmp_path / 'model.sts-model'
    save_checkpoint(bundle, learner)
    return bundle


def test_corpus_demonstrations_and_parallel_ppo_resume(tactical_corpus, tmp_path):
    corpus = tactical_corpus
    with pytest.raises(ValueError, match='Held-out'):
        collect_corpus_demonstrations(corpus_path=corpus.path, output_dir=tmp_path/'bad', split='test')
    bundle = make_model(corpus, tmp_path)
    experiment = PPOExperiment.load(corpus.path.parent / 'combat-ppo.json')
    experiment = replace(experiment, ppo=replace(experiment.ppo, rollout_steps=8, episode_decisions=2,
                                               batch_size=4, epochs=1))
    factory = training_factory(corpus.path, experiment)
    _, report = run_ppo(checkpoint=bundle, experiment=experiment, env_factory=factory,
                        output_dir=tmp_path/'ppo', decisions=8, workers=2)
    assert report['status'] == 'complete', report
    episodes = report['iterations'][0]['collection']['episodes']
    assert sum(r['steps'] for r in episodes) == 8
    for row in episodes:
        assert corpus.cases[row['case_id']]['split'] == 'train'
        assert row['evidence'] == 'headless_rollout'
        assert row['encounter'] == corpus.cases[row['case_id']]['encounter']
        assert row['start_kind'] == corpus.cases[row['case_id']]['start_kind']
    with restore_ppo(tmp_path/'ppo/final.sts-model', tmp_path/'ppo-private/final.resume.pt',
                     experiment=experiment, env_factory=factory, workers=2) as learner:
        assert learner.decisions == 8
        continuation = learner.collect(decisions=8)
        assert all(corpus.cases[r['case_id']]['split'] == 'train' for r in continuation.progress['episodes'])
    with restore_ppo(tmp_path/'ppo/final.sts-model', tmp_path/'ppo-private/final.resume.pt',
                     env_factory=factory) as repeated:
        assert comparable(continuation) == comparable(repeated.collect(decisions=8))
    with pytest.raises(ValueError, match='bound'):
        restore_ppo(tmp_path/'ppo/final.sts-model', tmp_path/'ppo-private/final.resume.pt',
                    env_factory=replace(factory, identity=factory.identity + '0'))
    assert not [p for p in multiprocessing.active_children() if p.name.startswith('sts-')]


@pytest.mark.parametrize('workers', [2, 16])
def test_matched_benchmark_parallel_parity_and_test_lock(corpus, tmp_path, workers):
    bundle = make_model(corpus, tmp_path)
    arguments = dict(corpus_path=corpus.path, checkpoints={'combat':bundle}, max_decisions=2)
    _, serial = evaluate_corpus(output_dir=tmp_path/'serial', **arguments)
    _, parallel = evaluate_corpus(output_dir=tmp_path/'parallel', workers=workers, **arguments)
    assert serial['status'] == parallel['status'] == 'complete'
    assert serial['summary'] == parallel['summary']
    for left, right in zip(serial['episodes'], parallel['episodes']):
        assert left['public_state_sha256'] == right['public_state_sha256']
        assert left['start_sha256'] == right['start_sha256']
        assert left['public_state_sha256'] == corpus.cases[left['case_id']]['public_state_sha256']
        a = load_trajectory(tmp_path/'serial'/left['trajectory'])
        b = load_trajectory(tmp_path/'parallel'/right['trajectory'])
        assert a.initial == b.initial
        assert a.transitions == b.transitions
    for row in serial['episodes']:
        key = row['case_id']
        assert len({r['start_sha256'] for r in serial['episodes'] if r['case_id'] == key}) == 1
    _, test = evaluate_corpus(output_dir=tmp_path/'test', split='test', **arguments)
    assert test['status'] == 'complete'
    with pytest.raises(ValueError, match='closed'):
        evaluate_corpus(output_dir=tmp_path/'late-dev', **arguments)
    with pytest.raises(ValueError, match='locked'):
        evaluate_corpus(corpus_path=corpus.path, output_dir=tmp_path/'changed-test',
                        split='test', checkpoints={'renamed':bundle}, max_decisions=2)
    assert not [p for p in multiprocessing.active_children() if p.name.startswith('sts-')]


@pytest.mark.parametrize('workers', [1, 2])
def test_failed_source_keeps_all_benchmark_denominators(corpus, tmp_path, workers):
    case = corpus.split('validation')[0]
    (corpus.private/(case['case_id']+'.start.json')).write_text('{}')
    _, report = evaluate_corpus(corpus_path=corpus.path, output_dir=tmp_path/'failed', max_decisions=2,
                                workers=workers)
    assert report['status'] == 'failed'
    assert all(s['planned'] == len(corpus.split('validation')) for s in report['summary'].values())
    assert report['summary']['heuristic']['failures'] == 1
    assert report['summary']['random_legal']['unattempted'] >= len(corpus.split('validation')) - 1
    assert not [p for p in multiprocessing.active_children() if p.name.startswith('sts-')]


@pytest.mark.parametrize('workers', [1, 2])
def test_postplan_startup_failure_and_cancellation_keep_planned_population(corpus, tmp_path, monkeypatch, workers):
    from game.agent.training import checkpoint
    bundle = make_model(corpus, tmp_path)
    stopped = threading.Event()
    stopped.set()
    _, report = evaluate_corpus(corpus_path=corpus.path, output_dir=tmp_path/'cancel',
        checkpoints={'combat':bundle}, max_decisions=2, workers=workers, cancel=stopped)
    assert report['status'] == 'interrupted'
    assert all(s['unattempted'] == s['planned'] for s in report['summary'].values())
    original = checkpoint.publish
    def publish(path, value, **kwargs):
        sha = original(path, value, **kwargs)
        if path.name == 'combat-plan.json':
            bundle.write_bytes(bundle.read_bytes() + b'changed')
        return sha
    monkeypatch.setattr(checkpoint, 'publish', publish)
    _, report = evaluate_corpus(corpus_path=corpus.path, output_dir=tmp_path/'changed',
        checkpoints={'combat':bundle}, max_decisions=2, workers=workers)
    assert report['status'] == 'failed' and report['failure'] == 'ValueError'
    assert all(s['unattempted'] == s['planned'] for s in report['summary'].values())
    assert not [p for p in multiprocessing.active_children() if p.name.startswith('sts-')]


def test_combat_benchmark_accepts_existing_campaign_actor_without_reusing_its_critic(corpus, tmp_path, bundles):
    _, report = evaluate_corpus(corpus_path=corpus.path, output_dir=tmp_path/'campaign-actor',
        checkpoints={'combat':bundles[0], 'act1':bundles[1]}, max_decisions=2, workers=2)
    assert report['status'] == 'complete'
    assert report['checkpoints']['act1']['training_reward']['schema'] == 'sts_full_run_reward_v1'
    assert report['reward_spec']['schema'] == 'sts_training_reward_v1'
    assert report['paired_checkpoints']['act1']['combat']['cases'] == len(corpus.split('validation'))


@pytest.fixture
def tactical_corpus(tmp_path):
    path, report = build_corpus(tmp_path / 'tactical', CorpusConfig(2, 1, 1, max_decisions=32,
                                route_policy='mixed_elites', capture_turns=4))
    assert report['status'] == 'complete'
    return CombatCorpus(path)


def test_later_turns_replay_from_the_same_genuine_fight(tactical_corpus):
    from game.agent import contracts as c
    from game.agent.full_policy import choose_action
    from game.headless.run.snapshots import restore_run
    corpus = tactical_corpus
    assert {r['route_policy'] for r in corpus.report['campaigns']} == {'collector', 'elite_first'}
    cases = corpus.split('train')
    later = next(r for r in cases if r['start_kind'] == 'continuation')
    opening = next(r for r in cases if r['combat_id'] == later['combat_id'] and r['start_kind'] == 'opening')
    run = corpus.restore(opening['case_id'], split='train')
    adapter = HeadlessAdapter(run, decision_profile='full_run_v2')
    for _ in range(32):
        frame = adapter.observe()
        assert not isinstance(frame, c.RunOutcome)
        if run.combat.turn == later['turn']:
            break
        action = choose_action(frame.decision)
        assert adapter.step(frame.binding, action.ref).status == 'reconciled'
    else:
        pytest.fail('The captured continuation must be reached by the declared collector')
    fresh = HeadlessAdapter(restore_run(run.snapshot()), decision_profile='full_run_v2')
    assert public_digest(fresh.observe().decision) == later['public_state_sha256']
    restored = corpus.restore(later['case_id'], split='train')
    assert restored.snapshot() == run.snapshot()
    coverage = corpus.report['coverage']['train']
    assert coverage['combats'] == len({r['combat_id'] for r in cases})
    assert coverage['starts'] > coverage['combats']
    assert sum(coverage['by_threat'].values()) == coverage['starts']
    assert not ({r['combat_id'] for r in cases} & {r['combat_id'] for r in corpus.split('validation')})


def test_frozen_potion_powers_preserve_public_order_after_json_serialization():
    from game.agent.contracts import full as f
    from game.agent.training.combat_corpus import _freeze_start
    from game.headless.run.engine import RunEngine
    from game.headless.run.inventory import add_potion
    from game.headless.run.snapshots import restore_run
    run = RunEngine(seed=4, card_ids=('defend',) * 5, rng_profile='native')
    for name in ('liquid_bronze', 'regen_potion'):
        add_potion(run.state, name)
    run.start_combat(encounter_id='overgrowth_vantom')
    adapter = HeadlessAdapter(run, decision_profile=f.PROFILE)
    for name in ('liquid_bronze', 'regen_potion'):
        frame = adapter.observe()
        nodes = {n.ref: n for root in (frame.decision.run, frame.decision.context) for n in f.walk(root) if n.ref}
        action = next(a for a in frame.decision.candidates if a.kind == 'use_potion' and nodes[a.subject].definition_id == name)
        assert adapter.step(frame.binding, action.ref).status == 'reconciled'
    live_copy = HeadlessAdapter(restore_run(run.snapshot()), decision_profile=f.PROFILE).observe().decision
    sorted_copy = HeadlessAdapter(restore_run(json.loads(data(run.snapshot()))), decision_profile=f.PROFILE).observe().decision
    assert live_copy != sorted_copy  # The original failure: thorns/regen reorder.
    raw, restored, frozen = _freeze_start(run)
    assert frozen == live_copy
    persisted = HeadlessAdapter(restore_run(json.loads(raw)), decision_profile=f.PROFILE).observe().decision
    assert persisted == live_copy and restored.snapshot() == run.snapshot()


def test_elite_route_uses_public_paths_not_only_the_next_room():
    from game.agent.contracts import full as f
    from game.agent.headless.full_projection import node
    graph = node('map', children=(
        node('node', 'combat', ref='node:0', links=(('next_nodes', ('node:2',)),)),
        node('node', 'rest', ref='node:1', links=(('next_nodes', ()),)),
        node('node', 'elite', ref='node:2', links=(('next_nodes', ()),))))
    actions = (f.Candidate('action:0', 'choose_map_node', 'node:1'),
               f.Candidate('action:1', 'choose_map_node', 'node:0'))
    decision = f.PublicDecision(f.SCHEMA, f.PROFILE, node('run', children=(graph,)), node('map'), actions)
    assert elite_route(decision) is actions[1]
    assert elite_route(replace(decision, candidates=(f.Candidate('action:0', 'end_turn'),))) is None


def test_opening_selection_retains_threat_and_hidden_context_is_unavailable():
    from game.agent.training.combat_corpus import _describe
    from game.agent.contracts import full as f
    from game.headless.run.engine import RunEngine
    run = RunEngine(seed=4, card_ids=('strike', 'defend'), rng_profile='native')
    run.obtain_relic('toolbox')
    run.start_combat(encounter_id='overgrowth_vantom')
    frame = HeadlessAdapter(run, decision_profile='full_run_v2').observe()
    # Toolbox is a nested combat selection: enemy intents remain public.
    assert frame.decision.context.kind == 'combat'
    assert _describe(run, frame.decision)['incoming_damage'] == 7
    # If a different context hides that graph, absence is not zero damage.
    description = _describe(run, replace(frame.decision, context=f.Node('relic_choice', 'select')))
    assert description['incoming_damage'] is description['block'] is None
    assert description['threat'] == 'unavailable'


def test_tactical_sampling_and_heldout_isolation(tactical_corpus, monkeypatch):
    corpus = tactical_corpus
    experiment = PPOExperiment.load(corpus.path.parent / 'combat-ppo.json')
    factory = training_factory(corpus.path, experiment)
    forbidden = {r['case_id'] + '.start.json' for s in ('validation', 'test') for r in corpus.split(s)}
    original = Path.read_bytes
    def guarded(path):
        assert path.name not in forbidden
        return original(path)
    monkeypatch.setattr(Path, 'read_bytes', guarded)
    selected = []
    with factory(encounter='combat', reward_spec=experiment.training.reward) as env:
        for seed in range(24):
            env.reset(seed=seed)
            selected.append(env.corpus_case)
            assert env.public_state.context.get('round') == env.corpus_case['turn']
            assert env.corpus_case['room_kind'] == 'combat'
    assert {r['start_kind'] for r in selected} == {'opening', 'continuation'}
    assert set(experiment.encounters) <= {'combat', 'elite', 'boss'}
    assert all(r['split'] == 'train' for r in selected)


def test_continuations_cannot_be_reassigned_to_another_campaign(tactical_corpus):
    corpus = tactical_corpus
    report = json.loads(corpus.path.read_bytes())
    registry = json.loads((corpus.private / 'registry.json').read_bytes())
    later = next(r for r in report['cases'] if r['start_kind'] == 'continuation')
    other = next(r for r in report['cases'] if r['source_group'] != later['source_group'])
    later['combat_id'] = other['combat_id']
    registry['cases'][later['case_id']]['case'] = later
    report['registry_sha256'] = digest(registry)
    corpus.path.write_bytes(data(report))
    (corpus.private / 'registry.json').write_bytes(data(registry))
    with pytest.raises(ValueError, match='cross-source'):
        CombatCorpus(corpus.path)


def test_benchmark_separates_whole_fights_and_continuations(tactical_corpus, tmp_path):
    corpus = tactical_corpus
    args = dict(corpus_path=corpus.path, max_decisions=2)
    _, openings = evaluate_corpus(output_dir=tmp_path / 'openings', **args)
    assert openings['status'] == 'complete'
    assert {r['start_kind'] for r in openings['episodes']} == {'opening'}
    assert openings['summary']['heuristic']['planned'] == corpus.report['coverage']['validation']['combats']
    assert openings['coverage']['starts'] == openings['summary']['heuristic']['planned']
    assert openings['corpus_coverage']['starts'] > openings['coverage']['starts']
    _, continuations = evaluate_corpus(output_dir=tmp_path / 'later', start_kind='continuation', workers=2, **args)
    assert continuations['status'] == 'complete'
    assert {r['start_kind'] for r in continuations['episodes']} == {'continuation'}
    assert continuations['coverage']['starts'] == continuations['summary']['heuristic']['planned']
    assert continuations['coverage']['openings'] == 0 and continuations['coverage']['combats'] > 0
    assert sum(v['summary']['heuristic']['planned'] for v in continuations['by_threat'].values()) == continuations['summary']['heuristic']['planned']
    evaluate_corpus(output_dir=tmp_path / 'test', split='test', **args)
    with pytest.raises(ValueError, match='locked'):
        evaluate_corpus(output_dir=tmp_path / 'test-later', split='test', start_kind='all', **args)

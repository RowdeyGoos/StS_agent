"""One public feature view through search teaching, learning and deployment."""
from dataclasses import replace
import gzip
import hashlib
import json
import zipfile

import pytest

torch = pytest.importorskip('torch')
pytest.importorskip('gymnasium')
from game.agent.contracts import full as f
from game.agent.input_views import RAW, DETACHED_HISTORY as VIEW, apply_view, planning_view
from game.agent.recording import load_trajectory
from game.agent.search import SearchConfig, SearchPolicy
from game.agent.training.checkpoint import load_policy, save_checkpoint, restore_learner
from game.agent.training.combat_features import GRAPH, COMBAT, SET_MLP
from game.agent.training.features import FeatureEncoder, Vocabulary, _RolloutEncoder
from game.agent.training.learner import Corpus, Example, ImitationLearner, load_corpus
from game.agent.training.model import ActorCritic, Architecture, collate, policy_statistics
from game.agent.training.rollout import fingerprint
from game.agent.training.search_run import OBJECTIVE, run_search, distill_search, reanalyse_search, load_search_corpus
from .test_training_model import decision, cpu_threads
from .test_search_training import checkpoint


def historical_decision(subject='card:0'):
    public = decision()
    events = (f.Node('history_event', 'play_card', links=(
        f.Link('history_subject', (subject,)), f.Link('history_target', ('enemy:0',)))),
        f.Node('history_event', 'use_potion', links=(f.Link('history_subject', ('potion:0',)),)))
    return replace(public, run=replace(public.run, children=(*public.run.children,
                   f.Node('history', 'history', children=events))))


def viewed_learner():
    public = historical_decision()
    vocabulary = Vocabulary.fit([public], split='train', include_catalog=False)
    encoder = FeatureEncoder(vocabulary, input_view=VIEW)
    example = Example(encoder.encode(public), 0, 1.05, (.1, .2, .3, .4))
    corpus = Corpus((example,), vocabulary, OBJECTIVE, 'controlled_view_corpus', 'train', 1, 0., input_view=VIEW)
    return ImitationLearner(ActorCritic(vocabulary, Architecture(16, 1), seed=7, input_view=VIEW), corpus)


@pytest.mark.parametrize('representation', [GRAPH, COMBAT, SET_MLP])
def test_view_removes_only_historical_card_links_and_has_identical_features(representation):
    public, ambiguous = historical_decision(), historical_decision('card:1')
    before = f.to_dict(public)
    normalized = planning_view(public)
    assert normalized == planning_view(ambiguous) == planning_view(normalized)
    assert f.to_dict(public) == before
    assert normalized.context is public.context and normalized.candidates is public.candidates
    history = normalized.run.children[-1]
    assert history.children[0].links[0].targets == ()
    assert history.children[0].links[1].targets == ('enemy:0',)
    assert history.children[1].links[0].targets == ('potion:0',)
    vocab = Vocabulary.fit([public], split='train', include_catalog=False)
    raw = FeatureEncoder(vocab, representation=representation)
    viewed = FeatureEncoder(vocab, representation=representation, input_view=VIEW)
    teacher = collate([raw.encode(normalized)], vocabulary=vocab)
    student_state = viewed.encode(public)
    student = collate([student_state], vocabulary=vocab)
    assert student.pop('input_view').item() == 1
    assert teacher.keys() == student.keys()
    assert all(torch.equal(teacher[k], student[k]) for k in teacher)
    assert viewed.identity != raw.identity
    # PPO's cached original graph must not bypass the checkpoint's view.
    prepared = _RolloutEncoder(viewed)
    prepared.encode(public)
    cached = collate([prepared.features_for(public).for_rollout()], vocabulary=vocab)
    assert cached['input_view'].item() == 1
    assert all(torch.equal(student[k], cached[k]) for k in student)


def test_bundle_view_round_trip_and_exact_imitation_resume(tmp_path):
    learner = viewed_learner()
    learner.step()
    bundle, private = tmp_path/'public/model.sts-model', tmp_path/'private/model.resume.pt'
    save_checkpoint(bundle, learner, resume_path=private)
    loaded = load_policy(bundle)
    assert loaded.manifest['schema'] == 'sts_inference_bundle_v4'
    assert loaded.model.input_view == loaded.encoder.input_view == VIEW
    assert loaded.probabilities(historical_decision()) == loaded.probabilities(historical_decision('card:1'))
    resumed = restore_learner(bundle, private, learner.corpus)
    for _ in range(2):
        left, right = learner.step(), resumed.step()
        assert {k:v for k,v in left.items() if k != 'seconds'} == {k:v for k,v in right.items() if k != 'seconds'}
    assert all(torch.equal(v, resumed.model.state_dict()[k]) for k,v in learner.model.state_dict().items())
    with pytest.raises(ValueError, match='input view'):
        restore_learner(bundle, private, replace(learner.corpus, input_view=RAW))
    with pytest.raises(ValueError, match='input view'):
        SearchPolicy(loaded)
    assert SearchPolicy(loaded, SearchConfig(model_version='direct_belief_v1')).input_view == VIEW
    from game.agent.tracking.records import bundle as inspect_bundle
    assert inspect_bundle(bundle, hashlib.sha256(bundle.read_bytes()).hexdigest())['input_view'] == VIEW


@pytest.mark.parametrize('change', ['missing', 'unknown', 'raw', 'legacy', 'feature'])
def test_inference_view_tampering_rejects(tmp_path, change):
    path = tmp_path/'source.sts-model'
    save_checkpoint(path, viewed_learner())
    with zipfile.ZipFile(path) as z:
        manifest, weights = json.loads(z.read('manifest.json')), z.read('weights.pt')
    if change == 'missing':
        manifest.pop('input_view')
    elif change in ('unknown', 'raw'):
        manifest['input_view'] = RAW if change == 'raw' else 'unknown'
    elif change == 'legacy':
        manifest['schema'] = 'sts_inference_bundle_v3'
    else:
        manifest['feature_identity'] = 'wrong'
    corrupt = tmp_path/'corrupt.sts-model'
    with zipfile.ZipFile(corrupt, 'w') as z:
        z.writestr('manifest.json', json.dumps(manifest))
        z.writestr('weights.pt', weights)
    with pytest.raises(ValueError):
        load_policy(corrupt)


def test_mixed_view_batches_corpora_and_behavior_identities_reject():
    learner = viewed_learner()
    state = learner.corpus.examples[0].state
    raw_model = ActorCritic(learner.model.vocabulary, learner.model.architecture)
    raw_model.load_state_dict(learner.model.state_dict())
    assert fingerprint(raw_model) != fingerprint(learner.model)
    with pytest.raises(ValueError, match='input view'):
        ImitationLearner(raw_model, learner.corpus)
    with pytest.raises(ValueError, match='input view'):
        collate([state, replace(state, input_view=RAW)], vocabulary=learner.model.vocabulary)
    with pytest.raises(ValueError, match='input view'):
        raw_model(collate([state], vocabulary=learner.model.vocabulary))
    with pytest.raises(ValueError, match='input view'):
        learner.model(collate([replace(state, input_view=RAW)], vocabulary=learner.model.vocabulary))
    with pytest.raises(ValueError, match='input view'):
        apply_view(historical_decision(), 'future')


def test_history_dependent_action_restriction_cannot_be_silently_widened():
    from game.agent.action_policy import COMMIT_SINGLE_CARD, COMMIT_DECISIONS
    from game.agent.training.checkpoint import CheckpointPolicy
    from game.agent.contracts import RunOutcome, ContractError
    vocabulary = viewed_learner().model.vocabulary
    for factory in (FeatureEncoder, ActorCritic):
        with pytest.raises(ValueError, match='commit_single_card_v1'):
            factory(vocabulary, input_view=VIEW, action_policy=COMMIT_SINGLE_CARD)
    base = CheckpointPolicy(ActorCritic(vocabulary, action_policy=COMMIT_SINGLE_CARD), OBJECTIVE, 'fixture', {})
    with pytest.raises(ValueError, match='commit_single_card_v1'):
        SearchPolicy(base, SearchConfig(model_version='direct_belief_v1'))
    encoder = FeatureEncoder(vocabulary, input_view=VIEW, action_policy=COMMIT_DECISIONS)
    with pytest.raises(ContractError, match='Terminal'):
        encoder.encode(RunOutcome('sts_run_outcome_v1', 'defeat', 'none'))


def direct_collection(checkpoint, output, **kwargs):
    return run_search(checkpoint=checkpoint, output_dir=output,
        search=SearchConfig(model_version='direct_belief_v1', simulations=4, max_depth=4,
                            time_limit=10, belief_particles=2),
        cases=1, split='train', collect=True, max_decisions=3, **kwargs)


def test_direct_collection_student_reanalysis_and_second_round_share_inputs(checkpoint, tmp_path):
    path, report = direct_collection(checkpoint, tmp_path/'collection', workers=2)
    assert report['status'] == 'complete' and report['schema'] == 'sts_search_report_v2'
    assert report['planning_view'] == VIEW
    row = report['episodes'][0]
    original = load_policy(checkpoint)
    corpus = load_search_corpus(path, original)
    assert corpus.input_view == VIEW
    assert all(e.value_target is None for e in corpus.examples)
    trajectory = load_trajectory(path.parent/row['trajectory'])
    target = json.loads(gzip.decompress((path.parent/row['targets']).read_bytes()))
    assert target['schema'] == 'sts_search_targets_v2' and target['planning_view'] == VIEW
    examples = iter(corpus.examples)
    for entry, transition in zip(target['targets'], trajectory.transitions):
        if entry['reason'] is not None:
            continue
        teacher = collate([original.encoder.encode(planning_view(transition.observation))], vocabulary=corpus.vocabulary)
        student = collate([next(examples).state], vocabulary=corpus.vocabulary)
        assert all(torch.equal(teacher[k], student[k]) for k in teacher)
    raw_corpus = load_corpus([(path.parent/row['trajectory'], path.parent/row['training'])], split='train',
                             vocabulary=original.model.vocabulary, reward_spec=OBJECTIVE)
    assert raw_corpus.input_view == RAW and raw_corpus.identity != corpus.identity
    training_path, trained = distill_search(checkpoint=checkpoint, report_path=path,
        output_dir=tmp_path/'student', updates=2)
    student_path = training_path.parent/'final.sts-model'
    student = load_policy(student_path)
    assert student.model.input_view == VIEW and student.algorithm == 'imitation'
    assert trained['input_view'] == VIEW and trained['updates'][-1]['value_loss'] == 0
    assert trained['initialization']['source_input_view'] == RAW
    initial = load_policy(training_path.parent/'initial.sts-model')
    for transition in trajectory.transitions:
        assert initial.probabilities(transition.observation) == original.probabilities(planning_view(transition.observation))
    refreshed, updated = reanalyse_search(checkpoint=student_path, report_path=path,
        output_dir=tmp_path/'reanalysis', search=SearchConfig(model_version='direct_belief_v1',
            simulations=4, max_depth=4, time_limit=10, belief_particles=2))
    assert updated['planning_view'] == VIEW and updated['outcome_provenance'] == 'original_behavior_unchanged'
    new = updated['episodes'][0]
    assert new['behavior_policy'] == report['policies']['gumbel']
    for kind in ('trajectory', 'training'):
        assert (path.parent/row[kind]).read_bytes() == (refreshed.parent/new[kind]).read_bytes()
    assert all(e.value_target is None for e in load_search_corpus(refreshed, student).examples)
    _, round2 = distill_search(checkpoint=student_path, report_path=refreshed,
                             output_dir=tmp_path/'round2', updates=1)
    assert round2['input_view'] == VIEW
    assert round2['initialization']['source_input_view'] == VIEW
    from game.agent.tracking.records import evaluations
    assert list(evaluations(updated))[0]['mode'] == 'target_refresh'
    assert not any(k.startswith('eval/') for k in list(evaluations(updated))[0]['metrics'])


@pytest.mark.parametrize('damage', ['report_missing', 'report_raw', 'target_missing', 'target_raw', 'target_legacy', 'behavior'])
def test_direct_dataset_view_and_behavior_bindings_reject(checkpoint, tmp_path, damage):
    path, report = direct_collection(checkpoint, tmp_path/'collection')
    row = report['episodes'][0]
    if damage.startswith('report'):
        report.pop('planning_view')
        if damage == 'report_raw':
            report['planning_view'] = RAW
    elif damage == 'behavior':
        row['behavior_policy'] = 'wrong'
    else:
        file = path.parent/row['targets']
        data = json.loads(gzip.decompress(file.read_bytes()))
        data.pop('planning_view')
        if damage == 'target_raw':
            data['planning_view'] = RAW
        if damage == 'target_legacy':
            data['schema'] = 'sts_search_targets_v1'
        file.write_bytes(gzip.compress(json.dumps(data).encode(), mtime=0))
        row['targets_sha256'] = hashlib.sha256(file.read_bytes()).hexdigest()
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match='input view|identity'):
        load_search_corpus(path, load_policy(checkpoint))


def test_legacy_raw_data_can_be_reanalysed_but_not_restore_links_to_a_student(checkpoint, tmp_path):
    path, report = run_search(checkpoint=checkpoint, output_dir=tmp_path/'raw',
        search=SearchConfig(model_version='public_belief_v1', simulations=4, max_depth=4,
                            time_limit=10, belief_particles=1),
        cases=1, split='train', collect=True, max_decisions=1)
    row = report['episodes'][0]
    target_path = path.parent/row['targets']
    data = json.loads(gzip.decompress(target_path.read_bytes()))
    data['schema'] = 'sts_search_targets_v1'
    data.pop('planning_view')
    target_path.write_bytes(gzip.compress(json.dumps(data).encode(), mtime=0))
    row['targets_sha256'] = hashlib.sha256(target_path.read_bytes()).hexdigest()
    report['schema'] = 'sts_search_report_v1'
    report.pop('planning_view')
    path.write_text(json.dumps(report))
    assert load_search_corpus(path, load_policy(checkpoint)).input_view == RAW
    student = tmp_path/'viewed.sts-model'
    save_checkpoint(student, viewed_learner())
    output = tmp_path/'rejected-transfer'
    with pytest.raises(ValueError, match='raw historical links'):
        distill_search(checkpoint=student, report_path=path, output_dir=output, updates=1)
    assert not output.exists()
    refreshed, new = reanalyse_search(checkpoint=student, report_path=path, output_dir=tmp_path/'refresh',
        search=SearchConfig(model_version='direct_belief_v1', simulations=4, max_depth=4,
                            time_limit=10, belief_particles=1))
    assert new['planning_view'] == VIEW and new['schema'] == 'sts_search_report_v2'
    assert load_search_corpus(refreshed, load_policy(student)).input_view == VIEW


@pytest.mark.parametrize('workers', [1, 2])
def test_ordinary_ppo_keeps_view_in_workers_and_exact_resume(tmp_path, workers):
    from game.agent.training.checkpoint import save_ppo_checkpoint, restore_ppo
    from game.agent.training.ppo import PPOLearner, replay_batch
    from game.agent.training.ppo_config import PPOConfig, PPOExperiment
    from .test_ppo import long_env
    learner = viewed_learner()
    experiment = PPOExperiment(ppo=PPOConfig(rollout_steps=4, batch_size=4, epochs=1),
                               encounters=('controlled',), source='view_ppo_fixture_v1')
    with PPOLearner(learner.model, experiment, env_factory=long_env, workers=workers) as owner:
        rollout = owner.collect()
        assert all(s.state.input_view == VIEW for s in rollout.steps)
        for step in rollout.steps:
            batch = replay_batch([step], owner.model.vocabulary)
            with torch.inference_mode():
                logits, _ = owner.model(batch)
                logp, _ = policy_statistics(logits, batch['mask'], torch.tensor([step.action]))
            assert logp.item() == pytest.approx(step.old_log_probability)
        with pytest.raises(ValueError, match='frozen-policy'):
            owner.update(replace(rollout, behavior='sts_combat_search_v1:other'))
        owner.update(rollout)
        public, private = tmp_path/'public/model.sts-model', tmp_path/'private/model.resume.pt'
        save_ppo_checkpoint(public, owner, resume_path=private)
        assert load_policy(public).model.input_view == VIEW
        with restore_ppo(public, private, env_factory=long_env) as resumed:
            a, b = owner.collect(), resumed.collect()
            assert [(s.action, s.old_log_probability) for s in a.steps] == [(s.action, s.old_log_probability) for s in b.steps]
            owner.update(a)
            resumed.update(b)
            assert all(torch.equal(v, resumed.model.state_dict()[k]) for k,v in owner.model.state_dict().items())

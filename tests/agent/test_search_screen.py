"""Supervised representation screen over collected search targets."""
from dataclasses import replace
import json

import pytest

torch = pytest.importorskip('torch')
pytest.importorskip('gymnasium')
from game.agent.search import SearchConfig
from game.agent.training.checkpoint import save_checkpoint
from game.agent.training.learner import ImitationLearner
from game.agent.training.model import ActorCritic, Architecture
from game.agent.training.search_run import OBJECTIVE, run_search
from game.agent.training.search_screen import SCHEMA, holdout, report, run_candidate, run_candidates, validate_config
from .test_training_model import tiny_corpus


@pytest.fixture(scope='module')
def collection(tmp_path_factory):
    tmp = tmp_path_factory.mktemp('screen')
    corpus = replace(tiny_corpus(), reward_spec=OBJECTIVE)
    learner = ImitationLearner(ActorCritic(corpus.vocabulary, Architecture(24, 1), seed=7), corpus)
    teacher = tmp / 'teacher.sts-model'
    save_checkpoint(teacher, learner)
    path, collected = run_search(checkpoint=teacher, output_dir=tmp / 'collect',
        search=SearchConfig(simulations=4, time_limit=20, exploration=True, model_version='public_belief_v1',
                            belief_particles=2), cases=6, split='train', collect=True, max_decisions=3)
    assert collected['status'] == 'complete'
    return tmp, teacher, path, collected


def config(tmp, teacher, path, **changes):
    value = dict(schema=SCHEMA, reports=[str(path)], holdout_fraction=.34, split_salt='test', epochs=2,
        checkpoints=[1, 2], learning_rate=3e-4, batch_size=4, value_weight=.25, gradient_clip=1., seeds=[1, 2],
        threads=1, candidates=dict(
            warm=dict(kind='checkpoint', checkpoint=str(teacher)),
            fresh=dict(kind='production', vocabulary_from=str(teacher), schema='sts_graph_actor_critic_v1',
                       hidden_size=16, message_layers=1),
            pooled=dict(kind='study', architecture='pooled_mlp', richness='basic', identities=False, hidden_size=16),
            flat_ids=dict(kind='study', architecture='flat_mlp', richness='basic', identities=True, hidden_size=8)))
    value.update(changes)
    file = tmp / 'screen.json'
    file.write_text(json.dumps(value))
    return file, value


def test_split_is_by_campaign_and_deterministic(collection):
    tmp, teacher, path, collected = collection
    _, value = config(tmp, teacher, path)
    groups = {r['source_group'] for r in collected['episodes']}
    held = {g for g in groups if holdout(g, value)}
    assert held and held != groups
    assert held == {g for g in groups if holdout(g, json.loads(json.dumps(value)))}


def test_candidates_share_held_out_decisions_and_report_compares_them(collection):
    from game.agent.training.search_run import _report_input_view
    tmp, teacher, path, collected = collection
    file, value = config(tmp, teacher, path)
    out = tmp / 'run'
    written = run_candidates(file, out, ('warm', 'fresh'), progress=lambda _: None)
    results = {r['candidate']: r for _, r in written}
    results.update({name: run_candidate(file, out, name, progress=lambda _: None)[1] for name in ('pooled', 'flat_ids')})
    # The warm and fresh production candidates shared one encoding.
    assert results['warm']['encode_seconds'] == results['fresh']['encode_seconds']
    assert len({r['holdout_index_sha256'] for r in results.values()}) == 1
    warm = results['warm']
    # Production candidates use the teacher's declared view; study encoders keep their own history.
    assert warm['input_view'] == results['fresh']['input_view'] == _report_input_view(collected)
    assert results['pooled']['input_view'] == 'public_observation_v1'
    assert results['flat_ids']['vocabulary_names'] > 0 and results['pooled']['vocabulary_names'] == 0
    assert warm['holdout_decisions'] > 0 and warm['fit_decisions'] > 0
    for result in results.values():
        assert set(result['seeds']) == {'1', '2'}
        for seed in result['seeds'].values():
            assert set(seed['curve']) == {'1', '2'} and len(seed['holdout_kl']) == warm['holdout_decisions']
            assert min(seed['holdout_kl']) > -1e-6
    with pytest.raises(FileExistsError):
        run_candidate(file, out, 'warm', progress=lambda _: None)
    summary_path, summary = report(file, out)
    assert summary_path.exists() and not summary['missing']
    assert set(summary['comparisons']) == {'fresh-warm', 'pooled-warm', 'flat_ids-warm', 'pooled-fresh',
                                           'flat_ids-fresh', 'flat_ids-pooled'}
    difference = summary['comparisons']['fresh-warm']['kl']
    assert difference['interval_95'][0] <= difference['estimate'] <= difference['interval_95'][1]
    assert summary['reference']['holdout']['decisions'] == warm['holdout_decisions']


def test_invalid_configuration_rejects(collection):
    tmp, teacher, path, _ = collection
    _, value = config(tmp, teacher, path)
    for change in (dict(checkpoints=[2, 1]), dict(epochs=3), dict(holdout_fraction=0),
                   dict(candidates=dict(bad=dict(kind='study', architecture='flat_mlp')))):
        with pytest.raises(ValueError):
            validate_config({**value, **change})


def test_every_fresh_candidate_seed_changes_its_initial_weights(collection):
    from game.agent.training.search_screen import build_model
    tmp, teacher, path, _ = collection
    _, value = config(tmp, teacher, path)
    for name in ('fresh', 'pooled'):
        first, second = (build_model(value['candidates'][name], seed, view='public_observation_v1',
                                     names=()).state_dict() for seed in (1, 2))
        assert any(not torch.equal(first[k], second[k]) for k in first), name
    warm = [build_model(value['candidates']['warm'], seed, view='public_observation_v1').state_dict() for seed in (1, 2)]
    assert all(torch.equal(warm[0][k], warm[1][k]) for k in warm[0])


def test_fit_subsample_is_nested_and_evaluation_reports_supply_held_out_decisions(collection):
    from game.agent.training.search_screen import fitted
    tmp, teacher, path, collected = collection
    _, value = config(tmp, teacher, path)
    groups = {r['source_group'] for r in collected['episodes']}
    small, large = ({g for g in groups if fitted(g, {**value, 'fit_fraction': f, 'fit_salt': 'sub'})} for f in (.5, 1.))
    assert small <= large == {g for g in groups if fitted(g, value)}
    with pytest.raises(ValueError, match='salt'):
        validate_config({**value, 'fit_fraction': .5})
    with pytest.raises(ValueError, match='salt'):
        validate_config({**value, 'fit_fraction': .5, 'fit_salt': value['split_salt']})
    file, _ = config(tmp, teacher, path, evaluation_reports=[str(path)], seeds=[1], epochs=1, checkpoints=[1])
    _, separate = run_candidate(file, tmp / 'evaluation', 'fresh', progress=lambda _: None)
    file, _ = config(tmp, teacher, path, seeds=[1], epochs=1, checkpoints=[1])
    _, shared = run_candidate(file, tmp / 'shared', 'fresh', progress=lambda _: None)
    assert separate['holdout_index_sha256'] == shared['holdout_index_sha256']
    assert separate['fit_decisions'] == shared['fit_decisions'] and separate['evaluation_reports'] == [str(path)]
    assert set(separate['seeds']['1']['by_checkpoint']) == {'1'}

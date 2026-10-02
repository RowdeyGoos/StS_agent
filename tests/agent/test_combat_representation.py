"""Public tactical channels, exact candidate joins, and supported CPU resume."""
from dataclasses import replace
import json
import pickle
import zipfile

import pytest

torch = pytest.importorskip('torch')
np = pytest.importorskip('numpy')
pytest.importorskip('gymnasium')

from game.agent.contracts import full as f
from game.agent.headless import HeadlessAdapter
from game.agent.training.combat_features import GRAPH, COMBAT, CHANNELS, ROLES
from game.agent.training.features import FeatureEncoder, Vocabulary
from game.agent.training.model import ActorCritic, Architecture, collate, log_probabilities
from game.agent.training.checkpoint import load_policy, save_ppo_checkpoint, restore_ppo
from .test_combat_training import fixture
from .test_ppo import owner, controlled_env, comparable
from .test_training_model import cpu_threads, decision, renamed


def scalar(features, index, key):
    column = CHANNELS.index(key) * 3
    return features.combat[index, column:column + 3]


def test_real_combat_numbers_roles_and_no_hidden_rng():
    run = fixture(7, cards=('strike', 'perfected_strike', 'defend'), enemy_hp=60,
                  potions=('block_potion',))
    run.combat.enemies[0].statuses.add('slippery', 3)
    public = HeadlessAdapter(run, decision_profile=f.PROFILE).observe().decision
    vocab = Vocabulary.fit([public], split='train')
    encoder = FeatureEncoder(vocab, representation=COMBAT)
    state = encoder.encode(public)
    nodes = [*f.walk(public.run), *f.walk(public.context)]
    for index, node in enumerate(nodes):
        if state.roles[index] == ROLES.index('enemy'):
            assert scalar(state, index, 'hp')[:2] == pytest.approx([1, .6])
            assert scalar(state, index, 'power.slippery')[:2] == pytest.approx([1, .03])
        if state.roles[index] == ROLES.index('hand_card'):
            spec = next(c for c in node.children if c.kind == 'spec')
            assert scalar(state, index, 'spec.base_damage')[:2] == pytest.approx([1, spec.get('base_damage') / 100])
    assert np.bincount(state.roles[state.roles >= 0], minlength=len(ROLES)).tolist() == [1, 1, 3, 1, 0]
    # A different private future shuffle cannot change public model inputs.
    run.combat.rng.random()
    other = HeadlessAdapter(run, decision_profile=f.PROFILE).observe().decision
    actual = encoder.encode(other)
    assert np.array_equal(actual.combat, state.combat)
    assert np.array_equal(actual.roles, state.roles)
    assert all(np.array_equal(v, actual.graph.observation[k]) for k, v in state.graph.observation.items())


def test_unknown_hp_and_intent_are_distinct_from_zero_and_candidates_keep_order():
    public = decision()
    enemy = replace(public.context.children[1], fields=(f.Field('hp', None), f.Field('infinite_hp', True)),
                    children=(f.Node('intent', 'attack', fields=(f.Field('damage', None), f.Field('hits', 2))),))
    public = replace(public, context=replace(public.context, children=(public.context.children[0], enemy)))
    vocab = Vocabulary.fit([public], split='train')
    encoder = FeatureEncoder(vocab, representation=COMBAT)
    state = encoder.encode(public)
    index = np.flatnonzero(state.roles == ROLES.index('enemy'))[0]
    assert scalar(state, index, 'hp').tolist() == [0, 0, 0]
    assert scalar(state, index, 'infinite_hp')[0] == 1
    assert scalar(state, index, 'unknown_attacks')[1] == pytest.approx(.01)
    zero = replace(enemy, fields=(f.Field('hp', 0),))
    other = encoder.encode(replace(public, context=replace(public.context, children=(public.context.children[0], zero))))
    assert scalar(other, index, 'hp').tolist() == [1, 0, 0]
    model = ActorCritic(vocab, Architecture(16, 1, COMBAT), seed=17)
    changed, mapping = renamed(public)
    alternate = encoder.encode(changed)
    def probabilities(value):
        batch = collate([value], vocabulary=vocab)
        logits, _ = model(batch)
        return dict(zip(value.graph.candidate_refs, log_probabilities(logits, batch['mask']).exp()[0].tolist()))
    left, right = probabilities(state), probabilities(alternate)
    assert all(right[mapping[ref]] == pytest.approx(value, abs=1e-7) for ref, value in left.items())


def test_baseline_initialization_and_compact_combat_batch_serialization():
    public = decision()
    vocab = Vocabulary.fit([public], split='train')
    rng = torch.get_rng_state().clone()
    baseline = ActorCritic(vocab, Architecture(16, 1), seed=17)
    enriched = ActorCritic(vocab, Architecture(16, 1, COMBAT), seed=17)
    assert torch.equal(rng, torch.get_rng_state())
    assert all(torch.equal(value, enriched.state_dict()[key]) for key, value in baseline.state_dict().items())
    state = FeatureEncoder(vocab, representation=COMBAT).encode(public)
    batch = collate([state], vocabulary=vocab)
    compact = pickle.loads(pickle.dumps(state.for_rollout()))
    assert all(torch.equal(value, collate([compact], vocabulary=vocab)[key]) for key, value in batch.items())
    logits, values = enriched(batch)
    (logits.square().mean() + values.square().mean()).backward()
    assert enriched.combat_node[0].weight.grad.abs().sum() > 0
    assert enriched.combat_state[0].weight.grad.abs().sum() > 0
    plain = FeatureEncoder(vocab).encode(public)
    with pytest.raises(ValueError, match='Mixed feature'):
        collate([plain, state], vocabulary=vocab)
    with pytest.raises(ValueError, match='representation'):
        baseline(batch)
    with pytest.raises(ValueError, match='representation'):
        enriched(collate([plain], vocabulary=vocab))


@pytest.fixture(params=(1, 4))
def combat_runtime(request):
    previous = (torch.get_num_threads(), torch.are_deterministic_algorithms_enabled(),
                torch.is_deterministic_algorithms_warn_only_enabled())
    torch.set_num_threads(request.param)
    torch.use_deterministic_algorithms(True, warn_only=False)
    yield
    torch.set_num_threads(previous[0])
    torch.use_deterministic_algorithms(previous[1], warn_only=previous[2])


def test_enriched_parallel_ppo_checkpoint_resume_and_schema_binding(tmp_path, combat_runtime):
    with owner(seed=17, workers=2, architecture=Architecture(16, 1, COMBAT)) as left:
        left.update(left.collect())
        bundle, state = tmp_path / 'public/model.sts-model', tmp_path / 'private/model.resume.pt'
        save_ppo_checkpoint(bundle, left, resume_path=state)
        policy = load_policy(bundle)
        assert policy.model.architecture.schema == COMBAT
        assert policy.manifest['feature_identity'] == policy.encoder.identity != policy.model.vocabulary.identity
        with controlled_env(encounter='strike_or_die') as env:
            env.reset(seed=0)
            assert policy(env.public_state) in env.public_state.candidates
        with restore_ppo(bundle, state, env_factory=controlled_env) as right:
            a, b = left.collect(), right.collect()
            assert comparable(a) == comparable(b)
            left.update(a)
            right.update(b)
            assert all(torch.equal(v, right.model.state_dict()[k]) for k, v in left.model.state_dict().items())
            assert torch.equal(left.action_generator.get_state(), right.action_generator.get_state())
            assert torch.equal(left.update_generator.get_state(), right.update_generator.get_state())
        with zipfile.ZipFile(bundle) as archive:
            manifest = json.loads(archive.read('manifest.json'))
            weights = archive.read('weights.pt')
        manifest['architecture']['schema'] = GRAPH
        bad = tmp_path / 'bad.sts-model'
        with zipfile.ZipFile(bad, 'w') as archive:
            archive.writestr('manifest.json', json.dumps(manifest))
            archive.writestr('weights.pt', weights)
        with pytest.raises(ValueError, match='Feature'):
            load_policy(bad)

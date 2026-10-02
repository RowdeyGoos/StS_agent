"""Native Slippery conformance and leakage-free action feature ablations."""
from dataclasses import replace
import pickle
from random import Random

import pytest

torch = pytest.importorskip('torch')
np = pytest.importorskip('numpy')

from game.agent.contracts import full as f
from game.agent.headless import HeadlessAdapter
from game.agent.training.action_features import CONTROL, DAMAGE, STACKS, previews
from game.agent.training.combat_features import COMBAT
from game.agent.training.features import FeatureEncoder, Vocabulary
from game.agent.training.model import ActorCritic, Architecture, collate, sample_actions
from game.agent.training.checkpoint import save_ppo_checkpoint, restore_ppo, load_policy
from game.headless.monsters.vantom import Vantom
from game.headless.run.config import RunConfig
from game.headless.run.engine import RunEngine
from .test_ppo import owner, controlled_env, comparable
from .test_training_model import cpu_threads


def fixture(cards=('strike', 'twin_strike', 'sword_boomerang'), *, slippery=8, block=0, hp=173, relics=()):
    run = RunEngine(seed=1, card_ids=cards, hp=40, rng_profile='native', config=RunConfig())
    for name in relics:
        run.obtain_relic(name)
    run.start_combat(enemy_factory=lambda: Vantom(Random(1)), cards_per_turn=len(cards))
    p, e = run.combat.player, run.combat.enemies[0]
    p.energy = 10
    e.hp, e.block = hp, block
    e.statuses._counts['slippery'] = slippery
    return run


def measure(run, name):
    adapter = HeadlessAdapter(run, decision_profile=f.PROFILE)
    public = adapter.observe().decision
    nodes = {n.ref: n for n in f.walk(public.context) if n.ref}
    action = next(a for a in public.candidates if a.kind == 'play_card' and nodes[a.subject].definition_id == name)
    before_snapshot = run.snapshot()
    predicted = previews(public)[action.ref]
    assert predicted == previews(public)[action.ref]
    assert run.snapshot() == before_snapshot
    e = run.combat.enemies[0]
    before = e.hp, e.block, e.statuses.get('slippery')
    adapter.step(adapter.observe().binding, action.ref)
    actual = tuple(a - b for a, b in zip(before, (e.hp, e.block, e.statuses.get('slippery'))))
    assert predicted.known, predicted
    assert (predicted.hp_removed, predicted.block_removed, predicted.slippery_removed) == actual
    return actual


@pytest.mark.parametrize('card,slippery,block,hp,relics,expected', [
    ('strike', 1, 0, 173, (), (1, 0, 1)),
    ('twin_strike', 1, 0, 173, (), (6, 0, 1)),
    ('twin_strike', 1, 10, 173, (), (0, 10, 0)),
    ('sword_boomerang', 2, 0, 173, (), (5, 0, 2)),
    ('sword_boomerang', 2, 0, 173, ('the_boot',), (15, 0, 2)),
    ('sword_boomerang', 8, 0, 1, (), (1, 0, 1)),
    ('sword_boomerang', 0, 2, 173, ('hand_drill',), (9, 2, 0)),
    ('perfected_strike', 0, 0, 173, ('strike_dummy',), (13, 0, 0)),
    ('whirlwind', 12, 0, 173, (), (10, 0, 10)),
])
def test_native_per_hit_resolution(card, slippery, block, hp, relics, expected):
    assert measure(fixture((card, 'strike'), slippery=slippery, block=block, hp=hp, relics=relics), card) == expected


@pytest.mark.parametrize('card', ['anger', 'bash', 'thunderclap', 'molten_fist', 'dismantle',
                                  'unrelenting', 'fight_me', 'rampage', 'iron_wave', 'bully', 'setup_strike'])
def test_native_supported_effects_and_damage_modifiers(card):
    run = fixture((card, 'strike'), slippery=1, block=3)
    p, e = run.combat.player, run.combat.enemies[0]
    p.strength = 3
    p.statuses.add('weak', 1)
    p.rules.powers['vigor'] = 2
    e.statuses.add('vulnerable', 1)
    measure(run, card)


def test_unknown_and_public_only_boundary():
    run = fixture(('strike', 'pommel_strike', 'tear_asunder', 'anger', 'defend'))
    deck = run.combat.player.deck
    for card in tuple(deck.hand):
        if card.definition.definition_id in ('anger', 'defend'):
            deck.hand.remove(card)
            deck.draw_pile.append(card)
    assert len(deck.draw_pile) == 2
    assert len({c.definition.definition_id for c in deck.draw_pile}) == 2
    adapter = HeadlessAdapter(run, decision_profile=f.PROFILE)
    public = adapter.observe().decision
    first = previews(public)
    run.combat.rng.random()
    run.combat.player.deck.target_rng.random()
    run.combat.player.deck.draw_pile.reverse()
    assert first == previews(HeadlessAdapter(run, decision_profile=f.PROFILE).observe().decision)
    by_ref = {n.ref: n.definition_id for n in f.walk(public.context) if n.ref}
    for action in public.candidates:
        if action.kind == 'play_card':
            assert first[action.ref].known == (by_ref[action.subject] == 'strike')
    run.combat.player.rules.powers['juggling'] = 1  # Missing attacks-finished counter.
    assert not any(p.known for p in previews(HeadlessAdapter(run, decision_profile=f.PROFILE).observe().decision).values())


def test_rage_block_juggernaut_consumes_a_second_stack():
    run = fixture(('strike',), slippery=3)
    run.combat.player.rules.powers.update(rage=3, juggernaut=5)
    assert measure(run, 'strike') == (2, 0, 2)


@pytest.mark.parametrize('name,card,counter,memory,powers,slippery,expected', [
    ('pen_nib', 'twin_strike', 8, {}, {}, 0, (10, 0, 0)),
    ('pen_nib', 'twin_strike', 9, {}, {}, 0, (20, 0, 0)),
    ('kusarigama', 'strike', 0, {'turn_attacks': 1}, {}, 3, (1, 0, 1)),
    ('kusarigama', 'strike', 0, {'turn_attacks': 5}, {}, 3, (2, 0, 2)),
    ('ornamental_fan', 'strike', 0, {'turn_attacks': 2}, {'juggernaut': 5}, 3, (2, 0, 2)),
    ('vambrace', 'iron_wave', 0, {'used': False}, {'juggernaut': 5}, 3, (2, 0, 2)),
    ('vambrace', 'iron_wave', 0, {'used': True}, {'juggernaut': 5}, 3, (2, 0, 2)),
    ('unsettling_lamp', 'thunderclap', 0, {'used': False}, {}, 3, (1, 0, 1)),
    ('unsettling_lamp', 'thunderclap', 0, {'used': True}, {}, 3, (1, 0, 1)),
    ('joss_paper', 'molten_fist', 3, {}, {}, 3, (1, 0, 1)),
])
def test_public_relic_counters_use_native_hooks(name, card, counter, memory, powers, slippery, expected):
    run = fixture((card, 'strike'), relics=(name,), slippery=slippery)
    relic = run.state.relics[0]
    run.state.relics[0] = replace(relic, counter=counter)
    run.combat.player.rules.relics[0]['counter'] = counter
    run.combat.player.rules.relic_data[relic.instance_id] = dict(memory)
    run.combat.player.rules.powers.update(powers)
    assert measure(run, card) == expected


def test_joss_draw_fails_closed_and_final_kill_horn_does_not_draw():
    run = fixture(('molten_fist',), relics=('joss_paper',))
    run.state.relics[0] = replace(run.state.relics[0], counter=4)
    run.combat.player.rules.relics[0]['counter'] = 4
    public = HeadlessAdapter(run, decision_profile=f.PROFILE).observe().decision
    value = next(v for k, v in previews(public).items() if k == public.candidates[0].ref)
    assert not value.known and value.reason == 'hidden_draw_or_autoplay'
    assert measure(fixture(('strike',), hp=1, relics=('gremlin_horn',)), 'strike') == (1, 0, 1)


def test_modified_public_mechanic_is_unknown_and_withheld_fields_never_enter_graph():
    public = HeadlessAdapter(fixture(('twin_strike',)), decision_profile=f.PROFILE).observe().decision
    def change(node):
        if node.kind == 'mechanic' and node.definition_id == 'Attack':
            return replace(node, fields=tuple(replace(v, value=10) if v.key == 'hits' else v for v in node.fields))
        return replace(node, children=tuple(change(c) for c in node.children))
    changed = replace(public, context=change(public.context))
    assert not any(p.known for p in previews(changed).values())


@pytest.mark.parametrize('pile', ['hand', 'draw', 'discard', 'exhaust', 'in_play', 'offered', 'sequestered'])
@pytest.mark.parametrize('mutation', ['absent', 'duplicate'])
def test_missing_or_duplicate_pile_is_not_treated_as_empty(pile, mutation):
    public = HeadlessAdapter(fixture(('perfected_strike', 'ashen_strike')), decision_profile=f.PROFILE).observe().decision
    group = next(n for n in public.context.children if n.kind == 'pile' and n.definition_id == pile)
    children = (tuple(n for n in public.context.children if n is not group) if mutation == 'absent'
                else (*public.context.children, group))
    changed = replace(public, context=replace(public.context, children=children))
    assert not any(p.known for p in previews(changed).values())


def test_candidate_reordering_and_reference_renaming_preserve_previews():
    public = HeadlessAdapter(fixture(), decision_profile=f.PROFILE).observe().decision
    mapping = {n.ref: n.ref.split(':')[0] + ':' + str(1000 + i)
               for i, n in enumerate([*f.walk(public.run), *f.walk(public.context)]) if n.ref}
    mapping.update({a.ref: 'action:' + str(i + 500) for i, a in enumerate(public.candidates)})
    def renamed(n):
        return replace(n, ref=mapping.get(n.ref), children=tuple(renamed(c) for c in n.children),
                       links=tuple(replace(link, targets=tuple(mapping[t] for t in link.targets)) for link in n.links))
    altered = replace(public, run=renamed(public.run), context=renamed(public.context),
        candidates=tuple(replace(a, ref=mapping[a.ref], subject=mapping.get(a.subject), target=mapping.get(a.target))
                         for a in reversed(public.candidates)))
    assert previews(altered) == {mapping[k]: v for k, v in previews(public).items()}


def test_ablations_preserve_initial_actor_critic_sampling_and_compact_features():
    public = HeadlessAdapter(fixture(), decision_profile=f.PROFILE).observe().decision
    vocabulary = Vocabulary.fit([public], split='train')
    old = ActorCritic(vocabulary, Architecture(16, 1, COMBAT), seed=5)
    old_state = FeatureEncoder(vocabulary, representation=COMBAT).encode(public)
    expected = old(collate([old_state], vocabulary=vocabulary))
    states, sizes = [], []
    for schema in (CONTROL, DAMAGE, STACKS):
        model = ActorCritic(vocabulary, Architecture(16, 1, schema), seed=5)
        missing = model.load_state_dict(old.state_dict(), strict=False)
        assert all(k.startswith('action_preview.') for k in missing.missing_keys) and not missing.unexpected_keys
        state = FeatureEncoder(vocabulary, representation=schema).encode(public)
        batch = collate([state], vocabulary=vocabulary)
        actual = model(batch)
        assert all(torch.equal(a, b) for a, b in zip(expected, actual))
        assert state.graph.candidate_refs == old_state.graph.candidate_refs
        assert all(np.array_equal(v, old_state.graph.observation[k]) for k, v in state.graph.observation.items())
        left, right = (torch.Generator().manual_seed(23) for _ in range(2))
        assert torch.equal(sample_actions(expected[0], batch['mask'], generator=left),
                           sample_actions(actual[0], batch['mask'], generator=right))
        assert torch.equal(left.get_state(), right.get_state())
        compact = pickle.loads(pickle.dumps(state.for_rollout()))
        assert all(torch.equal(v, collate([compact], vocabulary=vocabulary)[k]) for k, v in batch.items())
        sizes.append(sum(p.numel() for p in model.parameters()))
        states.append(state)
    assert len(set(sizes)) == 1
    assert not states[0].action_previews.any()
    assert not states[1].action_previews[:, 6:].any()
    assert np.array_equal(states[1].action_previews[:, :6], states[2].action_previews[:, :6])
    assert states[2].action_previews[:, 6:].any()
    with pytest.raises(ValueError, match='Mixed action preview'):
        collate(states, vocabulary=vocabulary)
    with pytest.raises(ValueError, match='unmasked'):
        collate([replace(states[1], action_previews=states[2].action_previews)], vocabulary=vocabulary)
    (-model(collate([states[2]], vocabulary=vocabulary))[0][0, 0]).backward()
    assert model.action_preview[-1].weight.grad.abs().sum() > 0


@pytest.mark.parametrize('schema', [CONTROL, DAMAGE, STACKS])
def test_checkpoint_and_parallel_resume(tmp_path, schema):
    with owner(seed=17, workers=2, architecture=Architecture(16, 1, schema)) as left:
        left.update(left.collect())
        bundle, resume = tmp_path / 'public/model.sts-model', tmp_path / 'private/model.resume.pt'
        save_ppo_checkpoint(bundle, left, resume_path=resume)
        assert load_policy(bundle).model.architecture.schema == schema
        with restore_ppo(bundle, resume, env_factory=controlled_env) as right:
            a, b = left.collect(), right.collect()
            assert comparable(a) == comparable(b)
            left.update(a)
            right.update(b)
            assert all(torch.equal(v, right.model.state_dict()[k]) for k, v in left.model.state_dict().items())

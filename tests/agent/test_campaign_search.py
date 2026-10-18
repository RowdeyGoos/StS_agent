"""Campaign entry, hidden information, native transitions and attachments."""
from copy import deepcopy
from dataclasses import replace
import pytest

from game.agent.contracts import full as f, RunOutcome
from game.agent.full_policy import choose_action
from game.agent.headless import HeadlessAdapter
from game.agent.headless.full_projection import FullProjection
from game.agent.headless.identity import Identities
from game.agent.headless.planning import CampaignPlanning
from game.agent.input_views import planning_view
from game.agent.search import SearchConfig, SearchPolicy
from game.agent.search.belief import BeliefBudget
from game.agent.search.campaign import ANCHOR, MODEL, CampaignCombatBelief, inventory
from game.agent.search.public_keys import public_key
from game.headless.encounters.catalog import NATIVE_OVERGROWTH_ENCOUNTERS, NATIVE_UNDERDOCKS_ENCOUNTERS
from game.headless.planning import UnsupportedSearch
from game.headless.reveals import run_reveals
from game.headless.run.config import RunConfig
from game.headless.run.construction import declared_combat_region, revealed_encounter
from game.headless.run.engine import RunEngine
from .test_search import UniformPolicy


def fixture(encounter='overgrowth_vantom', *, deck=('strike', 'defend', 'bash', 'pillage', 'pommel_strike'),
            relics=('burning_blood',), seed=13, edit=None, history=(), names=None):
    run = RunEngine(seed=seed, card_ids=deck, hp=70, max_hp=80,
        config=RunConfig(act=declared_combat_region(encounter)), rng_profile='native')
    for relic in relics:
        run.obtain_relic(relic)
    if edit:
        edit(run)
    values = []
    def entry():
        initial = f.PublicDecision(f.SCHEMA, f.PROFILE,
            FullProjection(run, names or Identities(), list(history), {}, 'attachment', 0, False).run(),
            f.Node('planning', 'combat_entry', fields=(f.Field('entry_action_kind', 'choose_map_node'),)),
            (f.Candidate('action:0', 'end_turn'),))
        values.append(f.to_dict(initial))
    run._combat_entry_observer = entry
    with run_reveals(run) as journal:
        run.start_combat(encounter_id=encounter)
    del run._combat_entry_observer
    adapter = HeadlessAdapter(run, decision_profile=f.PROFILE)
    if names is not None:
        adapter._ids = names  # One continuously attached owner named the deck earlier.
    adapter._history = list(history)
    # Reserve historical public names exactly as a continuously attached owner.
    for action in history:
        for ref in (action.subject, action.target):
            if ref:
                kind, serial = ref.split(':')
                adapter._ids.counts[kind] = max(adapter._ids.counts[kind], int(serial) + 1)
    opening = adapter.observe().decision
    anchor = dict(schema=ANCHOR, initial=values[0], opening=f.to_dict(opening),
                  opening_reveals=journal.events, transitions=[], facts={'card_combats': {}})
    return run, adapter, anchor


@pytest.mark.parametrize('encounter', (*NATIVE_OVERGROWTH_ENCOUNTERS.values(), *NATIVE_UNDERDOCKS_ENCOUNTERS.values()))
def test_every_ordinary_act1_roster_conditions_native_setup(encounter):
    run, adapter, anchor = fixture(encounter)
    opening = adapter.observe().decision
    names = [n.definition_id for n in f.walk(opening.context) if n.kind == 'enemy']
    assert revealed_encounter(names) == encounter
    belief = CampaignCombatBelief(anchor, opening, seed=54, budget=BeliefBudget(1, 1024, 10))
    assert belief.recover().reason is None
    for seed in (8, 42):
        _, sampled = belief.sample(seed)
        assert public_key(sampled) == public_key(planning_view(opening))


@pytest.mark.parametrize('region', ('overgrowth', 'underdocks'))
def test_campaign_receipts_are_passive_and_track_multiple_fights(region):
    def make():
        return RunEngine.campaign(seed=100, character='ironclad', first_act=region, ascension=0)
    run, plain = make(), make()
    adapter = HeadlessAdapter(run, decision_profile=f.PROFILE)
    control = HeadlessAdapter(plain, decision_profile=f.PROFILE)
    producer = CampaignPlanning(adapter)
    serial, belief = 0, None
    for _ in range(160):
        frame, reference = adapter.observe(), control.observe()
        if isinstance(frame, RunOutcome):
            assert frame == reference
            break
        assert frame.decision == reference.decision
        if run.combat is not None and producer.serial != serial:
            serial = producer.serial
            belief = CampaignCombatBelief(producer.export(), frame.decision, seed=3, budget=BeliefBudget(1, 512, 5))
            assert belief.recover().reason is None
        in_combat = run.combat is not None
        action = choose_action(frame.decision)
        execution = producer.step(frame.binding, action.ref)
        control.step(reference.binding, action.ref)
        assert run.snapshot() == plain.snapshot()
        assert not hasattr(run, '_combat_entry_observer') and not hasattr(run, '_combat_reveals')
        if in_combat:
            belief.receive_reveals(producer.reveals)
            successor = adapter.combat_completion or adapter.observe().decision
            assert belief.observe_transition(frame.decision, action, execution, successor).reason is None
    assert serial >= 3


def test_search_uses_only_public_receipt_and_never_real_rng():
    run, adapter, anchor = fixture(deck=('strike', 'defend') * 5)
    root = adapter.observe().decision
    results = []
    for hidden in range(2):
        run.combat.player.deck.draw_pile.reverse()
        run.state.rng.stream('niche').random()
        before = run.snapshot()
        planner = SearchPolicy(UniformPolicy(), SearchConfig(model_version=MODEL, simulations=8,
            time_limit=30, belief_particles=1, seed=4))
        planner.begin_campaign_combat(anchor, root)
        result = planner.choose(root)
        assert result.reason is None
        results.append((result.action_ref, result.probabilities, result.values, result.visits))
        assert run.snapshot() == before
    assert results[0] == results[1]


def test_room_entry_effects_applied_once_and_permanent_modifiers_preserved():
    def edit(run):
        run.state.deck[0].permanent_damage = 9
        run.state.deck[1].permanent_block = 7
    run, adapter, anchor = fixture(deck=('the_scythe', 'genetic_algorithm', 'strike', 'defend', 'bash'),
        relics=('burning_blood', 'maw_bank', 'venerable_tea_set'), edit=edit)
    belief = CampaignCombatBelief(anchor, adapter.observe().decision, seed=5, budget=BeliefBudget(1, 64, 5))
    assert belief.recover().reason is None
    world, _ = belief.sample(3)
    assert world._run.state.gold == run.state.gold
    assert sorted((c.definition.definition_id, c.permanent_damage, c.permanent_block) for c in world._run.state.deck) == sorted(
        (c.definition.definition_id, c.permanent_damage, c.permanent_block) for c in run.state.deck)


@pytest.mark.parametrize('enchanted', (0, -1))
def test_lone_enchanted_copy_keeps_its_public_name_among_equal_definitions(enchanted):
    from game.headless.enchantments.base import enchant
    names = Identities()
    def edit(run):
        # Public names precede the enchantment, as for a starting card enchanted later.
        FullProjection(run, names, [], {}, 'attachment', 0, False).run()
        enchant([c for c in run.state.deck if c.definition.definition_id == 'defend'][enchanted], 'spiral')
    run, adapter, anchor = fixture(deck=('defend',) * 4 + ('strike',) * 4 + ('bash',), edit=edit, names=names)
    restored = RunEngine()
    restored.restore(deepcopy(run.snapshot()))
    # Corpus starts attach to a fresh owner, which names equal copies by content.
    for current in (adapter.observe().decision, HeadlessAdapter(restored, decision_profile=f.PROFILE).observe().decision):
        belief = CampaignCombatBelief(anchor, current, seed=5, budget=BeliefBudget(1, 256, 10))
        assert belief.recover().reason is None
        _, sampled = belief.sample(3)
        assert public_key(sampled) == public_key(planning_view(current))


def test_past_consumed_potion_reference_cannot_rebind_to_generated_potion():
    history = (f.Candidate('action:0', 'use_potion', 'potion:0'),)
    run, adapter, anchor = fixture(history=history)
    root = adapter.observe().decision
    belief = CampaignCombatBelief(anchor, root, seed=6, budget=BeliefBudget(1, 128, 5))
    assert belief.recover().reason is None
    action = next(a for a in root.candidates if a.kind == 'play_card' and
        any(n.ref == a.subject and n.definition_id == 'pillage' for n in f.walk(root.context)))
    with run_reveals(run) as journal:
        receipt = adapter.step(adapter.observe().binding, action.ref)
    belief.receive_reveals(journal.events)
    after = adapter.observe().decision
    assert belief.observe_transition(root, action, receipt, after).reason is None
    assert all(n.ref != 'potion:0' for n in f.walk(after.run) if n.kind == 'potion')


def test_unsupported_public_history_is_an_explicit_fallback():
    from game.headless.relics.base import RelicInstance
    _, adapter, anchor = fixture(edit=lambda run: run.state.relics.append(
        RelicInstance('toy_box', run.state.allocate_item_id(), 3)))
    planner = SearchPolicy(UniformPolicy(), SearchConfig(model_version=MODEL, simulations=2))
    planner.begin_campaign_combat(anchor, adapter.observe().decision)
    result = planner.choose(adapter.observe().decision)
    assert result.reason == 'campaign_relic_history_toy_box'
    assert result.simulations == 0
    assert result.action_ref in {a.ref for a in adapter.observe().decision.candidates}


def test_campaign_search_keeps_work_across_fights():
    _, adapter, anchor = fixture()
    planner = SearchPolicy(UniformPolicy(), SearchConfig(model_version=MODEL, simulations=2, time_limit=10, belief_particles=1))
    for _ in range(2):
        planner.begin_campaign_combat(anchor, adapter.observe().decision)
        assert planner.choose(adapter.observe().decision).reason is None
    assert planner.summary()['decisions'] == 2 and planner.summary()['simulations'] == 4


def test_event_entry_cannot_masquerade_as_an_ordinary_roster():
    _, adapter, anchor = fixture()
    initial = f.from_dict(anchor['initial'])
    anchor['initial'] = f.to_dict(replace(initial, context=replace(initial.context,
        fields=(f.Field('entry_action_kind', 'choose_event_option'),))))
    with pytest.raises(UnsupportedSearch, match='event_or_missing_entry'):
        CampaignCombatBelief(anchor, adapter.observe().decision, seed=3, budget=BeliefBudget())


def test_lifetime_card_requires_public_history_and_expires_through_native_cleanup():
    run, adapter, anchor = fixture('overgrowth_nibbit',
        deck=('guilty', 'bludgeon', 'strike', 'defend', 'bash'),
        edit=lambda run: setattr(run.state.deck[0], 'combats_seen', 4))
    root = adapter.observe().decision
    with pytest.raises(UnsupportedSearch, match='missing_card_history'):
        CampaignCombatBelief(anchor, root, seed=7, budget=BeliefBudget())
    initial = f.from_dict(anchor['initial'])
    card = next(n for n in f.walk(initial.run) if n.kind == 'card' and n.definition_id == 'guilty')
    anchor['facts']['card_combats'][card.ref] = 4
    belief = CampaignCombatBelief(anchor, root, seed=7, budget=BeliefBudget(1, 128, 5))
    assert belief.recover().reason is None
    for _ in range(30):
        frame = adapter.observe()
        action = choose_action(frame.decision)
        with run_reveals(run) as journal:
            report = adapter.step(frame.binding, action.ref)
        successor = adapter.combat_completion or adapter.observe().decision
        belief.receive_reveals(journal.events)
        assert belief.observe_transition(frame.decision, action, report, successor).reason is None
        if run.combat is None:
            break
    assert adapter.combat_completion.result == 'victory'
    assert all(c.definition.definition_id != 'guilty' for c in run.state.deck)

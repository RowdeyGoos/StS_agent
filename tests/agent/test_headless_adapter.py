"""First producer integration, exact dispatch and public-information boundary."""
from copy import deepcopy
from dataclasses import replace
import ast
from pathlib import Path
import subprocess
import sys

import pytest

from game.agent import contracts as c
from game.agent.headless import AdapterFault, DecisionFrame, HeadlessAdapter, UnsupportedProfile
from game.agent.policy import choose_action
from game.headless.map.graph import MapGraph, MapNode
from game.headless.monsters.overgrowth import SimpleEnemy
from game.headless.run.actions import ChooseNode
from game.headless.run.config import RunConfig
from game.headless.run.engine import RunEngine
from game.headless.run.inventory import add_potion
from game.headless.run.state import RunPhase


def game(*, cards=('neows_fury', 'strike', 'strike', 'defend'), character='ironclad', seed=3):
    graph = MapGraph((MapNode('first', 'combat', ('next',), 'overgrowth_nibbit', row=1, column=0),
                      MapNode('next', 'combat', (), 'overgrowth_nibbit', row=2, column=0)), 'first')
    run = RunEngine(seed=seed, card_ids=cards, graph=graph,
                    config=RunConfig(character=character, reward_cards=('strike', 'defend', 'bash')))
    run.start_combat(cards_per_turn=0)
    return run


def fury_game():
    run = game()
    p = run.combat.player
    originals = list(p.deck.draw_pile)
    p.deck.draw_pile.clear()
    fury = next(card for card in originals if card.definition.definition_id == 'neows_fury')
    p.hand.append(fury)
    p.deck.discard_pile.extend(sorted((card for card in originals if card is not fury),
                                     key=lambda card: card.definition.definition_id != 'strike'))
    return run


def action(adapter, kind, *, subject=None, target=None):
    frame = adapter.observe()
    candidate = next(a for a in frame.decision.candidates if a.kind == kind and
                     (subject is None or a.subject == subject) and (target is None or a.target == target))
    assert adapter.step(frame.binding, candidate.ref).status == 'reconciled'
    return candidate


def decision(adapter):
    return adapter.observe().decision


def combat_cards(context):
    combat = context.combat if isinstance(context, c.CardSelection) else context
    return {card.ref: card for pile in combat.piles for card in pile.cards.value}


def reward_game():
    run = fury_game()
    run.combat.enemies[0].hp = 1
    adapter = HeadlessAdapter(run)
    action(adapter, 'play_card')
    assert run.state.phase is RunPhase.REWARD
    return run, adapter


def test_public_only_chooser_combat_optional_selection_rewards_and_map(monkeypatch):
    run = fury_game()
    run.combat.enemies[0].hp = 22
    adapter = HeadlessAdapter(run)
    commands = []
    apply = run.apply
    def record(command):
        commands.append(command)
        return apply(command)
    monkeypatch.setattr(run, 'apply', record)
    contexts, chosen = [], []
    for _ in range(30):
        frame = adapter.observe()
        assert isinstance(frame, DecisionFrame)
        public = c.loads(c.dumps(frame.decision))  # The chooser has no engine/frame.
        contexts.append(public.context.kind)
        if public.context.kind == 'map':
            break
        candidate = choose_action(public)
        chosen.append(candidate.kind)
        report = adapter.step(frame.binding, candidate.ref)
        assert c.loads(c.dumps(report)) == report
        assert report.status == 'reconciled'
    else:
        pytest.fail('Reference chooser did not complete the bounded slice')
    assert set(contexts) == {'combat', 'card_selection', 'rewards', 'map'}
    assert 'select_card' in chosen and 'confirm_selection' in chosen
    assert 'open_card_reward' in chosen and 'choose_reward_card' in chosen
    assert len(commands) == len(chosen) - 1  # Open is presentation, not a game rule.
    assert len(run.state.deck) == 5
    history = decision(adapter).run.history.value
    assert history.coverage == 'attachment'
    assert any(event.kind == 'combat_ended' for event in history.events)
    action(adapter, 'choose_map_node')
    assert run.state.current_node_id == 'first' and run.combat is not None
    assert decision(adapter).context.kind == 'combat'


def test_optional_toggle_zero_confirmation_and_exact_duplicate_dispatch():
    run = fury_game()
    adapter = HeadlessAdapter(run)
    action(adapter, 'play_card')
    context = decision(adapter).context
    assert context.minimum == 0 and context.maximum == 2 and context.manual_confirmation
    duplicates = [combat_cards(context)[ref] for ref in context.options
                  if combat_cards(context)[ref].definition_id == 'strike']
    assert len(duplicates) == 2 and duplicates[0].ref != duplicates[1].ref
    original = run.combat.player.deck.discard_pile[1]
    action(adapter, 'select_card', subject=duplicates[1].ref)
    assert run.combat.player.rules.selection['selected'] == [original.instance_id]
    action(adapter, 'deselect_card', subject=duplicates[1].ref)
    action(adapter, 'confirm_selection')
    assert not run.combat.player.hand  # Optional zero-card confirmation is valid.
    assert decision(adapter).context.kind == 'combat'


def test_stale_illegal_foreign_and_replayed_bindings_never_mutate():
    run = fury_game()
    adapter = HeadlessAdapter(run)
    first = adapter.observe()
    before = run.snapshot()
    for binding, ref, reason in ((first.binding, 'action:999', 'invalid_action'),
                                 (first.binding, {}, 'invalid_action'),
                                 (object(), first.decision.candidates[0].ref, 'stale_decision')):
        report = adapter.step(binding, ref)
        assert report.reason == reason and report.mutation == 'none'
        assert run.snapshot() == before
    action(adapter, 'play_card')
    after = run.snapshot()
    assert adapter.step(first.binding, first.decision.candidates[-1].ref).reason == 'stale_decision'
    assert run.snapshot() == after
    frame = adapter.observe()
    run.combat.player.energy += 1
    after = run.snapshot()
    assert adapter.step(frame.binding, frame.decision.candidates[0].ref).reason == 'stale_decision'
    assert run.snapshot() == after


def test_selection_capacity_and_old_toggle_rejected():
    run = fury_game()
    adapter = HeadlessAdapter(run)
    action(adapter, 'play_card')
    frame = adapter.observe()
    option = next(a for a in frame.decision.candidates if a.kind == 'select_card')
    action(adapter, 'select_card')
    action(adapter, 'select_card')
    full = decision(adapter)
    assert {a.kind for a in full.candidates} == {'deselect_card', 'confirm_selection'}
    before = run.snapshot()
    assert adapter.step(frame.binding, option.ref).reason == 'stale_decision'
    assert run.snapshot() == before


def test_enemy_target_identity_survives_an_earlier_death():
    run = game(cards=('strike', 'strike'))
    combat, p = run.combat, run.combat.player
    p.hand.extend(p.deck.draw_pile)
    p.deck.draw_pile.clear()
    combat.enemies[0].hp = 1
    second = SimpleEnemy(max_hp=40)
    second.combat_player = p
    combat.enemies.append(second)
    adapter = HeadlessAdapter(run)
    initial = decision(adapter)
    first_ref, second_ref = [enemy.ref for enemy in initial.context.enemies]
    action(adapter, 'play_card', target=first_ref)
    after = decision(adapter)
    assert after.context.enemies[1].ref == second_ref
    targets = {a.target for a in after.candidates if a.kind == 'play_card'}
    assert targets == {second_ref}
    action(adapter, 'play_card', target=second_ref)
    assert second.hp == 34


def test_combat_preview_modifiers_only_apply_to_hand_and_play_area():
    run = game(cards=('strike', 'defend') * 3)
    p = run.combat.player
    cards = list(p.deck.draw_pile)
    p.deck.draw_pile.clear()
    for definition in ('strike', 'defend'):
        copies = [card for card in cards if card.definition.definition_id == definition]
        p.hand.append(copies[0])
        p.deck.draw_pile.append(copies[1])
        p.deck.discard_pile.append(copies[2])
    p.strength = 3
    p.rules.powers['dexterity'] = 3
    p.statuses.add('frail', 1)
    before = run.snapshot()
    public = decision(HeadlessAdapter(run))
    assert run.snapshot() == before
    for pile in public.context.piles:
        if pile.kind not in ('hand', 'draw', 'discard'):
            continue
        values = {card.definition_id: {v.key: v.amount for v in card.values.value} for card in pile.cards.value}
        assert values['strike']['damage'] == (9 if pile.kind == 'hand' else 6)
        assert values['defend']['block'] == (6 if pile.kind == 'hand' else 5)


@pytest.mark.parametrize('weak, vulnerable, strength, damage', [(0, 1, 0, 9), (1, 1, 0, 6), (1, 1, 1, 7)])
def test_enemy_intent_uses_public_target_modifiers_with_one_rounding(weak, vulnerable, strength, damage):
    run = game()
    enemy = run.combat.enemies[0]
    enemy.strength = strength
    enemy.statuses.add('weak', weak)
    run.combat.player.statuses.add('vulnerable', vulnerable)
    before = run.snapshot()
    public = decision(HeadlessAdapter(run))
    assert public.context.enemies[0].intents.value[0].damage.value == damage
    assert run.snapshot() == before


def test_temporary_enemy_strength_reduction_projects_effective_stat_and_restoration():
    run = game(cards=('dark_shackles',))
    p = run.combat.player
    p.hand.extend(p.deck.draw_pile)
    p.deck.draw_pile.clear()
    adapter = HeadlessAdapter(run)
    action(adapter, 'play_card')
    enemy = decision(adapter).context.enemies[0]
    powers = {power.definition_id: power.amount for power in enemy.powers.value}
    assert powers == {'dark_shackles': 9, 'strength': -9}
    assert enemy.intents.value[0].damage.value == 0


def test_map_edge_storage_order_is_not_candidate_order():
    graph = MapGraph((MapNode('a', 'combat', ('c', 'b'), 'overgrowth_nibbit', row=1, column=0),
                      MapNode('b', 'combat', (), 'overgrowth_nibbit', row=2, column=1),
                      MapNode('c', 'combat', (), 'overgrowth_nibbit', row=2, column=2)), 'a')
    run = RunEngine(graph=graph)
    run.state.current_node_id = 'a'
    run.state.visited_nodes = ['a']
    adapter = HeadlessAdapter(run)
    before = decision(adapter)
    run.graph = replace(graph, nodes=(replace(graph.nodes[0], next_node_ids=('b', 'c')), *graph.nodes[1:]))
    assert decision(adapter) == before


def test_reapplied_power_gets_new_identity_after_visible_removal():
    run = fury_game()
    run.combat.player.rules.powers['vigor'] = 3
    adapter = HeadlessAdapter(run)
    original = decision(adapter).context.powers.value[0].ref
    action(adapter, 'play_card')
    assert decision(adapter).context.combat.powers.value == ()
    run.combat.player.rules.powers['vigor'] = 3
    assert decision(adapter).context.combat.powers.value[0].ref != original


def test_virtual_power_pile_requires_and_uses_public_play_history():
    run = game(cards=('inflame', 'strike'))
    p = run.combat.player
    p.hand.extend(p.deck.draw_pile)
    p.deck.draw_pile.clear()
    adapter = HeadlessAdapter(run)
    before = decision(adapter)
    card = next(card for card in combat_cards(before.context).values() if card.definition_id == 'inflame')
    action(adapter, 'play_card', subject=card.ref)
    after = decision(adapter)
    assert next(pile for pile in after.context.piles if pile.kind == 'powers').cards.value == (card,)
    with pytest.raises(UnsupportedProfile, match='power_card_history'):
        HeadlessAdapter(run).observe()
    # Only the private retained object changed; there is no native pile to read.
    p.deck.powers[0].upgrade()
    assert decision(adapter) == after


def test_leaving_resolved_rewards_does_not_invent_a_skip():
    run, adapter = reward_game()
    run.state.pending['potion'] = None
    action(adapter, 'claim_reward')
    action(adapter, 'open_card_reward')
    action(adapter, 'choose_reward_card')
    history = decision(adapter).run.history.value.events
    action(adapter, 'leave_rewards')
    assert decision(adapter).run.history.value.events == history


def test_leaving_unresolved_rewards_records_exact_forfeited_entries():
    _, adapter = reward_game()
    before = decision(adapter)
    unresolved = tuple(reward.ref for reward in before.context.entries if not reward.resolved)
    action(adapter, 'leave_rewards')
    history = decision(adapter).run.history.value.events
    assert tuple(event.subject.value for event in history if event.kind == 'reward_skipped') == unresolved


@pytest.mark.parametrize('character', ['ironclad', 'silent', 'regent', 'necrobinder', 'defect'])
def test_all_five_starter_resource_shapes(character):
    run = RunEngine.act1(character=character, seed=1)
    run.apply(ChooseNode(run.graph.start_id))
    adapter = HeadlessAdapter(run)
    before = run.snapshot()
    frame = adapter.observe()
    resources = frame.decision.context.resources
    assert run.snapshot() == before
    assert (resources.stars.status == 'known') == (character == 'regent')
    assert (resources.osty.status == 'known') == (character == 'necrobinder')
    assert (resources.orbs.status == 'known') == (character == 'defect')
    assert c.require_ready(frame.decision) == frame.decision


def test_per_blade_damage_osty_absence_and_focus_adjusted_orbs():
    run = game(character='regent', cards=('sovereign_blade', 'sovereign_blade'))
    p = run.combat.player
    p.deck.draw_pile[0].combat_state.extra_damage = 5
    p.deck.draw_pile[1].combat_state.extra_damage = 17
    public = decision(HeadlessAdapter(run))
    cards = combat_cards(public.context)
    assert sorted(next(v.amount for v in cards[ref].values.value if v.key == 'damage')
                  for ref in public.context.resources.sovereign_blades.value) == [15, 27]
    run = game(character='necrobinder', cards=('bodyguard', 'unleash'))
    p = run.combat.player
    p.rules.osty = None
    adapter = HeadlessAdapter(run)
    assert decision(adapter).context.resources.osty.value.creature is None
    p.rules.osty = {'hp': 7, 'max_hp': 11}
    public = decision(adapter)
    assert public.context.resources.osty.value.creature.hp == 7
    unleash = next(card for card in combat_cards(public.context).values() if card.definition_id == 'unleash')
    assert next(v.amount for v in unleash.values.value if v.key == 'damage') == 13
    run = game(character='defect', cards=('zap', 'dualcast'))
    p = run.combat.player
    p.rules.powers['focus'] = 2
    p.rules.orbs = {'private.999': {'kind': 'dark', 'value': 23}, 'private.54': {'kind': 'frost', 'value': 0}}
    p.rules.orb_order = ['private.999', 'private.54']
    resources = decision(HeadlessAdapter(run)).context.resources
    assert [(o.kind, o.passive, o.evoke) for o in resources.orbs.value] == [('dark', 8, 23), ('frost', 4, 7)]


def test_off_character_resource_cards_preserve_known_zero_and_absence():
    run = game(cards=('venerate', 'bodyguard', 'zap'))
    resources = decision(HeadlessAdapter(run)).context.resources
    assert resources.stars == c.known(0)
    assert resources.sovereign_blades == c.known(())
    assert resources.osty == c.known(c.OstyState(None))
    assert resources.orb_slots == c.known(0) and resources.orbs == c.known(())


def test_observation_is_read_only_and_policy_cannot_access_engine():
    run = fury_game()
    adapter = HeadlessAdapter(run)
    before = deepcopy(run.snapshot())
    first = adapter.observe()
    for _ in range(5):
        assert adapter.observe() is first
        choose_action(c.loads(c.dumps(first.decision)))
    assert run.snapshot() == before
    source = Path(__file__).parents[2] / 'game/agent/policy.py'
    imports = [node.module for node in ast.walk(ast.parse(source.read_text())) if isinstance(node, ast.ImportFrom)]
    assert imports == ['game.agent']
    assert set(c.to_dict(first.decision)) == {'schema', 'profile', 'run', 'context', 'candidates'}


def test_adapter_and_chooser_require_no_optional_dependencies():
    result = subprocess.run([sys.executable, '-S', '-c',
        'from game.agent.headless import HeadlessAdapter; '
        'from game.agent.policy import choose_action; '
        'from game.headless.run.engine import RunEngine; '
        'a = HeadlessAdapter(RunEngine.ironclad_slice(seed=2)); '
        'f = a.observe(); '
        'assert a.step(f.binding, choose_action(f.decision).ref).status == "reconciled"; '
        'assert a.observe().decision.context.kind == "combat"'],
        cwd=Path(__file__).parents[2], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('field', ['hp', 'gold', 'upgrade', 'cost', 'damage', 'weak'])
def test_changed_visible_state_is_distinguishable(field):
    run = fury_game()
    adapter = HeadlessAdapter(run)
    before = decision(adapter)
    p = run.combat.player
    if field == 'hp': p.hp -= 1
    elif field == 'gold': run.state.gold += 1
    elif field == 'upgrade': p.hand[0].upgrade()
    elif field == 'cost': p.hand[0].combat_state.turn_cost_change += 1
    elif field == 'damage': p.hand[0].combat_state.extra_damage += 5
    elif field == 'weak': p.statuses.add('weak', 1)
    after = decision(adapter)
    assert after != before
    assert c.require_ready(after) == after


def test_private_seed_and_allocator_history_do_not_change_public_names():
    left, right = game(seed=3), game(seed=42)
    right.state.next_card_id += 100
    right.state.next_item_id += 100
    assert decision(HeadlessAdapter(left)) == decision(HeadlessAdapter(right))


def test_hidden_draw_order_rng_allocators_and_future_map_assignments_are_not_features():
    run = game(cards=('strike', 'strike', 'defend', 'bash'))
    adapter = HeadlessAdapter(run)
    before = decision(adapter)
    p = run.combat.player
    p.deck.draw_pile.reverse()
    p.deck.rng.random()
    p.deck.selection_rng.random()
    run.state.next_card_id += 100
    run.state.next_item_id += 100
    run.state.potion_drop_chance = 90
    run.graph = replace(run.graph, nodes=tuple(replace(node, encounter_id='overgrowth_shrinker_beetle')
                                             for node in run.graph.nodes))
    assert decision(adapter) == before
    p.energy += 1
    assert decision(adapter) != before


def test_indistinguishable_draw_copies_do_not_reveal_the_next_physical_card():
    left, right = game(cards=('strike', 'strike', 'strike')), game(cards=('strike', 'strike', 'strike'))
    a, b = HeadlessAdapter(left), HeadlessAdapter(right)
    assert decision(a) == decision(b)
    right.combat.player.deck.draw_pile.reverse()
    # Drawing one is a controlled observation premise; it changes no adapter
    # policy rule and produces equal public traces for indistinguishable copies.
    for run in (left, right):
        run.combat.player.draw_cards(1)
    assert decision(a) == decision(b)
    for adapter in (a, b):
        action(adapter, 'play_card')
    assert decision(a) == decision(b)


def test_closed_rewards_hide_offers_and_open_without_rng_or_game_mutation():
    run, adapter = reward_game()
    parent = decision(adapter)
    assert all(reward.cards.status == 'not_applicable' for reward in parent.context.entries)
    run.state.pending['offers'].reverse()
    run.state.pending['card_modifiers'].reverse()
    assert decision(adapter) == parent
    before = run.snapshot()
    action(adapter, 'open_card_reward')
    assert run.snapshot() == before
    child = decision(adapter)
    assert {a.kind for a in child.candidates} == {'choose_reward_card', 'skip_reward'}
    assert [card.definition_id for reward in child.context.entries if reward.kind == 'card'
            for card in reward.cards.value] == run.state.pending['offers']
    action(adapter, 'skip_reward')
    assert all(reward.cards.status == 'not_applicable' for reward in decision(adapter).context.entries)


def test_duplicate_reward_offers_keep_exact_position_and_modifier():
    run, adapter = reward_game()
    run.state.pending['offers'] = ['strike', 'strike', 'defend']
    run.state.pending['card_modifiers'][0]['upgrade_level'] = 0
    run.state.pending['card_modifiers'][1]['upgrade_level'] = 1
    action(adapter, 'open_card_reward')
    public = decision(adapter)
    reward = next(r for r in public.context.entries if r.kind == 'card')
    assert reward.cards.value[0].ref != reward.cards.value[1].ref
    action(adapter, 'choose_reward_card', target=reward.cards.value[1].ref)
    assert run.state.deck[-1].definition.definition_id == 'strike' and run.state.deck[-1].upgrade_level == 1
    public = decision(adapter)
    assert any(card.ref == reward.cards.value[1].ref and card.upgrade_level == 1 for card in public.run.deck.value)
    resolved = next(r for r in public.context.entries if r.kind == 'card')
    assert resolved.resolved and resolved.cards.status == 'not_applicable'


def test_restore_reset_and_other_adapter_bindings_are_invalid():
    run = fury_game()
    adapter = HeadlessAdapter(run)
    first = adapter.observe()
    snapshot = deepcopy(run.snapshot())
    run.restore(snapshot)
    assert adapter.step(first.binding, first.decision.candidates[0].ref).reason == 'stale_decision'
    attached = adapter.observe()
    assert attached.binding is not first.binding
    assert attached.decision == first.decision
    assert attached.decision.run.history.value.events == ()
    adapter.reset(run)
    assert adapter.step(attached.binding, attached.decision.candidates[0].ref).reason == 'stale_decision'
    frame = adapter.observe()
    other = HeadlessAdapter(run)
    other.observe()
    assert other.step(frame.binding, frame.decision.candidates[0].ref).reason == 'stale_decision'


@pytest.mark.parametrize('phase,kind,reason', [(RunPhase.VICTORY, 'victory', 'none'),
    (RunPhase.DEFEAT, 'defeat', 'none'), (RunPhase.SLICE_COMPLETE, 'truncated', 'slice_complete'),
    (RunPhase.ACT_COMPLETE, 'truncated', 'act_complete')])
def test_outcomes_are_separate_from_adapter_failures(phase, kind, reason):
    run = game()
    run.combat = None
    run.state.phase = phase
    result = HeadlessAdapter(run).observe()
    assert result == c.RunOutcome('sts_run_outcome_v1', kind, reason)


def test_executed_death_is_a_game_outcome():
    run = game()
    run.combat.player.hp = 1
    run.state.hp = 1
    adapter = HeadlessAdapter(run)
    action(adapter, 'end_turn')
    assert adapter.observe() == c.RunOutcome('sts_run_outcome_v1', 'defeat', 'none')


def test_unsupported_legal_family_is_not_silently_filtered():
    run = game()
    add_potion(run.state, 'fire_potion')
    before = run.snapshot()
    with pytest.raises(UnsupportedProfile, match='legal_action_family') as error:
        HeadlessAdapter(run).observe()
    assert error.value.report.status == 'unsupported'
    assert error.value.report.mutation == 'none'
    assert run.snapshot() == before


def test_unsupported_visible_mechanism_does_not_claim_empty_public_values():
    run = game(cards=('demon_form',))
    run.combat.player.rules.powers['demon_form'] = 2
    with pytest.raises(UnsupportedProfile, match='power_display'):
        HeadlessAdapter(run).observe()


@pytest.mark.parametrize('name', ['decay', 'debt', 'regret'])
def test_unmapped_curse_hooks_are_not_known_empty_variables(name):
    run = game(cards=(name,))
    with pytest.raises(UnsupportedProfile, match='curse_variables'):
        HeadlessAdapter(run).observe()


def test_backend_exception_stops_without_fabricated_loss_or_retry(monkeypatch):
    run = fury_game()
    adapter = HeadlessAdapter(run)
    frame = adapter.observe()
    def fail(command):
        run.state.gold += 1
        raise RuntimeError('test backend failure after mutation')
    monkeypatch.setattr(run, 'apply', fail)
    with pytest.raises(AdapterFault, match='uncertain'):
        adapter.step(frame.binding, frame.decision.candidates[0].ref)
    with pytest.raises(AdapterFault, match='stopped'):
        adapter.observe()
    with pytest.raises(AdapterFault, match='stopped'):
        adapter.step(frame.binding, frame.decision.candidates[0].ref)

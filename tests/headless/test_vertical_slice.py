"""M1 gameplay acceptance and adversarial continuation cases.

Native scalar expectations are recorded in the vertical-slice evidence note;
authored routing/content sampling and synthetic boundary setups are explicit.
"""

import json
from copy import deepcopy

import pytest

from game.cli.headless_play import choose_demo_action, play_slice
from game.headless.core.actions import EndTurn, PlayCard
from game.headless.run.actions import (
    ChooseNode, ClaimGold, ChooseRewardCard, ClaimPotion, LeaveRewards,
    Rest, Smith, ChooseUpgrade, LeaveRest, UsePotion, DiscardPotion,
)
from game.headless.run.engine import RunEngine
from game.headless.run.inventory import add_potion, add_relic, remove_relic
from game.headless.run.rest_site import begin_rest_site
from game.headless.run.state import RunPhase


def serialized(engine):
    return json.loads(json.dumps(engine.snapshot()))


def clone(engine):
    result = RunEngine()
    result.restore(serialized(engine))
    return result


def advance_until(engine, phase):
    for _ in range(100):
        if engine.state.phase is phase:
            return
        engine.apply(choose_demo_action(engine))
    pytest.fail("Expected decision was not reached.")


def assert_rejected(engine, action):
    before = serialized(engine)
    with pytest.raises(ValueError):
        engine.apply(action)
    assert serialized(engine) == before


def test_native_ironclad_start_and_explicit_difficulty():
    engine = RunEngine.ironclad_slice(seed=2)
    state = engine.state
    assert (state.config.character, state.config.ascension) == ("ironclad", 0)
    assert (state.hp, state.max_hp, state.gold) == (80, 80, 99)
    assert [c.definition.definition_id for c in state.deck] == ["strike"] * 5 + ["defend"] * 4 + ["bash"]
    assert [r.definition_id for r in state.relics] == ["burning_blood"]
    assert state.potions == [None, None, None]
    assert engine.legal_actions() == (ChooseNode("fight_1"),)
    engine.apply(ChooseNode("fight_1"))
    assert engine.combat.player.energy == 3
    assert len(engine.combat.player.hand) == 5
    for unsupported in (-1, 1, 10, True, "0"):
        with pytest.raises(ValueError):
            RunEngine.ironclad_slice(ascension=unsupported)


@pytest.mark.parametrize("rest_choice", ["rest", "smith"])
@pytest.mark.parametrize("seed", [0, 2, 4])
def test_entire_slice_and_json_continuation_at_every_decision(seed, rest_choice):
    engine, trace = play_slice(seed=seed, rest_choice=rest_choice, verify_restore=True)
    assert engine.state.phase is RunPhase.SLICE_COMPLETE
    assert engine.state.combats_completed == 2
    assert engine.state.visited_nodes == ["fight_1", "camp", "fight_2", "slice_end"]
    assert 119 <= engine.state.gold <= 139
    assert len(engine.state.deck) == 12
    assert sum(c.upgrade_level for c in engine.state.deck) == (rest_choice == "smith")
    assert sum(t["action"] == "UsePotion" for t in trace) == (seed in (2, 4))
    assert engine.legal_actions() == ()
    assert serialized(clone(engine)) == serialized(engine)
    assert_rejected(engine, ChooseNode("fight_1"))


def test_smith_cancellation_identity_and_second_combat_handoff():
    engine = RunEngine.ironclad_slice(seed=2)
    advance_until(engine, RunPhase.ROOM)
    original = serialized(engine)
    assert_rejected(engine, LeaveRest())
    engine.apply(Smith())
    pending = clone(engine)
    engine.apply(ChooseUpgrade(None))
    assert serialized(engine) == original
    pending.apply(ChooseUpgrade("run.card.0"))
    assert [c.upgrade_level for c in pending.state.deck[:5]] == [1, 0, 0, 0, 0]
    assert_rejected(pending, ChooseUpgrade("run.card.1"))
    persistent = {c.instance_id: c.upgrade_level for c in pending.state.deck}
    hp, items = pending.state.hp, deepcopy(pending.state.potions)
    pending.apply(LeaveRest())
    pending.apply(ChooseNode("fight_2"))
    assert pending.combat.player.hp == hp
    assert pending.state.potions == items
    deck = pending.combat.player.deck
    combat_cards = deck.hand + deck.draw_pile + deck.discard_pile + deck.exhaust_pile
    assert {c.instance_id: c.upgrade_level for c in combat_cards} == persistent
    assert all(c is not next(p for p in pending.state.deck if p.instance_id == c.instance_id) for c in combat_cards)


@pytest.mark.parametrize("max_hp,hp,expected", [(80, 30, 54), (81, 30, 54), (80, 75, 80), (80, 80, 80)])
def test_rest_heals_thirty_percent_rounded_down_capped_once(max_hp, hp, expected):
    engine = RunEngine(max_hp=max_hp, hp=hp)
    begin_rest_site(engine.state)
    assert engine.apply(Rest()) == expected - hp
    assert engine.state.hp == expected
    assert_rejected(engine, Rest())
    assert_rejected(engine, Smith())
    engine.apply(LeaveRest())
    assert engine.state.phase is RunPhase.ROUTE


def test_smith_omitted_when_no_implemented_upgrade_is_available():
    engine = RunEngine(card_ids=["strike"])
    engine.upgrade_card("run.card.0")
    begin_rest_site(engine.state)
    assert engine.legal_actions() == (Rest(),)
    assert_rejected(engine, Smith())


@pytest.mark.parametrize("hp,expected", [(40, 46), (78, 80)])
def test_fire_potion_kill_consumes_before_single_victory_hook_and_rewards(hp, expected):
    engine = RunEngine.ironclad_slice(seed=2)
    engine.state.hp = hp
    potion = add_potion(engine.state, "fire_potion")
    engine.apply(ChooseNode("fight_1"))
    engine.combat.enemies[0].hp = 20  # Synthetic exact lethal boundary.
    engine.combat.player.energy = 0
    engine.apply(UsePotion(potion.instance_id, 0))
    assert engine.state.hp == expected
    assert engine.state.potions == [None] * 3
    assert engine.state.combats_completed == 1
    assert engine.state.phase is RunPhase.REWARD
    after = serialized(engine)
    with pytest.raises(ValueError):
        engine.finish_combat()
    assert serialized(engine) == after
    assert_rejected(engine, UsePotion(potion.instance_id, 0))


def test_defeat_has_no_heal_no_rewards_and_no_more_commands():
    engine = RunEngine.ironclad_slice(seed=0)
    engine.state.hp = 1
    engine.apply(ChooseNode("fight_1"))
    for _ in range(5):
        engine.apply(EndTurn())
        if engine.state.phase is RunPhase.DEFEAT:
            break
    assert engine.state.phase is RunPhase.DEFEAT
    assert engine.state.hp == 0 and engine.state.pending is None
    assert engine.state.rng.request_count("reward_gold") == 0
    assert engine.legal_actions() == ()
    assert serialized(clone(engine)) == serialized(engine)


def test_potions_validate_target_and_ignore_attack_modifiers_without_energy_cost():
    engine = RunEngine.ironclad_slice(seed=0)
    fire = add_potion(engine.state, "fire_potion")
    block = add_potion(engine.state, "block_potion")
    assert_rejected(engine, UsePotion(fire.instance_id, 0))
    engine.apply(ChooseNode("fight_1"))
    combat = engine.combat
    combat.player.energy = 0
    combat.player.strength = 50
    enemy = combat.enemies[0]
    enemy.apply_status("vulnerable", 2)
    enemy.block = 7
    hp = enemy.hp
    assert_rejected(engine, UsePotion(fire.instance_id))
    assert_rejected(engine, UsePotion(fire.instance_id, 1))
    assert_rejected(engine, UsePotion(block.instance_id, 0))
    engine.apply(UsePotion(fire.instance_id, 0))
    assert enemy.hp == hp - 13 and enemy.block == 0
    assert combat.player.energy == 0
    engine.apply(UsePotion(block.instance_id))
    assert combat.player.block == 12 and combat.player.energy == 0
    assert engine.state.potions == [None] * 3
    assert_rejected(engine, UsePotion(block.instance_id))


def test_potion_target_uses_stable_enemy_slots_and_rejects_dead_targets():
    engine = RunEngine.ironclad_slice(seed=0)
    advance_until(engine, RunPhase.ROOM)
    engine.apply(Rest())
    engine.apply(LeaveRest())
    engine.apply(ChooseNode("fight_2"))
    potion = add_potion(engine.state, "fire_potion")
    engine.combat.enemies[0].hp = 0  # Synthetic dead leading slot.
    assert UsePotion(potion.instance_id, 1) in engine.legal_actions()
    assert_rejected(engine, UsePotion(potion.instance_id, 0))


def test_full_inventory_discard_then_claim_and_no_item_identity_reuse():
    engine = RunEngine.ironclad_slice(seed=2)
    advance_until(engine, RunPhase.REWARD)
    assert engine.state.pending["potion"] is not None
    owned = [add_potion(engine.state, "block_potion") for _ in range(3)]
    before = serialized(engine)
    with pytest.raises(ValueError):
        add_potion(engine.state, "fire_potion")
    assert serialized(engine) == before
    assert_rejected(engine, ClaimPotion())
    engine.apply(DiscardPotion(owned[1].instance_id))
    restored = clone(engine)
    acquired = restored.apply(ClaimPotion())
    assert restored.state.potions[0] == owned[0]
    assert restored.state.potions[2] == owned[2]
    assert restored.state.potions[1] == acquired
    assert acquired.instance_id not in {p.instance_id for p in owned}
    assert_rejected(restored, ClaimPotion())
    assert_rejected(restored, DiscardPotion(owned[1].instance_id))


def test_rewards_claim_or_skip_independently_and_never_reroll_on_reads():
    engine = RunEngine.ironclad_slice(seed=2)
    advance_until(engine, RunPhase.REWARD)
    before = serialized(engine)
    for _ in range(3):
        engine.legal_actions()
    assert serialized(engine) == before
    skipped = clone(engine)
    skipped.apply(LeaveRewards())
    assert skipped.state.gold == 99 and len(skipped.state.deck) == 10
    assert skipped.state.potions == [None] * 3
    gold = engine.state.pending["gold"]
    assert 10 <= gold <= 20
    engine.apply(ChooseRewardCard(None))
    engine.apply(ClaimGold())
    assert engine.state.gold == 99 + gold
    assert_rejected(engine, ClaimGold())
    assert_rejected(engine, ChooseRewardCard(None))
    engine.apply(LeaveRewards())
    assert_rejected(engine, ClaimPotion())


def test_relic_acquisition_removal_and_owned_ids():
    engine = RunEngine.ironclad_slice()
    before = serialized(engine)
    with pytest.raises(ValueError):
        add_relic(engine.state, "burning_blood")
    assert serialized(engine) == before
    removed = remove_relic(engine.state, engine.state.relics[0].instance_id)
    replacement = add_relic(engine.state, "burning_blood")
    assert removed.instance_id != replacement.instance_id


@pytest.mark.parametrize("corruption", ["ascension", "unknown_potion", "duplicate_item", "allocator", "chance", "slots", "item_rules", "completion"])
def test_corrupt_inventory_and_configuration_restore_is_atomic(corruption):
    engine = RunEngine.ironclad_slice(seed=2)
    add_potion(engine.state, "fire_potion")
    before = serialized(engine)
    bad = deepcopy(before)
    state = bad["state"]
    if corruption == "ascension": state["config"]["ascension"] = 1
    elif corruption == "unknown_potion": state["potions"][0]["definition_id"] = "unknown"
    elif corruption == "duplicate_item": state["potions"][1] = state["potions"][0]
    elif corruption == "allocator": state["next_item_id"] = 1
    elif corruption == "chance": state["potion_drop_chance"] = 110
    elif corruption == "slots": state["potions"].pop()
    elif corruption == "item_rules": bad["items"]["potions"][0]["damage"] += 1
    elif corruption == "completion": state["phase"] = "slice_complete"
    with pytest.raises(ValueError):
        engine.restore(bad)
    assert serialized(engine) == before


def test_corrupt_pending_smith_rejected_without_changing_live_engine():
    engine = RunEngine.ironclad_slice(seed=2)
    advance_until(engine, RunPhase.ROOM)
    engine.apply(Smith())
    before = serialized(engine)
    bad = deepcopy(before)
    bad["state"]["pending"]["eligible"].append("run.card.unknown")
    with pytest.raises(ValueError):
        engine.restore(bad)
    assert serialized(engine) == before


def test_failed_encounter_construction_preserves_route_and_rng(monkeypatch):
    from game.headless.run import flow, engine as engine_module
    from game.headless.encounters.base import EncounterDefinition
    def broken_encounter(rng):
        rng.randint(1, 100)
        raise ValueError("Synthetic construction failure")
    catalog = {"overgrowth_nibbit": EncounterDefinition(broken_encounter)}
    monkeypatch.setattr(flow, "ENCOUNTERS", catalog)
    monkeypatch.setattr(engine_module, "ENCOUNTERS", catalog)
    engine = RunEngine.ironclad_slice(seed=2)
    assert_rejected(engine, ChooseNode("fight_1"))


@pytest.mark.parametrize("seed,expected_chance", [(0, 50), (2, 30)])
def test_hallway_potion_odds_change_once_per_generated_reward(seed, expected_chance):
    engine = RunEngine.ironclad_slice(seed=seed)
    advance_until(engine, RunPhase.REWARD)
    assert engine.state.potion_drop_chance == expected_chance
    assert engine.state.rng.request_count("potion_drop") == 1
    assert engine.state.rng.request_count("reward_gold") == 1
    restored = clone(engine)
    restored.apply(LeaveRewards())
    assert restored.state.potion_drop_chance == expected_chance
    assert restored.state.rng.snapshot() == engine.state.rng.snapshot()


def test_unknown_reward_state_and_impossible_potion_claim_restore_rejected():
    engine = RunEngine.ironclad_slice(seed=0)
    advance_until(engine, RunPhase.REWARD)
    before = serialized(engine)
    for key, value in (("potion_claimed", True), ("resolver", "callback")):
        bad = deepcopy(before)
        bad["state"]["pending"][key] = value
        with pytest.raises(ValueError):
            engine.restore(bad)
        assert serialized(engine) == before

"""Native card expectations for the first slice, including full run acquisition."""

import json

import pytest

from game.cli.headless_play import choose_demo_action
from game.headless.core.actions import EndTurn, PlayCard
from game.headless.monsters.overgrowth import SimpleEnemy
from game.headless.run.actions import ChooseNode, ChooseRewardCard, ChooseUpgrade, LeaveRest, LeaveRewards, Smith
from game.headless.run.engine import RunEngine
from game.headless.run.state import RunPhase


def snapshot(engine):
    return json.loads(json.dumps(engine.snapshot()))


def put_in_hand(combat, instance_id):
    """Synthetic pile setup; conserve every original and its identity."""
    deck = combat.player.deck
    for pile in (deck.hand, deck.draw_pile, deck.discard_pile):
        for card in pile:
            if card.instance_id == instance_id:
                pile.remove(card)
                deck.hand.append(card)
                return card
    raise AssertionError("Missing card")


@pytest.mark.parametrize("card_id,level,cost,damage,block,draw", [
    ("pommel_strike", 0, 1, 9, 0, 1), ("pommel_strike", 1, 1, 10, 0, 2),
    ("shrug_it_off", 0, 1, 0, 8, 1), ("shrug_it_off", 1, 1, 0, 11, 1),
    ("iron_wave", 0, 1, 5, 5, 0), ("iron_wave", 1, 1, 7, 7, 0),
    ("body_slam", 0, 1, 7, 0, 0), ("body_slam", 1, 0, 7, 0, 0),
])
def test_verified_reward_card_values_and_legal_effects(card_id, level, cost, damage, block, draw):
    run = RunEngine(card_ids=(card_id, card_id, "strike", "defend", "strike"))
    selected = run.state.deck[0].instance_id
    if level:
        run.upgrade_card(selected)
    combat = run.start_combat(cards_per_turn=0, enemy_factory=lambda: SimpleEnemy(max_hp=100))
    card = put_in_hand(combat, selected)
    combat.player.block = 7 if card_id == "body_slam" else 0
    before_block = combat.player.block
    action = PlayCard(selected, 0 if card.spec.uses_target else None)
    assert action in combat.legal_actions()
    combat.apply(action)
    assert combat.enemies[0].hp == 100 - damage
    assert combat.player.block == before_block + block
    assert combat.player.energy == 3 - cost
    assert len(combat.player.hand) == draw
    assert card in combat.player.deck.discard_pile
    assert [c.upgrade_level for c in run.state.deck[:2]] == [level, 0]


@pytest.mark.parametrize("card_id,expected_damage,expected_block", [
    ("pommel_strike", 10, 0), ("shrug_it_off", 0, 11),
])
def test_damage_or_block_happens_before_drawing(monkeypatch, card_id, expected_damage, expected_block):
    run = RunEngine(card_ids=(card_id, "strike", "strike"))
    run.upgrade_card("run.card.0")
    combat = run.start_combat(cards_per_turn=0)
    card = put_in_hand(combat, "run.card.0")
    original_draw = combat.player.draw_cards
    calls = []
    def checked_draw(count):
        assert combat.enemies[0].hp == 40 - expected_damage
        assert combat.player.block == expected_block
        assert card not in combat.player.hand
        assert card not in combat.player.deck.discard_pile
        calls.append(count)
        return original_draw(count)
    monkeypatch.setattr(combat.player, "draw_cards", checked_draw)
    combat.apply(PlayCard(card.instance_id, 0 if card.spec.uses_target else None))
    assert calls == [card.spec.draw_count]


@pytest.mark.parametrize("level", [0, 1])
def test_body_slam_uses_current_block_strength_and_vulnerable_rounding(level):
    run = RunEngine(card_ids=("body_slam",))
    if level:
        run.upgrade_card("run.card.0")
    combat = run.start_combat()
    combat.player.block = 8
    combat.player.strength = 3
    combat.enemies[0].apply_status("vulnerable", 2)
    combat.enemies[0].block = 5
    combat.player.energy = 0 if level else 1
    combat.apply(PlayCard("run.card.0", 0))
    # floor((8 + 3) * 1.5) = 16; target block absorbs five.
    assert combat.enemies[0].hp == 29
    assert combat.player.block == 8
    assert combat.player.energy == 0


def test_slimed_draws_before_exhaust_and_cannot_be_upgraded_or_rewarded():
    run = RunEngine(card_ids=("slimed", "strike"))
    with pytest.raises(ValueError):
        run.upgrade_card("run.card.0")
    combat = run.start_combat(cards_per_turn=0)
    slimed = put_in_hand(combat, "run.card.0")
    deck = combat.player.deck
    deck.discard_pile.extend(deck.draw_pile)
    deck.draw_pile.clear()
    combat.apply(PlayCard(slimed.instance_id))
    assert [c.instance_id for c in deck.hand] == ["run.card.1"]
    assert deck.exhaust_pile == [slimed]
    assert deck.discard_pile == [] and deck.draw_pile == []
    assert combat.player.energy == 2
    assert "slimed" not in RunEngine.ironclad_slice().state.config.reward_cards


@pytest.mark.parametrize("survivor", [False, True])
def test_lethal_pommel_only_draws_if_combat_continues(survivor):
    run = RunEngine(card_ids=("pommel_strike", "strike", "defend"))
    run.upgrade_card("run.card.0")
    combat = run.start_combat(cards_per_turn=0, encounter_factory=lambda rng:
                             [SimpleEnemy(max_hp=10)] + ([SimpleEnemy()] if survivor else []))
    put_in_hand(combat, "run.card.0")
    deck = combat.player.deck
    deck.discard_pile.extend(deck.draw_pile)
    deck.draw_pile.clear()
    rng_before = combat.rng.getstate()
    combat.apply(PlayCard("run.card.0", 0))
    assert len(deck.hand) == (2 if survivor else 0)
    assert combat.done is not survivor
    if not survivor:
        assert combat.rng.getstate() == rng_before
        assert len(deck.discard_pile) == 3
    restored = RunEngine()
    restored.restore(snapshot(run))
    assert restored.combat.player.combat_enemies is restored.combat.enemies
    assert snapshot(restored) == snapshot(run)


def test_iron_wave_blocks_before_lethal_and_bash_does_not_debuff_dead_target():
    for card_id, damage, block in (("iron_wave", 7, 7), ("bash", 10, 0)):
        run = RunEngine(card_ids=(card_id,))
        run.upgrade_card("run.card.0")
        combat = run.start_combat(enemy_factory=lambda: SimpleEnemy(max_hp=damage))
        combat.apply(PlayCard("run.card.0", 0))
        assert combat.done and combat.winner == "player"
        assert combat.player.block == block
        assert combat.enemies[0].statuses.get("vulnerable") == 0


@pytest.mark.parametrize("card_id", ["pommel_strike", "shrug_it_off", "iron_wave", "body_slam", "armaments", "true_grit"])
def test_acquire_smith_and_play_each_reward_upgrade_through_real_run_commands(card_id):
    # Find an authored seed offering the requested card, without editing rewards.
    for seed in range(10):
        run = RunEngine.ironclad_slice(seed=seed)
        for _ in range(100):
            if run.state.phase is RunPhase.REWARD:
                break
            run.apply(choose_demo_action(run))
        if card_id in run.state.pending["offers"]:
            break
    else:
        pytest.fail("No reward offer in bounded seed panel")
    card = run.apply(ChooseRewardCard(card_id))
    selected = card.instance_id
    run.apply(LeaveRewards())
    run.apply(ChooseNode("camp"))
    run.apply(Smith())
    assert ChooseUpgrade(selected) in run.legal_actions()
    saved_selection = snapshot(run)
    restored = RunEngine()
    restored.restore(saved_selection)
    for engine in (run, restored):
        engine.apply(ChooseUpgrade(selected))
        engine.apply(LeaveRest())
        engine.apply(ChooseNode("fight_2"))
    assert snapshot(run) == snapshot(restored)
    played = False
    for _ in range(100):
        if not run.legal_actions():
            break
        action = next((a for a in run.legal_actions() if isinstance(a, PlayCard) and a.instance_id == selected), None)
        action = action or choose_demo_action(run)
        if isinstance(action, PlayCard) and action.instance_id == selected:
            assert next(c for c in run.combat.player.hand if c.instance_id == selected).upgrade_level == 1
            played = True
        restored = RunEngine()
        restored.restore(snapshot(run))
        run.apply(action)
        restored.apply(action)
        assert snapshot(run) == snapshot(restored)
    assert played
    assert run.state.phase is RunPhase.SLICE_COMPLETE
    assert next(c for c in run.state.deck if c.instance_id == selected).upgrade_level == 1

"""Pinned relic behaviors and interrupted combat ownership."""

import json
from dataclasses import replace
import pytest

from game.headless.core.actions import PlayCard, EndTurn, ChooseCombatCard, ConfirmCombatSelection
from game.headless.core.combat import CombatEngine
from game.headless.run.engine import RunEngine
from game.headless.run.inventory import add_relic
from game.headless.relics.base import RELICS
from game.headless.monsters.overgrowth import SimpleEnemy
from game.headless.cards.catalog import DEFAULT_CARDS


def saved(engine):
    return json.loads(json.dumps(engine.snapshot()))


def setup(*relics, cards=("strike", "strike", "defend", "defend", "bash"), hp=60, draw=10):
    run = RunEngine(card_ids=cards, hp=hp)
    for name in relics:
        add_relic(run.state, name)
    c = run.start_combat(cards_per_turn=draw, enemy_factory=lambda: SimpleEnemy(max_hp=1000))
    return run, c


def settle(run):
    for _ in range(100):
        if run.combat.player.pending_play is None and run.combat.player.rules.selection is None:
            return
        clone = RunEngine()
        clone.restore(saved(run))
        assert saved(clone) == saved(run)
        actions = run.legal_actions()
        action = ConfirmCombatSelection() if ConfirmCombatSelection() in actions else actions[0]
        run.apply(action)
        clone.apply(action)
        assert saved(clone) == saved(run)
    pytest.fail("Relic continuation did not settle.")


@pytest.mark.parametrize(
    "name",
    [
        n
        for n in RELICS
        if n in __import__("game.headless.relics.combat", fromlist=["COMBAT_RELICS"]).COMBAT_RELICS
    ],
)
def test_registered_combat_relics_json_roundtrip_and_four_turns(name):
    run, c = setup(name)
    settle(run)
    for _ in range(4):
        run.sync_combat_loot()
        clone = RunEngine()
        clone.restore(saved(run))
        assert saved(clone) == saved(run)
        run.apply(EndTurn())
        clone.apply(EndTurn())
        assert saved(clone) == saved(run)
        settle(run)


def test_opening_hp_block_and_stat_setup_are_not_overwritten():
    run, c = setup("anchor", "blood_vial", "red_skull", "vajra", "ruined_helmet", hp=30)
    assert c.player.hp == 32 and c.player.block == 10
    assert c.player.strength == 5  # Vajra first gain doubled, then Skull's3.
    c.player.lose_hp(1)
    assert c.player.strength == 5
    from game.headless.relics.combat import heal

    heal(c.player, 20)
    assert c.player.strength == 2


def test_pinned_pendulum_and_permafrost_values():
    run, c = setup(
        "pendulum", "permafrost", cards=("inflame", "inflame", "strike", "strike", "defend"), draw=0
    )
    c.player.draw_cards(2)
    # Explicitly put a Power in hand; the starting shuffle isn't the behavior under test.
    card = next(x for x in c.player.deck.all_cards() if x.definition.definition_id == "inflame")
    from game.headless.core.resolution import move_out

    move_out(c.player, card)
    c.player.hand.append(card)
    run.apply(PlayCard(card.instance_id))
    assert c.player.block == 7
    run.apply(EndTurn())
    assert not c.player.hand
    run.apply(EndTurn())
    assert len(c.player.hand) == 1


@pytest.mark.parametrize(
    "relics,loss", [(("beating_remnant", "tungsten_rod"), 19), (("tungsten_rod", "beating_remnant"), 20)]
)
def test_hp_loss_modifiers_preserve_inventory_order(relics, loss):
    run, c = setup(*relics)
    c.player.lose_hp(30)
    from game.headless.core.resolution import drain

    drain(c.player)
    assert c.player.hp == 60 - loss
    c.player.lose_hp(30)
    from game.headless.core.resolution import drain

    drain(c.player)
    assert c.player.hp == 60 - loss


def test_pen_nib_applies_to_all_hits_and_counter_survives_combat():
    run = RunEngine(card_ids=("sword_boomerang",))
    relic = add_relic(run.state, "pen_nib")
    run.state.relics[0] = replace(relic, counter=9)
    c = run.start_combat(enemy_factory=lambda: SimpleEnemy(max_hp=1000))
    run.apply(PlayCard("run.card.0"))
    assert c.enemies[0].hp == 982
    assert run.state.relics[0].counter == 0
    c.enemies[0].hp = 0
    c.resolve_external_effect()
    run.finish_combat()
    run.start_combat()
    assert run.combat.player.rules.relics[0]["counter"] == 0


def test_gambling_chip_discards_then_draws_and_does_not_reroll_reads():
    run, c = setup("gambling_chip", cards=("strike",) * 8, draw=5)
    before = saved(run)
    run.legal_actions()
    run.legal_actions()
    assert saved(run) == before
    chosen = c.player.hand[:2]
    for card in chosen:
        run.apply(ChooseCombatCard(card.instance_id))
    clone = RunEngine()
    clone.restore(saved(run))
    run.apply(ConfirmCombatSelection())
    clone.apply(ConfirmCombatSelection())
    assert saved(run) == saved(clone)
    assert len(c.player.hand) == 5
    assert all(card in c.player.deck.discard_pile for card in chosen)


@pytest.mark.parametrize("value", ["oops", None, True, -1])
def test_invalid_relic_memory_rejected_before_install(value):
    run, c = setup("letter_opener")
    before = saved(c)
    bad = json.loads(json.dumps(before))
    key = c.player.rules.relics[0]["instance_id"]
    bad["player"]["rules"]["relic_data"][key]["turn_skills"] = value
    with pytest.raises(ValueError):
        c.restore(bad)
    assert saved(c) == before


def interrupted_enemy(*, kill=False):
    from random import Random
    from game.headless.monsters.byrdonis import Byrdonis
    from game.headless.powers.ironclad import apply_power

    run = RunEngine(card_ids=("defend", "strike", "defend"))
    add_relic(run.state, "centennial_puzzle")
    c = run.start_combat(
        cards_per_turn=0, encounter_factory=lambda rng: [Byrdonis(rng), SimpleEnemy(max_hp=100)]
    )
    c.enemies[0]._intent_index = 0
    if kill:
        c.enemies[0].hp = 2
    p = c.player
    p.deck.discard_pile[:] = p.deck.draw_pile
    p.deck.draw_pile.clear()
    apply_power(p, "stratagem", 1)
    if kill:
        apply_power(p, "hellraiser", 1)
    p.deck.target_rng.seed(1)
    c.apply(EndTurn())
    assert p.rules.enemy_turn["move"]["hit"] == 1 and p.hp == 77
    return c


def test_enemy_multihit_reactive_choice_roundtrip_and_no_skipped_hits():
    c = interrupted_enemy()
    before = saved(c)
    clone = CombatEngine()
    clone.restore(before)
    bad = json.loads(json.dumps(before))
    bad["player"]["rules"]["enemy_turn"]["move"]["stage"] = "advance"
    with pytest.raises(ValueError):
        clone.restore(bad)
    identity = next(
        x.instance_id for x in c.player.deck.all_cards() if x.definition.definition_id == "defend"
    )
    for action in (ChooseCombatCard(identity), ConfirmCombatSelection()):
        c.apply(action)
        clone.apply(action)
        assert saved(c) == saved(clone)
    assert c.player.hp == 65  # three Pecks plus the second enemy's6.


def test_attacker_killed_during_reactive_draw_cannot_hit_again():
    c = interrupted_enemy(kill=True)
    clone = CombatEngine()
    clone.restore(saved(c))
    identity = next(
        x.instance_id for x in c.player.deck.all_cards() if x.definition.definition_id == "defend"
    )
    for action in (ChooseCombatCard(identity), ConfirmCombatSelection()):
        c.apply(action)
        clone.apply(action)
        assert saved(c) == saved(clone)
    assert not c.enemies[0].is_alive and c.player.hp == 71


def test_vambrace_and_frail_round_once():
    run, c = setup("vambrace", cards=("defend",))
    c.player.apply_status("frail", 1)
    run.apply(PlayCard("run.card.0"))
    assert c.player.block == 7


def test_vexing_puzzlebox_cost_reduction_lasts_across_turns():
    run, c = setup("vexing_puzzlebox", draw=0)
    generated = next(x for x in c.player.deck.all_cards() if not x.instance_id.startswith("run.card."))
    assert c.player.card_cost(generated) == 0
    run.apply(EndTurn())
    assert c.player.card_cost(generated) == 0
    clone = RunEngine()
    clone.restore(saved(run))
    assert saved(clone) == saved(run)

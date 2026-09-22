"""Starter upgrades checked against the pinned assembly's card definitions."""

import json

import pytest

from game.headless.core.actions import EndTurn, PlayCard
from game.headless.monsters.overgrowth import SimpleEnemy
from game.headless.run.engine import RunEngine


def _snapshot(run):
    return json.loads(json.dumps(run.snapshot()))


def test_defend_upgrade_gains_block_once_without_enemy_targeting():
    run = RunEngine(card_ids=("defend", "defend"))
    upgraded, base = [card.instance_id for card in run.state.deck]
    run.upgrade_card(upgraded)
    combat = run.start_combat(encounter_factory=lambda rng: [SimpleEnemy(), SimpleEnemy()])
    assert combat.legal_actions() == (EndTurn(), *(
        PlayCard(card.instance_id) for card in combat.player.hand
    ))
    before = _snapshot(run)
    with pytest.raises(ValueError, match="Illegal action"):
        combat.apply(PlayCard(upgraded, 0))
    assert _snapshot(run) == before
    combat.apply(PlayCard(base))
    assert (combat.player.block, combat.player.energy) == (5, 2)
    combat.apply(PlayCard(upgraded))
    assert (combat.player.block, combat.player.energy) == (13, 1)
    assert [enemy.hp for enemy in combat.enemies] == [40, 40]


def test_bash_upgrade_damages_selected_enemy_before_applying_vulnerable():
    run = RunEngine(card_ids=("bash", "bash", "strike"))
    upgraded, base, strike = [card.instance_id for card in run.state.deck]
    run.upgrade_card(upgraded)
    combat = run.start_combat(
        encounter_factory=lambda rng: [SimpleEnemy(), SimpleEnemy()], energy_per_turn=5,
    )
    combat.apply(PlayCard(base, 0))
    assert (combat.enemies[0].hp, combat.enemies[0].statuses.get("vulnerable")) == (32, 2)
    assert combat.enemies[1].hp == 40
    combat.apply(PlayCard(upgraded, 1))
    # Applying Vulnerable first would incorrectly turn this fresh-target hit into 15.
    assert (combat.enemies[1].hp, combat.enemies[1].statuses.get("vulnerable")) == (30, 3)
    assert combat.player.energy == 1
    combat.apply(PlayCard(strike, 1))
    assert combat.enemies[1].hp == 21
    assert combat.enemies[0].hp == 32
    assert combat.player.energy == 0


@pytest.mark.parametrize("definition_id", ("defend", "bash"))
def test_upgraded_instance_survives_reshuffle_restore_and_two_combats(definition_id):
    run = RunEngine(seed=43, card_ids=(definition_id, definition_id, "strike"))
    upgraded, duplicate, strike = [card.instance_id for card in run.state.deck]
    before = _snapshot(run)
    assert run.preview_upgrade(upgraded).name.endswith("+")
    assert _snapshot(run) == before
    run.upgrade_card(upgraded)
    assert [c.instance_id for c in run.state.deck] == [upgraded, duplicate, strike]
    assert [c.upgrade_level for c in run.state.deck] == [1, 0, 0]
    assert run.state.rng.snapshot() == before["state"]["rng"]
    assert run.state.next_card_id == before["state"]["next_card_id"]
    before = _snapshot(run)
    with pytest.raises(ValueError, match="Unsupported upgrade"):
        run.upgrade_card(upgraded)
    assert _snapshot(run) == before

    # First fight forces discard/reshuffle; the second uses the same master deck.
    for fight in range(2):
        combat = run.start_combat(enemy_factory=lambda: SimpleEnemy(max_hp=25))
        card = next(c for c in combat.player.hand if c.instance_id == upgraded)
        assert card.upgrade_level == 1
        assert next(c for c in combat.player.hand if c.instance_id == duplicate).upgrade_level == 0
        command = PlayCard(upgraded, 0 if card.spec.uses_target else None)
        combat.apply(command)
        assert card in combat.player.deck.discard_pile
        combat.apply(EndTurn())
        assert card in combat.player.hand

        restored = RunEngine()
        restored.restore(_snapshot(run))
        for _ in range(20):
            assert combat.legal_actions() == restored.combat.legal_actions()
            if combat.done:
                break
            # Use the upgraded instance and Strike; leave the duplicate unchanged.
            actions = combat.legal_actions()
            action = command if command in actions else PlayCard(strike, 0)
            if action not in actions:
                action = EndTurn()
            assert combat.apply(action) == restored.combat.apply(action)
            assert _snapshot(run) == _snapshot(restored)
        assert combat.winner == "player"
        run.finish_combat()
        restored.finish_combat()
        assert _snapshot(run) == _snapshot(restored)
        assert run.state.combats_completed == fight + 1
        assert [c.upgrade_level for c in run.state.deck] == [1, 0, 0]

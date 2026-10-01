"""Lethal retaliation must settle as defeat unless the player actually revives."""
from copy import deepcopy
import json

import pytest

from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.core.actions import EndTurn
from game.headless.core.combat import CombatEngine
from game.headless.run.config import RunConfig
from game.headless.run.engine import RunEngine
from game.headless.run.inventory import add_potion
from game.headless.run.state import RunPhase


def retaliation_run(*, hp=3, enemy_hp=1, revival=None):
    # Authored regression state, not a claim of a native full-run comparison.
    run = RunEngine(seed=17, hp=hp, card_ids=['guilty', 'defend'],
                    rng_profile='native', config=RunConfig())
    run.state.deck[0].combats_seen = 4
    for relic in ('burning_blood', 'bronze_scales', 'pumpkin_candle'):
        run.obtain_relic(relic)
    if revival == 'lizard_tail':
        run.obtain_relic(revival)
    elif revival == 'fairy_in_a_bottle':
        add_potion(run.state, revival)
    run.start_combat(encounter_id='underdocks_haunted_ship', cards_per_turn=0)
    # Its opening turn adds Dazed/Weak; exercise the following attack normally.
    run.apply(EndTurn())
    run.combat.enemies[0].hp = enemy_hp
    return run


def saved(engine):
    return json.loads(json.dumps(engine.snapshot()))


@pytest.mark.parametrize('hp,enemy_hp,winner', [
    (3, 1, 'enemy'), (80, 1, 'player'), (3, 60, 'enemy'), (80, 60, None),
])
def test_lethal_retaliation_outcome_and_run_handoff(hp, enemy_hp, winner):
    run = retaliation_run(hp=hp, enemy_hp=enemy_hp)
    candle = next(r.counter for r in run.state.relics if r.definition_id == 'pumpkin_candle')
    rewards_rng = deepcopy(run.state.rng.stream('rewards').getstate())
    original = saved(run)
    clone = RunEngine()
    clone.restore(original)
    for engine in (run, clone):
        combat = engine.combat
        result = engine.apply(EndTurn())
        assert result.winner == combat.winner == winner
        assert result.done == combat.done == (winner is not None)
        assert combat.player.hp < hp  # The current hit lands even if Thorns kills its source.
        assert combat.enemies[0].hp == max(0, enemy_hp - 3)
        if winner is not None:
            assert combat.legal_actions() == () and engine.combat is None
            restored = CombatEngine(cards=DEFAULT_CARDS)
            restored.restore(saved(combat))
            assert saved(restored) == saved(combat)
        if winner == 'enemy':
            assert engine.state.phase is RunPhase.DEFEAT
            assert engine.state.hp == 0 and engine.state.pending is None
            assert engine.legal_actions() == ()
            assert engine.state.deck[0].combats_seen == 4
            assert next(r for r in engine.state.relics if r.definition_id == 'pumpkin_candle').counter == candle
            assert engine.state.rng.stream('rewards').getstate() == rewards_rng
        elif winner == 'player':
            assert engine.state.phase is RunPhase.REWARD and engine.state.hp > 0
        else:
            assert engine.state.phase is RunPhase.COMBAT and engine.combat is combat
        restored_run = RunEngine()
        restored_run.restore(saved(engine))
        assert saved(restored_run) == saved(engine)
    assert saved(clone) == saved(run)


@pytest.mark.parametrize('revival', ['fairy_in_a_bottle', 'lizard_tail'])
def test_revival_before_terminal_check_preserves_last_enemy_victory(revival):
    run = retaliation_run(revival=revival)
    combat = run.combat
    result = run.apply(EndTurn())
    assert result.done and result.winner == 'player'
    assert combat.enemies[0].hp == 0 and combat.player.hp > 0
    assert run.state.phase is RunPhase.REWARD and run.state.hp > 0
    if revival == 'fairy_in_a_bottle':
        assert all(p is None for p in run.state.potions)
    else:
        assert next(r for r in run.state.relics if r.definition_id == revival).counter == 1
    other = RunEngine()
    other.restore(saved(run))
    assert saved(other) == saved(run)


def test_restore_rejects_false_victory_after_both_sides_die_atomically():
    combat = retaliation_run().combat
    assert combat.apply(EndTurn()).winner == 'enemy'
    correct = saved(combat)
    forged = deepcopy(correct)
    forged['winner'] = 'player'
    with pytest.raises(ValueError, match='terminal state'):
        combat.restore(forged)
    assert saved(combat) == correct

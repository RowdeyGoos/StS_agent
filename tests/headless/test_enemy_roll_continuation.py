"""A completed monster move keeps its pending roll through a later draw choice."""
from copy import deepcopy

import pytest

from game.headless.core.actions import EndTurn, ChooseCombatCard, ConfirmCombatSelection
from game.headless.run.engine import RunEngine
from game.headless.run.inventory import add_relic
from tests.headless.test_act2_run import saved


def paused_roll():
    run = RunEngine(seed=2, max_hp=1000, card_ids=('strike', 'defend'))
    add_relic(run.state, 'centennial_puzzle')
    run.start_combat(encounter_id='overgrowth_nibbits', cards_per_turn=0)
    p = run.combat.player
    run.combat.enemies[0]._intent_index = 2  # Hiss completes before the later hit.
    run.combat.enemies[1]._intent_index = 0
    p.rules.powers['stratagem'] = 1
    p.deck.discard_pile.extend(p.deck.draw_pile)
    p.deck.draw_pile.clear()
    run.apply(EndTurn())
    assert p.rules.selection and run.combat.enemies[0].turn_roll_pending
    return run


def test_pending_enemy_roll_resumes_once_and_rejects_detached_receipts():
    run = paused_roll()
    snapshot = saved(run)
    other = RunEngine()
    other.restore(snapshot)
    for target in (run, other):
        target.apply(next(a for a in target.legal_actions() if isinstance(a, ChooseCombatCard)))
        target.apply(ConfirmCombatSelection())
        assert target.combat.enemies[0].intent.move_name == 'Butt'
        assert not any(e.turn_roll_pending for e in target.combat.enemies)
    assert saved(run) == saved(other)
    for damage in ('drop_action', 'drop_roll', 'drop_owner', 'old_run', 'old_combat'):
        bad = deepcopy(snapshot)
        progress = bad['combat']['player']['rules']['enemy_turn']
        if damage == 'drop_action':
            progress['actions'].clear()
        elif damage == 'drop_roll':
            progress['actions'][0]['roll_next'] = False
        elif damage == 'drop_owner':
            bad['combat']['enemies'][0]['state']['turn_roll_pending'] = False
        elif damage == 'old_run':
            bad['schema'] = 'headless_run_state_v66'
        else:
            bad['combat']['schema'] = 'headless_combat_state_v45'
        with pytest.raises(ValueError):
            RunEngine().restore(bad)


def test_later_reactive_attack_preserves_an_already_acted_enemys_forced_stun():
    from game.headless.monsters.hive_normal import Tunneler
    from game.headless.monsters.hive_normal import Chomper
    run = RunEngine(seed=0, max_hp=1000, card_ids=('strike',))
    add_relic(run.state, 'centennial_puzzle')
    run.start_combat(encounter_factory=lambda rng: [Tunneler(rng), Chomper(rng)], cards_per_turn=0)
    p = run.combat.player
    run.combat.enemies[0]._intent_index = 1
    p.rules.powers['hellraiser'] = 1
    p.strength = 40
    run.apply(EndTurn())
    assert run.combat.enemies[0].intent.move_name == 'Dizzy'
    assert not run.combat.enemies[0].turn_roll_pending
    other = RunEngine()
    other.restore(saved(run))
    assert saved(other) == saved(run)


def test_queen_enrage_can_transition_after_end_of_side_doom():
    from game.headless.monsters.glory_bosses import Queen, TorchHeadAmalgam
    run = RunEngine(seed=0, max_hp=1000, card_ids=('strike',))
    run.start_combat(encounter_factory=lambda rng: [Queen(rng), TorchHeadAmalgam(rng)], cards_per_turn=0)
    queen, amalgam = run.combat.enemies
    queen._intent_index = 2  # Burn Bright completes before Doom kills her teammate.
    amalgam.statuses.add('doom', 1000)
    run.apply(EndTurn())
    assert not amalgam.is_alive
    assert queen.intent.move_name == 'Off With Your Head'
    assert not queen.turn_roll_pending
    other = RunEngine()
    other.restore(saved(run))
    assert saved(other) == saved(run)

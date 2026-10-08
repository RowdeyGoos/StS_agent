"""Hypothetical pile sampling keeps ordinary cached selectors restorable."""
from copy import deepcopy

import pytest

from game.agent.headless import HeadlessAdapter
from game.agent.search.direct import DirectWorld
from game.agent.search.public_keys import public_key
from game.headless.core.actions import ChooseCombatCard, ConfirmCombatSelection
from game.headless.draw_knowledge import DrawKnowledge
from game.headless.run.construction import materialize_combat_draw
from game.headless.run.engine import RunEngine
from game.headless.run.snapshots import restore_run


def selecting(kind):
    powers = ('stratagem', 'foregone_conclusion')
    source = None if kind in powers or kind == 'droplet_of_precognition' else kind.removesuffix('_up')
    run = RunEngine(seed=2, card_ids=([source] if source else []) + ['strike', 'defend'] * 9,
                    rng_profile='native')
    if kind == 'droplet_of_precognition':
        from game.headless.run.inventory import add_potion
        add_potion(run.state, kind)
    run.start_combat(encounter_id='overgrowth_vantom')
    p = run.combat.player
    if source:
        card = next(c for c in p.deck.all_cards() if c.definition.definition_id == source)
        if card not in p.hand:
            old = p.hand.pop()
            p.deck.draw_pile.remove(card)
            p.deck.draw_pile.append(old)
            p.hand.append(card)
        if kind.endswith('_up'):
            card.upgrade()
    if kind in powers:
        from game.headless.core.choices import begin
        from game.headless.core.piles import stratagem_cards
        p.rules.powers[kind] = 2
        begin(p, kind, stratagem_cards(p), minimum=2, maximum=2,
              operation='move' if kind == 'stratagem' else 'regent_foregone_conclusion')
    else:
        adapter = HeadlessAdapter(run, decision_profile='full_run_v2')
        frame = adapter.observe()
        if source:
            from .test_belief import play
            action = play(frame.decision, source)
        else:
            action = next(a for a in frame.decision.candidates if a.kind == 'use_potion')
        adapter.step(frame.binding, action.ref)
    assert p.rules.selection is not None
    assert restore_run(run.snapshot()).snapshot() == run.snapshot()
    return run


@pytest.mark.parametrize('kind', ('droplet_of_precognition', 'secret_technique', 'secret_weapon',
    'seeker_strike', 'stratagem', 'cleanse', 'seance', 'charge', 'charge_up', 'foregone_conclusion'))
@pytest.mark.parametrize('selected', (False, True))
def test_sampled_draw_selectors_preserve_public_choices_and_native_validation(kind, selected):
    run = selecting(kind)
    p = run.combat.player
    if selected:
        run.apply(ChooseCombatCard(p.rules.selection['candidates'][0]))
    selection = deepcopy(p.rules.selection)
    knowledge = DrawKnowledge(top=[p.deck.draw_pile[-1].instance_id], bottom=[p.deck.draw_pile[0].instance_id])
    world = DirectWorld(run, knowledge)
    public = public_key(world.project())
    original, orders = run.snapshot(), set()
    for seed in range(16):
        branch = world.fork(seed)
        bp = branch._run.combat.player
        orders.add(tuple(c.instance_id for c in bp.deck.draw_pile))
        assert public_key(branch.project()) == public
        assert bp.deck.draw_pile[-1].instance_id == knowledge.top[0]
        assert bp.deck.draw_pile[0].instance_id == knowledge.bottom[0]
        assert {**bp.rules.selection, 'candidates': selection['candidates']} == selection
        assert set(bp.rules.selection['candidates']) == set(selection['candidates'])
        snapshot = branch._run.snapshot()
        assert restore_run(snapshot).snapshot() == snapshot
        branch.fork(seed + 100)  # The previously broken next selection boundary.
        # Resampling itself never draws the engine RNG or changes the parent.
        rng_before = branch._run.state.rng.snapshot()
        materialize_combat_draw(branch._run, branch.knowledge)
        assert branch._run.state.rng.snapshot() == rng_before
        assert run.snapshot() == original
        while len(bp.rules.selection['selected']) < bp.rules.selection['minimum']:
            candidate = next(i for i in bp.rules.selection['candidates'] if i not in bp.rules.selection['selected'])
            branch._run.apply(ChooseCombatCard(candidate))
        branch._run.apply(ConfirmCombatSelection())
        assert restore_run(branch._run.snapshot()).snapshot() == branch._run.snapshot()
    assert len(orders) > 1


def test_materialization_cannot_repair_invalid_active_membership():
    run = selecting('droplet_of_precognition')
    run.combat.player.rules.selection['candidates'].pop()
    with pytest.raises(ValueError, match='Potion choice differs'):
        restore_run(run.snapshot())
    with pytest.raises(ValueError, match='changed membership'):
        materialize_combat_draw(run, DrawKnowledge())


def test_deferred_live_membership_and_whitelist_are_preserved():
    run = selecting('seeker_strike')
    p = run.combat.player
    selection = deepcopy(p.rules.selection)
    selection['candidates'].pop()
    p.rules.selection = None
    # A parked live choice can legitimately have stale membership. The ordinary
    # scheduler owns updating it, and resampling must not add missing members.
    p.rules.deferred_hooks = [dict(selection=selection)]
    original = deepcopy(selection)
    materialize_combat_draw(run, DrawKnowledge())
    assert selection == original

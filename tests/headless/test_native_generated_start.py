"""One generated native Neow→combat trace, with JSON continuation at each action."""
import json
from pathlib import Path

from game.headless.core.actions import EndTurn, PlayCard
from game.headless.run import ancient
from game.headless.run.actions import ChooseAncientRelic, ChooseNode, ChooseRelicReward
from game.headless.run.engine import RunEngine
from game.headless.run.state import RunPhase
from tests.headless.test_act2_run import step

RECORD = json.loads((Path(__file__).parents[2] / 'docs/evidence/native_generated_start_verified_2026_09_20.json').read_text())


def card_id(card):
    name = card.definition.definition_id.upper()
    return name + '_IRONCLAD' if name in ('STRIKE', 'DEFEND') else name


def boundary(run):
    p = run.combat.player
    return dict(hp=p.hp, block=p.block, energy=p.energy,
                hand=[dict(id=card_id(c), upgrade=c.upgrade_level) for c in p.hand],
                enemies=[dict(id=e.name.upper(), hp=e.hp, block=e.block) for e in run.combat.enemies])


def test_generated_neow_and_complete_first_combat_match_native():
    row, = RECORD['result']['rows']
    run = RunEngine.ironclad_run(seed=int(row['seed']), ancient_profile=ancient.PROFILE)
    assert [a.definition_id.upper() for a in run.legal_actions()] == row['offers']
    step(run, ChooseAncientRelic(row['choice'].lower()))
    # Native TestCardSelector chooses the first complete Scroll Boxes bundle.
    assert run.state.relic_work[0]['offers'][0] == ['perfected_strike', 'shrug_it_off', 'battle_trance']
    step(run, ChooseRelicReward(0))
    assert run.state.rng.request_count('rewards') == row['rewardsAfterNeow']
    node = next(n for n in run.graph.nodes if (n.row,n.column)==(row['row'],row['col']))
    step(run, ChooseNode(node.node_id))
    assert row['encounter'] == 'NIBBITS_WEAK'
    assert run.state.active_encounter_id == 'overgrowth_nibbit'
    assert boundary(run) == row['initial']
    for action in row['actions']:
        if action['kind']=='play':
            card = run.combat.player.hand[action['index']]
            assert dict(id=card_id(card),upgrade=card.upgrade_level)==action['card']
            command = next(a for a in run.legal_actions() if isinstance(a,PlayCard) and a.instance_id==card.instance_id)
        else:
            command = EndTurn()
        step(run,command)
        if action['state'] is not None:
            assert boundary(run)==action['state']
    assert run.state.phase is RunPhase.REWARD
    assert run.combat is None and run.state.hp==row['hp']

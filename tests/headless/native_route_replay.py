"""Replay retained native route decisions without forcing gameplay outcomes."""
import re

from game.headless.core.actions import EndTurn, PlayCard, ChooseCombatCard, ConfirmCombatSelection
from game.headless.run import ancient
from game.headless.run.actions import (
    ChooseAncientRelic, ChooseNode, ChooseRelicReward, ChooseRewardCard,
    ClaimGold, ClaimRelic, LeaveRest, LeaveRewards, LeaveShop, LeaveTreasure,
    Rest, OpenChest, ContinueAct, ChooseEventOption, LeaveEvent, ClaimPotion, UsePotion, BuyShopItem, ClaimTreasureRelic,
)
from game.headless.run.engine import RunEngine
from tests.headless.test_act2_run import step
from tests.headless.test_native_generated_start import card_id


def combat_boundary(run, expected, slots, *, boosted):
    player = run.combat.player
    if boosted:
        # Native sorts encounter positions and removes dead creatures. Headless
        # appends stable slots. Bind creation IDs once, never by HP or target result.
        fresh = sorted(e['combatId'] for e in expected['enemies'] if e['combatId'] not in slots)
        unseen = [i for i in range(len(run.combat.enemies)) if i not in slots.values()]
        assert len(fresh) == len(unseen)
        slots.update(zip(fresh, unseen))
        assert len({e['combatId'] for e in expected['enemies']}) == len(expected['enemies'])
        enemies = []
        for native in expected['enemies']:
            enemy = run.combat.enemies[slots[native['combatId']]]
            # Tough Egg changes its display name to Hatchling but retains its model.
            name = getattr(type(enemy), 'NAME', enemy.name)
            enemies.append(dict(combatId=native['combatId'],
                                id=re.sub('[()]', '', name.upper()).replace(' ', '_').replace('-', '_'),
                                hp=enemy.hp, block=enemy.block))
        present = {slots[e['combatId']] for e in expected['enemies']}
        assert all(not e.is_alive or i in present for i, e in enumerate(run.combat.enemies))
    else:
        enemies = [dict(id=re.sub('[()]', '', e.name.upper()).replace(' ', '_').replace('-', '_'), hp=e.hp, block=e.block)
                   for e in run.combat.enemies if e.is_alive]
    result = dict(hp=player.hp, block=player.block, energy=player.energy,
                  hand=[dict(id=card_id(c), upgrade=c.upgrade_level) for c in player.hand], enemies=enemies)
    if boosted:
        result['maxHp'] = player.max_hp
    if 'potions' in expected:
        result['potions'] = [v['definition_id'].upper() if v else None for v in player.rules.potions]
        result['shopsCounter'] = run.state.rng.request_count('shops')
    return result


def run_boundary(run, *, boosted, coverage=False):
    state = run.state
    result = dict(hp=state.hp, gold=state.gold, relics=[r.definition_id.upper() for r in state.relics],
                  deck=[dict(id=card_id(c), upgrade=c.upgrade_level) for c in state.deck],
                  rewardsCounter=state.rng.request_count('rewards'),
                  nicheCounter=state.rng.request_count('niche'),
                  shuffleCounter=state.rng.request_count('shuffle'))
    if boosted:
        result['maxHp'] = state.max_hp
    if coverage:
        result['potions'] = [v.definition_id.upper() if v else None for v in state.potions]
        result['shopsCounter'] = state.rng.request_count('shops')
    return result


def replay_route(row, *, boosted=False):
    coverage = "firstAct" in row
    run = RunEngine.ironclad_run(seed=int(row['seed']), first_act=row.get("firstAct", "overgrowth"), ancient_profile=ancient.PROFILE)
    if boosted:
        assert row['startingHp'] == row['startingMaxHp'] == 1_000_000
        # The sole authored gameplay override, matching native setup before Neow.
        run.state.hp = row['startingHp']
        run.state.max_hp = row['startingMaxHp']
    assert [a.definition_id.upper() for a in run.legal_actions()] == row['offers']
    step(run, ChooseAncientRelic(row['choice'].lower()))
    if row["choice"] == "SCROLL_BOXES":
        step(run, ChooseRelicReward(0))
    assert run.state.rng.request_count('rewards') == row['rewardsAfterNeow']
    for item in row['route']:
        room = item['room'] if boosted else item
        kind = room['kind']
        if kind == 'ActTransition':
            step(run, ContinueAct())
            assert run.state.act_index == item['actIndex']
            assert run_boundary(run, boosted=boosted, coverage=coverage) == room['transition']
        elif kind == 'Victory':
            step(run, ContinueAct())
            assert run.state.pending['definition_id'] == 'the_architect'
            assert run_boundary(run, boosted=boosted, coverage=coverage) == room['entry']
            step(run, ChooseEventOption(run.state.pending['event_instance_id'], 'proceed'))
            assert room['recorded'] and room['disposedHp'] == 0
            assert run.state.hp == room['savedHp'] > 0
            assert run_boundary(run, boosted=boosted, coverage=coverage) == room['state']
            continue
        node = next(n for n in run.graph.nodes if (n.row, n.column) == (room['row'], room['col']))
        step(run, ChooseNode(node.node_id))
        assert run_boundary(run, boosted=boosted, coverage=coverage) == room['entry'], (run.state.act_index, room['row'], 'entry')
        if boosted:
            assert run.state.act_index == item['actIndex']
        if kind == 'ActTransition':
            assert run.state.pending['definition_id'].upper() == room['ancient']
            assert [a.option_id.upper() for a in run.legal_actions() if isinstance(a, ChooseEventOption)] == room['offers']
            step(run, ChooseEventOption(run.state.pending['event_instance_id'], room['choice'].lower()))
            step(run, next(a for a in run.legal_actions() if isinstance(a, LeaveEvent)))
        elif kind == 'CombatRoom':
            slots = {}
            assert combat_boundary(run, room['combat']['initial'], slots, boosted=boosted) == room['combat']['initial']
            for index, action in enumerate(room['combat']['actions']):
                if action['kind'] == 'potion':
                    item = run.state.potions[action['slot']]
                    assert item.definition_id.upper() == action['id']
                    command = UsePotion(item.instance_id, slots[action['targetCombatId']] if action['targetCombatId'] is not None else None)
                elif action['kind'] == 'play':
                    card = run.combat.player.hand[action['index']]
                    assert dict(id=card_id(card), upgrade=card.upgrade_level) == action['card']
                    if boosted:
                        slot = slots[action['targetCombatId']] if action['targetCombatId'] is not None else None
                    else:
                        living = [e for e in run.combat.enemies if e.is_alive]
                        target = living[action['targetIndex']] if action['targetIndex'] >= 0 else None
                        slot = run.combat.enemies.index(target) if target else None
                    command = next(a for a in run.legal_actions() if isinstance(a, PlayCard)
                                   and a.instance_id == card.instance_id and a.target_slot in (None, slot))
                else:
                    assert action['kind'] == 'end'
                    command = EndTurn()
                step(run, command)
                for choice_index in action.get('choiceIndices', []):
                    assert run.combat.player.rules.selection['operation'] == 'hive_knowledge'
                    options = [a for a in run.legal_actions() if isinstance(a, ChooseCombatCard)]
                    step(run, options[choice_index])
                    step(run, ConfirmCombatSelection())
                if action['state'] is not None:
                    assert combat_boundary(run, action['state'], slots, boosted=boosted) == action['state'], (run.state.act_index, room['row'], index)
            if room['rewards'] is not None:
                for reward in room['rewards']['claims']:
                    if reward['kind'] == 'GoldReward':
                        assert run.state.pending['gold'] == reward['amount']
                        step(run, ClaimGold())
                    elif reward['kind'] == 'PotionReward':
                        assert run.state.pending['potion'].upper() == reward['potion']
                        step(run, ClaimPotion())
                    elif reward['kind'] == 'RelicReward':
                        assert run.state.pending['relic'].upper() == reward['relic']
                        step(run, ClaimRelic())
                    else:
                        assert reward['kind'] == 'CardReward'
                        pending = run.state.pending
                        assert [dict(id=card_id(run.cards.create(name)), upgrade=modifier['upgrade_level'])
                                for name, modifier in zip(pending['offers'], pending['card_modifiers'])] == reward['cards']
                        if reward['index'] >= 0:
                            step(run, next(a for a in run.legal_actions() if isinstance(a, ChooseRewardCard)
                                           and a.definition_id == pending['offers'][reward['index']]
                                           and a.offer_index in (None, reward['index'])))
                step(run, LeaveRewards())
                assert run_boundary(run, boosted=boosted, coverage=coverage) == room['rewards']['state']
        elif kind == 'EventRoom':
            assert run.state.pending['definition_id'].upper() == room['eventId']
            step(run, ChooseEventOption(run.state.pending['event_instance_id'], room['eventChoice']))
            step(run, next(a for a in run.legal_actions() if isinstance(a, LeaveEvent)))
        elif kind == 'RestSiteRoom':
            step(run, Rest())
            step(run, LeaveRest())
        elif kind == 'TreasureRoom':
            if boosted:
                step(run, OpenChest())
                if room.get("chestClaim"):
                    assert run.state.pending["relic_id"].upper() == room["chestClaim"]
                    step(run, ClaimTreasureRelic(run.state.pending["treasure_id"]))
            step(run, LeaveTreasure())
        else:
            assert kind == 'MerchantRoom'
            for buy in room.get('purchases', []):
                offer = next(o for o in run.state.pending['offers'] if o['slot'] == buy['slot'])
                assert offer['definition_id'].upper() == buy['id'], (buy, run.state.pending['offers'])
                assert offer['price'] == buy['cost']
                assert offer['upgrade_level'] == buy['upgrade']
                step(run, BuyShopItem(offer['offer_id']))
            step(run, LeaveShop())
        assert run_boundary(run, boosted=boosted, coverage=coverage) == room['state'], (run.state.act_index, room['row'])
    assert run_boundary(run, boosted=boosted, coverage=coverage) == row['state']
    assert not run.legal_actions()
    return run

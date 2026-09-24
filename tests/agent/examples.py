"""Authored public examples, not captures or claims of producer conformance."""
from dataclasses import replace

from game.agent.contracts import (
    known as k, not_applicable as na, Card, Cost, Counter, Relic, PotionSlot,
    Intent, Enemy, Osty, OstyState, Orb, CharacterResources, MapNode, Map, History, Run, Pile,
    Combat, CardSelection, Reward, Rewards, MapChoice, Candidate, PublicDecision,
)


def card(number, definition='strike', origin=None):
    return Card(f'card:{number}', definition, 0, Cost(k(1), False, na(), False),
                k((Counter('damage', 10 if definition == 'neows_fury' else 6),)),
                k(()), na() if origin is None else k(f'card:{origin}'))


def resources(character):
    result = CharacterResources(na(), na(), na(), na(), na())
    if character == 'regent':
        return replace(result, stars=k(0), sovereign_blades=k(()))
    if character == 'necrobinder':
        return replace(result, osty=k(OstyState(Osty(6, 6, 0, k(())))))
    if character == 'defect':
        return replace(result, orb_slots=k(3), orbs=k((Orb('orb:0', 'lightning', 3, 8),)))
    return result


def combat_decision(character='ironclad'):
    run = Run(character, 0, 1, 1, 60, 80, 99,
              k((card(0, 'neows_fury'), card(1), card(2))),
              k((Relic('relic:0', 'burning_blood', k(())),)), k((PotionSlot(0, None),)),
              k(Map(k('node:0'), (MapNode('node:0', 0, 0, 'combat', ('node:1',)),
                                  MapNode('node:1', 1, 0, 'unknown', ())))), k(History('run_start', ())))
    piles = tuple(Pile(kind, len(cards), k(cards), 'canonical' if kind == 'draw' else 'visible')
                  for kind, cards in (
                      ('hand', (card(3, 'neows_fury', 0),)), ('draw', ()),
                      ('discard', (card(4, origin=1), card(5, origin=2))),
                      ('exhaust', ()), ('in_play', ()), ('powers', ())))
    combat = Combat('combat', 1, 0, 3, k(()), resources(character),
                    (Enemy('enemy:0', 'jaw_worm', 40, 40, 0, k(()),
                           k((Intent('attack', k(11), k(1)),))),), piles)
    return PublicDecision('sts_public_decision_v1', 'combat_reward_map_v1', run, combat,
                          (Candidate('action:0', 'play_card', 'card:3', 'enemy:0'),
                           Candidate('action:1', 'end_turn')))


def selection_decision(selected=()):
    base = combat_decision()
    piles = tuple(replace(p, cards=k(()), count=0) if p.kind == 'hand'
                  else replace(p, cards=base.context.piles[0].cards, count=1) if p.kind == 'in_play'
                  else p for p in base.context.piles)
    combat = replace(base.context, energy=2, piles=piles,
                     enemies=(replace(base.context.enemies[0], hp=30),))
    choice = CardSelection('card_selection', combat, k('card:3'), 'discard', ('card:4', 'card:5'),
                           tuple(selected), 0, 2, True, False)
    actions = [Candidate(f'action:{i}', 'deselect_card' if c in selected else 'select_card', c)
               for i, c in enumerate(choice.options) if c in selected or len(selected) < choice.maximum]
    actions.append(Candidate('action:2', 'confirm_selection'))
    return replace(base, context=choice, candidates=tuple(actions))


def rewards_decision(opened=False):
    base = combat_decision()
    rewards = Rewards('rewards', (
        Reward('reward:0', 'gold', 'summary', k(15), na(), na(), na(), False),
        Reward('reward:1', 'card', 'choice' if opened else 'summary', na(),
               k((card(6, 'bash'), card(7, 'bash'))) if opened else na(), na(), na(), False)))
    actions = (
        Candidate('action:0', 'choose_reward_card', 'reward:1', 'card:6'),
        Candidate('action:1', 'choose_reward_card', 'reward:1', 'card:7'),
        Candidate('action:2', 'skip_reward', 'reward:1')) if opened else (
        Candidate('action:0', 'claim_reward', 'reward:0'),
        Candidate('action:1', 'open_card_reward', 'reward:1'), Candidate('action:2', 'leave_rewards'))
    return replace(base, context=rewards, candidates=actions)


def map_decision():
    return replace(combat_decision(), context=MapChoice('map', ('node:1',)),
                   candidates=(Candidate('action:0', 'choose_map_node', 'node:1'),))

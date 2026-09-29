"""Public decision presentation and deliberately descriptive review signals."""
from collections import Counter
from dataclasses import asdict
import hashlib
import json

from game.agent import contracts as c
from game.agent.contracts import full as f
from game.agent.progress import cleared_act


def json_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def state_digest(decision):
    return hashlib.sha256(json_bytes(f.to_dict(decision))).hexdigest()


def fields(node):
    return {item.key: item.value for item in node.fields}


def entities(decision):
    return {n.ref: n for root in (decision.run, decision.context) for n in f.walk(root) if n.ref}


def name(node):
    if node is None:
        return None
    spec = next((n for n in node.children if n.kind == 'spec'), node)
    label = spec.get('name') or node.get('name') or node.definition_id.replace('_', ' ').title()
    upgrade = node.get('upgrade_level', 0)
    return label + (f' +{upgrade}' if upgrade else '')


def action_label(action, refs):
    subject = name(refs.get(action.subject)) or action.subject
    target = name(refs.get(action.target)) or action.target
    return ' · '.join(x for x in (action.kind.replace('_', ' ').capitalize(), subject,
                                  '→ '+target if target else None) if x)


def category(decision, action):
    # Selection is its own category even when owned by combat/rest/relic_choice.
    if action.kind in ('select_card', 'deselect_card', 'confirm_selection', 'cancel_selection',
                       'choose_relic_card', 'deselect_relic_card', 'confirm_relic_selection',
                       'choose_cook_card', 'deselect_cook_card', 'confirm_cook'):
        return 'selection'
    if action.kind in ('choose_reward_card', 'skip_reward', 'choose_extra_reward',
                       'reroll_card_reward', 'sacrifice_card_reward', 'choose_relic_reward'):
        return 'card_reward'
    return {'map': 'route', 'rewards': 'rewards', 'combat': 'combat',
            'shop': 'shop', 'rest': 'rest', 'event': 'event'}.get(decision.context.kind,
                                                               decision.context.kind)


def hud(decision):
    if type(decision) is not f.PublicDecision:
        return None
    return {key: decision.run.get(key) for key in ('act', 'floor', 'hp', 'max_hp', 'gold')}


def summarize(trajectory):
    timeline, flags, rooms = [], [], []
    completed = []
    for index, transition in enumerate(trajectory.transitions):
        before, after, action = transition.observation, transition.successor, transition.action
        refs = entities(before)
        start, end = hud(before), hud(after)
        row = {'step': index, **start, 'round': before.context.get('round'),
               'context': before.context.kind, 'category': category(before, action),
               'action': action.kind, 'label': action_label(action, refs),
               'choices': len(before.candidates), 'canonical_reward': transition.reward,
               'hp_delta': end['hp']-start['hp'] if end is not None else None}
        timeline.append(row)
        location = (start['act'], start['floor'])
        if not rooms or (rooms[-1]['act'], rooms[-1]['floor']) != location:
            rooms.append({'act': start['act'], 'floor': start['floor'], 'start': index,
                          'end': index, 'contexts': [], 'hp': start['hp']})
        rooms[-1]['end'] = index
        if row['category'] not in rooms[-1]['contexts']:
            rooms[-1]['contexts'].append(row['category'])
        act = cleared_act(before, after)
        if act is not None:
            completed.append({'act': act, 'step': index})
        if (action.kind == 'end_turn' and before.context.get('energy', 0) > 0
                and any(a.kind == 'play_card' for a in before.candidates)):
            flags.append({'kind': 'end_turn_with_playable_card', 'level': 'info', 'start': index,
                          'end': index, 'reason': 'Ended turn with energy and a legal card play. '
                          'This can be intentional; no better action is asserted.'})

    families = [({'select_card', 'deselect_card'}, {'deselect_card'}, 'selection_toggle'),
                ({'choose_relic_card', 'deselect_relic_card'}, {'deselect_relic_card'}, 'selection_toggle'),
                ({'choose_cook_card', 'deselect_cook_card'}, {'deselect_cook_card'}, 'selection_toggle'),
                ({'open_reward', 'close_reward'}, {'open_reward', 'close_reward'}, 'reward_navigation')]
    for actions, required, kind in families:
        start = None
        for i in range(len(timeline)+1):
            current = timeline[i] if i < len(timeline) else None
            same = current and current['action'] in actions and (start is None or all(
                current[key] == timeline[start][key] for key in ('act', 'floor', 'context')))
            if not same and start is not None:
                kinds = {r['action'] for r in timeline[start:i]}
                if i-start >= 8 and required <= kinds:
                    cutoff = i == len(timeline) and trajectory.outcome.kind == 'truncated'
                    flags.append({'kind': kind, 'level': 'warning', 'start': start, 'end': i-1,
                                  'reason': f'{i-start} consecutive selection/navigation actions '
                                  'including reversals in the same room/context.' +
                                  (' The recording ends at a cutoff.' if cutoff else '')})
                start = None
            if current and current['action'] in actions and start is None:
                start = i
    flags.sort(key=lambda row: (row['start'], row['kind']))
    public = [t.successor for t in trajectory.transitions if type(t.successor) is f.PublicDecision]
    last = public[-1] if public else trajectory.initial
    return {'timeline': timeline, 'rooms': rooms, 'flags': flags,
            'completed_acts': completed, 'last_hud': hud(last),
            'categories': dict(Counter(r['category'] for r in timeline)),
            'actions': dict(Counter(r['action'] for r in timeline))}


def detail(value):
    """A readable projection alongside the untouched structured public graph."""
    decision = f.from_dict(value['observation'])
    successor = f.from_dict(value['successor'])
    refs = entities(decision)
    candidates = [{**asdict(a), 'label': action_label(a, refs)} for a in decision.candidates]

    def node_view(node):
        return {'kind': node.kind, 'ref': node.ref, 'name': name(node), 'fields': fields(node),
                'links': {link.key: list(link.targets) for link in node.links},
                'children': [node_view(child) for child in node.children]}

    before, after = hud(decision), hud(successor)
    combat_delta, enemy_changes = {}, []
    if type(successor) is f.PublicDecision and decision.context.kind == successor.context.kind == 'combat':
        combat_delta = {key: successor.context.get(key)-decision.context.get(key)
                        for key in ('energy', 'block') if type(successor.context.get(key)) is int
                        and type(decision.context.get(key)) is int}
        next_refs = entities(successor)
        for ref, enemy in refs.items():
            other = next_refs.get(ref)
            if enemy.kind == 'enemy' and other is not None and other.kind == 'enemy':
                enemy_changes.append({'ref': ref, 'name': name(enemy), 'before_hp': enemy.get('hp'),
                                      'after_hp': other.get('hp'), 'before_block': enemy.get('block'),
                                      'after_block': other.get('block')})
    return {**value, 'state_sha256': state_digest(decision), 'hud': before, 'after_hud': after,
            'candidates': candidates, 'context_view': node_view(decision.context),
            'inventory': [node_view(n) for n in decision.run.children if n.kind != 'history'],
            'delta': {key: after[key]-before[key] for key in ('hp', 'max_hp', 'gold')
                      if after is not None and type(before[key]) is int and type(after[key]) is int},
            'combat_delta': combat_delta, 'enemy_changes': enemy_changes,
            'terminal': c.to_dict(successor) if type(successor) is c.RunOutcome else None}

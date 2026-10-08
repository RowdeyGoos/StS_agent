"""Public history and an opaque generative model over reconstructed combat.

The only production input is PublicDecision. The actual engine, dispatch
binding, corpus snapshots and private replay seeds are never accepted here.
"""
from itertools import product
import json

from game.agent.contracts import full as f
from .public_keys import action_key, observation_key
from .world import SimulationWorld
from game.agent.training.action_features import public_context, _card
from game.headless.planning import reconstruct, validate_inventory, UnsupportedSearch, MONSTERS


def _selection(decision):
    return any(n.kind == 'selection' for n in f.walk(decision.context))


def _pile(decision, name):
    return next(n.children for n in decision.context.children if n.kind == 'pile' and n.definition_id == name)


def _signature(card):
    value = _card(card)
    if value is None:
        raise UnsupportedSearch('known_card_description')
    return json.dumps({k: v for k, v in value.items() if k != 'ref'}, sort_keys=True)


class SearchHistory:
    def __init__(self):
        self.reset()

    def reset(self):
        self.initial = self.current = None
        self.transitions = []

    def attach(self, decision):
        if self.current is not None:
            if self.current != decision:
                raise UnsupportedSearch('unreconciled_history')
            return
        if decision.context.kind != 'combat' or decision.context.get('round') != 1 or _selection(decision):
            raise UnsupportedSearch('missing_opening_history')
        if any(n.children for n in decision.context.children if n.kind == 'pile' and
               n.definition_id not in ('hand', 'draw')):
            raise UnsupportedSearch('missing_opening_history')
        self.initial = self.current = decision

    def observe(self, before, action, execution, successor):
        if execution.status != 'reconciled':
            return
        if self.current != before:
            self.reset()
        if not isinstance(successor, f.PublicDecision) or successor.context.kind != 'combat':
            self.reset()
        elif self.current is not None:
            self.transitions.append((before, action, successor))
            self.current = successor

    def plays(self, decision):
        turn = decision.context.get('round')
        count = 0
        for before, action, _ in self.transitions:
            if before == decision:
                break
            count += action.kind == 'play_card' and before.context.get('round') == turn
        return count

    def records(self):
        return [(f.to_dict(b), a.ref, f.to_dict(s)) for b, a, s in self.transitions]

    def known_draw(self, decision):
        """Retain observed Headbutt placements without identifying equal copies.

        Supported draws enter hand, and shuffles consume the previous pile
        first. Other placement/autoplay sources fail the inventory contract.
        """
        top = []
        for before, action, after in self.transitions:
            if before == decision:
                break
            old_hand = {n.ref for n in _pile(before, 'hand')}
            drawn = (len(_pile(after, 'hand')) if action.kind == 'end_turn' else
                     sum(n.ref not in old_hand for n in _pile(after, 'hand')))
            top = top[drawn:]
            selection = next((n for n in before.context.children if n.kind == 'selection'), None)
            selected = None
            if action.kind == 'select_card' and selection is not None and selection.get('destination') == 'draw_pile':
                selected = next((n for n in _pile(before, 'discard') if n.ref == action.subject), None)
            elif action.kind == 'play_card':
                source = next((n for n in _pile(before, 'hand') if n.ref == action.subject), None)
                discard = _pile(before, 'discard')
                if source is not None and source.definition_id == 'headbutt' and len(discard) == 1:
                    selected = discard[0]
            if selected is not None:
                top.insert(0, _signature(selected))
        available = list(_pile(decision, 'draw'))
        refs = []
        for signature in top:
            card = next((c for c in available if _signature(c) == signature), None)
            if card is None:
                raise UnsupportedSearch('inconsistent_known_draw')
            refs.append(card.ref)
            available.remove(card)
        return refs


def facts_from(decision, history):
    facts = public_context(decision)
    if facts is None:
        raise UnsupportedSearch('public_combat_shape')
    facts.update(ascension=decision.run.get('ascension'), gold=decision.run.get('gold'),
                 plays_this_turn=history.plays(decision), room_kind='combat', known_top=history.known_draw(decision))
    nodes = {n.kind: n for n in decision.run.children}
    facts['deck'] = [_card(n) for n in nodes['deck'].children]
    if any(c is None for c in facts['deck']):
        raise UnsupportedSearch('public_deck')
    facts['potions'] = [dict(ref=n.children[0].ref, definition_id=n.children[0].definition_id)
                        if n.children else None for n in nodes['potions'].children]
    for value, n in zip(facts['relics'], nodes['relics'].children):
        value['ref'] = n.ref
    enemies = next(n for n in decision.context.children if n.kind == 'enemies')
    for value, n in zip(facts['enemies'], enemies.children):
        value['strength'] = n.get('strength')
    powers = next((n for n in decision.context.children if n.kind == 'pile' and n.definition_id == 'powers'), None)
    if powers:
        facts['piles']['powers'] = [_card(n) for n in powers.children]
        if any(c is None for c in facts['piles']['powers']):
            raise UnsupportedSearch('power_card_description')
    return facts


class PublicCombatModel:
    def __init__(self, decision, history):
        history.attach(decision)
        self.history, self.root = history, decision
        self.base, self.replay = decision, []
        if _selection(decision):
            for before, action, successor in reversed(history.transitions):
                self.replay.insert(0, (before, action, successor))
                self.base = before
                if not _selection(before):
                    break
            else:
                raise UnsupportedSearch('selection_history')
        self.facts = facts_from(self.base, history)
        # A consumed potion or exhausted generator must not erase evidence of
        # hidden effects that this reconstruction does not model.
        validate_inventory(facts_from(history.initial, history))
        if set(facts_from(history.initial, history)['powers']) & {'weak', 'vulnerable', 'frail'}:
            raise UnsupportedSearch('unknown_initial_status_duration')
        choices = []
        for e in self.facts['enemies']:
            cls = MONSTERS.get(e['definition_id'])
            if cls is None:
                raise UnsupportedSearch('enemy:' + e['definition_id'])
            choices.append(range(len(getattr(cls, 'MOVES', getattr(cls, 'INTENT_CYCLE', (None,))))) if e['alive'] else range(1))
        if not choices or len(choices) > 3:
            raise UnsupportedSearch('enemy_roster')
        matching = []
        self.projection_seconds = 0.
        expected = observation_key(self.base)
        for phases in product(*choices):
            run, refs = reconstruct(self.facts, seed=0, enemy_phases=phases)
            world = SimulationWorld(run, refs, self.base)
            if observation_key(world.project()) == expected:
                matching.append(phases)
            self.projection_seconds += world.timings['projection']
        if len(matching) != 1:
            raise UnsupportedSearch('ambiguous_or_inconsistent_root')
        self.phases = matching[0]

    def sample(self, seed):
        # Rejection here concerns only nested-choice reconstruction. Regular
        # decisions sample a fresh uniform unknown draw order without replaying
        # every observed draw since the opening.
        run, refs = reconstruct(self.facts, seed=seed, enemy_phases=self.phases)
        world = SimulationWorld(run, refs, self.base)
        observation = world.project()
        for before, action, successor in self.replay:
            observation = world.step(observation, action_key(before, action))
            if observation is None or observation_key(observation) != observation_key(successor):
                raise UnsupportedSearch('inconsistent_selection_sample')
        return world, observation

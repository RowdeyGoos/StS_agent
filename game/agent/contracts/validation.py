"""Structural invariants and readiness, without reproducing backend game rules."""
from dataclasses import fields, is_dataclass
import re

from . import models as m
from .codec import ContractError


def require(condition, message):
    if not condition:
        raise ContractError(message)


def ref(value, *kinds):
    require(any(re.fullmatch(kind + r':(?:0|[1-9][0-9]*)', value) for kind in kinds),
            f'Invalid public reference: {value}')


def unique(values, label):
    require(len(values) == len(set(values)), f'Duplicate {label}')


def available(value, label):
    require(value.status != 'not_applicable', f'{label} must be known or unknown')


def nonnegative(value, label):
    require(value >= 0, f'Negative {label}')


def health(value):
    require(0 <= value.hp <= value.max_hp and value.max_hp > 0, 'Invalid HP')


def children(value, path='$'):
    """Yield all nodes with paths, including availability wrappers."""
    yield path, value
    if is_dataclass(value):
        for f in fields(value):
            yield from children(getattr(value, f.name), path + '.' + f.name)
    elif isinstance(value, tuple):
        for i, item in enumerate(value):
            yield from children(item, f'{path}[{i}]')


def _local(value):
    if isinstance(value, m.Observed):
        require((value.status == 'known') == (value.value is not None), 'Availability/value mismatch')
    if isinstance(value, tuple) and value and all(isinstance(v, m.Counter) for v in value):
        unique([v.key for v in value], 'counter keys')
    if isinstance(value, (m.Card, m.Relic, m.Potion, m.Enemy, m.Power)):
        require(re.fullmatch(r'[a-z][a-z0-9]*(?:_[a-z0-9]+)*', value.definition_id), 'Invalid definition ID')
        ref(value.ref, type(value).__name__.lower())
    if isinstance(value, m.Counter):
        # Numeric counters may be negative (e.g. debuffed Strength).
        require(re.fullmatch(r'[a-z][a-z0-9]*(?:_[a-z0-9]+)*', value.key), 'Invalid counter key')
    if isinstance(value, (m.Run, m.Enemy, m.Osty)):
        health(value)
    if isinstance(value, (m.Enemy, m.Osty, m.Combat)):
        nonnegative(value.block, 'block')
        available(value.powers, 'powers')
    if isinstance(value, m.Cost):
        for currency, is_x in ((value.energy, value.energy_x), (value.stars, value.stars_x)):
            if currency.status == 'known':
                nonnegative(currency.value, 'cost')
            require(not is_x or currency.status == 'known', 'X cost needs its visible current amount')
    if isinstance(value, m.Card):
        nonnegative(value.upgrade_level, 'upgrade level')
        available(value.values, 'card values')
        available(value.modifiers, 'card modifiers')
        if value.origin.status == 'known':
            ref(value.origin.value, 'card')
    if isinstance(value, (m.Relic, m.Power)):
        available(value.counters, 'relic counters')
    if isinstance(value, m.PotionSlot):
        nonnegative(value.index, 'potion slot')
    if isinstance(value, m.Intent):
        require(re.fullmatch(r'[a-z][a-z0-9_]*', value.kind), 'Invalid intent kind')
        if value.damage.status == 'known':
            nonnegative(value.damage.value, 'intent damage')
        if value.hits.status == 'known':
            require(value.hits.value > 0, 'Invalid intent hit count')
        require((value.damage.status == 'not_applicable') == (value.hits.status == 'not_applicable'),
                'Intent damage/hits applicability must agree')
    if isinstance(value, m.Enemy):
        available(value.intents, 'enemy intents')
    if isinstance(value, m.Orb):
        ref(value.ref, 'orb')
        require(value.kind in ('lightning', 'frost', 'dark', 'plasma', 'glass'), 'Unknown orb kind')
        nonnegative(value.passive, 'orb passive')
        nonnegative(value.evoke, 'orb evoke')
    if isinstance(value, m.MapNode):
        ref(value.ref, 'node')
        nonnegative(value.row, 'map row')
        nonnegative(value.column, 'map column')
        unique(value.next_nodes, 'map edges')
    if isinstance(value, m.Map):
        ids = [v.ref for v in value.nodes]
        unique(ids, 'map nodes')
        for node in value.nodes:
            require(set(node.next_nodes) <= set(ids) and node.ref not in node.next_nodes, 'Invalid map edge')
        if value.current.status == 'known':
            require(value.current.value in ids, 'Unknown current node')
    if isinstance(value, m.HistoryEvent):
        for item in (value.subject, value.target):
            if item.status == 'known':
                ref(item.value, 'card', 'enemy', 'reward', 'node')
    if isinstance(value, m.Run):
        require(0 <= value.ascension <= 10 and value.act >= 1 and value.floor >= 0, 'Invalid run location/difficulty')
        nonnegative(value.gold, 'gold')
        for field in ('deck', 'relics', 'potions', 'map', 'history'):
            available(getattr(value, field), 'run.' + field)
        if value.potions.status == 'known':
            require(tuple(slot.index for slot in value.potions.value) == tuple(range(len(value.potions.value))),
                    'Potion slots must retain contiguous physical indexes, including empties')
    if isinstance(value, m.Pile):
        nonnegative(value.count, 'pile count')
        available(value.cards, 'pile cards')
        require(value.kind != 'draw' or value.order == 'canonical', 'Hidden draw order is not public')
        if value.cards.status == 'known':
            require(len(value.cards.value) == value.count, 'Pile count mismatch')
    if isinstance(value, m.Combat):
        require(value.round >= 1, 'Invalid round')
        nonnegative(value.energy, 'energy')
        require({p.kind for p in value.piles} == {'hand', 'draw', 'discard', 'exhaust', 'in_play', 'powers'}
                and len(value.piles) == 6, 'All six public piles are required')
    if isinstance(value, m.CardSelection):
        available(value.source, 'selection source')
        unique(value.options, 'selection options')
        unique(value.selected, 'selected cards')
        require(0 <= value.minimum <= value.maximum <= len(value.options) and value.maximum > 0,
                'Invalid selection bounds')
        require(set(value.selected) <= set(value.options) and len(value.selected) <= value.maximum,
                'Invalid selected cards')
        for item in value.options:
            ref(item, 'card')
        if value.source.status == 'known':
            ref(value.source.value, 'card')
        pile = next(p for p in value.combat.piles if p.kind == value.pile)
        if pile.cards.status == 'known':
            require(set(value.options) <= {c.ref for c in pile.cards.value}, 'Selection outside source pile')
        if value.source.status == 'known':
            known_cards = {c.ref for p in value.combat.piles if p.cards.status == 'known' for c in p.cards.value}
            require(value.source.value in known_cards, 'Selection source must be a visible card')
    if isinstance(value, m.Reward):
        ref(value.ref, 'reward')
        field = {'gold': 'amount', 'card': 'cards', 'potion': 'potion', 'relic': 'relic'}[value.kind]
        require(value.presentation != 'choice' or (value.kind == 'card' and not value.resolved),
                'Only an unresolved card reward can own an open choice')
        if value.resolved or (value.kind == 'card' and value.presentation == 'summary'):
            # Resolved items now belong to inventory; do not duplicate identities.
            # Unopened offers are not yet public, even if precomputed.
            field = None
        for name in ('amount', 'cards', 'potion', 'relic'):
            observed = getattr(value, name)
            if name == field:
                available(observed, 'reward.' + name)
            else:
                require(observed.status == 'not_applicable', 'Inapplicable reward payload')
        if value.amount.status == 'known':
            nonnegative(value.amount.value, 'gold reward')
        if value.cards.status == 'known':
            require(bool(value.cards.value), 'Empty card offer')
    if isinstance(value, m.Rewards):
        require(sum(r.presentation == 'choice' for r in value.entries) <= 1, 'Multiple active reward children')
    if isinstance(value, m.MapChoice):
        unique(value.reachable, 'reachable nodes')
        for item in value.reachable:
            ref(item, 'node')


def _resources(character, combat):
    resources = combat.resources
    required = {'regent': {'stars', 'sovereign_blades'}, 'necrobinder': {'osty'},
                  'defect': {'orb_slots', 'orbs'}}.get(character, set())
    for f in fields(resources):
        observed = getattr(resources, f.name)
        if f.name in required:
            available(observed, 'character resource ' + f.name)
        if f.name in ('stars', 'orb_slots') and observed.status == 'known':
            nonnegative(observed.value, f.name)
    # Off-character cards/items can activate these resources too.
    require((resources.orbs.status == 'not_applicable') == (resources.orb_slots.status == 'not_applicable'),
            'Orb queue/capacity applicability must agree')
    if resources.orbs.status == resources.orb_slots.status == 'known':
        require(len(resources.orbs.value) <= resources.orb_slots.value, 'Orb queue exceeds capacity')
    if resources.sovereign_blades.status == 'known':
        unique(resources.sovereign_blades.value, 'Sovereign Blades')
        for item in resources.sovereign_blades.value:
            ref(item, 'card')
        if all(p.cards.status == 'known' for p in combat.piles):
            require(set(resources.sovereign_blades.value) == {c.ref for p in combat.piles for c in p.cards.value
                                                            if c.definition_id == 'sovereign_blade'},
                    'Sovereign Blade references must match public piles')


def _candidates(decision):
    context = decision.context
    require(bool(decision.candidates), 'A decision needs at least one candidate')
    unique([a.ref for a in decision.candidates], 'candidate references')
    unique([(a.kind, a.subject, a.target) for a in decision.candidates], 'candidate semantics')
    for action in decision.candidates:
        ref(action.ref, 'action')
        kind, subject, target = action.kind, action.subject, action.target
        if isinstance(context, m.Combat):
            require(kind in ('play_card', 'end_turn'), 'Wrong combat candidate')
            if kind == 'end_turn':
                require(subject is target is None, 'End turn has no arguments')
            else:
                require(subject is not None, 'Play card needs a subject')
                ref(subject, 'card')
                hand = next(p for p in context.piles if p.kind == 'hand')
                if hand.cards.status == 'known':
                    require(subject in {c.ref for c in hand.cards.value}, 'Play card outside hand')
                if target is not None:
                    require(target in {e.ref for e in context.enemies if e.hp > 0}, 'Unknown or dead target')
        elif isinstance(context, m.CardSelection):
            require(kind in ('select_card', 'deselect_card', 'confirm_selection', 'cancel_selection') and target is None,
                    'Wrong selection candidate')
            if kind in ('select_card', 'deselect_card'):
                require(subject in context.options, 'Unknown choice card')
                require((subject in context.selected) == (kind == 'deselect_card'), 'Selection toggle mismatch')
                require(kind == 'deselect_card' or len(context.selected) < context.maximum, 'Selection is full')
            else:
                require(subject is None, 'Confirmation/cancel has no subject')
                require((context.manual_confirmation and len(context.selected) >= context.minimum)
                        if kind == 'confirm_selection' else context.cancelable, 'Unavailable confirmation/cancel')
        elif isinstance(context, m.Rewards):
            child = next((r for r in context.entries if r.presentation == 'choice'), None)
            if child:
                require(kind in ('choose_reward_card', 'skip_reward') and subject == child.ref,
                        'Only the active reward child may act')
            else:
                require(kind in ('claim_reward', 'open_card_reward', 'leave_rewards'), 'Wrong reward-parent candidate')
            if kind == 'leave_rewards':
                require(subject is target is None, 'Leave rewards has no arguments')
                continue
            reward = next((r for r in context.entries if r.ref == subject and not r.resolved), None)
            require(reward is not None, 'Unknown or resolved reward')
            if kind == 'choose_reward_card':
                require(reward.kind == 'card' and target is not None, 'Not a card reward')
                ref(target, 'card')
                if reward.cards.status == 'known':
                    require(target in {c.ref for c in reward.cards.value}, 'Unknown reward card')
            else:
                require(target is None and (kind != 'claim_reward' or reward.kind != 'card'), 'Invalid reward arguments')
                require(kind != 'open_card_reward' or reward.kind == 'card', 'Only card rewards can be opened')
        else:
            require(kind == 'choose_map_node' and subject in context.reachable and target is None, 'Invalid map candidate')


def validate_semantics(message):
    # Validate children first, so parent cross-references only see well-formed data.
    nodes = list(children(message))
    for _, value in reversed(nodes):
        _local(value)
    if isinstance(message, m.PublicDecision):
        entities = [v.ref for _, v in nodes if isinstance(v, (m.Card, m.Relic, m.Potion, m.Enemy, m.Orb, m.Reward, m.Power))]
        unique(entities, 'entity references')
        deck = message.run.deck
        if deck.status == 'known':
            originals = {c.ref for c in deck.value}
            for _, card in nodes:
                if isinstance(card, m.Card) and card.origin.status == 'known':
                    require(card.origin.value in originals and card.ref not in originals, 'Invalid deck origin')
        combat = message.context.combat if isinstance(message.context, m.CardSelection) else message.context
        if isinstance(combat, m.Combat):
            _resources(message.run.character, combat)
        if isinstance(message.context, m.MapChoice) and message.run.map.status == 'known':
            public_map = message.run.map.value
            require(set(message.context.reachable) <= {n.ref for n in public_map.nodes}, 'Unknown reachable node')
            if public_map.current.status == 'known':
                current = next(n for n in public_map.nodes if n.ref == public_map.current.value)
                require(set(message.context.reachable) <= set(current.next_nodes), 'Unconnected reachable node')
        _candidates(message)
    elif isinstance(message, m.RunOutcome):
        require((message.kind == 'truncated') == (message.reason != 'none'), 'Outcome/reason mismatch')
    elif isinstance(message, m.ExecutionReport):
        allowed = {
            'pending': ({'queued'}, {'none'}),
            'reconciled': ({'applied'}, {'none'}),
            'rejected': ({'none'}, {'invalid_action', 'stale_decision'}),
            'unsupported': ({'none'}, {'missing_public_fields', 'unsupported_version', 'unsupported_capability'}),
            'uncertain': ({'unknown'}, {'transport_failure', 'deadline'}),
            'faulted': ({'none', 'applied', 'unknown'}, {'transport_failure', 'cleanup_failure', 'deadline'}),
        }
        mutations, reasons = allowed[message.status]
        require(message.mutation in mutations and message.reason in reasons, 'Execution status/side-effect mismatch')


class UnsupportedDecision(ContractError):
    def __init__(self, missing):
        self.missing = tuple(missing)
        super().__init__('Required public fields unavailable: ' + ', '.join(self.missing))


def missing_fields(decision):
    """All applicable v1 fields except optional deck-origin links must be known."""
    from .codec import to_dict
    require(type(decision) is m.PublicDecision, 'Expected a public decision')
    to_dict(decision)
    return tuple(path for path, value in children(decision) if isinstance(value, m.Observed)
                 and value.status == 'unknown' and not path.endswith('.origin'))


def require_ready(decision):
    missing = missing_fields(decision)
    if missing:
        raise UnsupportedDecision(missing)
    return decision

"""Campaign combat beliefs built exclusively from public entry receipts.

The engine owns every rule. This module translates public inventory and
history-derived facts, then conditions ordinary setup on observed reveals.
It never accepts a continuation snapshot, game seed or native identity.
"""
from collections import defaultdict
from copy import deepcopy

from game.agent.contracts import full as f
from game.agent.headless.full_cards import CardViews, _signature
from game.agent.headless.full_projection import FullProjection
from game.agent.headless.full_relics import WRAPPED
from game.agent.headless.identity import Identities
from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.draw_knowledge import DrawKnowledge, HPKnowledge, InconsistentKnowledge
from game.headless.planning import UnsupportedSearch
from game.headless.reveals import CombatReveals, validate_reveals
from game.headless.run.construction import campaign_combat, revealed_encounter
from .belief import _boundary
from .observed import ObservedCombatBelief, ObservedWorld
from .public_keys import _paths

MODEL = 'campaign_belief_v1'
ANCHOR = 'sts_campaign_combat_anchor_v1'


def inventory(initial, facts):
    run = initial.run
    if run.get('character') != 'ironclad' or run.get('ascension') != 0 or run.get('act') != 1:
        raise UnsupportedSearch('campaign_inventory_scope')
    groups = {n.kind: n for n in run.children}
    deck = []
    for card in groups['deck'].children:
        lifetime = DEFAULT_CARDS.definition(card.definition_id).combat_lifetime
        seen = facts['card_combats'].get(card.ref) if lifetime else 0
        if seen is None:
            raise UnsupportedSearch('campaign_missing_card_history')
        enchantment = next((n for n in card.children if n.kind == 'enchantment'), None)
        record = dict(definition_id=card.definition_id, upgrade_level=card.get('upgrade_level'),
            combats_seen=seen, permanent_damage=card.get('permanent_damage', 0),
            permanent_block=card.get('permanent_block', 0),
            enchantment=None if enchantment is None else {v.key: v.value for v in enchantment.fields})
        if card.definition_id == 'mad_science':
            modifier = next((n for n in card.children if n.kind == 'modifier' and n.definition_id == 'mad_science'), None)
            if modifier is None:
                raise UnsupportedSearch('campaign_missing_card_configuration')
            record['event_data'] = {v.key: v.value for v in modifier.fields}
        deck.append(record)
    relics = []
    for relic in groups['relics'].children:
        name, data = relic.definition_id, {}
        if relic.children:
            raise UnsupportedSearch('campaign_stored_card_history')
        for public, private in (('wax', '_wax'), ('melted', '_melted'), ('card', 'card'), ('family', 'family')):
            value = relic.get(public)
            if value:
                data[private] = value
        if name in WRAPPED or name in ('girya', 'joss_paper', 'sword_of_stone', 'pumpkin_candle'):
            count = relic.get('display_counter')
        elif name in ('maw_bank', 'lizard_tail', 'lava_rock', 'silken_tress'):
            count = int(relic.get('status') == 'disabled')
        elif name in ('venerable_tea_set', 'fake_venerable_tea_set'):
            count = int(relic.get('status') == 'active')
        elif name in ('bone_tea', 'ember_tea', 'tea_of_discourtesy'):
            count = (5 if name == 'ember_tea' else 1) - relic.get('remaining_combats')
        elif name == 'wongos_mystery_ticket':
            count = 5 - relic.get('display_counter') if relic.get('show_counter') else (6 if relic.get('status') == 'disabled' else 5)
        elif name == 'winged_boots':
            count = 3 - relic.get('display_counter') if relic.get('show_counter') else 3
        elif name in ('toy_box', 'silver_crucible'):
            # Their display aliases persistent counters/data. Do not invent a
            # unique value on attachment; add a public history proof first.
            raise UnsupportedSearch('campaign_relic_history_' + name)
        else:
            count = 0
        if type(count) is not int or count < 0:
            raise UnsupportedSearch('campaign_inventory_counter')
        relics.append((name, count, data))
    map_node = groups.get('map')
    current = set(map_node.linked('current')) if map_node else set()
    fur = any(n.ref in current and n.get('fur_coat_marked') for n in map_node.children) if map_node else False
    return dict(deck=deck, relics=relics,
        potions=[slot.children[0].definition_id if slot.children else None for slot in groups['potions'].children],
        hp=run.get('hp'), max_hp=run.get('max_hp'), gold=run.get('gold'), fur_coat_active=fur)


def validate_anchor(anchor):
    if (not isinstance(anchor, dict) or set(anchor) != {'schema', 'initial', 'opening', 'opening_reveals', 'transitions', 'facts'}
            or anchor['schema'] != ANCHOR or not isinstance(anchor['transitions'], list)
            or len(anchor['transitions']) > 512):
        raise ValueError('Invalid campaign combat anchor')
    facts = anchor['facts']
    if (not isinstance(facts, dict) or set(facts) != {'card_combats'} or not isinstance(facts['card_combats'], dict)
            or any(type(k) is not str or type(v) is not int or v < 0 for k, v in facts['card_combats'].items())):
        raise ValueError('Invalid public campaign facts')
    initial, opening = f.from_dict(anchor['initial']), f.from_dict(anchor['opening'])
    if initial.context.get('entry_action_kind') != 'choose_map_node':
        # Event settlement has its own continuation even if it happens to
        # reveal a familiar ordinary enemy roster.
        raise UnsupportedSearch('campaign_event_or_missing_entry_context')
    inventory(initial, facts)
    validate_reveals(anchor['opening_reveals'])
    _boundary(opening)
    enemies = [n for n in f.walk(opening.context) if n.kind == 'enemy']
    try:
        revealed_encounter([n.definition_id for n in enemies])
    except ValueError as error:
        raise UnsupportedSearch('campaign_event_or_unknown_encounter') from error
    if opening.context.get('round') != 1:
        raise UnsupportedSearch('campaign_missing_opening')
    current = opening
    for row in anchor['transitions']:
        if not isinstance(row, dict) or set(row) != {'action_ref', 'successor', 'reveals'}:
            raise ValueError('Invalid campaign combat prefix')
        if row['action_ref'] not in {a.ref for a in current.candidates}:
            raise ValueError('Prefix action is not advertised')
        validate_reveals(row['reveals'])
        current = f.from_dict(row['successor'])
        _boundary(current)
    return deepcopy(anchor)


class CampaignWorld(ObservedWorld):
    def __init__(self, run, knowledge, opening):
        super().__init__(run, knowledge, opening)
        self.attach(opening)

    def attach(self, root):
        super().attach(root)
        for node in (*f.walk(root.run), *f.walk(root.context)):
            refs = ([node.ref] if node.ref else []) + [r for link in node.links for r in link.targets]
            for ref in refs:
                kind, serial = ref.split(':')
                self._ids.counts[kind] = max(self._ids.counts[kind], int(serial) + 1)
        # The projection orders equal definitions by public name, and a root's
        # names need not follow content (a lone copy enchanted after naming).
        # Give each deck card the name of a publicly identical root card.
        views, names = CardViews(), defaultdict(list)
        for node in next(n for n in root.run.children if n.kind == 'deck').children:
            names[_signature(f.Node(node.kind, node.definition_id, None, node.fields, node.links, node.children))].append(node.ref)
        deck = self._run.state.deck
        contents = [views.signature(card) for card in deck]
        if sorted(contents) == sorted(key for key, refs in names.items() for _ in refs):
            for card, key in zip(deck, contents):
                self._ids.refs['card', ('deck', card.instance_id)] = names[key].pop(0)
        # Establish remaining identity using public positions only. Past campaign
        # actions remain part of the network input; private allocator values do not.
        owner = FullProjection(self._run, self._ids, [], {}, 'attachment', 0, False)
        sample = owner.decision()
        positions = {path: ref for ref, path in _paths(root).items()}
        rename = {ref: positions[path] for ref, path in _paths(sample).items() if path in positions}
        for key, ref in list(self._ids.refs.items()):
            self._ids.refs[key] = rename.get(ref, ref)
        self._history = [f.Candidate('action:0', n.definition_id,
            next(iter(n.linked('history_subject')), None), next(iter(n.linked('history_target')), None))
            for group in root.run.children if group.kind == 'history' for n in group.children]


class CampaignCombatBelief(ObservedCombatBelief):
    validate_anchor = staticmethod(validate_anchor)

    def _fresh_opening(self):
        events = self.anchor['opening_reveals']
        knowledge = DrawKnowledge()
        knowledge.condition([tuple(e['value']) for e in events if e['kind'] in ('draw', 'autoplay_top')], self._seed())
        journal = CombatReveals(events, seed=self._seed())
        enemies = [n for n in f.walk(self.opening.context) if n.kind == 'enemy']
        hp = HPKnowledge(tuple(n.get('max_hp') for n in enemies))
        try:
            run = campaign_combat(**inventory(self.initial, self.anchor['facts']),
                encounter_id=revealed_encounter([n.definition_id for n in enemies]),
                seed=self._seed(), draw_knowledge=knowledge, hp_knowledge=hp, reveal_journal=journal)
            knowledge.finish()
            journal.finish()
            world = CampaignWorld(run, knowledge, self.opening)
            world.log_weight = knowledge.log_likelihood + journal.log_likelihood + hp.log_likelihood
            return world, self._key(world.project()) == self._opening_key
        except InconsistentKnowledge:
            return None, False
        except (ValueError, KeyError) as error:
            raise UnsupportedSearch('campaign_setup_unsupported') from error

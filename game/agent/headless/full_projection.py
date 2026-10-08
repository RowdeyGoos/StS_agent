"""Full-run allowlist projection and exact command bindings.

No engine snapshot enters this module. Future event pages, reward queues, enemy
AI, encounter assignments, random generators and native identities stay private.
"""
from dataclasses import dataclass, replace

from game.agent.contracts import full as f
from game.headless.core import actions as ca
from game.headless.run import actions as ra
from game.headless.run.state import RunPhase
from game.headless.powers.status import SUPPORTED_STATUS_NAMES, modify_attack_damage_for_statuses
from game.headless.powers.hive import damage_multiplier
from game.headless.powers.necrobinder import TEMP_STRENGTH
from .errors import UnsupportedProfile
from .full_cards import CardViews, card_node
from .full_relics import labels as relic_labels
from .identity import number

# Exhaustive command inventory; tests compare this against both engine modules.
COMMANDS = {
    ca.PlayCard: 'play_card', ca.EndTurn: 'end_turn',
    ca.ChooseCombatCard: 'select_card', ca.ConfirmCombatSelection: 'confirm_selection',
    ra.ChooseNode: 'choose_map_node', ra.ClaimGold: 'claim_gold',
    ra.ChooseRewardCard: 'choose_reward_card', ra.ClaimPotion: 'claim_potion',
    ra.ClaimRelic: 'claim_relic', ra.LeaveRewards: 'leave_rewards', ra.Rest: 'rest',
    ra.Smith: 'smith', ra.Hatch: 'hatch', ra.ChooseUpgrade: 'choose_upgrade',
    ra.LeaveRest: 'leave_rest', ra.UsePotion: 'use_potion', ra.DiscardPotion: 'discard_potion',
    ra.BuyShopItem: 'buy_shop_item', ra.BeginShopRemoval: 'begin_shop_removal',
    ra.ChooseShopRemoval: 'choose_shop_removal', ra.LeaveShop: 'leave_shop',
    ra.OpenChest: 'open_chest', ra.ClaimTreasureRelic: 'claim_treasure_relic',
    ra.LeaveTreasure: 'leave_treasure', ra.ChooseEventOption: 'choose_event_option',
    ra.LeaveEvent: 'leave_event', ra.ChooseEventCard: 'choose_event_card',
    ra.ChooseAncientRelic: 'choose_ancient_relic', ra.ChooseRelicCard: 'choose_relic_card',
    ra.ConfirmRelicSelection: 'confirm_relic_selection', ra.ChooseRelicReward: 'choose_relic_reward',
    ra.Lift: 'lift', ra.Dig: 'dig', ra.UseRestRelic: 'use_rest_relic',
    ra.ChooseCookCard: 'choose_cook_card', ra.ConfirmCook: 'confirm_cook',
    ra.ChooseExtraReward: 'choose_extra_reward', ra.RerollCardReward: 'reroll_card_reward',
    ra.SacrificeCardReward: 'sacrifice_card_reward', ra.ContinueAct: 'continue_act',
}
PILES = (('hand', 'hand'), ('draw', 'draw_pile'), ('discard', 'discard_pile'),
         ('exhaust', 'exhaust_pile'), ('in_play', 'in_play'), ('offered', 'offered'),
         ('sequestered', 'sequestered'))
# These are creature power/counter values, not next-move or targeting state.
ENEMY_COUNTERS = ('thorns', 'plating', 'ritual', 'curl_up', 'off_balance', 'slumber',
                  'burrowed', 'soaring', 'flutter', 'escape_countdown',
                  'slow_count', 'remaining_turns', 'personal_hive', 'vital_spark',
                  'shriek', 'shell_damage', 'steam', 'about_to_blow',
                  'intangible', 'asleep', 'rage', 'sandpit',
                  'liquified', 'reviving', 'binding',
                  'cards_left', 'nemesis_intangible', 'stolen_gold', 'dexterity')


@dataclass(frozen=True, slots=True)
class Presentation:
    key: int | str
    opened: bool


def node(node_type, definition=None, *, ref=None, children=(), links=(), **values):
    return f.Node(node_type, definition or node_type, ref, tuple(f.Field(k, v) for k, v in values.items()),
                  tuple(f.Link(k, tuple(v)) for k, v in links), tuple(children))


class FullProjection:
    def __init__(self, engine, identities, history, power_cards, coverage, epoch, opened, *, generation=0):
        self.engine, self.state, self.ids = engine, engine.state, identities
        self.history, self.power_cards, self.epoch = history, power_cards, epoch
        self.opened, self.modal, self.modal_keys = opened, False, set()
        self.commands, self.card_refs, self.enemy_refs, self.node_refs = {}, {}, {}, {}
        self.potion_refs, self.relic_refs, self.option_refs, self.offer_refs = {}, {}, {}, {}
        self.reward_refs, self.reward_cards = {}, {}
        self.selected = ()
        self.serial = (self.state.act_index, self.state.visited_room_count, self.epoch, generation)

    def ref(self, kind, key):
        return self.ids.ref(kind, key)

    def item(self, kind, definition, key, **values):
        return node(kind, definition, ref=self.ref(kind, key), **values)

    def offer_card(self, definition, key, modifiers=None):
        from game.headless.enchantments.base import restore
        modifiers = modifiers or {}
        card = self.engine.cards.create(definition, upgrade_level=modifiers.get('upgrade_level', 0))
        card.enchantment = restore(modifiers.get('enchantment'))
        # A merchant's still-owned offer survives a nested pickup child. A
        # reroll creates new offer instances even if their definitions repeat.
        scope = None if isinstance(key, tuple) and key[0] == 'shop' else self.serial
        reward_ref = self.reward_refs.get(key[0]) if isinstance(key, tuple) else None
        rerolls = sum(a.kind == 'reroll_card_reward' and a.subject == reward_ref for a in self.history) if reward_ref else 0
        return card_node(card, self.ref('card', ('offer', scope, key, rerolls)))

    def map(self):
        graph = self.engine.graph
        if graph is None:
            return node('map', available=False)
        depths, columns, positions = {}, {}, {}
        def visit(key, depth):
            if depth <= depths.get(key, -1):
                return
            depths[key] = depth
            for child in graph.node(key).next_node_ids:
                visit(child, depth + 1)
        for key in graph.entry_node_ids or (graph.start_id,):
            visit(key, 0)
        for n in graph.nodes:
            row = n.row if n.row is not None else depths[n.node_id]
            col = n.column if n.column is not None else columns.get(row, 0)
            columns[row] = col + 1
            positions[n.node_id] = (row, col)
        if len(set(positions.values())) != len(positions):
            raise UnsupportedProfile('ambiguous_map_layout')
        keys = sorted(positions, key=positions.__getitem__)
        self.node_refs = {key: self.ref('node', (self.state.act_index, key)) for key in keys}
        coat = next((r for r in self.state.relics if r.definition_id == 'fur_coat' and not r.data.get('_melted')
                     and r.data.get('act') == self.state.act_index + 1), None)
        marked = set(map(tuple, coat.data.get('coordinates', ()))) if coat else set()
        quest = self.state.spoils_map or {}
        children = [node('node', graph.node(key).kind, ref=self.node_refs[key], row=positions[key][0],
                         column=positions[key][1], visited=key in self.state.visited_nodes,
                         fur_coat_marked=positions[key] in marked,
                         spoils_map_marked=key == quest.get('target') and any(i in self.card_refs for i in quest.get('card_ids', ())),
                         links=(('next_nodes', (self.node_refs[k] for k in sorted(graph.node(key).next_node_ids,
                                                                                 key=positions.__getitem__))),)) for key in keys]
        current = self.node_refs.get(self.state.current_node_id)
        return node('map', available=True, children=children, links=(('current', (current,) if current else ()),))

    def run(self):
        s, combat = self.state, self.engine.combat
        p = combat.player if combat else None
        cards = CardViews()
        deck = []
        for card in sorted(s.deck, key=cards.signature):
            ref = self.ref('card', ('deck', card.instance_id))
            self.card_refs[card.instance_id] = ref
            deck.append(cards.card(card, ref))
        # Equal copies use already-public names as tie breakers.
        deck.sort(key=lambda n: (n.definition_id, n.get('upgrade_level'), number(n.ref)))
        current = self.engine.graph.node(s.current_node_id) if self.engine.graph and s.current_node_id else None
        before_boss = bool(current and any(self.engine.graph.node(i).kind == 'boss' for i in current.next_node_ids))
        rest_status = 'normal'
        if s.pending and s.pending.get('kind') == 'rest_site':
            rest_status = 'normal' if 'rest' in s.pending['used'] else 'active'
        elif current and current.kind == 'rest':
            # Once the room's result has been discarded, an attaching observer
            # cannot reconstruct whether the pillow's heal animation occurred.
            rest_status = 'unavailable_on_attachment'
            for action in reversed(self.history):
                if action.kind in ('rest', 'choose_map_node'):
                    rest_status = 'normal' if action.kind == 'rest' else 'active'
                    break
        relics = []
        for relic in s.relics:
            ref = self.ref('relic', ('owned', relic.instance_id))
            self.relic_refs[relic.instance_id] = ref
            values = relic_labels(relic, p, empty_belt=not any(s.potions),
                                  before_boss=before_boss, rest_status=rest_status)
            for key in ('card', 'family'):
                if key in relic.data:
                    values[key] = relic.data[key]
            children = []
            if 'cards' in relic.data:
                from game.headless.core.snapshots import restore_card
                for record in relic.data['cards']:
                    stored = restore_card(record, self.engine.cards)
                    # Pael's Tooth's tooltip lists titles, not inspectable
                    # serialized cards or their private enchantment modifiers.
                    children.append(node('stored_card_title', stored.definition.definition_id, title=stored.definition.levels[0].name))
            relics.append(node('relic', relic.definition_id, ref=ref, children=children, **values))
        potions = []
        for i, potion in enumerate(s.potions):
            children = ()
            if potion:
                ref = self.ref('potion', ('owned', potion.instance_id))
                self.potion_refs[potion.instance_id] = ref
                children = (node('potion', potion.definition_id, ref=ref),)
            potions.append(node('potion_slot', index=i, children=children))
        history = [node('history_event', action.kind,
                        links=(('history_subject', (action.subject,) if action.subject else ()),
                               ('history_target', (action.target,) if action.target else ()))) for action in self.history]
        return node('run', character=s.config.character if s.config else 'ironclad',
                    ascension=s.config.ascension if s.config else 0, act=s.act_index + 1,
                    floor=s.visited_room_count, hp=p.hp if p else s.hp,
                    max_hp=p.max_hp if p else s.max_hp, gold=s.gold, wongo_points=s.wongo_points,
                    freed_repy=s.freed_repy, children=(node('deck', children=deck), node('relics', children=relics),
                    node('potions', capacity=s.potion_capacity, children=potions), self.map(),
                    node('history', coverage='attachment', children=history)))

    def combat(self):
        combat = self.engine.combat
        p, d, r = combat.player, combat.player.deck, combat.player.rules
        cards = CardViews(p)
        visible = [(('combat', self.epoch, card.instance_id), card)
                   for name, attr in PILES if name != 'draw' for card in getattr(d, attr)]
        draw = [(('combat', self.epoch, card.instance_id), card) for card in sorted(d.draw_pile, key=cards.signature)]
        self.ids.reconcile_draw(visible, draw, cards.signature)
        for key, card in (*visible, *draw):
            self.card_refs[card.instance_id] = self.ref('card', key)
        piles = []
        for name, attr in PILES:
            originals = getattr(d, attr)
            if name == 'draw':
                originals = sorted(originals, key=lambda c: (cards.signature(c), number(self.card_refs[c.instance_id])))
            piles.append(node('pile', name, count=len(originals), order='canonical' if name == 'draw' else 'visible',
                              children=[cards.card(card, self.card_refs[card.instance_id], on_table=name in ('hand', 'in_play')) for card in originals]))
        # Detached power cards have no native inspectable pile. Only retained
        # pre-play descriptions may be included, not their hidden later state.
        piles.append(node('pile', 'powers', count=len(self.power_cards), coverage='observed_plays',
                          children=tuple(self.power_cards.values())))
        powers, used_counters = [], set()
        for key, amount in r.powers.items():
            if not amount:
                continue
            counters = []
            for auxiliary in (key, key + '.ready'):
                if auxiliary in r.auxiliaries:
                    used_counters.add(auxiliary)
                    # A ready flag controls hook dispatch, and Void Form's
                    # auxiliary includes a private sentinel, neither is a label.
                    if auxiliary != key or key == 'void_form':
                        continue
                    base, displayed = key.split(':')[0], r.auxiliaries[auxiliary]
                    label = {'orbit': 'energy_until_refund', 'monologue': 'strength_applied',
                             'feral': 'returns_remaining', 'outbreak': 'poison_applications',
                             'crimson_mantle': 'hp_cost', 'inferno': 'hp_cost',
                             'tender': 'cards_played', 'toric_toughness': 'block',
                             'surrounded': 'facing'}.get(base, 'remaining')
                    if base == 'orbit':
                        displayed = 4 - displayed % 4
                    elif base == 'feral':
                        displayed = max(0, amount - displayed)
                    counters.append(node('counter', label, amount=displayed))
            title = {}
            if key in r.nightmares:
                from game.headless.core.snapshots import restore_card
                chosen = restore_card(r.nightmares[key], self.engine.cards)
                title = dict(selected_card_title=chosen.spec.name,
                             selected_definition_id=chosen.definition.definition_id,
                             selected_upgrade_level=chosen.upgrade_level)
            powers.append(node('power', key.split(':')[0], ref=self.ref('power', (self.epoch, key)),
                               amount=amount, children=counters, **title))
        powers += [node('power', name, amount=p.statuses.get(name)) for name in SUPPORTED_STATUS_NAMES if p.statuses.get(name)]
        for public_name, attribute in (('dampen', 'dampen_active'), ('hex', 'hex_active')):
            if any(getattr(enemy, attribute, False) for enemy in combat.enemies):
                powers.append(node('power', public_name, amount=1))
        for relic in self.state.relics:
            memory = r.relic_data.get(relic.instance_id, {})
            if relic.definition_id == 'self_forming_clay' and memory.get('next_block'):
                powers.append(node('power', 'self_forming_clay', amount=memory['next_block']))
            elif relic.definition_id == 'diamond_diadem' and memory.get('protected'):
                powers.append(node('power', 'diamond_diadem', amount=1))
        for key, value in sorted(r.auxiliaries.items()):
            if key in used_counters or key in ('void_form', 'exhaust_ethereal', 'smoggy.ready', 'summon_next_turn', 'block_gains'):
                continue
            if type(value) is not int or ':' in key:
                raise UnsupportedProfile('public_power_counter')
            powers.append(node('power_counter', key, amount=value))
        enemies = []
        for slot, enemy in enumerate(combat.enemies):
            ref = self.ref('enemy', (self.epoch, slot))
            self.enemy_refs[slot] = ref
            children = []
            strength = enemy.strength - sum(enemy.statuses.get(name) for name in TEMP_STRENGTH)
            if enemy.is_alive or getattr(enemy, 'reviving', False):
                children += [node('power', name, amount=enemy.statuses.get(name)) for name in SUPPORTED_STATUS_NAMES if enemy.statuses.get(name)]
                for name in ENEMY_COUNTERS:
                    if hasattr(enemy, name) and type(getattr(enemy, name)) in (int, bool):
                        value, label = getattr(enemy, name), name
                        if name == 'shell_damage':
                            label, value = 'hardened_shell_remaining', max(0, 20 - value)
                        elif name == 'slow_count':
                            label, value = 'slow_damage_percent', value * 10
                        elif name == 'shriek':
                            value = enemy.ascension_value('ShriekAmount', 70) if value else 0
                        elif name == 'ritual' and type(value) is bool:
                            value = 9 if value else 0
                        children.append(node('power_counter', label, amount=value))
                if hasattr(enemy, 'wither_upgrades'):
                    preview = self.engine.cards.create('wither')
                    preview.combat_state.wither_level = enemy.wither_upgrades
                    children.append(node('hover_preview', 'withering_presence', children=(card_node(preview),)))
                intent = enemy.intent
                strength = enemy.strength - sum(enemy.statuses.get(name) for name in TEMP_STRENGTH)
                damage = (modify_attack_damage_for_statuses(intent.base_attack_damage, p.statuses,
                          enemy.statuses, strength, extra_multiplier=damage_multiplier(p, enemy)) if intent.attack_count else None)
                icons = list(intent.kind.split('_'))
                if type(enemy).__name__ == 'TestSubject' and getattr(enemy, 'reviving', False):
                    icons.append('buff')
                if intent.attack_count and 'attack' not in icons:
                    icons.insert(0, 'attack')
                for category, present in (('defend', bool(intent.block_gain)),
                                          ('buff', bool(intent.strength_gain)),
                                          ('debuff', bool(intent.status_name)),
                                          ('shuffle', bool(intent.slimed_added or intent.discard_cards))):
                    if present and category not in icons:
                        icons.append(category)
                children.extend(node('intent', category, damage=damage if category == 'attack' else None,
                                     hits=intent.attack_count or None if category == 'attack' else None) for category in icons)
            infinite = bool(getattr(enemy, 'about_to_blow', False))
            enemies.append(node('enemy', type(enemy).__name__, ref=ref, slot=slot, hp=None if infinite else max(0, enemy.hp),
                                max_hp=None if infinite else enemy.max_hp, infinite_hp=infinite,
                                block=enemy.block, strength=strength,
                                alive=enemy.is_alive, children=children))
        from game.headless.core.orbs import value as orb_value
        resources = [node('orb', r.orbs[key]['kind'], ref=self.ref('orb', (self.epoch, key)),
                          passive=orb_value(p, r.orbs[key], 'passive'), evoke=orb_value(p, r.orbs[key], 'evoke')) for key in r.orb_order]
        if r.osty is not None:
            resources.append(node('osty', hp=r.osty['hp'], max_hp=r.osty['max_hp']))
        children = [*piles, node('powers', children=powers), node('enemies', children=enemies),
                    node('resources', stars=r.stars, orb_slots=r.orb_slots, children=resources)]
        public_order = [card.ref for pile in piles for card in pile.children]
        def ordered_options(identities):
            available = {self.card_refs[i] for i in identities}
            return tuple(ref for ref in public_order if ref in available)
        selection = r.selection
        if selection:
            source = selection['source']
            source_ref = (self.card_refs.get(source) or self.relic_refs.get(source)
                          or self.potion_refs.get(source))
            if source in r.potion_uses and source_ref is None:
                source_ref = self.ref('potion', ('owned', source))
                children.append(node('potion', r.potion_uses[source]['definition_id'], ref=source_ref))
            if source.startswith('monster.') and source.removeprefix('monster.').isdigit():
                source_ref = self.enemy_refs.get(int(source.removeprefix('monster.')))
            if source in r.powers:
                source_ref = self.ref('power', (self.epoch, source))
            self.selected = tuple(self.card_refs[i] for i in selection['selected'])
            children.append(node('selection', selection['operation'], minimum=selection['minimum'],
                                 maximum=selection['maximum'], manual_confirmation=True, cancelable=False,
                                 destination=selection['destination'], cost_modifier=selection['free'],
                                 source_status='known' if source_ref else 'unavailable_on_attachment',
                                 links=((('source', (source_ref,)),) if source_ref else ()) +(('options', ordered_options(selection['candidates'])),
                                        ('selected', self.selected))))
        elif p.pending_play:
            effect = p.current_card.definition.effects[p.pending_play.effect_index]
            children.append(node('selection', getattr(effect, 'operation', type(effect).__name__),
                                 minimum=1, maximum=1, manual_confirmation=False, cancelable=False,
                                 destination=getattr(effect, 'destination', getattr(effect, 'operation', '')),
                                 cost_modifier='', source_status='known',
                                 links=(('source', (self.card_refs[p.current_card.instance_id],)),) +(('options', ordered_options(p.pending_options())),)))
        return node('combat', round=combat.turn, hp=p.hp, max_hp=p.max_hp, block=p.block,
                    energy=p.energy, strength=p.strength, children=children)

    def reward(self, kind, offers, modifiers, key, *, resolved=False):
        ref = self.ref('reward', ('reward', self.serial, key))
        self.reward_refs[key] = ref
        children = []
        hidden = self.modal and kind in ('card', 'remove') and not resolved and self.opened != ref
        if self.modal and kind in ('card', 'remove') and not resolved:
            self.modal_keys.add(key)
        if not resolved and not hidden:
            for i, name in enumerate(offers):
                if kind == 'card':
                    mod = modifiers[i] if isinstance(modifiers, list) and modifiers else modifiers.get(name, {}) if isinstance(modifiers, dict) else {}
                    child = self.offer_card(name, (key, i, name, repr(mod)), mod)
                elif kind == 'stolen_card':
                    from game.headless.core.snapshots import restore_card
                    card = restore_card(modifiers['card'], self.engine.cards)
                    child = card_node(card, self.ref('card', ('deck', card.instance_id)))
                elif kind == 'special_card':
                    child = self.offer_card(name, (key, i, name))
                elif kind in ('potion', 'relic'):
                    child = self.item(kind, name, ('reward', self.serial, key, i, name))
                elif kind == 'gold':
                    child = node('gold', amount=modifiers['gold'])
                elif kind == 'remove':
                    continue  # Candidates link the owned deck, not a copied card.
                else:
                    raise UnsupportedProfile('reward_kind:' + kind)
                self.reward_cards[key, i] = child.ref
                if child.ref in self.card_refs.values():
                    children.append(node('offer', kind, links=(('card', (child.ref,)),), acquired=True))
                else:
                    children.append(child)
        return node('reward', kind, ref=ref, resolved=resolved, presentation='summary' if hidden else 'choice', children=children)

    def rewards(self):
        self.modal = True
        pending = self.state.pending
        children = [self.reward('gold', ['gold'], {'gold': pending['gold']}, 'gold', resolved=pending['gold_claimed']),
                    self.reward('card', pending['offers'], pending['card_modifiers'], -1, resolved=pending['card_resolved'])]
        for kind in ('potion', 'relic'):
            if pending.get(kind) is not None:
                children.append(self.reward(kind, [pending[kind]], {}, kind, resolved=pending[kind + '_claimed']))
        for i, reward in enumerate(pending.get('extra_rewards', ())):
            children.append(self.reward(reward['kind'], reward['offers'], reward['modifiers'], i, resolved=reward['resolved']))
        return node('rewards', children=children)

    def relic_work(self):
        work = self.state.relic_work[0]
        kind = work['kind']
        children, links = [], [('source', (self.relic_refs[work['source']],))]
        values = {}
        if kind == 'select':
            values = {key: work[key] for key in ('operation', 'minimum', 'maximum', 'enchantment', 'amount')}
            self.selected = tuple(self.card_refs[i] for i in work['selected'])
            links += [('options', (self.card_refs[i] for i in work['candidates'])), ('selected', self.selected)]
        elif kind in ('card_reward', 'card_grid', 'potion_reward', 'relic_reward', 'bundle'):
            for i, offer in enumerate(work['offers']):
                key = ('relic_work', self.serial, work['source'], i, repr(offer))
                if kind in ('card_reward', 'card_grid'):
                    child = self.offer_card(offer['definition_id'], key, offer)
                elif kind == 'bundle':
                    child = node('offer', 'bundle', ref=self.ref('offer', key), children=[self.offer_card(name, (key, j)) for j, name in enumerate(offer)])
                else:
                    child = self.item(kind.removesuffix('_reward'), offer, key)
                children.append(child)
                self.offer_refs[i] = child.ref
            if kind == 'card_grid':
                links.append(('selected', (self.offer_refs[i] for i in work['selected'])))
                values.update(minimum=0, maximum=len(children), manual_confirmation=True)
            else:
                values['optional'] = not work.get('mandatory', False) and kind != 'bundle'
            ref = self.ref('reward', ('relic_work', self.serial, work['source']))
            self.reward_refs[-1] = ref
            children = [node('reward', kind, ref=ref, children=children)]
        else:
            raise UnsupportedProfile('relic_work:' + kind)
        return node('relic_choice', kind, children=children, links=links, **values)

    def room(self):
        p = self.state.pending or {}
        kind = p.get('kind')
        if kind == 'ancient':
            children = []
            for name in self.state.ancient_start.offers:
                child = self.item('relic', name, ('ancient', name))
                self.offer_refs[name] = child.ref
                children.append(child)
            return node('ancient', 'neow', children=children)
        if kind == 'rest_site':
            from game.headless.run.rest_site import heal_amount
            links = []
            if 'eligible' in p:
                links.append(('options', (self.card_refs[i] for i in p['eligible'])))
            self.selected = tuple(self.card_refs[i] for i in p.get('selected', ()))
            links.append(('selected', self.selected))
            return node('rest', stage=p['stage'], heal=heal_amount(self.state),
                        minimum=2 if p['stage'] == 'cook' else 1, maximum=2 if p['stage'] == 'cook' else 1,
                        children=[node('used_option', name) for name in p['used']], links=links)
        if kind == 'shop':
            from game.headless.run.shop import removal_price
            children = []
            for offer in p['offers']:
                ref = self.ref('offer', ('shop', p['shop_id'], offer['offer_id']))
                self.offer_refs[offer['offer_id']] = ref
                payload = ()
                if not offer['sold']:
                    if offer['kind'] == 'card':
                        payload = (self.offer_card(offer['definition_id'], ('shop', ref), offer),)
                    else:
                        payload = (self.item(offer['kind'], offer['definition_id'], ('shop', ref)),)
                children.append(node('offer', offer['kind'], ref=ref, slot=offer['slot'],
                                     price=offer['price'], on_sale=offer['on_sale'], sold=offer['sold'], children=payload))
            return node('shop', stage=p['stage'], removal_price=removal_price(self.state),
                        removal_used=p['removal_used'], children=children)
        if kind == 'treasure':
            children = []
            if p['stage'] == 'open' and p.get('relic_id'):
                child = self.item('relic', p['relic_id'], ('treasure', self.serial, p['treasure_id']))
                self.offer_refs['treasure'] = child.ref
                children.append(child)
            return node('treasure', stage=p['stage'], children=children)
        if kind == 'scripted_event':
            from .full_events import project_event
            return project_event(self)
        raise UnsupportedProfile('room_kind:' + str(kind))

    def decision(self, *, transform=None):
        legal = self.engine.legal_actions()
        if any(type(action) not in COMMANDS for action in legal):
            raise UnsupportedProfile('legal_action_family')
        public_run = self.run()
        if self.state.relic_work:
            context = self.relic_work()
        elif self.engine.combat is not None:
            context = self.combat()
        elif self.state.phase is RunPhase.REWARD:
            context = self.rewards()
        elif self.state.phase is RunPhase.ACT_COMPLETE:
            context = node('act_transition', completed_act=self.state.act_index + 1)
        elif self.state.phase is RunPhase.ROUTE and self.state.pending is None:
            context = node('map', links=(('reachable', (self.node_refs[a.node_id] for a in legal if isinstance(a, ra.ChooseNode))),))
        else:
            context = self.room()
        legal = self.present(legal)
        # Options are public controls with their semantic label, not raw event
        # or shop allocator IDs. They also cover Ancient rest actions.
        options = []
        for action in legal:
            if isinstance(action, (ra.ChooseEventOption, ra.UseRestRelic)):
                label = action.option_id if isinstance(action, ra.ChooseEventOption) else action.option
                ref = self.ref('option', (self.serial, context.definition_id, context.get('stage'), label))
                self.option_refs[label] = ref
                options.append(node('option', label, ref=ref))
        context = replace(context, children=(*context.children, *options))
        candidates = [self.bind(action, context) for action in legal]
        rank = {n.ref: i for i, n in enumerate((*f.walk(public_run), *f.walk(context)), 1) if n.ref}
        candidates.sort(key=lambda a: (f.ACTIONS.index(a.kind), rank.get(a.subject, 0), rank.get(a.target, 0)))
        commands = self.commands
        self.commands = {f'action:{i}': commands[a.ref] for i, a in enumerate(candidates)}
        candidates = tuple(replace(a, ref=f'action:{i}') for i, a in enumerate(candidates))
        result = f.PublicDecision(f.SCHEMA, f.PROFILE, public_run, context, candidates)
        if transform is not None:
            result = transform(result)
        self.prepared = f.PreparedPublic(result)
        return self.prepared.value

    def present(self, legal):
        if not self.modal:
            return legal
        def owner(action):
            if isinstance(action, ra.ChooseRewardCard):
                return -1
            if isinstance(action, (ra.ChooseExtraReward, ra.RerollCardReward, ra.SacrificeCardReward)):
                return action.index if action.index in self.modal_keys else None
            if isinstance(action, ra.ChooseEventOption):
                parts = action.option_id.split('_')
                if parts[0] in ('reward', 'skip') and len(parts) >= 2 and parts[1].isdigit():
                    index = int(parts[1])
                    return index if index in self.modal_keys else None
            return None
        opened = next((key for key in self.modal_keys if self.reward_refs[key] == self.opened), None)
        if opened is not None:
            return (*[a for a in legal if owner(a) == opened], Presentation(opened, False))
        result, offered = [], set()
        for action in legal:
            key = owner(action)
            if key is None:
                result.append(action)
            elif key not in offered:
                result.append(Presentation(key, True))
                offered.add(key)
        return result

    def bind(self, action, context):
        if isinstance(action, Presentation):
            kind = 'open_reward' if action.opened else 'close_reward'
            ref = f'action:{len(self.commands)}'
            self.commands[ref] = action
            return f.Candidate(ref, kind, self.reward_refs[action.key])
        kind, subject, target = COMMANDS[type(action)], None, None
        if isinstance(action, ca.PlayCard):
            subject, target = self.card_refs[action.instance_id], self.enemy_refs.get(action.target_slot)
        elif isinstance(action, (ca.ChooseCombatCard, ra.ChooseUpgrade, ra.ChooseShopRemoval, ra.ChooseRelicCard, ra.ChooseCookCard)):
            subject = self.card_refs.get(action.instance_id)
            if action.instance_id is None:
                kind = 'cancel_selection'
            elif subject in self.selected:
                kind = {ca.ChooseCombatCard: 'deselect_card', ra.ChooseRelicCard: 'deselect_relic_card', ra.ChooseCookCard: 'deselect_cook_card'}.get(type(action), kind)
        elif isinstance(action, ra.ChooseEventCard):
            subject = self.card_refs[action.card_instance_id]
        elif isinstance(action, ra.ChooseNode):
            subject = self.node_refs[action.node_id]
        elif isinstance(action, (ra.UsePotion, ra.DiscardPotion)):
            subject = self.potion_refs[action.instance_id]
            if isinstance(action, ra.UsePotion):
                target = self.enemy_refs.get(action.target_slot)
        elif isinstance(action, (ra.ClaimGold, ra.ClaimPotion, ra.ClaimRelic)):
            subject = self.reward_refs[{ra.ClaimGold: 'gold', ra.ClaimPotion: 'potion', ra.ClaimRelic: 'relic'}[type(action)]]
        elif isinstance(action, (ra.ChooseRewardCard, ra.ChooseExtraReward)):
            key = action.index if isinstance(action, ra.ChooseExtraReward) else -1
            subject = self.reward_refs[key]
            if action.definition_id is None:
                kind = 'skip_reward'
            else:
                reward = self.state.pending['extra_rewards'][key] if key != -1 else self.state.pending
                if reward.get('kind') == 'remove':
                    target = self.card_refs[action.definition_id]
                else:
                    index = action.offer_index if action.offer_index is not None else reward['offers'].index(action.definition_id)
                    target = self.reward_cards.get((key, index))
        elif isinstance(action, (ra.RerollCardReward, ra.SacrificeCardReward)):
            subject = self.reward_refs[action.index]
        elif isinstance(action, ra.BuyShopItem):
            subject = self.offer_refs[action.offer_id]
        elif isinstance(action, ra.ClaimTreasureRelic):
            subject = self.offer_refs['treasure']
        elif isinstance(action, ra.ChooseAncientRelic):
            subject = self.offer_refs[action.definition_id]
        elif isinstance(action, ra.ChooseRelicReward):
            subject = self.offer_refs.get(action.index)
            if action.index is None:
                kind, subject = 'skip_reward', self.reward_refs[-1]
        elif isinstance(action, (ra.ChooseEventOption, ra.UseRestRelic)):
            label = action.option_id if isinstance(action, ra.ChooseEventOption) else action.option
            subject = self.option_refs[label]
            parts = label.split('_')
            if label.startswith('card_') and len(parts) == 2 and parts[1].isdigit():
                target = self.reward_cards.get((-1, int(parts[1])))
            elif label.startswith('reward_') and len(parts) == 3 and all(v.isdigit() for v in parts[1:]):
                key, index = map(int, parts[1:])
                target = self.reward_cards.get((key, index)) or self.reward_refs.get(key)
            elif label.startswith('claim_potion_'):
                index = int(parts[-1])
                target = self.reward_cards.get(('potion', 0)) or self.reward_cards.get((index, 0))
            elif label == 'claim':
                target = self.reward_cards.get((-1, 0)) or self.reward_refs.get(-1)
            if context.definition_id == 'trial' and context.get('page') == 'confirm_abandon' and label == 'confirm':
                kind = 'abandon_run'
        ref = f'action:{len(self.commands)}'
        self.commands[ref] = action
        return f.Candidate(ref, kind, subject, target)

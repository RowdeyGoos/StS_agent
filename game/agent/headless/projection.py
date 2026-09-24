"""Direct allowlist projection; private snapshots are never policy inputs."""
from game.agent import contracts as c
from game.headless.core.actions import PlayCard, EndTurn, ChooseCombatCard, ConfirmCombatSelection
from game.headless.run.actions import ChooseNode, ClaimGold, ClaimPotion, ClaimRelic, ChooseRewardCard, LeaveRewards
from game.headless.run.state import RunPhase
from game.headless.powers.status import SUPPORTED_STATUS_NAMES, modify_attack_damage_for_statuses
from game.headless.powers.hive import damage_multiplier
from game.headless.powers.necrobinder import TEMP_STRENGTH
from game.headless.monsters.overgrowth import SimpleEnemy, Nibbit, ShrinkerBeetle
from game.headless.core.orbs import value as orb_value
from game.headless.cards.operations import ChoosePileCard
from .cards import project, signature, resources as card_resources
from .errors import UnsupportedProfile
from .identity import number

PILES = (('hand', 'hand'), ('draw', 'draw_pile'), ('discard', 'discard_pile'),
         ('exhaust', 'exhaust_pile'), ('in_play', 'in_play'), ('powers', 'powers'))
ENEMIES = {SimpleEnemy: 'simple_enemy', Nibbit: 'nibbit', ShrinkerBeetle: 'shrinker_beetle'}
# These relics have no changing display counter. Other relics need an explicit
# public-counter mapping, including any combat-owned value, before support.
RELICS = frozenset(('burning_blood', 'ring_of_the_snake', 'divine_right', 'bound_phylactery',
                   'cracked_core', 'strawberry', 'pear', 'mango', 'golden_pearl', 'nutritious_oyster'))
POWERS = frozenset(('dexterity', 'focus', 'vigor'))
NODE_KINDS = frozenset(('combat', 'elite', 'boss', 'event', 'unknown', 'rest', 'shop', 'treasure', 'ancient'))


class Projection:
    def __init__(self, engine, identities, history, power_cards, coverage, epoch, opened):
        self.engine, self.ids = engine, identities
        self.state = engine.state
        self.history, self.coverage = history, coverage
        self.power_cards = power_cards
        self.epoch, self.opened = epoch, opened
        self.commands = {}
        self.card_refs, self.enemy_refs, self.node_refs = {}, {}, {}
        self.reward_refs = {}
        self.offers = {}
        self.seen_powers = set()

    def card_key(self, card):
        return ('combat', self.epoch, card.instance_id)

    def candidate(self, kind, command, subject=None, target=None):
        ref = f'action:{len(self.commands)}'
        self.commands[ref] = command
        return c.Candidate(ref, kind, subject, target)

    def map(self):
        graph = self.engine.graph
        if graph is None:
            raise UnsupportedProfile('run_map')
        # Authored fixture routes have no coordinates. Lay out their public DAG
        # by depth and authored sibling order; generated maps retain native cells.
        depths = {}
        def visit(node_id, depth):
            if depth <= depths.get(node_id, -1):
                return
            depths[node_id] = depth
            for child in graph.node(node_id).next_node_ids:
                visit(child, depth + 1)
        for entry in graph.entry_node_ids or (graph.start_id,):
            visit(entry, 0)
        positions, columns = {}, {}
        for node in graph.nodes:
            if node.kind not in NODE_KINDS:
                if node.kind in ('slice_end', 'terminal') and not node.next_node_ids:
                    continue  # Fixture termination markers are not game rooms.
                raise UnsupportedProfile('map_node_kind')
            row = node.row if node.row is not None else depths[node.node_id]
            column = node.column if node.column is not None else columns.get(row, 0)
            columns[row] = column + 1
            positions[node.node_id] = row, column
        ordered = sorted(positions, key=positions.__getitem__)
        if len(set(positions.values())) != len(positions):
            raise UnsupportedProfile('ambiguous_map_layout')
        for node_id in ordered:
            self.node_refs[node_id] = self.ids.ref('node', (self.state.act_index, node_id))
        nodes = tuple(c.MapNode(self.node_refs[i], *positions[i], graph.node(i).kind,
                               tuple(self.node_refs[j] for j in sorted(graph.node(i).next_node_ids,
                                     key=lambda j: positions.get(j, (10**9, 0))) if j in positions))
                      for i in ordered)
        current = self.node_refs.get(self.state.current_node_id)
        return c.known(c.Map(c.known(current) if current is not None else c.not_applicable(), nodes))

    def relic(self, name, key):
        if name not in RELICS:
            raise UnsupportedProfile('relic_counters')
        return c.Relic(self.ids.ref('relic', key), name, c.known(()))

    def run(self):
        s, combat = self.state, self.engine.combat
        p = None if combat is None else combat.player
        character = s.config.character if s.config else (p.rules.character if p else 'ironclad')
        cards = sorted(s.deck, key=signature)
        deck = tuple(project(card, self.ids.ref('card', ('deck', card.instance_id))) for card in cards)
        # Tie-break already public names, not raw allocated identities.
        deck = tuple(sorted(deck, key=lambda card: (card.definition_id, card.upgrade_level, number(card.ref))))
        relics = tuple(self.relic(r.definition_id, ('owned', r.instance_id)) for r in s.relics)
        potions = tuple(c.PotionSlot(i, None if item is None else
                          c.Potion(self.ids.ref('potion', ('owned', item.instance_id)), item.definition_id))
                        for i, item in enumerate(s.potions))
        return c.Run(character, s.config.ascension if s.config else 0, s.act_index + 1,
                     s.visited_room_count, p.hp if p else s.hp, p.max_hp if p else s.max_hp,
                     s.gold, c.known(deck), c.known(relics), c.known(potions), self.map(),
                     c.known(c.History(self.coverage, tuple(self.history))))

    def powers(self, owner, key, extra=None, *, enemy=False):
        values = {name: owner.statuses.get(name) for name in SUPPORTED_STATUS_NAMES if owner.statuses.get(name)}
        strength = owner.strength - (sum(owner.statuses.get(name) for name in TEMP_STRENGTH) if enemy else 0)
        if strength:
            values['strength'] = strength
        if extra:
            if any(amount and name not in POWERS for name, amount in extra.items()):
                raise UnsupportedProfile('power_display')
            values.update(extra)
        powers = []
        for name, amount in sorted(values.items()):
            if not amount:
                continue
            identity = (key, name)
            self.seen_powers.add(identity)
            ref = (self.ids.ref('power', identity) if identity in self.ids.active_powers
                   else self.ids.fresh('power', identity))
            powers.append(c.Power(ref, name, amount, c.known(())))
        return c.known(tuple(powers))

    def combat(self):
        combat = self.engine.combat
        p, d, r = combat.player, combat.player.deck, combat.player.rules
        if d.offered or d.sequestered:
            raise UnsupportedProfile('additional_combat_piles')
        if any((self.epoch, card.instance_id) not in self.power_cards for card in d.powers):
            raise UnsupportedProfile('power_card_history')
        # Validate the power/relic mechanisms before their pure cost/preview
        # helpers are used. Unknown mechanisms cannot masquerade as base values.
        powers = self.powers(p, ('player', self.epoch), r.powers)
        for relic in r.relics:
            if relic['definition_id'] not in RELICS:
                raise UnsupportedProfile('combat_relic_counters')
        visible = [(self.card_key(card), card) for name, attr in PILES if name not in ('draw', 'powers')
                   for card in getattr(d, attr)]
        draw = [(self.card_key(card), card) for card in sorted(d.draw_pile, key=lambda card: signature(card, p, on_table=False))]
        self.ids.reconcile_draw(visible, draw, lambda card: signature(card, p, on_table=False))
        for key, card in (*visible, *draw):
            self.card_refs[card.instance_id] = self.ids.ref('card', key)
        piles = []
        for name, attr in PILES:
            if name == 'powers':
                # Native has no inspectable power-card pile. Keep only the last
                # publicly observed descriptions from our own play history,
                # never the later private state/order of detached engine cards.
                cards = tuple(self.power_cards.values())
                piles.append(c.Pile(name, len(cards), c.known(cards), 'visible'))
                continue
            originals = getattr(d, attr)
            if name == 'draw':
                originals = sorted(originals, key=lambda card: (signature(card, p, on_table=False), number(self.card_refs[card.instance_id])))
            cards = tuple(project(card, self.card_refs[card.instance_id], p, combat=True,
                                  on_table=name in ('hand', 'in_play')) for card in originals)
            piles.append(c.Pile(name, len(cards), c.known(cards), 'canonical' if name == 'draw' else 'visible'))
        enemies = []
        for slot, enemy in enumerate(combat.enemies):
            if type(enemy) not in ENEMIES:
                raise UnsupportedProfile('enemy_public_powers')
            ref = self.ids.ref('enemy', (self.epoch, slot))
            self.enemy_refs[slot] = ref
            intent = enemy.intent
            # Resolve the displayed label with both creatures' public modifiers
            # in one pass (rounding twice changes Weak + Vulnerable labels).
            # The execution base is an input to this pure engine calculator,
            # never a public field, move template or future-intent feature.
            damage = intent.attack_damage
            if intent.attack_count:
                strength = enemy.strength - sum(enemy.statuses.get(name) for name in TEMP_STRENGTH)
                damage = modify_attack_damage_for_statuses(
                    intent.base_attack_damage, p.statuses, enemy.statuses, strength,
                    extra_multiplier=damage_multiplier(p, enemy))
            intents = () if not enemy.is_alive else (c.Intent(intent.kind,
                       c.known(damage) if intent.attack_count else c.not_applicable(),
                       c.known(intent.attack_count) if intent.attack_count else c.not_applicable()),)
            enemies.append(c.Enemy(ref, ENEMIES[type(enemy)], max(0, enemy.hp), enemy.max_hp, enemy.block,
                                   self.powers(enemy, ('enemy', self.epoch, slot), enemy=True), c.known(intents)))
        blades = tuple(card.ref for pile in piles for card in pile.cards.value if card.definition_id == 'sovereign_blade')
        relevant = {resource for _, card in (*visible, *draw) for resource in card_resources(card)}
        regent = r.character == 'regent' or 'regent' in relevant or bool(r.stars) or bool(blades)
        osty = c.not_applicable()
        if r.character == 'necrobinder' or 'necrobinder' in relevant or r.osty is not None:
            if r.osty is not None and set(r.osty) != {'hp', 'max_hp'}:
                raise UnsupportedProfile('osty_public_powers')
            osty = c.known(c.OstyState(None if r.osty is None else
                            c.Osty(r.osty['hp'], r.osty['max_hp'], 0, c.known(()))))
        has_orbs = r.character == 'defect' or 'defect' in relevant or bool(r.orb_slots) or bool(r.orb_order)
        orbs = tuple(c.Orb(self.ids.ref('orb', (self.epoch, key)), r.orbs[key]['kind'],
                          orb_value(p, r.orbs[key], 'passive'), orb_value(p, r.orbs[key], 'evoke'))
                     for key in r.orb_order)
        resources = c.CharacterResources(c.known(r.stars) if regent else c.not_applicable(),
                         c.known(blades) if regent else c.not_applicable(), osty,
                         c.known(r.orb_slots) if has_orbs else c.not_applicable(),
                         c.known(orbs) if has_orbs else c.not_applicable())
        return c.Combat('combat', combat.turn, p.block, p.energy, powers, resources, tuple(enemies), tuple(piles))

    def selection(self, combat):
        p = self.engine.combat.player
        s = p.rules.selection
        if s:
            ids, selected = s['candidates'], s['selected']
            source, low, high, manual = s['source'], s['minimum'], s['maximum'], True
        else:
            source_card = p.current_card
            effect = source_card.definition.effects[p.pending_play.effect_index]
            if type(effect) is not ChoosePileCard:
                raise UnsupportedProfile('selection_family')
            ids, selected = p.pending_options(), ()
            source, low, high, manual = source_card.instance_id, 1, 1, False
        pile = next((name for name, attr in PILES if name in ('discard', 'exhaust') and
                     set(ids) <= {card.instance_id for card in getattr(p.deck, attr)}), None)
        if not ids or pile is None or source not in self.card_refs:
            raise UnsupportedProfile('selection_family')
        public_pile = next(pile_value for pile_value in combat.piles if pile_value.kind == pile)
        options = {self.card_refs[i] for i in ids}
        return c.CardSelection('card_selection', combat, c.known(self.card_refs[source]), pile,
                               tuple(card.ref for card in public_pile.cards.value if card.ref in options),
                               tuple(self.card_refs[i] for i in selected),
                               low, high, manual, False)

    def rewards(self):
        p = self.state.pending
        if not p or p.get('kind') != 'reward' or not p.get('combat_reward') or p.get('extra_rewards'):
            raise UnsupportedProfile('reward_family')
        entries = []
        for kind in ('gold', 'card', 'potion', 'relic'):
            if kind in ('potion', 'relic') and p.get(kind) is None:
                continue
            ref = self.ids.ref('reward', (self.epoch, kind))
            self.reward_refs[kind] = ref
            resolved = p['card_resolved'] if kind == 'card' else p[kind + '_claimed']
            payload = dict(amount=c.not_applicable(), cards=c.not_applicable(),
                           potion=c.not_applicable(), relic=c.not_applicable())
            opened = kind == 'card' and self.opened and not resolved
            if not resolved:
                if kind == 'gold':
                    payload['amount'] = c.known(p['gold'])
                elif kind == 'card' and opened:
                    from game.headless.enchantments.base import restore
                    cards = []
                    for i, name in enumerate(p['offers']):
                        mod = p['card_modifiers'][i] if isinstance(p['card_modifiers'], list) else p['card_modifiers'][name]
                        card = self.engine.cards.create(name, upgrade_level=mod['upgrade_level'])
                        card.enchantment = restore(mod['enchantment'])
                        card_ref = self.ids.ref('card', ('offer', self.epoch, i))
                        self.offers[i] = card_ref
                        cards.append(project(card, card_ref))
                    payload['cards'] = c.known(tuple(cards))
                elif kind == 'potion':
                    payload['potion'] = c.known(c.Potion(self.ids.ref('potion', ('reward', self.epoch)), p[kind]))
                elif kind == 'relic':
                    payload['relic'] = c.known(self.relic(p[kind], ('reward', self.epoch)))
            entries.append(c.Reward(ref, kind, 'choice' if opened else 'summary', **payload, resolved=resolved))
        return c.Rewards('rewards', tuple(entries))

    def decision(self):
        legal = self.engine.legal_actions()
        allowed = (PlayCard, EndTurn, ChooseCombatCard, ConfirmCombatSelection, ChooseNode,
                   ClaimGold, ClaimPotion, ClaimRelic, ChooseRewardCard, LeaveRewards)
        if any(type(action) not in allowed for action in legal):
            raise UnsupportedProfile('legal_action_family')
        public_run = self.run()
        phase = self.state.phase
        if phase is RunPhase.COMBAT:
            context = self.combat()
            p = self.engine.combat.player
            if p.rules.selection is not None or p.pending_play is not None:
                context = self.selection(context)
                legal = tuple(sorted(legal, key=lambda a: context.options.index(self.card_refs[a.instance_id])
                              if type(a) is ChooseCombatCard else len(context.options)))
        elif phase is RunPhase.REWARD:
            context = self.rewards()
        elif phase is RunPhase.ROUTE and self.state.pending is None:
            reachable = [action.node_id for action in legal if type(action) is ChooseNode]
            if any(key not in self.node_refs for key in reachable):
                raise UnsupportedProfile('fixture_terminal_command')
            reachable.sort(key=lambda key: number(self.node_refs[key]))
            legal = tuple(sorted(legal, key=lambda a: number(self.node_refs[a.node_id])))
            context = c.MapChoice('map', tuple(self.node_refs[key] for key in reachable))
        else:
            raise UnsupportedProfile('decision_family')
        candidates = []
        opened = isinstance(context, c.Rewards) and any(r.presentation == 'choice' for r in context.entries)
        offer_actions = [a for a in legal if type(a) is ChooseRewardCard]
        for action in legal:
            if opened and type(action) is not ChooseRewardCard:
                continue  # Presentation child suspends parent controls.
            if type(action) is PlayCard:
                candidates.append(self.candidate('play_card', action, self.card_refs[action.instance_id],
                                                 self.enemy_refs.get(action.target_slot)))
            elif type(action) is EndTurn:
                candidates.append(self.candidate('end_turn', action))
            elif type(action) is ChooseCombatCard:
                ref = self.card_refs[action.instance_id]
                candidates.append(self.candidate('deselect_card' if ref in context.selected else 'select_card', action, ref))
            elif type(action) is ConfirmCombatSelection:
                candidates.append(self.candidate('confirm_selection', action))
            elif type(action) is ChooseNode:
                candidates.append(self.candidate('choose_map_node', action, self.node_refs[action.node_id]))
            elif type(action) in (ClaimGold, ClaimPotion, ClaimRelic):
                kind = {ClaimGold: 'gold', ClaimPotion: 'potion', ClaimRelic: 'relic'}[type(action)]
                candidates.append(self.candidate('claim_reward', action, self.reward_refs[kind]))
            elif type(action) is ChooseRewardCard:
                if opened:
                    index = action.offer_index if action.offer_index is not None else (
                        self.state.pending['offers'].index(action.definition_id) if action.definition_id else None)
                    candidates.append(self.candidate('skip_reward' if index is None else 'choose_reward_card', action,
                                                     self.reward_refs['card'], self.offers.get(index)))
                elif action is offer_actions[0]:
                    candidates.append(self.candidate('open_card_reward', None, self.reward_refs['card']))
            elif type(action) is LeaveRewards:
                candidates.append(self.candidate('leave_rewards', action))
        if not candidates:
            raise UnsupportedProfile('no_decision')
        result = c.PublicDecision('sts_public_decision_v1', 'combat_reward_map_v1', public_run, context, tuple(candidates))
        c.require_ready(result)
        self.ids.active_powers = self.seen_powers
        return result

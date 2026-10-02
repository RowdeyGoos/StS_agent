"""Bounded, public-value-only immediate damage previews for Vantom experiments.

This is deliberately a partial capability. It runs native card resolution on a
disposable reconstruction, never on an engine clone. Missing rules/counters,
draws, and non-singleton randomness produce unknown, not guessed damage. Inputs
are plain descriptions; this module cannot access adapters or training state.
"""
from copy import deepcopy
from dataclasses import asdict, dataclass

from game.headless.cards.base import Card
from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.cards.effects import (ApplyDebuffs, ApplyTargetStatus,
                                        DealDamage, GainBlock, RandomEnemyAttack)
from game.headless.cards.operations import Attack, CardOperation, Power
from game.headless.core.deck import Deck
from game.headless.core.player import Player
from game.headless.enchantments.base import EnchantmentInstance
from game.headless.monsters.vantom import Vantom
from game.headless.powers.status import StatusCollection, SUPPORTED_STATUS_NAMES


class UnknownPreview(Exception):
    """A dependency cannot be established from the supported public context."""


@dataclass(frozen=True, slots=True)
class DamagePreview:
    hp_removed: int | None = None
    block_removed: int | None = None
    slippery_removed: int | None = None
    reason: str | None = None

    @property
    def known(self):
        return self.reason is None and self.hp_removed is not None


class _PublicRandom:
    def choice(self, values):
        if len(values) != 1:
            raise UnknownPreview('random_target')
        return values[0]

    def shuffle(self, values):
        if values:
            raise UnknownPreview('hidden_shuffle')

    def __getattr__(self, name):
        if name.startswith('__'):
            raise AttributeError(name)
        raise UnknownPreview('randomness')


class _PublicPlayer(Player):
    def card_cost(self, card):
        # This is the currently displayed cost, not reconstructed cost history.
        return card.preview_energy

    def star_cost(self, card):
        return card.preview_stars


# Conservative capability lists. Unlisted content stays in the observation and
# policy graph; it only disables this optional preview. Expand with conformance
# cases, never infer a missing counter from a default value.
SAFE_RELICS = frozenset('''burning_blood regal_pillow strawberry blood_vial
meal_ticket juzu_bracelet bag_of_marbles bronze_scales anchor war_paint
red_mask pear vajra oddly_smooth_stone pantograph whetstone horn_cleat
eternal_feather molten_egg captains_wheel potion_belt prayer_wheel ice_cream
art_of_war bag_of_preparation gambling_chip orichalcum toxic_egg
white_beast_statue girya white_star the_courier strike_dummy fake_strike_dummy
miniature_cannon paper_phrog the_boot hand_drill chemical_x amethyst_aubergine
gorget book_of_five_rings lantern planisphere venerable_tea_set lasting_candy
candelabra happy_flower sparkling_rouge petrified_toad stone_cracker
mercury_hourglass chandelier sturdy_clamp tiny_mailbox pendulum festive_popper
ripple_basin bellows lucky_fysh sword_of_stone vexing_puzzlebox pocketwatch
bowler_hat tungsten_rod gremlin_horn game_piece mummified_hand permafrost
razor_tooth centennial_puzzle red_skull self_forming_clay unceasing_top'''.split())
# These inactive hooks are safe only within the effect/monster whitelist below:
# no HP-loss/max-HP effects, no power-card plays, no replays, and no enemy
# retaliation. Draws (including an empty-hand Top trigger) still fail closed.
PUBLIC_COUNTER_RELICS = {'pen_nib': 10, 'nunchaku': 10, 'joss_paper': 5,
                         'shuriken': 3, 'kunai': 3, 'ornamental_fan': 3,
                         'kusarigama': 3, 'letter_opener': 3}
PUBLIC_STATUS_RELICS = frozenset(('lizard_tail', 'vambrace', 'unsettling_lamp'))
SAFE_POWERS = frozenset('''weak vulnerable frail artifact shrink dexterity
vigor thorns plating barricade temporary_strength temporary_dexterity ritual
regen clarity radiance free_attack free_skill no_draw rage juggernaut
strength setup_strike colossus gigantification cruelty no_energy_gain'''.split())
SAFE_ENEMY_POWERS = frozenset('slippery vulnerable weak artifact shrink frail mangle demise'.split())
SAFE_ENCHANTMENTS = frozenset('sown nimble sharp vigorous instinct steady royally_approved momentum'.split())
SAFE_FLAGS = frozenset('''is_dupe hexed extra_damage return_next_turn
free_until_played free_this_turn star_free_this_turn free_this_combat
sly_this_turn sly_this_combat retain_this_turn retain_this_combat all_enemies
ethereal_this_combat'''.split())


def _card(value, identity):
    try:
        definition = DEFAULT_CARDS.definition(value['definition_id'])
    except ValueError:
        raise UnknownPreview('card_definition')
    if [(type(e).__name__, asdict(e)) for e in definition.effects] != value['mechanics']:
        raise UnknownPreview('card_mechanics')
    card = Card(definition, upgrade_level=value['upgrade_level'], instance_id=identity)
    card.permanent_damage = value['permanent_damage']
    card.permanent_block = value['permanent_block']
    for key, amount in value['flags'].items():
        if key not in SAFE_FLAGS:
            raise UnknownPreview('card_modifier:' + key)
        setattr(card.combat_state, key, amount)
    if value['enchantment'] is not None:
        if value['enchantment']['definition_id'] not in SAFE_ENCHANTMENTS:
            raise UnknownPreview('enchantment')
        card.enchantment = EnchantmentInstance(**value['enchantment'])
    if asdict(card.spec) != value['spec']:
        raise UnknownPreview('card_spec')
    if card.spec.kind == 'curse' and card.definition.definition_id != 'clumsy':
        raise UnknownPreview('passive_curse')
    card.preview_energy, card.preview_stars = value['energy'], value['stars']
    return card


def _effects(card):
    if card.spec.kind != 'attack':
        raise UnknownPreview('non_attack')
    for effect in card.definition.effects:
        if type(effect) is Attack:
            if (effect.expression not in ('base', 'block', 'strikes', 'vulnerable', 'exhaust', 'draw_pile') or
                    effect.hit_expression not in ('fixed', 'vulnerable', 'x') or effect.fatal_max_hp):
                raise UnknownPreview('attack_expression')
        elif type(effect) in (DealDamage, GainBlock, ApplyTargetStatus, ApplyDebuffs, RandomEnemyAttack):
            pass
        elif type(effect) is CardOperation and effect.operation in ('clone', 'area_vulnerable', 'double_vulnerable', 'rampage'):
            pass
        elif type(effect) is Power and effect.name in SAFE_POWERS | SAFE_ENEMY_POWERS:
            pass
        else:
            raise UnknownPreview('card_effect:' + type(effect).__name__)


class PublicCombatPreview:
    """Prepare once per decision; each action gets its own isolated copy."""
    def __init__(self, context):
        self.reason = None
        self.target_ref = None
        try:
            self.player, self.cards = self._prepare(context)
            self.target_ref = context['enemies'][0]['ref']
        except UnknownPreview as error:
            self.reason = str(error)

    @staticmethod
    def _prepare(context):
        if context is None or context['character'] != 'ironclad':
            raise UnknownPreview('combat_context')
        if context['selection'] or context['resources']:
            raise UnknownPreview('pending_selection_or_resource')
        enemies = context['enemies']
        if len(enemies) != 1 or enemies[0]['definition_id'] != 'Vantom':
            raise UnknownPreview('enemy_family')
        ev = enemies[0]
        if ev['hp'] is None or not ev['alive']:
            raise UnknownPreview('enemy_hp')
        p = _PublicPlayer(Deck([], _PublicRandom()), max_hp=context['player']['max_hp'])
        p.catalog = DEFAULT_CARDS
        for key in ('hp', 'block', 'energy', 'strength'):
            setattr(p, key, context['player'][key])
        p.rules.round_number = context['player']['round']
        p.rules.stars = context['stars']
        for name, amount in context['powers'].items():
            if name not in SAFE_POWERS:
                raise UnknownPreview('player_power:' + name)
            if name in SUPPORTED_STATUS_NAMES:
                p.statuses.add(name, amount)
            else:
                p.rules.powers[name] = amount
        enemy = Vantom(_PublicRandom())
        enemy.hp, enemy.max_hp, enemy.block = ev['hp'], ev['max_hp'], ev['block']
        enemy.statuses = StatusCollection()
        for name, amount in ev['powers'].items():
            if name not in SAFE_ENEMY_POWERS:
                raise UnknownPreview('enemy_power:' + name)
            enemy.statuses.add(name, amount)
        enemy.combat_player = p
        p.combat_enemies = [enemy]
        for i, relic in enumerate(context['relics']):
            if relic['melted']:
                continue
            name = relic['definition_id']
            if name not in SAFE_RELICS | PUBLIC_COUNTER_RELICS.keys() | PUBLIC_STATUS_RELICS:
                raise UnknownPreview('relic:' + name)
            counter, memory = 0, {}
            if name in PUBLIC_COUNTER_RELICS:
                value = relic['display_counter']
                if (relic['show_counter'] is not True or type(value) is not int or
                        not 0 <= value < PUBLIC_COUNTER_RELICS[name] or relic['status'] not in ('active', 'normal')):
                    raise UnknownPreview('relic_counter:' + name)
                if name in ('shuriken', 'kunai', 'ornamental_fan', 'kusarigama', 'letter_opener'):
                    memory['turn_skills' if name == 'letter_opener' else 'turn_attacks'] = value
                else:
                    counter = value
            if name == 'lizard_tail':
                if relic['status'] not in ('normal', 'disabled'):
                    raise UnknownPreview('relic_status:' + name)
                counter = int(relic['status'] == 'disabled')
            elif name in ('vambrace', 'unsettling_lamp'):
                if relic['status'] not in ('normal', 'active'):
                    raise UnknownPreview('relic_status:' + name)
                memory['used'] = relic['status'] != 'active'
            p.rules.relics.append(dict(definition_id=name, instance_id=str(i), counter=counter, data={}))
            p.rules.relic_data[str(i)] = memory
        refs = {}
        for pile, values in context['piles'].items():
            if pile not in ('hand', 'draw_pile', 'discard_pile', 'exhaust_pile'):
                if values:
                    raise UnknownPreview('active_card_work')
                continue
            cards = []
            for value in values:
                card = _card(value, str(len(refs)))
                refs[value['ref']] = card.instance_id
                cards.append(card)
            setattr(p.deck, pile, cards)
        p.deck._allocated_ids = set(refs.values())
        p.deck._next_instance_id = len(refs)
        return p, refs

    def action(self, card_ref, target_ref=None):
        if self.reason is not None:
            return DamagePreview(reason=self.reason)
        if target_ref is not None and target_ref != self.target_ref:
            return DamagePreview(reason='target_ref')
        try:
            p = deepcopy(self.player)
            card = next((c for c in p.hand if c.instance_id == self.cards.get(card_ref)), None)
            if card is None:
                raise UnknownPreview('hand_card')
            _effects(card)
            enemy = p.combat_enemies[0]
            before = (enemy.hp, enemy.block, enemy.statuses.get('slippery'))
            from game.headless.core.resolution import execute
            from game.headless.core.hook_scheduler import run
            tasks = 0

            def bounded(player, task):
                nonlocal tasks
                tasks += 1
                if tasks > 512:
                    raise UnknownPreview('resolution_budget')
                # Even the public draw multiset must never stand in for order.
                if ((task[0] in ('draw', 'draw_next', 'draw_after_shuffle', 'hand_draw') and task[1] > 0) or
                        task[0] in ('pillage', 'pillage_after_shuffle') or task[0].startswith('autoplay')):
                    raise UnknownPreview('hidden_draw_or_autoplay')
                execute(player, task)

            p._resolving = True
            p.play_card(p.hand.index(card), enemy if card.spec.uses_target else None)
            run(p, bounded)
            if p.pending_play is not None or p.rules.selection is not None or p.rules.tasks:
                raise UnknownPreview('unfinished_action')
            after = (enemy.hp, enemy.block, enemy.statuses.get('slippery'))
            return DamagePreview(*(a - b for a, b in zip(before, after)))
        except UnknownPreview as error:
            return DamagePreview(reason=str(error))

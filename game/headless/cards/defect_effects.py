"""Defect card operations using existing card IDs, selections and command queues."""

from dataclasses import dataclass
from game.headless.cards.operations import value, Attack
from game.headless.core.resolution import push, find, move_out
from game.headless.core import orbs


def zero_combat(card):
    state = card.combat_state
    state.combat_cost_override = 0
    from game.headless.core.card_costs import mark_setter
    mark_setter(state, 'combat')
    state.combat_override_baseline = state.combat_cost_change


@dataclass(frozen=True, slots=True)
class Defect:
    operation: str
    amount: int = 0
    upgraded_amount: int | None = None

    @property
    def resolves_after_combat_end(self):
        return self.operation == 'genetic'

    def apply(self, card, p, target):
        if not p.combat_is_ending or self.resolves_after_combat_end:
            apply(self.operation, card, p, target, value(card, self.amount, self.upgraded_amount))


def apply(op, card, p, target, amount):
    r = p.rules
    if op == 'slots':
        orbs.add_slots(p, amount)
    elif op == 'remove_slots':
        orbs.remove_slots(p, amount)
    elif op == 'focus':
        from game.headless.powers.defect import focus
        focus(p, amount)
    elif op == 'energy':
        p.gain_energy(amount)
    elif op == 'double_energy':
        p.gain_energy(p.energy)
    elif op == 'evoke' or op == 'multi_cast':
        n = amount if op == 'evoke' else r.plays[card.instance_id]['x'] + int(card.upgraded)
        push(p, *[['orb_evoke', False, i == n - 1] for i in range(n)])
    elif op == 'shatter':
        push(p, *[task for _ in tuple(r.orb_order) for task in (['orb_evoke', False, False], ['orb_evoke', False, True])])
    elif op in ('darkness', 'tesla'):
        kind = 'dark' if op == 'darkness' else 'lightning'
        slot = None if target is None else p.combat_enemies.index(target)
        push(p, *[['orb_trigger', i, 'passive', slot] for i in tuple(r.orb_order) if r.orbs[i]['kind'] == kind for _ in range(amount)])
    elif op == 'compile_driver':
        push(p, ['draw', orbs.distinct(p), False])
    elif op == 'synchronize':
        from game.headless.powers.ironclad import apply_power
        apply_power(p, 'synchronize', 2 * orbs.distinct(p))
    elif op == 'ftl':
        if r.finished_plays_turn < amount:
            push(p, ['draw', card.spec.draw_count, False])
    elif op == 'eyes':
        if target.intent.attack_count:
            push(p, ['status', p.combat_enemies.index(target), 'weak', amount])
    elif op == 'claw':
        for c in p.deck.all_cards():
            if c not in p.deck.offered and c.definition.definition_id == 'claw':
                c.combat_state.extra_damage += amount
    elif op == 'cost_increase':
        card.combat_state.combat_cost_change += amount
    elif op == 'zero_combat':
        zero_combat(card)
    elif op == 'adaptive':
        from copy import deepcopy
        clone = deepcopy(card)
        clone.instance_id = None
        clone.combat_state.return_next_turn = False
        p.deck._ensure_identity(clone)
        zero_combat(clone)
        p.deck.discard_pile.append(clone)
        from game.headless.core.piles import after_generated_entry
        after_generated_entry(p, clone, is_clone=True)
    elif op == 'all_for_one':
        for c in tuple(p.deck.discard_pile):
            if c.spec.kind in ('attack', 'skill', 'power', 'block') and not c.spec.x_cost and p.card_cost(c) == 0:
                move_out(p, c)
                (p.hand if len(p.hand) < 10 else p.deck.discard_pile).append(c)
    elif op == 'reboot':
        from game.headless.core.piles import shuffle
        shuffle(p, include_hand=True)
    elif op == 'compact':
        push(p, *[['def_compact', card.instance_id, c.instance_id] for c in tuple(p.hand) if c.spec.kind == 'status'])
    elif op == 'genetic':
        card.permanent_block += amount
        r.genetic_gains[card.instance_id] = r.genetic_gains.get(card.instance_id, 0) + amount
    elif op == 'flak_cannon':
        statuses = [c for c in p.deck.all_cards() if c.spec.kind == 'status' and c not in p.deck.exhaust_pile and c not in p.deck.offered]
        push(p, *[['exhaust', c.instance_id] for c in statuses], ['def_flak', card.instance_id, len(statuses)])
    elif op == 'sunder':
        push(p, ['def_sunder', card.instance_id, p.combat_enemies.index(target), amount])
    elif op == 'scrape':
        r.plays[card.instance_id]['def_scrape'] = []
        from game.headless.relics.combat import has
        draw = [] if r.powers.get('no_draw') or r.player_side and has(p, 'fiddle') else [['def_scrape_draw', card.instance_id, card.spec.draw_count]]
        push(p, *draw, ['def_scrape', card.instance_id])
    elif op == 'white_noise':
        from game.headless.powers.defect import generate_power
        generate_power(p, free=True)
    elif op == 'uproar':
        from game.headless.core.native_shuffle import stable_shuffle
        options = [c for c in reversed(p.deck.draw_pile) if c.spec.kind == 'attack' and c.cost >= 0]
        if not options:
            options = [c for c in reversed(p.deck.draw_pile) if c.spec.kind == 'attack']
        stable_shuffle(options, p.deck.rng)
        if options:
            push(p, ['autoplay', options[0].instance_id, False])
    else:
        raise ValueError(f'Unknown Defect operation: {op}')


def execute(p, op, args):
    if p.combat_is_ending:
        return
    if op == 'def_status':
        from game.headless.cards.colorless_effects import create, catalog
        create(p, catalog(p).definition(args[0]), destination='discard_pile')
    elif op == 'def_compact':
        source, identity = args
        original, card = find(p, identity), find(p, source)
        if original is None:
            return
        from game.headless.cards.colorless_effects import catalog
        from game.headless.core.piles import after_generated_entry
        for name in ('hand', 'draw_pile', 'discard_pile', 'exhaust_pile'):
            pile = getattr(p.deck, name)
            if original in pile:
                replacement = catalog(p).create('fuel', upgrade_level=int(card.upgraded))
                p.deck._ensure_identity(replacement)
                pile[pile.index(original)] = replacement
                after_generated_entry(p, replacement, generated=False)
                break
    elif op == 'def_flak':
        from game.headless.cards.effects import RandomEnemyAttack
        RandomEnemyAttack(args[1], args[1]).apply(find(p, args[0]), p, None)
    elif op == 'def_sunder':
        from game.headless.cards.colorless_effects import hit
        card, enemy = find(p, args[0]), p.combat_enemies[args[1]]
        if enemy.is_alive:
            from game.headless.potions.powers import begin_attack
            begin_attack(p, card)
            hit(p, card, enemy, extra=p.rules.powers.pop('vigor', 0))
            if not enemy.is_alive:
                p.gain_energy(args[2])
    elif op in ('def_scrape_draw', 'def_scrape_after_shuffle'):
        from game.headless.powers.colorless import ensure_draw
        if args[1] <= 0 or p.combat_is_ending:
            return
        if op == 'def_scrape_draw':
            if not ensure_draw(p, ['def_scrape_after_shuffle', *args]):
                return
        elif not p.deck.draw_pile or len(p.hand) >= 10:
            return
        drawn = p.deck.draw(1)
        if drawn:
            c = drawn[0]
            p.rules.plays[args[0]]['def_scrape'].append(c.instance_id)
            p.rules.drawn_combat += 1
            p.rules.drawn_turn += 1
            from game.headless.powers.defect import draw_record
            draw_record(p, c)
            push(p, ['after_draw'], ['silent_draw_hook', False, c.instance_id], ['after_draw_card', c.instance_id], ['def_scrape_draw', args[0], args[1] - 1])
            if p.rules.powers.get('hellraiser') and c.definition.strike:
                push(p, ['autoplay', c.instance_id, False])
    elif op == 'def_discard':
        card = find(p, args[0])
        if card is not None and card in p.hand:
            from game.headless.core.discard import discard_and_draw
            discard_and_draw(p, [card])
    elif op == 'def_scrape':
        from game.headless.powers.ironclad import local_cost
        identities = p.rules.plays[args[0]].pop('def_scrape')
        cards = [find(p, identity) for identity in identities]
        from game.headless.core.discard import discard_and_draw
        discard_and_draw(p, [c for c in cards if c is not None and c in p.hand and (c.spec.x_cost or local_cost(c) != 0)])
    else:
        from game.headless.powers.defect import execute as power_execute
        power_execute(p, op, args)


@dataclass(frozen=True, slots=True)
class AddCardToDiscard:
    definition: str
    count: int = 1

    def apply(self, card, p, target):
        push(p, *[['def_status', self.definition] for _ in range(self.count)])

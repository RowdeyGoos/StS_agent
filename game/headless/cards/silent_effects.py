"""Silent card operations; choices and reactions resume through owned tasks."""

from dataclasses import dataclass
from game.headless.core.resolution import push, find, start_play
from game.headless.cards.operations import value


@dataclass(frozen=True, slots=True)
class Silent:
    operation: str
    amount: int = 0
    upgraded_amount: int | None = None

    def apply(self, card, player, target):
        if not player.combat_is_ending:
            apply(self.operation, card, player, target, value(card, self.amount, self.upgraded_amount))


def shivs(p, count, *, upgraded=False, inky=False):
    from game.headless.cards.colorless_effects import create
    from game.headless.enchantments.base import enchant
    for _ in range(count):
        card = create(p, (p.catalog).definition('shiv'), upgraded=upgraded)
        if inky:
            enchant(card, 'inky')


def choose(p, source, operation, count=1, *, optional=False):
    from game.headless.core.choices import begin
    from game.headless.powers.silent import is_sly
    cards = list(p.hand)
    if operation == 'hand_trick':
        cards = [c for c in cards if c.spec.kind in ('skill', 'block') and not is_sly(c)]
    elif operation == 'well_laid_plans':
        cards = [c for c in cards if not c.spec.retain]
    begin(p, source, cards, operation=operation, minimum=0 if optional else count, maximum=count)


def apply(op, card, p, target, amount):
    from game.headless.powers.ironclad import apply_power
    from game.headless.core.discard import discard_and_draw
    r = p.rules
    if op == 'energy':
        p.gain_energy(amount)
    elif op in ('shivs', 'inky_shivs'):
        shivs(p, amount, upgraded=card.upgraded and card.definition.definition_id == 'hidden_daggers', inky=op == 'inky_shivs')
    elif op in ('discard', 'hand_trick', 'nightmare'):
        choose(p, card.instance_id, op, amount if op == 'discard' else 1)
    elif op in ('gamble', 'discard_all', 'storm_of_steel'):
        count = len(p.hand)
        if op == 'storm_of_steel':
            push(p, ['silent_shivs', count, card.upgraded, False])
        discard_and_draw(p, tuple(p.hand), draw=count if op == 'gamble' else 0)
    elif op == 'anticipate':
        apply_power(p, 'dexterity', amount)
        apply_power(p, 'anticipate', amount)
    elif op == 'bullet_time':
        for other in p.hand:
            if not other.spec.x_cost:
                other.combat_state.free_this_turn = True
        apply_power(p, 'no_draw', 1)
    elif op == 'bouncing_flask':
        push(p, *[['silent_random_poison', 3] for _ in range(amount)])
    elif op == 'bubble_bubble':
        if target.is_alive and target.statuses.get('poison'):
            push(p, ['status', p.combat_enemies.index(target), 'poison', amount])
    elif op in ('area_poison', 'area_weak', 'area_shackles'):
        key = {'area_poison':'poison', 'area_weak':'weak', 'area_shackles':'dark_shackles'}[op]
        push(p, *[['status', i, key, amount] for i, e in enumerate(p.combat_enemies) if e.is_alive])
    elif op == 'expose':
        if target.is_alive:
            target.block = 0
            target.statuses.decrement('artifact', target.statuses.get('artifact'))
            push(p, ['status', p.combat_enemies.index(target), 'vulnerable', amount])
    elif op == 'malaise':
        amount = r.plays[card.instance_id]['x'] + int(card.upgraded)
        slot = p.combat_enemies.index(target)
        push(p, ['silent_strength_loss', slot, amount], ['status', slot, 'weak', amount])
    elif op == 'mirage':
        p.gain_block(sum(e.statuses.get('poison') for e in p.combat_enemies if e.is_alive), powered=True)
    elif op == 'dodge_and_roll':
        before = p.block
        p.gain_block(card.spec.block_gain, powered=True)
        apply_power(p, 'block_next_turn', p.block - before)
    elif op == 'expertise':
        push(p, ['draw', max(0, amount - len(p.hand)), False])
    elif op == 'escape_plan':
        # Capture the actual drawn instance at the draw command, before hooks.
        push(p, ['silent_escape_draw', card.instance_id, amount])
    elif op == 'cheaper':
        card.combat_state.combat_cost_change -= 1
    elif op == 'knife_trap':
        slot = p.combat_enemies.index(target)
        push(p, *[['silent_knife', c.instance_id, slot, card.upgraded] for c in p.deck.exhaust_pile if c.definition.definition_id == 'shiv'])
    elif op in ('shiv', 'the_hunt', 'echoing_slash'):
        from game.headless.potions.powers import begin_attack
        begin_attack(p, card)
        vigor = r.powers.pop('vigor', 0)
        if op == 'shiv':
            area = bool(r.powers.get('fan_of_knives'))
            slot = None if area else p.combat_enemies.index(target)
            push(p, ['attack', card.instance_id, slot, area, 'base', 0, 0, vigor])
        elif op == 'the_hunt':
            push(p, ['silent_hunt', card.instance_id, p.combat_enemies.index(target), vigor])
        else:
            r.plays[card.instance_id]['echo_kills'] = 0
            push(p, ['silent_echo', card.instance_id, 1, vigor, 0])
    else:
        raise ValueError(f'Unknown Silent operation: {op}')


def execute(p, op, args):
    from game.headless.powers.silent import poison, area_damage
    r = p.rules
    if op == "silent_outbreak_reset":
        r.auxiliaries["outbreak"] %= 3
        return
    if p.combat_is_ending:
        return
    if op == 'silent_shivs':
        shivs(p, args[0], upgraded=args[1], inky=args[2])
    elif op == 'silent_random_poison':
        living = [e for e in p.combat_enemies if e.is_alive]
        if living:
            poison(p, p.deck.target_rng.choice(living), args[0])
    elif op == 'silent_strength_loss':
        e = p.combat_enemies[args[0]]
        if e.is_alive:
            from game.headless.powers.necrobinder import lose_strength
            lose_strength(p, args[1], e)
    elif op == 'silent_knife':
        card = find(p, args[0])
        target = p.combat_enemies[args[1]]
        if card is not None and target.is_alive:
            if args[2] and card.upgrade_level + 1 < len(card.definition.levels):
                card.upgrade()
            start_play(p, card, target, auto=True)
    elif op == 'silent_hunt':
        card, target = find(p, args[0]), p.combat_enemies[args[1]]
        if target.is_alive:
            fatal = not target.statuses.get('minion') and not target.statuses.get('illusion')
            target.take_damage(card.spec.base_damage + card.combat_state.extra_damage + args[2], attacker_statuses=p.statuses, attacker_strength=p.strength)
            if fatal and not target.is_alive:
                r.extra_card_rewards += 1
    elif op == 'silent_echo':
        identity, remaining, vigor, previous_kills = args
        kills = r.plays[identity]["echo_kills"]
        remaining += kills - previous_kills
        if remaining:
            push(p, ['attack', identity, None, True, 'base', 0, 0, vigor], ['silent_echo', identity, remaining - 1, vigor, kills])
    elif op == 'silent_escape_draw':
        from game.headless.powers.colorless import ensure_draw
        if r.powers.get('no_draw') or not ensure_draw(p, [op, *args]):
            return
        drawn = p.deck.draw(1)
        if drawn:
            c = drawn[0]
            r.drawn_combat += 1
            r.drawn_turn += 1
            push(p, ['after_draw'], ['silent_draw_hook', False, c.instance_id], ['after_draw_card', c.instance_id], ['silent_escape_block', args[0], args[1], c.spec.kind in ('skill', 'block')])
            if r.powers.get('hellraiser') and c.definition.strike:
                push(p, ['autoplay', c.instance_id, False])
    elif op == 'silent_escape_block':
        if args[2]:
            p.gain_block(args[1], powered=True)
    else:
        from game.headless.powers.silent import execute as execute_power
        execute_power(p, op, args)

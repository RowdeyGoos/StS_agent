"""Necrobinder pile commands and source-owned choices."""

from dataclasses import dataclass
from game.headless.cards.operations import Attack, value
from game.headless.core.resolution import push, find, move_out
from game.headless.core import osty

CHOICE_OPS = frozenset(('cleanse', 'dredge', 'graveblast', 'sculpting_strike', 'seance', 'snap', 'transfigure'))


@dataclass(frozen=True, slots=True)
class Necro:
    operation: str
    amount: int = 0
    upgraded_amount: int | None = None

    @property
    def resolves_after_combat_end(self):
        return self.operation == 'scythe'

    def apply(self, card, p, target):
        if not p.combat_is_ending or self.resolves_after_combat_end:
            apply(self.operation, card, p, target, value(card, self.amount, self.upgraded_amount))


def choice_settings(p, operation):
    from game.headless.core.piles import stratagem_cards
    count = 1
    if operation in ('cleanse', 'seance'):
        cards = stratagem_cards(p)
    elif operation in ('dredge', 'graveblast'):
        cards = list(p.deck.discard_pile)
        if operation == 'dredge':
            count = min(3, max(0, 10 - len(p.hand)))
    else:
        cards = list(p.hand)
        if operation == 'sculpting_strike':
            cards = [c for c in cards if not c.spec.ethereal]
        elif operation == 'snap':
            cards = [c for c in cards if not c.spec.retain]
    return cards, count


def souls(p, count, *, upgraded=False, destination='draw_pile'):
    from game.headless.cards.colorless_effects import catalog
    from game.headless.core.piles import after_generated_entry
    # Allocate the whole batch before insertion hooks (Soul.Create).
    cards = [catalog(p).create('soul', upgrade_level=int(upgraded)) for _ in range(count)]
    for card in cards:
        p.deck._ensure_identity(card)
    for card in cards:
        pile = getattr(p.deck, destination)
        if destination == 'draw_pile':
            # Native index is top-first; the simulator stores top at the end.
            pile.insert(len(pile) - p.deck.rng.randrange(len(pile) + 1), card)
        else:
            (p.deck.discard_pile if destination == 'hand' and len(p.hand) >= 10 else pile).append(card)
        after_generated_entry(p, card)
    return cards


def apply(op, card, p, target, amount):
    from game.headless.powers.ironclad import apply_power
    r = p.rules
    if op in CHOICE_OPS:
        from game.headless.core.choices import begin
        cards, count = choice_settings(p, op)
        if count:
            begin(p, card.instance_id, cards, operation='nec_' + op, minimum=count, maximum=count)
    elif op == 'summon':
        osty.summon(p, amount)
    elif op == 'heal_osty':
        osty.heal(p, amount)
    elif op in ('souls', 'souls_up'):
        souls(p, amount, upgraded=op == 'souls_up' and card.upgraded)
    elif op == 'capture_spirit':
        push(p, ['nec_enemy_loss', p.combat_enemies.index(target), card.spec.base_damage, True, card.instance_id],
             ['nec_souls', card.instance_id, amount, False])
    elif op == 'dirge':
        x = r.plays[card.instance_id]['x']
        push(p, *[['nec_summon', amount, card.instance_id, None] for _ in range(x)], ['nec_souls', card.instance_id, x, card.upgraded])
    elif op in ('area_doom', 'area_weak'):
        push(p, *[['status', i, op.removeprefix('area_'), amount] for i, e in enumerate(p.combat_enemies) if e.is_alive])
    elif op == 'doom_kill':
        from game.headless.powers.necrobinder import doom_tasks
        push(p, *doom_tasks(p, source=card.instance_id))
    elif op == 'no_escape':
        push(p, ['status', p.combat_enemies.index(target), 'doom', amount + 5 * (target.statuses.get('doom') // 10)])
    elif op == 'deaths_door':
        push(p, *[['block', card.spec.block_gain, True] for _ in range(3 if r.doom_applied_turn else 1)])
    elif op == 'drain_power':
        cards = [c for c in p.deck.discard_pile if c.upgrade_level + 1 < len(c.definition.levels)]
        for chosen in p.deck.selection_rng.sample(cards, min(amount, len(cards))):
            chosen.upgrade()
    elif op == 'eidolon':
        original = tuple(p.hand)
        push(p, *[['exhaust', c.instance_id] for c in original],
             *([['nec_intangible']] if len(original) >= 9 else []))
    elif op == 'strength_loss':
        from game.headless.powers.necrobinder import lose_strength
        lose_strength(p, amount)
    elif op == 'enemy_strength_loss':
        push(p, ['silent_strength_loss', p.combat_enemies.index(target), amount])
    elif op == 'hang':
        push(p, ['status', p.combat_enemies.index(target), 'hang', min(max(2, target.statuses.get('hang')), 999999999 - target.statuses.get('hang'))])
    elif op == 'blight':
        from game.headless.potions.powers import begin_attack
        begin_attack(p, card)
        push(p, ['nec_blight', card.instance_id, p.combat_enemies.index(target), r.powers.pop('vigor', 0)])
    elif op == 'misery':
        # Capture before the attack, including dead-target debuffs for the spread.
        from game.headless.powers.necrobinder import copied_debuffs
        copied = copied_debuffs(target)
        r.plays[card.instance_id]['nec_misery'] = copied
        push(p, ['nec_spread', card.instance_id, p.combat_enemies.index(target)])
        Attack().apply(card, p, target)
    elif op == 'sacrifice':
        if osty.alive(p):
            block = 2 * r.osty['max_hp']
            osty.kill(p)
            push(p, ['block', block, True])
    elif op == 'severance':
        souls(p, 1)
        souls(p, 1, destination='discard_pile')
        souls(p, 1, destination='hand')
    elif op == 'scythe':
        card.permanent_damage += amount
        r.scythe_gains[card.instance_id] = r.scythe_gains.get(card.instance_id, 0) + amount
    elif op == 'clone_discard':
        from game.headless.cards.special import clone_to
        clone_to(p, card, 'discard_pile')
    else:
        raise ValueError(f'Unknown Necrobinder operation: {op}')


def selected(p, card, operation):
    from game.headless.cards.colorless_effects import catalog
    from game.headless.core.piles import after_generated_entry
    op = operation.removeprefix('nec_')
    if op == 'cleanse':
        push(p, ['exhaust', card.instance_id])
    elif op in ('dredge', 'graveblast'):
        move_out(p, card)
        (p.hand if len(p.hand) < 10 else p.deck.discard_pile).append(card)
    elif op == 'sculpting_strike':
        card.combat_state.ethereal_this_combat = True
    elif op == 'snap':
        card.combat_state.retain_this_combat = True
    elif op == 'transfigure':
        from game.headless.powers.ironclad import local_cost
        if not card.spec.x_cost and local_cost(card) >= 0:
            card.combat_state.combat_cost_change += 1
        card.combat_state.replay_count += 1
    elif op == 'seance':
        pile = p.deck.draw_pile
        replacement = catalog(p).create('soul')
        p.deck._ensure_identity(replacement)
        pile[pile.index(card)] = replacement
        after_generated_entry(p, replacement, generated=False)
    else:
        raise ValueError('Unknown Necrobinder selection.')


def execute(p, op, args):
    # Earned summon hooks still update pet maximum HP during ending.
    if p.combat_is_ending and op not in ('nec_summon', 'nec_doom_after'):
        return
    if op == 'nec_souls':
        souls(p, args[1], upgraded=args[2])
    elif op == 'nec_intangible':
        from game.headless.powers.ironclad import apply_power
        apply_power(p, 'intangible', 1)
    elif op == 'nec_blight':
        from game.headless.cards.colorless_effects import hit
        card, target = find(p, args[0]), p.combat_enemies[args[1]]
        if target.is_alive:
            total = hit(p, card, target, extra=args[2])
            push(p, ['status', args[1], 'doom', total])
    elif op == 'nec_copy_debuff':
        from game.headless.powers.necrobinder import TEMP_STRENGTH
        enemy, name, amount = p.combat_enemies[args[0]], args[1], args[2]
        if enemy.is_alive:
            before = enemy.statuses.get(name)
            enemy.apply_status(name, amount, source=p, temporary_copy=True)
            if name in TEMP_STRENGTH:
                enemy.strength += enemy.statuses.get(name) - before
    elif op == 'nec_spread':
        copied = p.rules.plays[args[0]]['nec_misery']
        tasks = []
        for i, e in enumerate(p.combat_enemies):
            if i == args[1] or not e.is_alive:
                continue
            for name, amount in copied.items():
                tasks.append(['silent_strength_loss', i, -amount] if name == 'strength' else ['nec_copy_debuff', i, name, amount])
        push(p, *tasks)
    else:
        from game.headless.powers.necrobinder import execute as execute_power
        execute_power(p, op, args)

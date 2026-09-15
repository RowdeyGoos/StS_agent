"""Regent commands using owned resources, card instances and resumable choices."""

from dataclasses import dataclass
from game.headless.cards.operations import Attack, value
from game.headless.core.resolution import push, find, move_out


@dataclass(frozen=True, slots=True)
class Regent:
    operation: str
    amount: int = 0
    upgraded_amount: int | None = None

    def apply(self, card, p, target):
        if not p.combat_is_ending:
            apply(self.operation, card, p, target, value(card, self.amount, self.upgraded_amount))


def colorless(p, count, *, upgraded=False, offered=False):
    from game.headless.cards.colorless_effects import pool, create
    from game.headless.generation.combat import select_cards
    return [create(p, d, upgraded=upgraded, destination='offered' if offered else 'hand')
            for d in select_cards(pool(p, 'colorless'), p.deck.generation_rng, count, distinct=True)]


def is_colorless(card):
    # Native event/token pools are colorless; statuses and curses are not.
    return card.definition.pool in ('colorless', 'token', 'event')


def choice_settings(p, operation):
    from game.headless.core.piles import stratagem_cards
    if operation == 'charge':
        return stratagem_cards(p), 2, 2
    if operation == 'cosmic_indifference':
        return list(p.deck.discard_pile), 1, 1
    cards = list(p.hand)
    if operation == 'decisions_decisions':
        cards = [c for c in cards if c.spec.kind in ('skill', 'block') and c.cost >= 0]
    elif operation == 'heirloom_hammer':
        cards = [c for c in cards if is_colorless(c)]
    return cards, 0 if operation == 'guards' else 1, len(cards) if operation == 'guards' else 1


def choose(p, card, operation):
    from game.headless.core.choices import begin
    cards, minimum, maximum = choice_settings(p, operation)
    suffix = '_up' if card.upgraded and operation in ('begone', 'charge', 'guards') else ''
    begin(p, card.instance_id, cards, operation='regent_' + operation + suffix,
          minimum=minimum, maximum=maximum)


def forge(p, amount):
    from game.headless.cards.colorless_effects import create, catalog
    blades = [c for c in p.deck.all_cards() if c.definition.definition_id == 'sovereign_blade' and c not in p.deck.offered]
    if not any(c not in p.deck.exhaust_pile for c in blades):
        blades.append(create(p, catalog(p).definition('sovereign_blade')))
    for blade in blades:
        blade.combat_state.extra_damage += amount


def apply(op, card, p, target, amount):
    from game.headless.powers.ironclad import apply_power
    from game.headless.powers.regent import gain_stars
    from game.headless.cards.colorless_effects import create, catalog
    r = p.rules
    if op == 'stars':
        gain_stars(p, amount)
    elif op == 'forge':
        forge(p, amount)
    elif op in ('begone', 'charge', 'guards', 'topdeck', 'cosmic_indifference', 'heirloom_hammer', 'decisions_decisions'):
        choose(p, card, op)
    elif op in ('colorless', 'manifest_authority'):
        colorless(p, amount if op == 'colorless' else 1, upgraded=op == 'manifest_authority' and card.upgraded)
    elif op == 'quasar':
        from game.headless.core.choices import begin
        offers = colorless(p, 3, upgraded=card.upgraded, offered=True)
        begin(p, card.instance_id, offers, operation='regent_quasar', minimum=0)
    elif op in ('debris', 'fill_debris'):
        for _ in range(amount if op == 'debris' else max(0, 10 - len(p.hand))):
            create(p, catalog(p).definition('debris'))
    elif op in ('area_shackles', 'area_strength_loss'):
        push(p, *[[('status' if op == 'area_shackles' else 'silent_strength_loss'), i,
                   *([card.definition.definition_id, amount] if op == 'area_shackles' else [amount])]
                  for i, e in enumerate(p.combat_enemies) if e.is_alive])
    elif op in ('return_hand', 'return_top'):
        frame = r.plays[card.instance_id]
        if frame['destination'] == 'discard_pile':
            frame['destination'] = 'hand' if op == 'return_hand' else 'draw_pile'
    elif op == 'summon_forth':
        for blade in tuple(p.deck.all_cards()):
            if blade.definition.definition_id == 'sovereign_blade' and blade not in p.hand and blade not in p.deck.in_play:
                move_out(p, blade)
                (p.hand if len(p.hand) < 10 else p.deck.discard_pile).append(blade)
    elif op == 'glitterstream':
        next_block = p.block_amount(amount, powered=True)
        p.gain_block(card.spec.block_gain, powered=True)
        apply_power(p, 'block_next_turn', next_block)
    elif op == 'blade':
        Attack(all_enemies=bool(r.powers.get('seeking_edge'))).apply(card, p, target)
    elif op == 'parry':
        if r.powers.get('parry'):
            p.gain_block(r.powers['parry'], powered=True)
    elif op == 'stardust':
        from game.headless.potions.powers import begin_attack
        begin_attack(p, card)
        vigor = r.powers.pop('vigor', 0)
        push(p, *[['random_hit', card.instance_id, vigor] for _ in range(r.plays[card.instance_id]['star_value'])])
    elif op in ('beat_into_shape', 'knockout_blow'):
        slot = p.combat_enemies.index(target)
        if op == 'beat_into_shape':
            # Freeze prior hit history before this attack creates its own result.
            captured = amount * (1 + r.regent_hits.get(str(slot), 0))
            r.plays[card.instance_id]['forge_amount'] = captured
            push(p, ['regent_forge', card.instance_id, captured])
            Attack().apply(card, p, target)
        else:
            from game.headless.potions.powers import begin_attack
            begin_attack(p, card)
            vigor = r.powers.pop('vigor', 0)
            push(p, ['regent_knockout', card.instance_id, slot, vigor, amount])
    elif op == 'end_turn':
        r.regent_end_requested = True
    else:
        raise ValueError(f'Unknown Regent operation: {op}')


def selected(p, card, operation):
    from game.headless.cards.colorless_effects import catalog
    from game.headless.core.piles import after_generated_entry
    from game.headless.cards.special import clone_to
    op = operation.removeprefix('regent_')
    upgraded = op.endswith('_up')
    op = op.removesuffix('_up')
    if op in ('begone', 'charge', 'guards'):
        identity = {'begone':'minion_strike', 'charge':'minion_dive_bomb', 'guards':'minion_sacrifice'}[op]
        for name in ('hand', 'draw_pile', 'discard_pile', 'exhaust_pile'):
            pile = getattr(p.deck, name)
            if card in pile:
                replacement = catalog(p).create(identity, upgrade_level=int(upgraded))
                p.deck._ensure_identity(replacement)
                pile[pile.index(card)] = replacement
                # Transform creates/enters a card, but is not a generated-card event.
                after_generated_entry(p, replacement, generated=False)
                return
        raise ValueError('Minion transform requires an owned pile.')
    elif op == 'heirloom_hammer':
        clone_to(p, card, 'hand')
    elif op == 'decisions_decisions':
        push(p, *[['autoplay', card.instance_id, False] for _ in range(3)])
    elif op in ('topdeck', 'cosmic_indifference', 'foregone_conclusion', 'quasar'):
        offered = card in p.deck.offered
        move_out(p, card)
        destination = p.deck.draw_pile if op in ('topdeck', 'cosmic_indifference') else (p.hand if len(p.hand) < 10 else p.deck.discard_pile)
        destination.append(card)
        if offered:
            after_generated_entry(p, card)
    elif op == 'tyranny':
        push(p, ['exhaust', card.instance_id])
    else:
        raise ValueError('Unknown Regent selection.')


def execute(p, op, args):
    if p.combat_is_ending:
        return
    if op == 'regent_forge':
        forge(p, args[1])
    elif op == 'regent_knockout':
        from game.headless.powers.regent import gain_stars
        card, target = find(p, args[0]), p.combat_enemies[args[1]]
        if target.is_alive:
            target.take_damage(card.spec.base_damage + card.combat_state.extra_damage + args[2], attacker_statuses=p.statuses, attacker_strength=p.strength)
            if not target.is_alive:
                gain_stars(p, args[3])
    else:
        from game.headless.powers.regent import execute as execute_power
        execute_power(p, op, args)

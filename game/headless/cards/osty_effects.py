"""Osty attack commands keep the pet dealer separate from the card owner."""

from dataclasses import dataclass
from game.headless.core import osty
from game.headless.core.resolution import push, find


@dataclass(frozen=True, slots=True)
class OstyAttack:
    expression: str = 'base'
    hits: str = 'one'
    all_enemies: bool = False
    random: bool = False
    after: str = ''

    def damage(self, p, card):
        amount = card.spec.base_damage + card.combat_state.extra_damage
        if self.expression == 'protector':
            amount += p.rules.osty['max_hp'] if osty.alive(p) else 0
        elif self.expression == 'unleash':
            amount += p.rules.osty['hp'] if osty.alive(p) else 0
        elif self.expression == 'squeeze':
            amount += (6 if card.upgraded else 5) * sum(
                is_osty_attack(c) for c in p.deck.all_cards() if c is not card and c not in p.deck.offered)
        return amount

    def apply(self, card, p, target):
        if not osty.alive(p) or p.combat_is_ending:
            return
        from game.headless.potions.powers import begin_attack
        begin_attack(p, card)
        hits = 1 + p.rules.osty_attacks_turn if self.hits == 'rattle' else 1
        slot = None if target is None else p.combat_enemies.index(target)
        # Freeze expressions once per command, before a multihit's summon hooks.
        amount = self.damage(p, card)
        from game.headless.core.enemy_lifecycle import attack_boundary
        push(p, *attack_boundary(p, card, before=True), *[['osty_hit', card.instance_id, slot, self.all_enemies, self.random, amount] for _ in range(hits)],
             *attack_boundary(p, card, before=False), ['osty_after', card.instance_id, self.after])


def is_osty_attack(card):
    return any(isinstance(effect, OstyAttack) for effect in card.definition.effects)


def execute(p, op, args):
    if p.combat_is_ending:
        return
    card = find(p, args[0])
    if op == 'osty_hit':
        _, slot, area, random, amount = args
        if area:
            push(p, *[['osty_hit', card.instance_id, i, False, False, amount] for i, e in enumerate(p.combat_enemies) if e.is_alive])
            return
        if random:
            slots = [i for i, e in enumerate(p.combat_enemies) if e.is_alive]
            slot = p.deck.target_rng.choice(slots) if slots else None
        if slot is not None and p.combat_enemies[slot].is_alive:
            p.combat_enemies[slot].take_damage(amount, pet=True)
    elif op == 'osty_after':
        osty.after_attack(p)
        if args[1] == 'bone_shards':
            # Block precedes sacrifice; its hooks may themselves change combat.
            push(p, ['block', card.spec.block_gain, True], ['nec_kill_osty'])
        elif args[1] == 'fetch' and card.instance_id not in p.rules.fetch_plays:
            push(p, ['draw', 1, False])
        elif args[1] == 'high_five':
            push(p, *[['status', i, 'vulnerable', 3 if card.upgraded else 2] for i, e in enumerate(p.combat_enemies) if e.is_alive])
    else:
        raise ValueError('Unknown Osty command.')

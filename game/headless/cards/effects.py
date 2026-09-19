"""Implemented reusable card operations, in authored execution order."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DealDamage:
    def apply(self, card, player, target) -> None:
        if target is None:
            raise ValueError("Damage requires a target.")
        from game.headless.cards.operations import Attack
        Attack(expression='block' if card.spec.damage_equals_player_block else 'base',
               factor=1 if card.spec.damage_equals_player_block else 0).apply(card, player, target)



@dataclass(frozen=True, slots=True)
class GainBlock:
    def apply(self, card, player, target) -> None:
        if not player.combat_is_ending:
            player.gain_block(card.spec.block_gain, powered=True)


@dataclass(frozen=True, slots=True)
class DrawCards:
    def apply(self, card, player, target) -> None:
        player.draw_cards(card.spec.draw_count)


@dataclass(frozen=True, slots=True)
class ApplyTargetStatus:
    def apply(self, card, player, target) -> None:
        if target is None or card.spec.applies_status_name is None:
            raise ValueError("Status application requires its target and status rule.")
        if target.is_alive and not player.combat_is_ending:
            target.apply_status(card.spec.applies_status_name, card.spec.applies_status_stacks, source=player)


@dataclass(frozen=True, slots=True)
class SelectHandCard:
    """Select and modify hand instances; the resolving card is in its own pile."""

    operation: str
    mode: str = "choose"
    upgraded_mode: str = "choose"

    def __post_init__(self):
        if self.operation not in ("upgrade", "exhaust") or any(
            m not in ("choose", "random", "all") for m in (self.mode, self.upgraded_mode)
        ):
            raise ValueError("Unsupported hand selection rule.")

    def mode_for(self, card):
        return self.upgraded_mode if card.upgraded else self.mode

    def eligible(self, player):
        return tuple(c for c in player.hand if self.operation != "upgrade" or
                     c.upgrade_level + 1 < len(c.definition.levels))

    def resolve(self, player, selected):
        if self.operation == "upgrade":
            selected.upgrade()
        else:
            player.hand.remove(selected)
            player.deck.exhaust_card(selected)

    def apply(self, card, player, target):
        from game.headless.core.selection import HandChoice
        if player.combat_is_ending:
            return None
        eligible = self.eligible(player)
        if not eligible:
            return None
        mode = self.mode_for(card)
        if mode == "choose" and len(eligible) > 1:
            return HandChoice(tuple(c.instance_id for c in eligible))
        selected = (player.deck.selection_rng.choice(eligible),) if mode == "random" else (
            eligible if mode == "all" else eligible[:1]
        )
        for candidate in selected:
            self.resolve(player, candidate)
        return None


@dataclass(frozen=True, slots=True)
class ApplyDebuffs:
    names: tuple[str, ...]
    all_enemies: bool = False

    def apply(self, card, player, target):
        if player.combat_is_ending:
            return
        targets = player.combat_enemies if self.all_enemies else (target,)
        if targets is None:
            raise ValueError("Area effects require an owning combat.")
        from game.headless.core.resolution import push
        push(player, *[['status', player.combat_enemies.index(enemy), name, card.spec.applies_status_stacks]
                      for enemy in targets if enemy is not None and enemy.is_alive for name in self.names])


@dataclass(frozen=True, slots=True)
class LoseHp:
    amount: int

    def apply(self, card, player, target):
        if not player.combat_is_ending:
            from game.headless.cards.special import apply_operation
            apply_operation('hp_loss', card, player, target, self.amount)


@dataclass(frozen=True, slots=True)
class GainEnergy:
    amount: int

    def apply(self, card, player, target):
        if not player.combat_is_ending:
            player.gain_energy(self.amount)


@dataclass(frozen=True, slots=True)
class ExhaustHandAttack:
    def apply(self, card, player, target):
        if target is None:
            raise ValueError("Attack requires a target.")
        if player.combat_is_ending:
            return
        from game.headless.cards.special import apply_operation
        apply_operation('fiend_fire', card, player, target, 0)



@dataclass(frozen=True, slots=True)
class RandomEnemyAttack:
    hits: int
    upgraded_hits: int

    def apply(self, card, player, target):
        if player.combat_enemies is None:
            raise ValueError("Random attacks require an owning combat.")
        from game.headless.potions.powers import begin_attack
        begin_attack(player, card)
        vigor = player.rules.powers.pop("vigor", 0)
        from game.headless.core.enemy_lifecycle import attack_boundary
        from game.headless.core.resolution import push
        push(player, *attack_boundary(player, card, before=True), *[['random_hit', card.instance_id, vigor] for _ in range(self.upgraded_hits if card.upgraded else self.hits)], *attack_boundary(player, card, before=False))

"""Reusable card effects for powers, damage expressions and pile operations."""

from dataclasses import dataclass
from game.headless.core.selection import HandChoice


def value(card, base, upgraded):
    return upgraded if card.upgraded and upgraded is not None else base


@dataclass(frozen=True, slots=True)
class Attack:
    hits: int = 1
    upgraded_hits: int | None = None
    all_enemies: bool = False
    expression: str = "base"
    factor: int = 0
    upgraded_factor: int | None = None
    hit_expression: str = "fixed"
    fatal_max_hp: int = 0
    upgraded_max_hp: int | None = None

    def damage(self, card, player, target):
        extra = value(card, self.factor, self.upgraded_factor)
        n = {
            "base": 0,
            "turn_draws": player.rules.drawn_turn,
            "doom": 0 if target is None else target.statuses.get('doom'),
            "exhausted_souls": sum(c.definition.definition_id == 'soul' for c in player.deck.exhaust_pile),
            "exhaust": len(player.deck.exhaust_pile),
            "vulnerable": 0 if target is None else target.statuses.get("vulnerable"),
            "strikes": sum(c.definition.strike for c in player.deck.all_cards()),
            "block": player.block,
            "plays": player.rules.plays_finished,
            "draw_pile": len(player.deck.draw_pile),
            "discards": player.rules.discarded_turn,
            "draws": player.rules.drawn_combat,
            "precise": 0,
            "star_cards": sum(c.spec.star_cost >= 0 or c.spec.star_x for c in player.deck.all_cards() if c not in player.deck.offered),
            "generated": player.rules.generated_combat,
            "debuffs": (
                sum(
                    target.statuses.get(n) > 0
                    for n in (
                        "weak",
                        "vulnerable",
                        "frail",
                        "slow",
                        "constrict",
                        "tangled",
                        "ringing",
                        "shrink",
                        "demise", "conqueror", "doom", "debilitate", "hang", "oblivion", "sic_em",
                    )
                ) + int(target.strength - sum(target.statuses.get(k) for k in ("mangle", "dark_shackles", "crush_under", "dying_star", "monarchs_gaze_strength_down", "enfeebling_touch")) < 0)
                if target is not None
                else 0
            ),
        }[self.expression]
        amount = card.spec.base_damage + card.combat_state.extra_damage + extra * n
        return max(0, amount - 2 * len(player.hand)) if self.expression == "precise" else amount

    def apply(self, card, player, target):
        from game.headless.core.resolution import push

        hits = value(card, self.hits, self.upgraded_hits)
        if self.hit_expression == "vulnerable":
            hits = 2 if target and target.statuses.get("vulnerable") else 1
        elif self.hit_expression == "hp_loss":
            hits = 1 + player.rules.hp_loss_events
        elif self.hit_expression == "spite":
            hits = hits if player.rules.hp_lost_this_turn else 1
        elif self.hit_expression == "attacks_finished":
            hits = player.rules.attacks_finished
        elif self.hit_expression == "hand_skills":
            hits = sum(c.spec.kind in ("skill", "block") for c in player.hand)
        elif self.hit_expression == "skills_finished":
            hits = player.rules.skills_finished
        elif self.hit_expression == "orbs":
            hits = len(player.rules.orb_order)
        elif self.hit_expression == "spent_energy":
            hits = max(0, player.rules.energy_spent_turn - player.card_cost(card))
        elif self.hit_expression == "ethereal_plays":
            hits = player.rules.ethereal_plays
        elif self.hit_expression == "stars_gained":
            hits = player.rules.stars_gained_turn
        elif self.hit_expression == "heavenly_drill":
            x = player.rules.plays[card.instance_id]["x"]
            hits = x * (2 if x >= 4 else 1)
        elif self.hit_expression == "x":
            hits = player.rules.plays[card.instance_id]["x"]
        elif self.hit_expression == "pacts_end" and len(player.deck.exhaust_pile) < 3:
            return
        slot = None if self.all_enemies or target is None else player.combat_enemies.index(target)
        from game.headless.potions.powers import begin_attack
        begin_attack(player, card)
        vigor = player.rules.powers.pop("vigor", 0)
        from game.headless.core.enemy_lifecycle import attack_boundary
        push(
            player,
            *attack_boundary(player, card, before=True),
            *[
                [
                    "attack",
                    card.instance_id,
                    slot,
                    self.all_enemies,
                    self.expression,
                    value(card, self.factor, self.upgraded_factor),
                    value(card, self.fatal_max_hp, self.upgraded_max_hp),
                    vigor,
                ]
                for _ in range(hits)
            ],
            *attack_boundary(player, card, before=False),
        )


@dataclass(frozen=True, slots=True)
class Power:
    name: str
    amount: int = 1
    upgraded_amount: int | None = None
    target: bool = False

    def apply(self, card, player, target):
        from game.headless.powers.ironclad import apply_power

        if not player.combat_is_ending:
            amount = value(card, self.amount, self.upgraded_amount)
            if self.target:
                from game.headless.core.resolution import push

                push(player, ["status", player.combat_enemies.index(target), self.name, amount])
            else:
                apply_power(player, self.name, amount)


@dataclass(frozen=True, slots=True)
class ChoosePileCard:
    pile: str = "discard_pile"
    destination: str = "draw_pile"

    def eligible(self, player):
        return tuple(getattr(player.deck, self.pile))

    def mode_for(self, card):
        return "choose"

    def resolve(self, player, selected):
        getattr(player.deck, self.pile).remove(selected)
        destination = "discard_pile" if self.destination == "hand" and len(player.hand) >= 10 else self.destination
        getattr(player.deck, destination).append(selected)

    def apply(self, card, player, target):
        if player.combat_is_ending:
            return
        choices = self.eligible(player)
        if len(choices) > 1:
            return HandChoice(tuple(c.instance_id for c in choices))
        if choices:
            self.resolve(player, choices[0])


@dataclass(frozen=True, slots=True)
class CardOperation:
    """A named content operation; continuations are owned plain engine tasks."""

    operation: str
    amount: int = 0
    upgraded_amount: int | None = None

    def apply(self, card, player, target):
        from game.headless.cards.special import apply_operation

        apply_operation(self.operation, card, player, target, value(card, self.amount, self.upgraded_amount))

"""Colorless operations using shared owned piles, RNG streams and continuations."""

from dataclasses import dataclass
from game.headless.cards.operations import value
from game.headless.core.resolution import push, move_out
from game.headless.core.choices import begin


def catalog(p):
    from game.headless.cards.catalog import DEFAULT_CARDS

    return p.catalog or DEFAULT_CARDS


def pool(p, family="ironclad", kind=None):
    return sorted(
        (
            d
            for d in catalog(p).definitions
            if d.pool == family
            and d.rarity in ("common", "uncommon", "rare")
            and d.generate_in_combat
            and (kind is None or d.levels[0].kind == kind)
        ),
        key=lambda d: d.definition_id,
    )


def create(p, definition, *, upgraded=False, destination="hand"):
    card = catalog(p).create(definition.definition_id, upgrade_level=int(upgraded))
    p.deck._ensure_identity(card)
    if card.definition.definition_id == "stomp":
        card.combat_state.cost_change = -p.rules.attacks_finished
    if destination == "hand" and len(p.hand) >= 10:
        destination = "discard_pile"
    getattr(p.deck, destination).append(card)
    return card


def transform(p, card):
    family = card.definition.pool
    if card.spec.kind == "curse":
        choices = [d for d in catalog(p).definitions if d.levels[0].kind == "curse"]
    elif card.spec.kind == "status":
        choices = [d for d in catalog(p).definitions if d.levels[0].kind == "status"]
    else:
        choices = pool(
            p, "ironclad" if family == "ironclad" and card.definition.rarity != "ancient" else "colorless"
        )
    choices = [d for d in choices if d.definition_id != card.definition.definition_id]
    if not choices:
        return
    definition = p.deck.selection_rng.choice(choices)
    for name in ("hand", "draw_pile", "discard_pile", "exhaust_pile"):
        pile = getattr(p.deck, name)
        if card in pile:
            index = pile.index(card)
            replacement = catalog(p).create(definition.definition_id)
            p.deck._ensure_identity(replacement)
            pile[index] = replacement
            return


def hit(p, card, target, *, extra=0):
    from game.headless.powers.status import modify_attack_damage_for_statuses
    from game.headless.powers.damage import resolve_unblocked_damage

    amount = card.spec.base_damage + card.combat_state.extra_damage + extra
    incoming = modify_attack_damage_for_statuses(
        amount, target.statuses, p.statuses, p.strength, target._attack_multiplier(p.statuses)
    )
    blocked = min(target.block, incoming)
    # Damage-result totals include block and overkill, after flat HP caps.
    from copy import deepcopy

    total = blocked + resolve_unblocked_damage(deepcopy(target.statuses), incoming - blocked)
    target.take_damage(amount, attacker_statuses=p.statuses, attacker_strength=p.strength)
    return total


@dataclass(frozen=True, slots=True)
class ColorlessOperation:
    operation: str
    amount: int = 0
    upgraded_amount: int | None = None

    def apply(self, card, p, target):
        if p.combat_is_ending:
            return
        amount = value(card, self.amount, self.upgraded_amount)
        op = self.operation
        r = p.rules
        if op == "return":
            card.combat_state.return_next_turn = True
        elif op == "alchemize":
            potion = p.deck.potion_rng.choice(r.potion_pool)
            if r.potion_slots:
                r.potions_generated.append(potion)
                r.potion_slots -= 1
        elif op == "anointed":
            for other in tuple(p.deck.draw_pile):
                if other.definition.rarity == "rare":
                    move_out(p, other)
                    (p.hand if len(p.hand) < 10 else p.deck.discard_pile).append(other)
        elif op == "beat_down":
            choices = [
                c for c in p.deck.discard_pile if c.spec.kind == "attack" and (c.cost >= 0 or c.spec.x_cost)
            ]
            p.deck.rng.shuffle(choices)
            push(p, *[["autoplay", c.instance_id, False] for c in choices[:amount]])
        elif op == "catastrophe":
            push(p, ["catastrophe", amount])
        elif op in ("discovery", "splash"):
            choices = pool(p)
            if op == "splash":
                families = {
                    d.pool
                    for d in catalog(p).definitions
                    if d.rarity in ("common", "uncommon", "rare") and d.pool not in ("colorless", "special")
                }
                if len(families) > 1:
                    families.discard("ironclad")
                choices = [d for family in sorted(families) for d in pool(p, family, "attack")]
            offers = [
                create(p, d, upgraded=op == "splash" and card.upgraded, destination="offered")
                for d in p.deck.generation_rng.sample(choices, min(3, len(choices)))
            ]
            begin(
                p,
                card.instance_id,
                offers,
                minimum=0,
                free="free_until_played" if op == "discovery" else "free_this_turn",
            )
        elif op in ("fisticuffs", "omnislice", "hand_of_greed"):
            if target is None or not target.is_alive:
                return
            eligible = not target.statuses.get("minion") and not target.statuses.get("illusion")
            total = hit(p, card, target, extra=r.powers.pop("vigor", 0))
            if op == "hand_of_greed" and eligible and not target.is_alive and p.is_alive:
                r.gold_gained += amount
            elif op == "fisticuffs" and not p.combat_is_ending:
                p.gain_block(total, powered=True)
            elif op == "omnislice":
                for enemy in tuple(p.combat_enemies):
                    if enemy is not target and enemy.is_alive and not p.combat_is_ending:
                        enemy.take_damage(total, powered=False)
        elif op == "hidden_gem":
            choices = [
                c
                for c in p.deck.draw_pile
                if (c.cost >= 0 or c.spec.x_cost)
                and c.spec.kind not in ("curse", "quest")
                and not c.combat_state.replay_count
            ]
            preferred = [c for c in choices if c.spec.kind in ("attack", "skill", "block", "power")]
            if choices:
                p.deck.selection_rng.choice(preferred or choices).combat_state.replay_count += amount
        elif op == "impatience":
            if not any(c.spec.kind == "attack" for c in p.hand):
                push(p, ["draw", amount, False])
        elif op == "jack_of_all_trades":
            choices = [d for d in pool(p, "colorless") if d.definition_id != op]
            for definition in p.deck.generation_rng.sample(choices, min(amount, len(choices))):
                create(p, definition)
        elif op == "jackpot":
            choices = [d for d in pool(p) if d.levels[0].cost == 0 and not d.levels[0].x_cost]
            for _ in range(amount):
                create(p, p.deck.generation_rng.choice(choices), upgraded=card.upgraded)
        elif op == "prolong":
            from game.headless.powers.ironclad import apply_power

            apply_power(p, "block_next_turn", p.block)
        elif op == "purity":
            begin(p, card.instance_id, tuple(p.hand), operation="exhaust", minimum=0, maximum=amount)
        elif op == "restlessness":
            if not p.hand:
                push(p, ["draw", amount, False], ["energy", amount])
        elif op == "scrawl":
            push(p, ["draw", max(0, 10 - len(p.hand)), False])
        elif op in ("secret_technique", "secret_weapon", "seeker_strike", "thinking_ahead"):
            choices = list(p.hand if op == "thinking_ahead" else p.deck.draw_pile)
            if op == "secret_technique":
                choices = [c for c in choices if c.spec.kind in ("skill", "block")]
            elif op == "secret_weapon":
                choices = [c for c in choices if c.spec.kind == "attack"]
            elif op == "seeker_strike":
                p.deck.selection_rng.shuffle(choices)
                choices = choices[:3]
            begin(p, card.instance_id, choices, destination="draw_pile" if op == "thinking_ahead" else "hand")
        elif op == "shockwave":
            push(
                p,
                *[
                    ["status", i, name, amount]
                    for i, e in enumerate(p.combat_enemies)
                    if e.is_alive
                    for name in ("weak", "vulnerable")
                ],
            )
        elif op == "volley":
            vigor = r.powers.pop("vigor", 0)
            push(p, *[["random_hit", card.instance_id, vigor] for _ in range(r.plays[card.instance_id]["x"])])
        else:
            raise ValueError(f"Unknown colorless operation: {op}")

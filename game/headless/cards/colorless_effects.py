"""Colorless operations using shared owned piles, RNG streams and continuations."""

from dataclasses import dataclass
from game.headless.cards.operations import value
from game.headless.core.resolution import push, move_out
from game.headless.core.choices import begin
from game.headless.generation.combat import select_cards


def catalog(p):
    from game.headless.cards.catalog import DEFAULT_CARDS

    return p.catalog or DEFAULT_CARDS


def pool(p, family="ironclad", kind=None):
    from game.headless.generation.combat import card_pool
    return card_pool(catalog(p), family, kind)


def create(p, definition, *, upgraded=False, destination="hand"):
    card = catalog(p).create(definition.definition_id, upgrade_level=int(upgraded))
    p.deck._ensure_identity(card)
    if destination == "hand" and len(p.hand) >= 10:
        destination = "discard_pile"
    getattr(p.deck, destination).append(card)
    if destination != "offered":
        from game.headless.core.piles import after_generated_entry
        after_generated_entry(p, card)
    return card


def transform(p, card):
    from game.headless.generation.transforms import combat_options
    choices = combat_options(catalog(p), card)
    for name in ("hand", "draw_pile", "discard_pile", "exhaust_pile"):
        pile = getattr(p.deck, name)
        if card in pile:
            definition = p.deck.selection_rng.choice(choices)
            index = pile.index(card)
            replacement = catalog(p).create(definition.definition_id)
            p.deck._ensure_identity(replacement)
            pile[index] = replacement
            from game.headless.core.piles import after_generated_entry
            after_generated_entry(p, replacement, generated=False)
            return
    raise ValueError("Combat transformation requires an owned card in a combat pile.")


def hit(p, card, target, *, extra=0):
    from game.headless.powers.status import modify_attack_damage_for_statuses
    from game.headless.powers.damage import resolve_unblocked_damage

    amount = card.spec.base_damage + card.combat_state.extra_damage + extra
    incoming = target.damage_amount(amount, attacker_statuses=p.statuses, attacker_strength=p.strength)
    blocked = min(target.block, incoming)
    # Damage-result totals include block and overkill, after flat HP caps.
    from copy import deepcopy

    total = blocked + target.modify_unblocked_damage(resolve_unblocked_damage(deepcopy(target.statuses), incoming - blocked))
    frame = p.rules.plays.get(card.instance_id, {})
    tracks = 'enemy_attack' not in frame and any(e.TRACKS_CARD_ATTACKS for e in p.combat_enemies or ())
    if tracks:
        frame['enemy_attack'] = {}
    target.take_damage(amount, attacker_statuses=p.statuses, attacker_strength=p.strength)
    if tracks:
        from game.headless.core.enemy_lifecycle import finish_card_attack
        finish_card_attack(p, frame)
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
            from game.headless.potions.pools import generate
            potion = generate(r.potion_pool, p.deck.potion_rng, in_combat=True)
            from game.headless.relics.combat import has
            if r.potion_slots and not has(p, "sozu"):
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
                from game.headless.generation.foreign import splash_pool
                choices = splash_pool(catalog(p))
            offers = [
                create(p, d, upgraded=op == "splash" and card.upgraded, destination="offered")
                for d in select_cards(choices, p.deck.generation_rng, 3, distinct=True)
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
            from game.headless.potions.powers import begin_attack
            begin_attack(p, card)
            total = hit(p, card, target, extra=r.powers.pop("vigor", 0))
            if op == "hand_of_greed" and eligible and not target.is_alive and p.is_alive:
                from game.headless.relics.combat import gain_gold
                gain_gold(p, amount)
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
            for definition in select_cards(choices, p.deck.generation_rng, amount, distinct=True):
                create(p, definition)
        elif op == "jackpot":
            choices = [d for d in pool(p) if d.levels[0].cost == 0 and not d.levels[0].x_cost]
            for definition in select_cards(choices, p.deck.generation_rng, amount, distinct=False):
                create(p, definition, upgraded=card.upgraded)
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
                from game.headless.core.native_rng import NativeRng
                if isinstance(p.deck.selection_rng, NativeRng):
                    from game.headless.core.native_shuffle import stable_shuffle
                    choices.reverse()  # Native pile enumerates from the top.
                    stable_shuffle(choices, p.deck.selection_rng)
                else:
                    p.deck.selection_rng.shuffle(choices)
                whitelist = [c.instance_id for c in choices[:3]]
                from game.headless.core.piles import stratagem_cards
                choices = [c for c in stratagem_cards(p) if c.instance_id in whitelist]
                begin(p, card.instance_id, choices, whitelist=whitelist)
                return
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
            from game.headless.potions.powers import begin_attack
            begin_attack(p, card)
            vigor = r.powers.pop("vigor", 0)
            from game.headless.core.enemy_lifecycle import attack_tasks
            push(p, *attack_tasks(p, card, [["random_hit", card.instance_id, vigor] for _ in range(r.plays[card.instance_id]["x"])]))
        else:
            raise ValueError(f"Unknown colorless operation: {op}")

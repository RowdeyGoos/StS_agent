"""Resumable event operations shared by reward grids and deck selections.

Definitions own branches. A continuation stores a branch cursor and the current
owned selection; it never stores executable callbacks or a second run engine.
"""

from dataclasses import dataclass
from copy import deepcopy
from game.headless.core.snapshots import card_record, restore_card


@dataclass(frozen=True)
class StepEvent:
    definition_id: str
    branches: tuple
    uses_steps: bool = True

    def generate(self, rng, *, state, cards):
        from game.headless.events.act1_content import variables, offered_options

        values = variables(self.definition_id, rng, state)
        data = dict(
            choice=None,
            cursor=0,
            active=None,
            receipts=[],
            eligible=[],
            variables=values,
            options=offered_options(self, values, state),
            originals=[card_record(c) for c in state.deck],
        )
        from game.headless.events.checkpoint import capture

        data["checkpoint"] = capture(state, data)
        return data

    def options(self, pending):
        data = pending["data"]
        if pending["stage"] == "options":
            return tuple(data["options"])
        active = data["active"]
        if pending["stage"] == "card_rewards":
            return tuple(f"card_{i}" for i in range(len(active["offers"])) if i not in active["selected"]) + (
                ("skip",) if active["optional"] else ()
            )
        if pending["stage"] == "potion_rewards":
            return ("claim_potion_0", "skip")
        return ()

    def plan(self, data):
        from game.headless.events.act1_content import plan

        return plan(self, data)

    def choose(self, state, pending, option_id, *, cards):
        return atomic(state, cards, option_id=option_id)

    def select_card(self, state, pending, identity, *, cards):
        return atomic(state, cards, identity=identity)

    def validate(self, pending, *, state, cards, defeated=False):
        from game.headless.events.step_snapshots import validate

        validate(self, pending, state, cards, defeated=defeated)

    def is_allowed(self, conditions):
        from game.headless.events.act1_content import allowed

        return allowed(self.definition_id, conditions)


def atomic(state, cards, *, option_id=None, identity=None):
    trial = deepcopy(state)
    pending = trial.pending
    from game.headless.events.catalog import EVENTS

    definition = EVENTS[pending["definition_id"]]
    data = pending["data"]
    if identity is not None:
        select(trial, pending, cards, identity)
    elif pending["stage"] == "options":
        if option_id not in data["options"]:
            raise ValueError("Event option is unavailable.")
        data["choice"] = option_id
    else:
        reward(trial, pending, cards, option_id)
    drain(trial, cards)
    from game.headless.events.checkpoint import refresh

    refresh(trial)
    state.__dict__.clear()
    state.__dict__.update(trial.__dict__)


def eligible(state, mode, argument):
    from game.headless.enchantments.base import can_enchant

    return [
        c
        for c in state.deck
        if (mode == "remove" and not c.spec.eternal)
        or (mode == "transform_basic" and not c.spec.eternal and c.definition.rarity == "basic")
        or (
            mode == "enchant"
            and can_enchant(c, argument)
            and (argument != "sharp" or c.spec.kind == "attack")
            and (argument != "nimble" or c.spec.kind in ("skill", "block"))
            and (argument != "swift" or c.spec.kind == "power")
        )
    ]


def complete(data, operation, result=None):
    data["receipts"].append({"operation": list(operation), "result": result})
    data["cursor"] += 1
    data["active"] = None
    data["eligible"] = []


def drain(state, cards):
    pending = state.pending
    if not pending or pending.get("kind") != "scripted_event":
        return
    from game.headless.events.catalog import EVENTS

    definition = EVENTS[pending["definition_id"]]
    if not getattr(definition, "uses_steps", False) or pending["data"]["choice"] is None:
        return
    data = pending["data"]
    plan = definition.plan(data)
    while data["cursor"] < len(plan):
        if state.relic_work:
            pending["stage"] = "relic_work"
            return
        if data["active"] is not None:
            return
        operation = plan[data["cursor"]]
        op, *args = operation
        if not state.hp and op in ("select", "cards", "potion"):
            complete(data, operation, None)
            continue
        if op == "select":
            mode, count, argument, amount = args
            candidates = eligible(state, mode, argument)
            data["active"] = dict(
                candidates=[c.instance_id for c in candidates],
                selected=[],
                originals=[card_record(c) for c in state.deck],
                results=[],
                count=min(count, len(candidates)),
            )
            pending["stage"] = "select_card"
            data["eligible"] = [c.instance_id for c in candidates]
            if len(candidates) > count:
                return
            for c in candidates:
                select(state, pending, cards, c.instance_id)
            if not candidates:
                complete(data, operation, [])
            continue
        if op == "cards":
            family, rarity, kind, count, take, optional, upgrade = args
            from game.headless.relics.rewards import decorate, extend_pool

            pool = [
                d.definition_id
                for d in cards.definitions
                if d.pool == family
                and d.rarity in (("common", "uncommon", "rare") if rarity == "any" else (rarity,))
                and (kind == "any" or d.levels[0].kind == kind)
            ]
            # Rip and Future prohibit pool modification; Cheese/Share use their
            # ordinary card-factory pool hooks.
            if (
                definition.definition_id not in ("brain_leech", "the_future_of_potions")
                or data["choice"] == "share_knowledge"
            ):
                pool = extend_pool(state, cards, pool)
            state.rng.shuffle("event.card_reward", pool)
            offers = pool[:count]
            modifiers = decorate(state, cards, offers, upgrade_all=upgrade, card_reward=optional)
            data["active"] = dict(
                offers=offers,
                modifiers=modifiers,
                selected=[],
                results=[],
                count=min(take, len(offers)),
                optional=optional,
            )
            pending["stage"] = "card_rewards"
            if not offers:
                complete(data, operation, [])
                continue
            return
        if op == "potion":
            from game.headless.potions.pools import ORDINARY_POTIONS

            # Legends directly samples unlocked definitions uniformly, without
            # calling the rarity-based potion factory.
            name = state.rng.choice("event.legends_potion", ORDINARY_POTIONS)
            data["active"] = {"definition_id": name}
            pending["stage"] = "potion_rewards"
            return
        result = execute(state, cards, operation)
        if state.pending is None and not state.hp:
            state.pending = pending
        complete(data, operation, result)
    pending["stage"] = "relic_work" if state.relic_work else ("resolved" if state.hp else "defeated")


def execute(state, cards, operation):
    from game.headless.relics.run_rules import damage, gain_gold, heal, max_hp

    op, *args = operation
    if op == "damage":
        damage(state, args[0])
    elif op == "gold":
        gain_gold(state, args[0])
    elif op == "spend":
        if state.gold < args[0]:
            raise ValueError("Insufficient gold for event.")
        state.gold -= args[0]
    elif op == "heal":
        heal(state, args[0])
    elif op == "max_hp":
        max_hp(state, args[0])
    elif op == "card":
        if not state.hp:
            return None
        from game.headless.run.deck import add_card

        return card_record(add_card(state, cards.definition(args[0])))
    elif op == "relic":
        from game.headless.run.inventory import add_relic
        from game.headless.relics.pools import ORDINARY_RELICS

        name = args[0]
        if name == "random":
            owned = {r.definition_id for r in state.relics}
            pool = state.config.reward_relics if state.config else ORDINARY_RELICS
            name = state.rng.choice("event.relic", [n for n in pool if n not in owned] or ["circlet"])
        relic = add_relic(state, name, cards=cards, allow_dead=True)
        return {"definition_id": name, "instance_id": relic.instance_id}
    elif op == "discard_potion":
        from game.headless.run.inventory import discard_potion
        from dataclasses import asdict

        return asdict(discard_potion(state, args[0]))
    else:
        raise ValueError("Unknown event operation.")


def select(state, pending, cards, identity):
    from game.headless.events.catalog import EVENTS
    from game.headless.run.deck import find_card, remove_card, replace_card
    from game.headless.enchantments.base import enchant

    data = pending["data"]
    operation = EVENTS[pending["definition_id"]].plan(data)[data["cursor"]]
    _, mode, count, argument, amount = operation
    active = data["active"]
    if pending["stage"] != "select_card" or identity not in data["eligible"]:
        raise ValueError("Unavailable event card.")
    card = find_card(state, identity)
    if card not in eligible(state, mode, argument):
        raise ValueError("Ineligible event card.")
    result = None
    if mode == "remove":
        remove_card(state, identity)
    elif mode == "transform_basic":
        result = card_record(replace_card(state, identity, cards.definition(argument)))
    elif mode == "enchant":
        result = card_record(enchant(card, argument, amount))
    active["selected"].append(identity)
    active["results"].append(result)
    data["eligible"].remove(identity)
    if len(active["selected"]) == active["count"]:
        complete(data, operation, {"selected": active["selected"], "results": active["results"]})


def reward(state, pending, cards, option):
    from game.headless.events.catalog import EVENTS

    data = pending["data"]
    definition = EVENTS[pending["definition_id"]]
    if option not in definition.options(pending):
        raise ValueError("Unavailable event reward.")
    operation = definition.plan(data)[data["cursor"]]
    active = data["active"]
    if pending["stage"] == "potion_rewards":
        result = None
        if option != "skip":
            from game.headless.run.inventory import add_potion
            from dataclasses import asdict

            result = asdict(add_potion(state, active["definition_id"]))
        complete(data, operation, result)
    elif pending["stage"] == "card_rewards":
        if option == "skip":
            complete(data, operation, active["results"])
            return
        index = int(option.removeprefix("card_"))
        from game.headless.run.rewards import acquire_card

        card = acquire_card(state, cards, active["offers"][index], active["modifiers"])
        active["selected"].append(index)
        active["results"].append(card_record(card))
        if len(active["selected"]) == active["count"]:
            complete(data, operation, active["results"])
    else:
        raise ValueError("No event reward is pending.")

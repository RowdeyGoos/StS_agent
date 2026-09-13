"""Tablet's repeated maximum-HP costs and automatic permanent upgrades."""

from copy import deepcopy
from dataclasses import dataclass

from game.headless.run.deck import upgrade_card


@dataclass(frozen=True, slots=True)
class TabletOfTruth:
    definition_id: str = "tablet_of_truth"
    heal: int = 20
    costs: tuple[int, ...] = (3, 6, 12, 24)

    def generate(self, rng, *, state, cards):
        return {"count": 0, "initial_max_hp": state.max_hp, "initial_hp": state.hp,
                "initial_levels": {c.instance_id: c.upgrade_level for c in state.deck},
                "upgrades": [], "choice": None}

    def options(self, pending):
        if pending["stage"] != "options":
            return ()
        count = pending["data"]["count"]
        return (f"decipher_{count + 1}", "smash" if count == 0 else "give_up")

    def choose(self, state, pending, option_id, *, cards):
        data = pending["data"]
        if option_id == "smash":
            state.hp = min(state.max_hp, state.hp + self.heal)
            data["choice"], pending["stage"] = "smash", "resolved"
            return
        if option_id == "give_up":
            data["choice"], pending["stage"] = "give_up", "resolved"
            return
        # Prepare the entire repeated step before changing owned run state.
        trial = deepcopy(state)
        count = data["count"]
        cost = self.costs[count] if count < len(self.costs) else state.max_hp - 1
        killed = cost >= state.max_hp
        trial.max_hp = max(1, state.max_hp - cost)
        trial.hp = 0 if killed else min(state.hp, trial.max_hp)
        upgraded = []
        if not killed:
            eligible = [c for c in trial.deck if c.upgrade_level + 1 < len(c.definition.levels)]
            selected = eligible if count == 4 else ([trial.rng.choice("event.tablet_upgrade", eligible)] if eligible else [])
            for card in selected:
                upgrade_card(trial, card.instance_id)
                upgraded.append(card.instance_id)
        state.deck, state.rng = trial.deck, trial.rng
        state.max_hp, state.hp = trial.max_hp, trial.hp
        data["upgrades"].append(upgraded)
        data["count"] += 1
        data["choice"] = option_id
        if killed or data["count"] == 5:
            pending["stage"] = "resolved"

    def validate(self, pending, *, state, cards, defeated=False):
        data = pending["data"]
        if not isinstance(data, dict) or set(data) != {"count", "initial_max_hp", "initial_hp", "initial_levels", "upgrades", "choice"}:
            raise ValueError("Invalid Tablet state.")
        count, initial_max, initial_hp = data["count"], data["initial_max_hp"], data["initial_hp"]
        if (type(count) is not int or not 0 <= count <= 5
                or type(initial_max) is not int or initial_max <= 0
                or type(initial_hp) is not int or not 0 < initial_hp <= initial_max
                or not isinstance(data["upgrades"], list) or len(data["upgrades"]) != count
                or not isinstance(data["initial_levels"], dict)):
            raise ValueError("Invalid Tablet counters.")
        levels = dict(data["initial_levels"])
        deck = {c.instance_id: c for c in state.deck}
        if set(levels) != set(deck) or any(type(v) is not int or not 0 <= v < len(deck[k].definition.levels) for k,v in levels.items()):
            raise ValueError("Invalid Tablet initial deck.")
        max_hp, hp, killed = initial_max, initial_hp, False
        from types import SimpleNamespace
        from game.headless.events.potion_context import apply_at
        for index, upgraded in enumerate(data["upgrades"]):
            resources = SimpleNamespace(hp=hp, max_hp=max_hp, relics=[])
            apply_at(resources, state, pending, index)
            hp, max_hp = resources.hp, resources.max_hp
            if killed or not isinstance(upgraded, list) or any(not isinstance(i, str) for i in upgraded):
                raise ValueError("Invalid Tablet upgrade history.")
            cost = self.costs[index] if index < 4 else max_hp - 1
            killed = cost >= max_hp
            max_hp = max(1, max_hp - cost)
            hp = 0 if killed else min(hp, max_hp)
            eligible = [i for i in levels if levels[i] + 1 < len(deck[i].definition.levels)]
            expected = 0 if killed else len(eligible) if index == 4 else min(1, len(eligible))
            if len(upgraded) != expected or len(set(upgraded)) != len(upgraded) or any(i not in eligible for i in upgraded):
                raise ValueError("Invalid Tablet upgraded cards.")
            for identity in upgraded:
                levels[identity] += 1
        resources = SimpleNamespace(hp=hp, max_hp=max_hp, relics=[])
        apply_at(resources, state, pending, count)
        hp, max_hp = resources.hp, resources.max_hp
        choice = data["choice"]
        if choice == "smash":
            if count != 0: raise ValueError("Smash is only available initially.")
            hp = min(max_hp, hp + self.heal)
        elif choice == "give_up":
            if not 1 <= count < 5 or killed: raise ValueError("Invalid Tablet give-up.")
        elif choice != (None if count == 0 else f"decipher_{count}"):
            raise ValueError("Invalid Tablet choice.")
        resources = SimpleNamespace(hp=hp, max_hp=max_hp, relics=[])
        apply_at(resources, state, pending, 999)
        hp, max_hp = resources.hp, resources.max_hp
        resolved = choice in ("smash", "give_up") or count == 5 or killed
        if (pending["stage"] != ("resolved" if resolved else "options")
                or defeated != killed or state.max_hp != max_hp or state.hp != hp
                or any(c.upgrade_level != levels[i] for i,c in deck.items())):
            raise ValueError("Tablet result differs from its recorded effects.")

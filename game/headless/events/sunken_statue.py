"""Sunken Statue's persistent sword or gold-before-damage choice."""

from dataclasses import dataclass

from game.headless.run.inventory import add_relic


@dataclass(frozen=True, slots=True)
class SunkenStatue:
    definition_id: str = "sunken_statue"
    damage: int = 7

    def generate(self, rng, *, state, cards):
        return {"choice": None, "gold": rng.randint("event.statue_gold", 101, 121),
                "initial_gold": state.gold, "initial_hp": state.hp, "relic_id": None}

    def options(self, pending):
        return ("grab_sword", "dive_into_water") if pending["stage"] == "options" else ()

    def choose(self, state, pending, option_id, *, cards):
        data = pending["data"]
        if option_id == "grab_sword":
            relic = add_relic(state, "sword_of_stone")
            data["relic_id"] = relic.instance_id
        else:
            state.gold += data["gold"]
            state.hp = max(0, state.hp - self.damage)
        data["choice"] = option_id
        pending["stage"] = "resolved"

    def validate(self, pending, *, state, cards, defeated=False):
        data = pending["data"]
        if (not isinstance(data, dict) or set(data) != {"choice", "gold", "initial_gold", "initial_hp", "relic_id"}
                or type(data["gold"]) is not int or not 101 <= data["gold"] <= 121
                or type(data["initial_gold"]) is not int or data["initial_gold"] < 0
                or type(data["initial_hp"]) is not int or not 0 < data["initial_hp"] <= state.max_hp):
            raise ValueError("Invalid Sunken Statue state.")
        choice = data["choice"]
        dive = choice == "dive_into_water"
        if (choice not in (None, "grab_sword", "dive_into_water")
                or pending["stage"] != ("options" if choice is None else "resolved")
                or state.gold != data["initial_gold"] + (data["gold"] if dive else 0)
                or state.hp != max(0, data["initial_hp"] - (self.damage if dive else 0))
                or defeated != (state.hp == 0)):
            raise ValueError("Sunken Statue result differs from its choice.")
        if choice == "grab_sword":
            relic = next((r for r in state.relics if r.instance_id == data["relic_id"]), None)
            if relic is None or relic.definition_id != "sword_of_stone" or relic.counter:
                raise ValueError("Sunken Statue sword is not owned.")
        elif data["relic_id"] is not None:
            raise ValueError("Unclaimed sword has an item ID.")

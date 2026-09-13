"""Dense Vegetation: trudge for gold, or rest before a mandatory fight."""

from dataclasses import dataclass

from game.headless.events.combat import EventCombatRequest
from game.headless.run.rest_site import heal_amount


@dataclass(frozen=True, slots=True)
class DenseVegetation:
    definition_id: str = "dense_vegetation"
    combat_encounter_id: str = "dense_vegetation_event"
    damage: int = 8
    gold_range: tuple[int, int] = (61, 99)

    def generate(self, rng, *, state, cards):
        if state.config is None:
            raise ValueError("Dense Vegetation requires declared combat reward pools.")
        return {"choice": None, "gold": rng.randint("event.dense_gold", *self.gold_range),
                "initial_hp": state.hp, "initial_gold": state.gold, "heal": heal_amount(state)}

    def options(self, pending):
        return ("trudge_on", "rest") if pending["stage"] == "options" else ("fight",) if pending["stage"] == "fight" else ()

    def choose(self, state, pending, option_id, *, cards):
        if option_id == "fight":
            return EventCombatRequest(self.combat_encounter_id)
        data = pending["data"]
        data["choice"] = option_id
        if option_id == "trudge_on":
            from game.headless.relics.run_rules import damage
            damage(state, self.damage)
            from game.headless.relics.run_rules import gain_gold
            gain_gold(state, data["gold"])
            pending["stage"] = "resolved"
        else:
            state.hp += data["heal"]
            from game.headless.relics.run_rules import rest_rewards
            rest_rewards(state)
            pending["stage"] = "fight"

    def validate(self, pending, *, state, cards, defeated=False):
        data = pending["data"]
        if (state.config is None or not isinstance(data, dict) or set(data) != {"choice", "gold", "initial_hp", "initial_gold", "heal"}
                or type(data["gold"]) is not int or not self.gold_range[0] <= data["gold"] <= self.gold_range[1]
                or type(data["initial_hp"]) is not int or not 0 < data["initial_hp"] <= state.max_hp
                or type(data["initial_gold"]) is not int or data["initial_gold"] < 0
                or type(data["heal"]) is not int
                or data["heal"] != expected_heal(state, pending)):
            raise ValueError("Invalid Dense Vegetation data.")
        stage, choice = pending["stage"], data["choice"]
        if (stage, choice) not in (("options", None), ("fight", "rest"), ("resolved", "trudge_on")):
            raise ValueError("Invalid Dense Vegetation choice or stage.")
        from game.headless.events.resources import validate
        effects = [("damage", self.damage), ("gold", data["gold"])] if choice == "trudge_on" else [("heal", data["heal"]), ("rest_bonus", 0)] if choice == "rest" else []
        validate(state, pending, effects)
        if defeated != (state.hp == 0):
            raise ValueError("Dense Vegetation defeat differs from HP.")


def expected_heal(state, pending):
    from game.headless.events.resources import expected
    initial = expected(state, pending)
    return heal_amount(initial)

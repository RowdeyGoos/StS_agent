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
            state.hp = max(0, state.hp - self.damage)
            state.gold += data["gold"]
            pending["stage"] = "resolved"
        else:
            state.hp += data["heal"]
            pending["stage"] = "fight"

    def validate(self, pending, *, state, cards, defeated=False):
        data = pending["data"]
        if (state.config is None or not isinstance(data, dict) or set(data) != {"choice", "gold", "initial_hp", "initial_gold", "heal"}
                or type(data["gold"]) is not int or not self.gold_range[0] <= data["gold"] <= self.gold_range[1]
                or type(data["initial_hp"]) is not int or not 0 < data["initial_hp"] <= state.max_hp
                or type(data["initial_gold"]) is not int or data["initial_gold"] < 0
                or type(data["heal"]) is not int
                or data["heal"] != min(state.max_hp * 3 // 10, state.max_hp - data["initial_hp"])):
            raise ValueError("Invalid Dense Vegetation data.")
        stage, choice = pending["stage"], data["choice"]
        if (stage, choice) not in (("options", None), ("fight", "rest"), ("resolved", "trudge_on")):
            raise ValueError("Invalid Dense Vegetation choice or stage.")
        expected_hp = (max(0, data["initial_hp"] - self.damage) if choice == "trudge_on"
                       else data["initial_hp"] + (data["heal"] if choice == "rest" else 0))
        if (state.hp != expected_hp or defeated != (state.hp == 0)
                or state.gold != data["initial_gold"] + (data["gold"] if choice == "trudge_on" else 0)):
            raise ValueError("Dense Vegetation resources differ from its choice.")

"""Jungle Maze Adventure's single-player rules, verified against build 23811903."""

from dataclasses import dataclass

from game.headless.events.safe import apply_effect


@dataclass(frozen=True, slots=True)
class JungleMazeAdventure:
    definition_id: str = "jungle_maze_adventure"
    solo_damage: int = 18
    solo_gold_range: tuple[int, int] = (135, 164)
    join_gold_range: tuple[int, int] = (35, 64)

    def generate(self, rng, *, state=None, cards=None):
        # Native values are 150/50 + NextFloat(-15, 15), then truncated on gain.
        # Integer sampling of the resulting amounts is authored, not native RNG.
        return {"solo_gold": rng.randint("event.jungle_maze", *self.solo_gold_range),
                "join_gold": rng.randint("event.jungle_maze", *self.join_gold_range),
                "choice": None}

    def options(self, pending):
        return ("solo_quest", "join_forces") if pending["stage"] == "options" else ()

    def choose(self, state, pending, option_id, *, cards=None):
        data = pending["data"]
        if option_id == "solo_quest":
            apply_effect(state, "lose_hp", self.solo_damage)
            # Native awaits damage, then grants gold without an alive guard.
            apply_effect(state, "gain_gold", data["solo_gold"])
        else:
            apply_effect(state, "gain_gold", data["join_gold"])
        data["choice"] = option_id
        pending["stage"] = "resolved"

    def validate(self, pending, *, state=None, cards=None, defeated=False):
        data = pending["data"]
        if not isinstance(data, dict) or set(data) != {"solo_gold", "join_gold", "choice"}:
            raise ValueError("Invalid Jungle Maze event data.")
        for field, bounds in (("solo_gold", self.solo_gold_range), ("join_gold", self.join_gold_range)):
            if type(data[field]) is not int or not bounds[0] <= data[field] <= bounds[1]:
                raise ValueError("Invalid Jungle Maze gold offer.")
        if pending["stage"] == "options":
            if data["choice"] is not None:
                raise ValueError("Unresolved event already has a choice.")
        elif pending["stage"] != "resolved" or data["choice"] not in ("solo_quest", "join_forces"):
            raise ValueError("Invalid Jungle Maze completion.")
        if defeated and (pending["stage"] != "resolved" or data["choice"] != "solo_quest"):
            raise ValueError("Jungle Maze defeat requires its lethal branch.")

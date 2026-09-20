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
        if getattr(rng, "native", False):
            from game.headless.core.native_rng import single
            def gold(base):
                return int(base + single(single(-15) + single(rng.random("event.jungle_maze") * single(30))))
            return {"solo_gold": gold(150), "join_gold": gold(50), "choice": None}
        return {"solo_gold": rng.randint("event.jungle_maze", *self.solo_gold_range),
                "join_gold": rng.randint("event.jungle_maze", *self.join_gold_range),
                "choice": None}

    def options(self, pending):
        return ("solo_quest", "join_forces") if pending["stage"] == "options" else ()

    def choose(self, state, pending, option_id, *, cards=None):
        data = pending["data"]
        if option_id == "solo_quest":
            if getattr(state.rng, "native", False):
                # Native shuffles its three cosmetic effects on the event stream.
                state.rng.shuffle("event.jungle_maze", [0, 1, 2])
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

        if state is not None and 'resources' in pending:
            from game.headless.events.resources import validate
            effects = [('damage', self.solo_damage), ('gold', data['solo_gold'])] if data['choice'] == 'solo_quest' else [('gold', data['join_gold'])] if data['choice'] == 'join_forces' else []
            validate(state, pending, effects)

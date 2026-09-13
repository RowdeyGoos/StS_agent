"""Slippery Bridge's offered-card removal and escalating hold-on damage."""

from copy import deepcopy
from dataclasses import dataclass

from game.headless.core.snapshots import card_record, restore_card
from game.headless.run.deck import remove_card


@dataclass(frozen=True, slots=True)
class SlipperyBridge:
    definition_id: str = "slippery_bridge"
    initial_damage: int = 3
    basic_cards: tuple[str, ...] = ("strike", "defend", "bash")

    def is_allowed(self, conditions):
        return conditions.get("floor", 0) > 6 and conditions["transformable_cards"] > 0

    def candidates(self, originals, offers):
        if not offers:
            result = [r["instance_id"] for r in originals if r["definition_id"] not in self.basic_cards]
        else:
            previous = next(r["definition_id"] for r in originals if r["instance_id"] == offers[-1])
            result = [r["instance_id"] for r in originals if r["definition_id"] != previous and r["instance_id"] not in offers]
        return result or [r["instance_id"] for r in originals]

    def generate(self, rng, *, state, cards):
        if not state.deck:
            raise ValueError("Slippery Bridge requires a removable card.")
        originals = [card_record(c) for c in state.deck]
        offered = rng.choice("event.bridge_card", self.candidates(originals, []))
        return {"initial_hp": state.hp, "originals": originals, "offers": [offered], "choice": None}

    def options(self, pending):
        if pending["stage"] != "options":
            return ()
        count = len(pending["data"]["offers"]) - 1
        return (f"overcome_{count}", f"hold_on_{count}")

    def choose(self, state, pending, option_id, *, cards):
        data = pending["data"]
        if option_id.startswith("overcome_"):
            remove_card(state, data["offers"][-1])
            data["choice"] = "overcome"
            pending["stage"] = "resolved"
        else:
            rng = deepcopy(state.rng)
            next_card = rng.choice("event.bridge_card", self.candidates(data["originals"], data["offers"]))
            state.hp = max(0, state.hp - self.initial_damage - (len(data["offers"]) - 1))
            state.rng = rng
            data["offers"].append(next_card)
            data["choice"] = "hold_on"

    def validate(self, pending, *, state, cards, defeated=False):
        data = pending["data"]
        if (not isinstance(data, dict) or set(data) != {"initial_hp", "originals", "offers", "choice"}
                or type(data["initial_hp"]) is not int or not 0 < data["initial_hp"] <= state.max_hp
                or not isinstance(data["originals"], list) or not data["originals"]
                or not isinstance(data["offers"], list) or not data["offers"]):
            raise ValueError("Invalid Slippery Bridge state.")
        for record in data["originals"]:
            restore_card(record, cards)
        identities = [r["instance_id"] for r in data["originals"]]
        if len(identities) != len(set(identities)):
            raise ValueError("Duplicate Bridge original.")
        history, hp = [], data["initial_hp"]
        for index, offer in enumerate(data["offers"]):
            if hp <= 0 or offer not in self.candidates(data["originals"], history):
                raise ValueError("Invalid Bridge offered-card history.")
            if index:
                hp = max(0, hp - self.initial_damage - index + 1)
            history.append(offer)
        resolved = data["choice"] == "overcome"
        if (data["choice"] not in (None, "hold_on", "overcome")
                or data["choice"] is None and len(history) != 1
                or data["choice"] == "hold_on" and len(history) < 2
                or resolved and hp == 0
                or pending["stage"] != ("resolved" if resolved else "options")
                or state.hp != hp or defeated != (hp == 0)):
            raise ValueError("Invalid Bridge choice or HP.")
        expected = [r for r in data["originals"] if not resolved or r["instance_id"] != history[-1]]
        if expected != [card_record(c) for c in state.deck]:
            raise ValueError("Bridge removal differs from its offered card.")

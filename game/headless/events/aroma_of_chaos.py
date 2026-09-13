"""Aroma's mandatory one-card choices and permanent deck effects."""

from dataclasses import dataclass

from game.headless.events.transformation import TRANSFORM_POOL, check_content, transform, replacement_pool
from game.headless.run.deck import find_card, transform_card, upgrade_card


@dataclass(frozen=True, slots=True)
class AromaOfChaos:
    definition_id: str = "aroma_of_chaos"
    transform_pool: tuple[str, ...] = TRANSFORM_POOL

    def check_content(self, state, cards):
        check_content(state, cards, self.transform_pool)

    def generate(self, rng, *, state, cards):
        self.check_content(state, cards)
        return {"choice": None, "eligible": [], "selected_card_id": None, "result": None}

    def options(self, pending):
        return ("let_go", "maintain_control") if pending["stage"] == "options" else ()

    def eligible(self, state, choice):
        return tuple(c.instance_id for c in state.deck if choice == "let_go"
                     or c.upgrade_level + 1 < len(c.definition.levels))

    def choose(self, state, pending, option_id, *, cards):
        self.check_content(state, cards)
        eligible = self.eligible(state, option_id)
        if len(eligible) == 1:
            # Complete potentially failing operations before changing the parent.
            self._resolve(state, pending, option_id, eligible[0], cards)
        else:
            pending["data"]["choice"] = option_id
            pending["data"]["eligible"] = list(eligible)
            pending["stage"] = "select_card" if eligible else "resolved"

    def select_card(self, state, pending, instance_id, *, cards):
        choice = pending["data"]["choice"]
        self.check_content(state, cards)
        if instance_id not in pending["data"]["eligible"] or instance_id not in self.eligible(state, choice):
            raise ValueError("Card is not eligible for the event choice.")
        self._resolve(state, pending, choice, instance_id, cards)

    def _resolve(self, state, pending, choice, instance_id, cards):
        source = find_card(state, instance_id).definition.definition_id
        card = (transform(state, cards, instance_id, self.transform_pool, stream="event.aroma_transform")
                if choice == "let_go" else upgrade_card(state, instance_id))
        pending["data"] = {"choice": choice, "eligible": [], "selected_card_id": instance_id,
                           "result": {"instance_id": card.instance_id, "definition_id": card.definition.definition_id,
                                      "upgrade_level": card.upgrade_level, "source_definition": source}}
        pending["stage"] = "resolved"

    def validate(self, pending, *, state, cards, defeated=False):
        self.check_content(state, cards)
        data = pending["data"]
        if defeated or not isinstance(data, dict) or set(data) != {"choice", "eligible", "selected_card_id", "result"}:
            raise ValueError("Invalid Aroma state.")
        stage = pending["stage"]
        if stage == "options":
            if data != {"choice": None, "eligible": [], "selected_card_id": None, "result": None}:
                raise ValueError("Unresolved Aroma already has a choice.")
            return
        if data["choice"] not in ("let_go", "maintain_control"):
            raise ValueError("Unknown Aroma choice.")
        if stage == "select_card":
            if (data["eligible"] != list(self.eligible(state, data["choice"])) or len(data["eligible"]) < 2
                    or data["selected_card_id"] is not None or data["result"] is not None):
                raise ValueError("Invalid Aroma card selection.")
            return
        if stage != "resolved" or data["eligible"] != []:
            raise ValueError("Invalid Aroma stage.")
        if data["result"] is None:
            if data["selected_card_id"] is not None or self.eligible(state, data["choice"]):
                raise ValueError("Aroma empty selection has eligible cards.")
            return
        result = data["result"]
        if not isinstance(result, dict) or set(result) != {"instance_id", "definition_id", "upgrade_level", "source_definition"}:
            raise ValueError("Invalid Aroma result.")
        if not isinstance(result["source_definition"], str):
            raise ValueError("Invalid Aroma source definition.")
        cards.definition(result["source_definition"])
        card = find_card(state, result["instance_id"])
        if (type(result["upgrade_level"]) is not int or result["definition_id"] != card.definition.definition_id
                or result["upgrade_level"] != card.upgrade_level):
            raise ValueError("Aroma result differs from the master deck.")
        selected = data["selected_card_id"]
        if not isinstance(selected, str) or not selected:
            raise ValueError("Missing original Aroma card identity.")
        if data["choice"] == "maintain_control":
            if selected != card.instance_id or card.upgrade_level < 1 or result["source_definition"] != card.definition.definition_id:
                raise ValueError("Invalid Aroma upgrade result.")
        elif card.upgrade_level != 0 or card.combats_seen != 0 or card.enchantment is not None or card.definition.definition_id not in replacement_pool(result["source_definition"], self.transform_pool) or card.definition.definition_id == result["source_definition"] or any(c.instance_id == selected for c in state.deck):
            raise ValueError("Invalid Aroma transformation result.")

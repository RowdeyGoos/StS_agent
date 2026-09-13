"""Morphic Grove: gain maximum HP or spend all gold to transform two cards."""

from copy import deepcopy
from dataclasses import dataclass

from game.headless.events.transformation import TRANSFORM_POOL, CURSE_POOL, check_content, replacement_pool
from game.headless.run.deck import transform_card


@dataclass(frozen=True, slots=True)
class MorphicGrove:
    definition_id: str = "morphic_grove"
    max_hp_gain: int = 5
    minimum_gold: int = 100
    card_count: int = 2
    transform_pool: tuple[str, ...] = TRANSFORM_POOL

    def is_allowed(self, conditions):
        return conditions["gold"] >= self.minimum_gold and conditions["transformable_cards"] >= self.card_count

    def generate(self, rng, *, state, cards):
        check_content(state, cards, self.transform_pool)
        return {"choice": None, "eligible": [], "selected": [], "results": [],
                "initial_gold": state.gold, "initial_hp": state.hp, "initial_max_hp": state.max_hp,
                "original_ids": [c.instance_id for c in state.deck],
                "original_definitions": {c.instance_id: c.definition.definition_id for c in state.deck}}

    def options(self, pending):
        return ("group", "loner") if pending["stage"] == "options" else ()

    def choose(self, state, pending, option_id, *, cards):
        check_content(state, cards, self.transform_pool)
        if option_id == "loner":
            state.max_hp += self.max_hp_gain
            state.hp += self.max_hp_gain
            pending["data"]["choice"], pending["stage"] = "loner", "resolved"
            return
        eligible = [c.instance_id for c in state.deck]
        if len(eligible) <= self.card_count:
            self._resolve(state, pending, eligible, cards)
        else:
            state.gold = 0
            pending["data"]["choice"] = "group"
            pending["data"]["eligible"] = eligible
            pending["stage"] = "select_card"

    def select_card(self, state, pending, instance_id, *, cards):
        data = pending["data"]
        if instance_id not in data["eligible"]:
            raise ValueError("Card is unavailable for Morphic Grove.")
        selected = [*data["selected"], instance_id]
        if len(selected) == self.card_count:
            self._resolve(state, pending, selected, cards)
        else:
            data["selected"] = selected
            data["eligible"].remove(instance_id)

    def _resolve(self, state, pending, selected, cards):
        check_content(state, cards, self.transform_pool)
        # Selection completes before any transform is revealed; stage both draws
        # and replacements so failure cannot consume the first card or RNG draw.
        trial = deepcopy(state)
        results = []
        for identity in selected:
            source = next(c.definition.definition_id for c in trial.deck if c.instance_id == identity)
            card = transform_card(trial, cards, identity, replacement_pool(source, self.transform_pool), stream="event.morphic_transform")
            results.append({"instance_id": card.instance_id, "definition_id": card.definition.definition_id})
        state.deck, state.rng, state.next_card_id = trial.deck, trial.rng, trial.next_card_id
        state.gold = 0
        pending["data"].update(choice="group", eligible=[], selected=list(selected), results=results)
        pending["stage"] = "resolved"

    def validate(self, pending, *, state, cards, defeated=False):
        check_content(state, cards, self.transform_pool)
        data = pending["data"]
        if (defeated or not isinstance(data, dict) or set(data) != {"choice", "eligible", "selected", "results", "initial_gold", "initial_hp", "initial_max_hp", "original_ids", "original_definitions"}
                or type(data["initial_gold"]) is not int or data["initial_gold"] < 0
                or type(data["initial_max_hp"]) is not int or data["initial_max_hp"] <= 0
                or type(data["initial_hp"]) is not int or not 0 < data["initial_hp"] <= data["initial_max_hp"]):
            raise ValueError("Invalid Morphic Grove state.")
        for field in ("original_ids", "eligible", "selected"):
            values = data[field]
            if not isinstance(values, list) or any(not isinstance(i,str) for i in values) or len(values) != len(set(values)):
                raise ValueError("Invalid Morphic card identities.")
        original, selected = data["original_ids"], data["selected"]
        current = [c.instance_id for c in state.deck]
        definitions = data["original_definitions"]
        if not isinstance(definitions, dict) or set(definitions) != set(original):
            raise ValueError("Invalid Morphic source definitions.")
        for name in definitions.values():
            if not isinstance(name, str) or name not in (*self.transform_pool, "strike", "defend", "bash", *CURSE_POOL):
                raise ValueError("Unsupported Morphic source definition.")
        if any(c.instance_id in definitions and c.definition.definition_id != definitions[c.instance_id] for c in state.deck):
            raise ValueError("Morphic original definitions differ from the deck.")
        if any(i not in original for i in selected) or not isinstance(data["results"], list):
            raise ValueError("Invalid Morphic selection.")
        stage, choice = pending["stage"], data["choice"]
        gain = self.max_hp_gain if choice == "loner" else 0
        if state.hp != data["initial_hp"] + gain or state.max_hp != data["initial_max_hp"] + gain:
            raise ValueError("Morphic HP effect differs from its choice.")
        if state.gold != (0 if choice == "group" else data["initial_gold"]):
            raise ValueError("Morphic gold differs from its choice.")
        if stage == "options" and choice is None or stage == "resolved" and choice == "loner":
            if selected or data["eligible"] or data["results"] or current != original:
                raise ValueError("Unselected Morphic transformation has results.")
        elif stage == "select_card" and choice == "group":
            if (len(original) <= self.card_count or len(selected) >= self.card_count or data["results"]
                    or current != original or data["eligible"] != [i for i in original if i not in selected]):
                raise ValueError("Invalid pending Morphic selection.")
        elif stage == "resolved" and choice == "group":
            if len(selected) != min(self.card_count,len(original)) or data["eligible"] or len(data["results"]) != len(selected):
                raise ValueError("Invalid resolved Morphic selection.")
            expected = list(original)
            for source, result in zip(selected, data["results"]):
                if not isinstance(result, dict) or set(result) != {"instance_id", "definition_id"}:
                    raise ValueError("Invalid Morphic result.")
                card = next((c for c in state.deck if c.instance_id == result["instance_id"]), None)
                if (card is None or card.instance_id in original or card.upgrade_level != 0 or card.combats_seen != 0 or card.enchantment is not None
                        or card.definition.definition_id != result["definition_id"]
                        or result["definition_id"] not in replacement_pool(definitions[source], self.transform_pool)
                        or result["definition_id"] == definitions[source]):
                    raise ValueError("Morphic result differs from the deck.")
                expected[original.index(source)] = card.instance_id
            if current != expected:
                raise ValueError("Morphic replacements differ from their original positions.")
        else:
            raise ValueError("Invalid Morphic stage or choice.")

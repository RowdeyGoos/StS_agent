"""Byrdonis Nest: immediate maximum HP or an egg with a rest-site hatch."""

from dataclasses import dataclass
from game.headless.core.snapshots import card_record, restore_card
from game.headless.run.deck import add_card


@dataclass(frozen=True, slots=True)
class ByrdonisNest:
    definition_id: str = "byrdonis_nest"
    max_hp_gain: int = 7

    def is_allowed(self, conditions):
        return not conditions.get("event_pet", False)

    def generate(self, rng, *, state, cards):
        cards.definition("byrdonis_egg"); cards.definition("byrd_swoop")
        return {"choice": None, "initial_hp": state.hp, "initial_max_hp": state.max_hp,
                "originals": [card_record(c) for c in state.deck], "egg_id": None}

    def options(self, pending):
        return ("eat", "take") if pending["stage"] == "options" else ()

    def choose(self, state, pending, option_id, *, cards):
        if option_id == "eat":
            state.max_hp += self.max_hp_gain
            state.hp += self.max_hp_gain
        else:
            pending["data"]["egg_id"] = add_card(state, cards.definition("byrdonis_egg")).instance_id
        pending["data"]["choice"] = option_id
        pending["stage"] = "resolved"

    def validate(self, pending, *, state, cards, defeated=False):
        data = pending["data"]
        if (defeated or not isinstance(data, dict) or set(data) != {"choice", "initial_hp", "initial_max_hp", "originals", "egg_id"}
                or type(data["initial_max_hp"]) is not int or data["initial_max_hp"] <= 0
                or type(data["initial_hp"]) is not int or not 0 < data["initial_hp"] <= data["initial_max_hp"]
                or not isinstance(data["originals"], list)):
            raise ValueError("Invalid Byrdonis Nest data.")
        originals = [restore_card(row, cards) for row in data["originals"]]
        ids = [c.instance_id for c in originals]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate Nest original card.")
        choice, stage = data["choice"], pending["stage"]
        if (stage, choice) not in (("options", None), ("resolved", "eat"), ("resolved", "take")):
            raise ValueError("Invalid Nest stage.")
        gain = self.max_hp_gain if choice == "eat" else 0
        from game.headless.events.resources import validate
        validate(state, pending, [("max_hp", gain), ("cards_added", int(choice == "take"))])
        expected = list(data["originals"])
        if choice == "take":
            egg = next((c for c in state.deck if c.instance_id == data["egg_id"]), None)
            if (egg is None or egg.instance_id in ids or egg.definition.definition_id != "byrdonis_egg"
                    or egg.upgrade_level or egg.combats_seen or egg.enchantment is not None):
                raise ValueError("Invalid Nest egg grant.")
            expected.append(card_record(egg))
            from game.headless.relics.run_rules import has
            if has(state, 'bing_bong'):
                clones = [c for c in state.deck if c.instance_id not in {*ids, egg.instance_id}]
                if len(clones) != 1 or {k: v for k, v in card_record(clones[0]).items() if k != 'instance_id'} != {k: v for k, v in card_record(egg).items() if k != 'instance_id'}:
                    raise ValueError("Nest clone differs from its egg.")
                expected.append(card_record(clones[0]))
        elif data["egg_id"] is not None:
            raise ValueError("Unchosen egg grant.")
        if expected != [card_record(c) for c in state.deck]:
            raise ValueError("Nest deck differs from its choice.")

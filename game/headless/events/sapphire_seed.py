"""Sapphire Seed: heal then upgrade, or permanently enchant one card with Sown."""

from dataclasses import dataclass

from game.headless.core.snapshots import card_record, restore_card
from game.headless.enchantments.base import can_enchant, enchant, validate as validate_enchantment
from game.headless.run.deck import find_card


@dataclass(frozen=True, slots=True)
class SapphireSeed:
    definition_id: str = "sapphire_seed"
    heal: int = 9

    def generate(self, rng, *, state, cards):
        return {"choice": None, "initial_hp": state.hp,
                "originals": [card_record(c) for c in state.deck], "eligible": [], "selected": None}

    def options(self, pending):
        return ("eat", "plant") if pending["stage"] == "options" else ()

    def eligible(self, deck, choice):
        return [c.instance_id for c in deck if (c.upgrade_level + 1 < len(c.definition.levels)
                                               if choice == "eat" else can_enchant(c))]

    def choose(self, state, pending, option_id, *, cards):
        data = pending["data"]
        eligible = self.eligible(state.deck, option_id)
        if option_id == "eat":
            state.hp = min(state.max_hp, state.hp + self.heal)
        data.update(choice=option_id, eligible=eligible)
        if len(eligible) > 1:
            pending["stage"] = "select_card"
        else:
            self._resolve(state, pending, eligible[0] if eligible else None)

    def select_card(self, state, pending, identity, *, cards):
        if identity not in pending["data"]["eligible"] or identity not in self.eligible(state.deck, pending["data"]["choice"]):
            raise ValueError("Unavailable Sapphire Seed card.")
        self._resolve(state, pending, identity)

    def _resolve(self, state, pending, identity):
        if identity is not None:
            card = find_card(state, identity)
            if pending["data"]["choice"] == "eat":
                card.upgrade()
            else:
                enchant(card)
        pending["data"].update(selected=identity, eligible=[])
        pending["stage"] = "resolved"

    def validate(self, pending, *, state, cards, defeated=False):
        data = pending["data"]
        if (defeated or not isinstance(data, dict) or set(data) != {"choice", "initial_hp", "originals", "eligible", "selected"}
                or type(data["initial_hp"]) is not int or not 0 < data["initial_hp"] <= state.max_hp
                or not isinstance(data["originals"], list)):
            raise ValueError("Invalid Sapphire Seed data.")
        originals = [restore_card(row, cards) for row in data["originals"]]
        for card in originals:
            validate_enchantment(card, permanent=True)
        identities = [c.instance_id for c in originals]
        if len(set(identities)) != len(identities):
            raise ValueError("Duplicate Sapphire Seed original.")
        choice, stage = data["choice"], pending["stage"]
        if stage == "options" and choice is None:
            if data["eligible"] or data["selected"] is not None:
                raise ValueError("Unchosen Sapphire Seed has a selection.")
        elif choice in ("eat", "plant") and stage in ("select_card", "resolved"):
            eligible = self.eligible(originals, choice)
            if stage == "select_card":
                if len(eligible) < 2 or data["eligible"] != eligible or data["selected"] is not None:
                    raise ValueError("Invalid Sapphire Seed selector.")
            else:
                selected = data["selected"]
                if data["eligible"] or (selected not in eligible if eligible else selected is not None):
                    raise ValueError("Invalid Sapphire Seed result.")
                if selected is not None:
                    card = originals[identities.index(selected)]
                    card.upgrade() if choice == "eat" else enchant(card)
        else:
            raise ValueError("Invalid Sapphire Seed stage.")
        from game.headless.events.resources import expected
        expected_hp = expected(state, pending, [("heal", self.heal if choice == "eat" else 0)]).hp
        if state.hp != expected_hp or [card_record(c) for c in state.deck] != [card_record(c) for c in originals]:
            raise ValueError("Sapphire Seed effects differ from the original deck/HP.")

"""Whispering Hollow's priced potion pair or transform-then-damage choice."""

from copy import deepcopy
from dataclasses import dataclass

from game.headless.core.snapshots import card_record
from game.headless.events import deck_choice, potion_rewards
from game.headless.events.transformation import TRANSFORM_POOL, check_content, transform


@dataclass(frozen=True, slots=True)
class WhisperingHollow:
    definition_id: str = "whispering_hollow"
    potion_pool: tuple[str, ...] = ("fire_potion", "block_potion")
    damage: int = 9

    def is_allowed(self, conditions):
        return conditions["gold"] >= 44

    def generate(self, rng, *, state, cards):
        check_content(state, cards, TRANSFORM_POOL)
        return {"choice": None, "price": rng.randint("event.whisper_price", 26, 44),
                "initial_hp": state.hp, "initial_gold": state.gold, "rewards": [], **deck_choice.empty()}

    def options(self, pending):
        return potion_rewards.options(pending) if pending["stage"] == "potion_rewards" else ("hug", "gold") if pending["stage"] == "options" else ()

    def choose(self, state, pending, option_id, *, cards):
        if pending["stage"] == "potion_rewards":
            return potion_rewards.choose(state, pending, option_id)
        data = pending["data"]
        if option_id == "gold":
            trial = deepcopy(state)
            rewards = potion_rewards.generate(trial.rng, self.potion_pool, 2)
            state.gold = max(0, state.gold - data["price"])
            state.rng = trial.rng
            data.update(choice="gold", rewards=rewards)
            pending["stage"] = "potion_rewards"
        else:
            check_content(state, cards, TRANSFORM_POOL)
            if len(deck_choice.eligible(state)) <= 1:
                self._resolve(state, pending, deck_choice.eligible(state)[0].instance_id if deck_choice.eligible(state) else None, cards)
            else:
                deck_choice.prepare(state, data)
                data["choice"] = "hug"
                pending["stage"] = "select_card"

    def select_card(self, state, pending, identity, *, cards):
        if identity not in pending["data"]["eligible"]:
            raise ValueError("Unavailable Whispering Hollow card.")
        self._resolve(state, pending, identity, cards)

    def _resolve(self, state, pending, identity, cards):
        trial = deepcopy(state)
        result = None if identity is None else card_record(transform(trial, cards, identity, TRANSFORM_POOL, stream="event.whisper_transform"))
        data = pending["data"]
        if data["choice"] is None:
            deck_choice.prepare(state, data)
        from game.headless.run.deck import commit_trial
        commit_trial(state, trial)
        from game.headless.relics.run_rules import damage
        damage(state, self.damage)
        data.update(choice="hug", eligible=[], selected=identity, result=result)
        pending["stage"] = "resolved"

    def validate(self, pending, *, state, cards, defeated=False):
        data = pending["data"]
        if (not isinstance(data, dict) or set(data) != {"choice", "price", "initial_hp", "initial_gold", "rewards", *deck_choice.empty()}
                or type(data["price"]) is not int or not 26 <= data["price"] <= 44
                or type(data["initial_hp"]) is not int or not 0 < data["initial_hp"] <= state.max_hp
                or type(data["initial_gold"]) is not int or data["initial_gold"] < 0):
            raise ValueError("Invalid Whispering Hollow data.")
        stage, choice = pending["stage"], data["choice"]
        damaged = choice == "hug" and stage == "resolved"
        from game.headless.events.resources import validate
        effects = [("cards_added", int(data["selected"] is not None)), ("damage", self.damage)] if damaged else [("spend_gold", data["price"])] if choice == "gold" else []
        validate(state, pending, effects)
        if defeated != (state.hp == 0):
            raise ValueError("Whispering Hollow defeat differs from HP.")
        if choice == "gold" and stage in ("potion_rewards", "resolved"):
            potion_rewards.validate(state, data["rewards"], self.potion_pool, 2)
            if any(data[k] != v for k,v in deck_choice.empty().items()):
                raise ValueError("Potion branch contains a deck selection.")
        elif choice == "hug" and stage in ("select_card", "resolved"):
            if data["rewards"]: raise ValueError("Hug contains potion rewards.")
            deck_choice.validate(state, data, cards, operation="transform", finished=stage=="resolved")
        elif stage == "options" and choice is None:
            if data["rewards"] or any(data[k] != v for k,v in deck_choice.empty().items()):
                raise ValueError("Unchosen Whispering Hollow has results.")
        else:
            raise ValueError("Invalid Whispering Hollow stage.")

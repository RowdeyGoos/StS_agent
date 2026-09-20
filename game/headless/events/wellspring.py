"""Wellspring potion reward or permanent removal followed by Guilty."""

from copy import deepcopy
from dataclasses import dataclass
from game.headless.potions.pools import ORDINARY_POTIONS

from game.headless.events import deck_choice, potion_rewards
from game.headless.run.deck import add_card, remove_card


@dataclass(frozen=True, slots=True)
class Wellspring:
    definition_id: str = "wellspring"
    potion_pool: tuple[str, ...] = ORDINARY_POTIONS

    def generate(self, rng, *, state, cards):
        cards.definition("guilty")
        return {"choice": None, "rewards": [], "guilty_id": None, **deck_choice.empty()}

    def options(self, pending):
        return potion_rewards.options(pending) if pending["stage"] == "potion_rewards" else ("bottle", "bathe") if pending["stage"] == "options" else ()

    def choose(self, state, pending, option_id, *, cards):
        if pending["stage"] == "potion_rewards":
            return potion_rewards.choose(state, pending, option_id)
        data = pending["data"]
        if option_id == "bottle":
            trial = deepcopy(state)
            rewards = potion_rewards.generate(trial.rng, self.potion_pool, 1, uniform=True)
            state.rng = trial.rng
            data.update(choice="bottle", rewards=rewards)
            pending["stage"] = "potion_rewards"
        elif len(deck_choice.eligible(state)) <= 1:
            self._resolve(state, pending, deck_choice.eligible(state)[0].instance_id if deck_choice.eligible(state) else None, cards)
        else:
            deck_choice.prepare(state, data)
            data["choice"] = "bathe"
            pending["stage"] = "select_card"

    def select_card(self, state, pending, identity, *, cards):
        if identity not in pending["data"]["eligible"]:
            raise ValueError("Unavailable Wellspring card.")
        self._resolve(state, pending, identity, cards)

    def _resolve(self, state, pending, identity, cards):
        trial = deepcopy(state)
        if identity is not None:
            remove_card(trial, identity)
        guilty = add_card(trial, cards.definition("guilty"))
        data = pending["data"]
        if data["choice"] is None:
            deck_choice.prepare(state, data)
        from game.headless.run.deck import commit_trial
        commit_trial(state, trial)
        data.update(choice="bathe", eligible=[], selected=identity, guilty_id=guilty.instance_id)
        pending["stage"] = "resolved"

    def validate(self, pending, *, state, cards, defeated=False):
        data = pending["data"]
        if defeated or not isinstance(data, dict) or set(data) != {"choice", "rewards", "guilty_id", *deck_choice.empty()}:
            raise ValueError("Invalid Wellspring data.")
        choice, stage = data["choice"], pending["stage"]
        if 'resources' in pending:
            from game.headless.events.resources import validate
            validate(state, pending, [('cards_added', int(choice == 'bathe' and stage == 'resolved'))])
        if choice == "bottle" and stage in ("potion_rewards", "resolved"):
            potion_rewards.validate(state, data["rewards"], self.potion_pool, 1)
            if data["guilty_id"] is not None or any(data[k] != v for k,v in deck_choice.empty().items()):
                raise ValueError("Bottle has deck effects.")
        elif choice == "bathe" and stage in ("select_card", "resolved"):
            if data["rewards"]: raise ValueError("Bathe has potion rewards.")
            extra = ()
            if stage == "resolved":
                guilty = next((c for c in state.deck if c.instance_id == data["guilty_id"]), None)
                if (guilty is None or guilty.definition.definition_id != "guilty" or guilty.combats_seen
                        or guilty.instance_id in [r["instance_id"] for r in data["originals"]]):
                    raise ValueError("Wellspring Guilty grant differs from the deck.")
                extra = (guilty.instance_id,)
                from game.headless.relics.run_rules import has
                if has(state, "bing_bong"):
                    from game.headless.core.snapshots import card_record
                    original_ids = {r["instance_id"] for r in data["originals"]}
                    clones = [c for c in state.deck if c.instance_id not in {*original_ids, guilty.instance_id}]
                    if len(clones) != 1 or {k: v for k, v in card_record(clones[0]).items() if k != "instance_id"} != {k: v for k, v in card_record(guilty).items() if k != "instance_id"}:
                        raise ValueError("Wellspring clone differs from Guilty.")
                    extra += (clones[0].instance_id,)
                if tuple(c.instance_id for c in state.deck[-len(extra):]) != extra:
                    raise ValueError("Wellspring grants are not appended in acquisition order.")
            elif data["guilty_id"] is not None:
                raise ValueError("Pending removal already granted Guilty.")
            deck_choice.validate(state, data, cards, operation="remove", finished=stage=="resolved", extra=extra)
        elif choice is None and stage == "options":
            if data["rewards"] or data["guilty_id"] is not None or any(data[k] != v for k,v in deck_choice.empty().items()):
                raise ValueError("Unchosen Wellspring has results.")
        else:
            raise ValueError("Invalid Wellspring stage.")

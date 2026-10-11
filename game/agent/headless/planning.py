"""Passive campaign planning receipts at the existing adapter boundary.

Only this producer sees the real engine. Receipts contain allowlisted public
graphs, intermediate reveals and facts inferred from accepted public history.
Observers are scoped to one command and never draw random numbers.
"""
from copy import deepcopy

from game.agent.contracts import full as f
from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.reveals import run_reveals
from .full_projection import FullProjection


class CampaignPlanning:
    def __init__(self, adapter):
        self.adapter = adapter
        self.anchor = None
        self.serial = 0
        self.reveals = []
        self.card_combats = {}
        self._known_cards = set()
        self._completed = set()
        self._remember(adapter.observe(), acquired=False)

    def _remember(self, frame, *, acquired=True):
        if not hasattr(frame, 'decision'):
            return
        for group in frame.decision.run.children:
            if group.kind == 'deck':
                for card in group.children:
                    # A card newly revealed by a reconciled acquisition has not
                    # participated in a fight yet. Initial attachment to an old
                    # lifetime card is intentionally not certified.
                    if card.ref not in self._known_cards and acquired:
                        self.card_combats[card.ref] = 0
                    self._known_cards.add(card.ref)

    def step(self, binding, action_ref):
        adapter, entry = self.adapter, []
        run = adapter._engine
        frame = adapter._frame
        action = next((a for a in frame.decision.candidates if a.ref == action_ref), None) if frame else None
        if action is None:
            return adapter.step(binding, action_ref)
        if hasattr(run, '_combat_entry_observer'):
            raise ValueError('Combat entry already has an observer')

        def observe_entry():
            owner = FullProjection(run, deepcopy(adapter._ids), adapter._history,
                                   adapter._power_cards, 'attachment', adapter._epoch, False)
            initial = f.PublicDecision(f.SCHEMA, f.PROFILE, owner.run(),
                f.Node('planning', 'combat_entry', fields=(f.Field('entry_action_kind', action.kind),)),
                (f.Candidate('action:0', 'end_turn'),))
            entry.append((f.to_dict(initial), deepcopy(self.card_combats)))

        run._combat_entry_observer = observe_entry
        try:
            with run_reveals(run) as journal:
                report = adapter.step(binding, action_ref)
        finally:
            del run._combat_entry_observer
        self.reveals = deepcopy(journal.events)
        if report.status != 'reconciled':
            return report
        frame = adapter.observe()
        if entry:
            self.serial += 1
            self.anchor = None
            if len(entry) == 1 and hasattr(frame, 'decision') and run.combat is not None:
                from game.agent.search.campaign import ANCHOR
                initial, facts = entry[0]
                self.anchor = dict(schema=ANCHOR, initial=initial, opening=f.to_dict(frame.decision),
                    opening_reveals=self.reveals, transitions=[], facts={'card_combats': facts})
        elif self.anchor is not None and run.combat is not None:
            self.anchor['transitions'].append(dict(action_ref=action_ref,
                successor=f.to_dict(frame.decision), reveals=self.reveals))
        completion, summary = adapter.combat_completion, adapter.combat_summary
        if completion is not None and summary is not None and summary.combat_ref not in self._completed:
            self._completed.add(summary.combat_ref)
            if completion.result == 'victory':
                for group in completion.run.children:
                    if group.kind == 'deck':
                        for card in group.children:
                            if (DEFAULT_CARDS.definition(card.definition_id).combat_lifetime
                                    and card.ref in self.card_combats):
                                self.card_combats[card.ref] += 1
        self._remember(frame)
        return report

    def export(self):
        """A public-only attachment prefix; absent for unsupported entry paths."""
        return deepcopy(self.anchor)

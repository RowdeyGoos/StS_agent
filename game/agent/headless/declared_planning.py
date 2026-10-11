"""Public receipts for a declared fresh scenario, using ordinary setup rules."""
from game.agent.contracts import full as f
from game.headless.reveals import CombatReveals
from .full_projection import FullProjection
from .identity import Identities


class DeclaredPlanning:
    def __init__(self, scenario):
        self.scenario = scenario
        self.initial = None
        self.journal = None

    def make(self, seed):
        self.journal = CombatReveals()

        def entry(run):
            owner = FullProjection(run, Identities(), [], {}, 'attachment', 0, False)
            self.initial = f.PublicDecision(f.SCHEMA, f.PROFILE, owner.run(),
                f.Node('planning', 'combat_entry', fields=(f.Field('entry_action_kind', 'declared_combat'),)),
                (f.Candidate('action:0', 'end_turn'),))

        return self.scenario.make(seed, entry_observer=entry, reveal_journal=self.journal)

    def anchor(self, opening):
        from game.agent.search.combat import ANCHOR
        if self.initial is None:
            raise ValueError('Missing declared combat entry')
        cards = {n.ref: 0 for g in self.initial.run.children if g.kind == 'deck' for n in g.children}
        return dict(schema=ANCHOR, setup_stage='after_room_entry', ruleset='declared_combat_v1', initial=f.to_dict(self.initial),
                    opening=f.to_dict(opening), opening_reveals=self.journal.events,
                    facts={'card_combats': cards}, transitions=[])

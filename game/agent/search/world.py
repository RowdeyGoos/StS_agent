"""Hypothetical engine execution shared by combat reconstruction models."""
from dataclasses import replace
from copy import deepcopy
import time

from game.agent.contracts import full as f
from game.agent.headless.full_projection import FullProjection
from game.agent.headless.identity import Identities
from game.headless.planning import UnsupportedSearch
from .public_keys import action_key


class SimulationWorld:
    """Owns only a newly reconstructed engine; policies see project() values."""
    def __init__(self, run, refs=None, root=None):
        self._run = run
        self._root = root
        self._ids = Identities()
        self._history, self._powers, self._commands = [], {}, {}
        self.terminal_value = self.completion = None
        self.prepared = None
        self.timings = dict(transition=0., projection=0.)
        if root is None:
            return
        for n in (*f.walk(root.run), *f.walk(root.context)):
            if n.ref:
                kind, number = n.ref.split(':')
                self._ids.counts[kind] = max(self._ids.counts[kind], int(number) + 1)
        for ref, (kind, identity) in refs.items():
            key = ('deck', identity) if kind == 'deck' else ('combat', 0, identity) if kind == 'combat' else ('owned', identity)
            self._ids.refs['card' if kind in ('deck', 'combat') else kind, key] = ref
        for slot, n in enumerate(next(n for n in root.context.children if n.kind == 'enemies').children):
            self._ids.refs['enemy', (0, slot)] = n.ref
        self._history = [f.Candidate('action:0', n.definition_id,
                          next(iter(n.linked('history_subject')), None), next(iter(n.linked('history_target')), None))
                         for node in root.run.children if node.kind == 'history' for n in node.children]
        self._powers = {}
        for node in root.context.children:
            if node.kind == 'pile' and node.definition_id == 'powers':
                for card in node.children:
                    self._powers[0, refs[card.ref][1]] = card
        self._commands = {}
        self.terminal_value = None
        self.timings = dict(transition=0., projection=0.)

    def fork(self, seed=None):
        from game.headless.run.construction import fork_combat
        # Public history stays with the branch; the engine helper owns the
        # independent domain state and future RNG.
        from copy import copy
        result = copy(self)
        try:
            result._run = fork_combat(self._run, future_seed=seed)
        except ValueError as error:
            raise UnsupportedSearch('simulation_fork_unsupported') from error
        result._ids = deepcopy(self._ids)
        result._history, result._powers = list(self._history), dict(self._powers)
        result._commands = {}
        result.prepared = None
        result.timings = dict(transition=0., projection=0.)
        return result

    def project(self):
        started = time.perf_counter()
        owner = FullProjection(self._run, self._ids, self._history, self._powers, 'attachment', 0, False)
        from game.agent.headless.errors import UnsupportedProfile
        try:
            result = owner.decision(transform=self._project_view)
        except UnsupportedProfile as error:
            raise UnsupportedSearch('simulation_projection_unsupported') from error
        self._commands = owner.commands
        self.prepared = owner.prepared
        self.timings['projection'] += time.perf_counter() - started
        return result

    def _project_view(self, result):
        """Apply branch public context before the final ownership validation."""
        if self._root is None:
            return result
        # Preserve actual public strategic context; no invented map or rewards
        # may alter the critic. Dynamic inventory/HP come from the simulation.
        dynamic = {n.kind: n for n in result.run.children}
        children = tuple(dynamic.get(n.kind, n) if n.kind != 'map' else n for n in self._root.run.children)
        fields = tuple(v if v.key not in ('hp', 'max_hp', 'gold') else
                       f.Field(v.key, result.run.get(v.key)) for v in self._root.run.fields)
        result = replace(result, run=replace(self._root.run, fields=fields, children=children))
        return result

    def step(self, decision, key):
        action = next((a for a in decision.candidates if action_key(decision, a) == key), None)
        if action is None:
            raise UnsupportedSearch('sampled_action_mismatch')
        previous = self._run.combat
        card = next((n for n in f.walk(decision.context) if n.ref == action.subject), None)
        command = self._commands[action.ref]
        started = time.perf_counter()
        self._run.apply(command)
        self.timings['transition'] += time.perf_counter() - started
        self._history.append(action)
        if action.kind == 'play_card' and previous is self._run.combat:
            if any(c.instance_id == command.instance_id for c in previous.player.deck.powers):
                self._powers[0, command.instance_id] = card
        if self._run.combat is None:
            from game.agent.contracts.planning import CombatEnd
            owner = FullProjection(self._run, self._ids, self._history, self._powers, 'attachment', 0, False)
            self.completion = CombatEnd('victory' if previous.winner == 'player' else 'defeat', owner.run())
            self.terminal_value = (1. + .1 * self._run.state.hp / self._run.state.max_hp
                                   if previous.winner == 'player' else 0.)
            return None
        return self.project()

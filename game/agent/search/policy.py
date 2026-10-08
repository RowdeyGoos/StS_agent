"""Single-player, observation-history Gumbel search with an exact rules model."""
from collections import Counter
from dataclasses import asdict, dataclass, field, replace
import hashlib
import json
import math
from random import Random
import sys
import time

from game.agent.action_policy import action_mask
from game.agent.search.model import PublicCombatModel, SearchHistory, action_key, observation_key
from game.headless.planning import UnsupportedSearch
from .belief import BeliefBudget, CombatBelief, MODEL as BELIEF_MODEL
from .direct import DirectCombatBelief, MODEL as DIRECT_MODEL
from .observed import ObservedCombatBelief, MODEL as OBSERVED_MODEL
from .public_keys import public_key

BELIEF_MODELS = (BELIEF_MODEL, DIRECT_MODEL, OBSERVED_MODEL)
DETACHED_MODELS = (DIRECT_MODEL, OBSERVED_MODEL)


def _checkpoint_provider(policy):
    # A custom public policy need not install/import the optional Torch stack.
    module = sys.modules.get('game.agent.training.checkpoint')
    return module is not None and type(policy) is module.CheckpointPolicy


@dataclass(frozen=True)
class SearchConfig:
    simulations: int = 64
    considered_actions: int = 16
    max_depth: int = 64
    time_limit: float = 5.
    seed: int = 0
    method: str = 'gumbel'
    exploration: bool = False
    model_version: str = 'reconstruction_v1'
    belief_particles: int = 4
    belief_proposals: int = 1024
    belief_replay_proposals: int = 2048
    belief_replay_steps: int = 16384
    belief_seconds: float = 5.
    leaf_rollout_steps: int = 0
    q_scale: float = .1
    final_selection: str = 'prior_value'

    def __post_init__(self):
        for key, lower, upper in (('simulations', 1, 4096), ('considered_actions', 1, 256), ('max_depth', 1, 512)):
            value = getattr(self, key)
            if type(value) is not int or not lower <= value <= upper:
                raise ValueError('Invalid search ' + key)
        if type(self.seed) is not int or not 0 <= self.seed < 2**63:
            raise ValueError('Invalid search seed')
        if type(self.leaf_rollout_steps) is not int or not 0 <= self.leaf_rollout_steps <= 512:
            raise ValueError('Invalid leaf rollout budget')
        if type(self.q_scale) not in (int, float) or not math.isfinite(self.q_scale) or not 0 < self.q_scale <= 100:
            raise ValueError('Invalid search Q scale')
        if self.final_selection not in ('prior_value', 'max_value'):
            raise ValueError('Invalid search final selection')
        if type(self.time_limit) not in (int, float) or not math.isfinite(self.time_limit) or self.time_limit <= 0:
            raise ValueError('Invalid search time limit')
        if self.method not in ('gumbel', 'root') or type(self.exploration) is not bool:
            raise ValueError('Invalid search method/exploration')
        if self.model_version not in ('reconstruction_v1', *BELIEF_MODELS):
            raise ValueError('Invalid search model version')
        self.belief_budget()

    @property
    def uses_belief(self):
        return self.model_version in BELIEF_MODELS

    def belief_budget(self):
        return BeliefBudget(self.belief_particles, self.belief_proposals, self.belief_seconds,
                            self.belief_replay_proposals, self.belief_replay_steps)


@dataclass(frozen=True)
class SearchResult:
    action_ref: str
    probabilities: dict
    values: dict
    visits: dict
    simulations: int
    seconds: float
    reason: str | None
    timings: dict = field(default_factory=dict)
    cutoff: str | None = None
    leaf_work: dict = field(default_factory=dict)
    tree_work: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


def softmax(values):
    maximum = max(values)
    weights = [math.exp(v - maximum) for v in values]
    total = sum(weights)
    return [w / total for w in weights]


class Node:
    def __init__(self, keys, priors, value, q_scale=.1):
        self.keys, self.priors, self.value = keys, priors, value
        self.q_scale = q_scale
        self.counts = [0] * len(keys)
        self.sums = [0.] * len(keys)
        self.children = {}

    def completed(self):
        visited = [i for i, n in enumerate(self.counts) if n]
        n = sum(self.counts)
        mass = sum(self.priors[i] for i in visited)
        weighted = sum(self.priors[i] * self.sums[i] / self.counts[i] for i in visited)
        mixed = (self.value + n * weighted / mass) / (n + 1) if mass else self.value
        return [self.sums[i] / count if count else mixed for i, count in enumerate(self.counts)]

    def scores(self):
        q = self.completed()
        low, high = min(q), max(q)
        scale = self.q_scale * (50 + max(self.counts))
        return [math.log(max(p, 1e-30)) + scale * (v - low) / max(high - low, 1e-8)
                for p, v in zip(self.priors, q)]

    def improved(self):
        return softmax(self.scores())

    def select(self):
        probabilities = self.improved()
        total = 1 + sum(self.counts)
        return max(range(len(self.keys)), key=lambda i: probabilities[i] - self.counts[i] / total)


class SearchPolicy:
    """A checkpoint-compatible chooser with explicit reconciled history hooks.

Time is a ceiling on work, not a game outcome. Fixed-budget reproducibility is
guaranteed only when that ceiling does not interrupt the requested simulations.
"""
    def __init__(self, policy, config=SearchConfig()):
        from game.agent.input_views import RAW, DETACHED_HISTORY, validate_view
        from game.agent.training.rewards import RewardSpec
        expected = RewardSpec({'combat_win': 1., 'win_hp_fraction': .1})
        if policy.reward_spec != expected:
            raise ValueError('Search requires unshaped combat victory + 0.1 winning HP fraction')
        manifest = getattr(policy, 'manifest', {})
        if manifest.get('algorithm') == 'ppo' and manifest.get('learner_config', {}).get('ppo', {}).get('gamma') != 1.:
            raise ValueError('Search requires an undiscounted combat critic (PPO gamma=1)')
        self.base, self.config = policy, config
        self.reward_spec, self.model = policy.reward_spec, policy.model
        self.input_view = DETACHED_HISTORY if config.model_version in DETACHED_MODELS else RAW
        validate_view(self.input_view, action_policy=self.model.action_policy)
        checkpoint_view = validate_view(getattr(self.model, 'input_view', RAW))
        if checkpoint_view not in (RAW, self.input_view):
            raise ValueError('Search model and checkpoint public input view differ; use direct_belief_v1')
        identity_config = asdict(config)
        # Preserve identities of the unchanged, critic-only historical teacher.
        if not config.leaf_rollout_steps:
            identity_config.pop('leaf_rollout_steps')
        # Explicit experimental settings must not rename unchanged teachers.
        if config.q_scale == .1:
            identity_config.pop('q_scale')
        if config.final_selection == 'prior_value':
            identity_config.pop('final_selection')
        payload = json.dumps([policy.identity, identity_config], sort_keys=True)
        self.identity = 'sts_combat_search_v1:' + hashlib.sha256(payload.encode()).hexdigest()
        self.reset()

    def reset(self):
        self.history = SearchHistory()
        self.rng = Random(self.config.seed)
        self.simulation_rng = Random(self._seed('simulation'))
        self.last_result = None
        self.results = []
        self.reconciled_results = []
        self._last_decision = None
        self.belief = None
        self.planning_start = None
        self.planning_ends = {}
        self.planning_reveals = []
        self._belief_failure = 'missing_planning_anchor'

    def _seed(self, domain):
        return int.from_bytes(hashlib.sha256(f'{BELIEF_MODEL}:{domain}:{self.config.seed}'.encode()).digest()[:8], 'big')

    def begin_combat(self, setup, opening):
        """Attach an explicit public declaration; never infer it from a display.

        Reset between fights. Callers retain all bindings and actual engines.
        Initialization work is deferred to choose(), inside its search deadline.
        """
        if not self.config.uses_belief:
            raise ValueError('A declared anchor requires the public belief model')
        if self.planning_start is not None:
            raise ValueError('Reset before declaring another combat')
        if self.config.model_version == OBSERVED_MODEL:
            from .observed import validate_anchor
            self.planning_start = validate_anchor(setup)
            self.belief = ObservedCombatBelief(self.planning_start, opening, seed=self._seed('belief'),
                                              budget=self.config.belief_budget())
            self._belief_failure = None
            return
        from game.agent.contracts.planning import validate_start
        self.planning_start = validate_start(setup)
        try:
            model = DirectCombatBelief if self.config.model_version == DIRECT_MODEL else CombatBelief
            self.belief = model(setup, opening, seed=self._seed('belief'),
                                      budget=self.config.belief_budget(), initialize=False)
        except UnsupportedSearch as error:
            self._belief_failure = str(error)
        else:
            self._belief_failure = None

    @property
    def needs_combat_reveals(self):
        return self.config.model_version == OBSERVED_MODEL

    def observe_reveals(self, events):
        if not self.needs_combat_reveals or self.belief is None:
            raise ValueError('This search session does not accept reveal receipts')
        from game.headless.reveals import validate_reveals
        events = validate_reveals(events)
        self.belief.receive_reveals(events)
        self.planning_reveals.append(events)

    def observe_transition(self, before, action, execution, successor):
        record = execution.status == 'reconciled' and self._last_decision == before
        if self.config.uses_belief:
            from game.agent.contracts.planning import CombatEnd
            if isinstance(successor, CombatEnd):
                self.planning_ends[len(self.reconciled_results)] = successor
            started = time.perf_counter()
            if self.belief is not None:
                try:
                    remaining = (max(0., self.config.time_limit - self.last_result.seconds)
                                 if record else self.config.belief_seconds)
                    self.belief.observe_transition(before, action, execution, successor, seconds=remaining)
                except UnsupportedSearch as error:
                    self._belief_failure = str(error)
            if record:
                seconds = time.perf_counter() - started
                self.last_result = replace(self.last_result, seconds=self.last_result.seconds + seconds,
                    timings={**self.last_result.timings, 'conditioning': seconds})
                self.results[-1] = self.last_result
                self.reconciled_results.append(self.last_result)
            return
        self.history.observe(before, action, execution, successor)
        if record:
            self.reconciled_results.append(self.last_result)

    def _node(self, decision, timings, prepared=None):
        start = time.perf_counter()
        if self.config.model_version in DETACHED_MODELS:
            from .direct import planning_view
            decision = planning_view(decision)
        probabilities, value = self._predict(decision, prepared)
        timings['inference'] += time.perf_counter() - start
        allowed = action_mask(decision, self.model.action_policy)
        actions = [a for a, ok in zip(decision.candidates, allowed) if ok]
        p = [probabilities[a.ref] for a in actions]
        if not p or any(not math.isfinite(v) or v < 0 for v in p) or not math.isfinite(value) or sum(p) <= 0:
            raise ValueError('Invalid search network output')
        # This objective is bounded. Clipping is part of the search version,
        # never applied to recorded realized returns or the checkpoint itself.
        keys = [action_key(decision, a) for a in actions]
        if len(set(keys)) != len(keys):
            raise ValueError('Ambiguous public action mapping')
        return Node(keys, [v / sum(p) for v in p], min(1.1, max(0., value)), self.config.q_scale), actions

    def _predict(self, decision, prepared=None):
        from game.agent.contracts import full as f
        cache = getattr(self, '_prediction_cache', None)
        if prepared is None and cache is not None:
            from game.agent.training.features import canonical_records
            if not canonical_records(decision):
                # Structural callers retain the encoder's wire-order path.
                cache = None
        if cache is not None:
            # Full immutable public inputs, including history, references and
            # candidate order. Never use a hidden state or a normalized tree key.
            if prepared is None or prepared.value is not decision:
                prepared = f.PreparedPublic(decision)
                decision = prepared.value
            # Python considers 1 and True equal, but the encoder distinguishes
            # numeric and boolean fields. Include their exact scalar types.
            key = (decision, tuple(type(field.value) for root in (decision.run, decision.context)
                                   for node in f.walk(root) for field in node.fields))
            cached = cache.get(key)
            if cached is not None:
                self.prediction_cache_stats['hits'] += 1
                return dict(cached[0]), cached[1]
        if _checkpoint_provider(self.base) and prepared is not None and prepared.value is decision:
            result = self.base.probabilities_prepared(decision, prepared)
        else:
            result = self.base.probabilities(decision)
        if cache is not None:
            self.prediction_cache_stats['misses'] += 1
            if len(cache) == 128:
                del cache[next(iter(cache))]
            cache[key] = (tuple(result[0].items()), result[1])
            self.prediction_cache_stats['peak_entries'] = max(self.prediction_cache_stats['peak_entries'], len(cache))
        return result

    def _leaf_value(self, world, observation, node, timings, work, deadline):
        """Greedy public-observation continuation of this simulation's world.

        A bounded nonterminal continuation uses its final critic, not a defeat
        label. Its value is backed up for this simulation only: storing it on
        a shared history node would couple later simulations to one hidden world.
        """
        for _ in range(self.config.leaf_rollout_steps):
            if time.perf_counter() >= deadline:
                work['time_bootstraps'] += 1
                break
            branch = max(range(len(node.keys)), key=lambda i: node.priors[i])
            observation = world.step(observation, node.keys[branch])
            work['steps'] += 1
            for key, seconds in world.timings.items():
                timings[key] += seconds
            world.timings = dict(transition=0., projection=0.)
            if observation is None:
                work['terminals'] += 1
                return world.terminal_value
            node, _ = self._node(observation, timings, getattr(world, 'prepared', None))
        work['bootstraps'] += 1
        return node.value

    def choose(self, decision):
        # One synchronous search with one frozen built-in provider. Custom hooks
        # and trainable/stochastic providers retain every inference call.
        base = self.base
        reusable = False
        if _checkpoint_provider(base):
            from game.agent.training.features import FeatureEncoder
            from game.agent.training.model import ActorCritic
            from game.agent.encoding.full import FullRunEncoder
            reusable = (type(base.model) is ActorCritic and type(base.encoder) is FeatureEncoder
                and not base.model.training
                and type(base.encoder.public) is FullRunEncoder and set(vars(base.encoder.public)) == {'profile'}
                and not any(p.requires_grad for p in base.model.parameters())
                and not {'probabilities', 'probabilities_prepared', '_probabilities'} & vars(base).keys()
                and not {'encode', 'encode_inference', 'encode_prepared', '_features'} & vars(base.encoder).keys()
                and all(not m._forward_hooks and not m._forward_pre_hooks and 'forward' not in vars(m)
                        for m in base.model.modules()))
        self._prediction_cache = {} if reusable else None
        self.prediction_cache_stats = dict(hits=0, misses=0, peak_entries=0)
        try:
            return self._choose(decision)
        finally:
            # Release public graphs even on an unsupported branch or exception.
            self._prediction_cache = None

    def _choose(self, decision):
        started = time.perf_counter()
        timings = dict(inference=0., reconstruction=0., sampling=0., transition=0., projection=0.)
        leaf_work = dict(steps=0, terminals=0, bootstraps=0, time_bootstraps=0)
        # Public work diagnostics only; never consulted by action selection.
        tree_work = dict(depth_histogram={}, expansions=0, terminals=0, root_rounds=[])
        root, actions = self._node(decision, timings)
        fallback = max(range(len(actions)), key=lambda i: root.priors[i])
        completed = 0
        reason = cutoff = None
        selected = fallback
        try:
            if self.config.model_version == 'reconstruction_v1':
                self.history.attach(decision)
            if len(actions) == 1:
                raise UnsupportedSearch('forced_action')
            before = time.perf_counter()
            try:
                if self.config.uses_belief:
                    if self.belief is None:
                        raise UnsupportedSearch(self._belief_failure)
                    if self.belief.current != decision:
                        self.belief._invalidate('belief_history_mismatch')
                        raise UnsupportedSearch('belief_history_mismatch')
                    if self.belief.reason == 'belief_budget':
                        remaining = max(0., self.config.time_limit - (time.perf_counter() - started))
                        self.belief.recover(seconds=remaining)
                    if self.belief.reason:
                        raise UnsupportedSearch(self.belief.reason)
                    model = self.belief
                else:
                    model = PublicCombatModel(decision, self.history)
            finally:
                timings['reconstruction'] += time.perf_counter() - before
            timings['reconstruction'] -= getattr(model, 'projection_seconds', 0.)
            timings['projection'] += getattr(model, 'projection_seconds', 0.)
            noise = [-math.log(-math.log(max(1e-15, self.rng.random()))) if self.config.exploration else 0.
                     for _ in actions]
            considered = sorted(range(len(actions)), key=lambda i: (math.log(max(root.priors[i], 1e-30)) + noise[i], -i),
                                reverse=True)[:min(len(actions), self.config.considered_actions, self.config.simulations)]
            rounds = max(1, math.ceil(math.log2(len(considered))))
            tree_work['root_value'] = root.value
            evidence = tree_work['root_evidence'] = {
                a.ref: dict(prior=root.priors[i], tree_terminals=0, leaf_terminals=0,
                            critic_bootstraps=0, value_sum_squares=0.)
                for i, a in enumerate(actions)}
            finalists = []
            while completed < self.config.simulations:
                round_started = completed
                allocation = (1 if self.config.method == 'root' else
                              max(1, self.config.simulations // (rounds * len(considered))))
                for index in considered:
                    for _ in range(allocation):
                        if completed >= self.config.simulations:
                            break
                        if time.perf_counter() - started >= self.config.time_limit:
                            cutoff = 'search_time_budget'
                            break
                        before = time.perf_counter()
                        sampling_rng = self.simulation_rng if self.config.uses_belief else self.rng
                        world, observation = model.sample(sampling_rng.randrange(2**63))
                        timings['sampling'] += time.perf_counter() - before - world.timings['projection'] - world.timings['transition']
                        for key, seconds in world.timings.items():
                            timings[key] += seconds
                        world.timings = dict(transition=0., projection=0.)
                        node, branch = root, index
                        path = []
                        for depth in range(self.config.max_depth):
                            path.append((node, branch))
                            observation = world.step(observation, node.keys[branch])
                            for key, seconds in world.timings.items():
                                timings[key] += seconds
                            world.timings = dict(transition=0., projection=0.)
                            if observation is None:
                                tree_work['terminals'] += 1
                                value = world.terminal_value
                                break
                            key = branch, (public_key(observation) if self.config.uses_belief
                                           else observation_key(observation))
                            fresh = key not in node.children
                            if fresh:
                                node.children[key], _ = self._node(observation, timings, getattr(world, 'prepared', None))
                                tree_work['expansions'] += 1
                            node = node.children[key]
                            value = node.value
                            if fresh or self.config.method == 'root' or time.perf_counter() - started >= self.config.time_limit:
                                break
                            branch = node.select()
                        depth_key = str(len(path))
                        tree_work['depth_histogram'][depth_key] = tree_work['depth_histogram'].get(depth_key, 0) + 1
                        leaf_terminals_before = leaf_work['terminals']
                        if observation is not None and self.config.leaf_rollout_steps:
                            value = self._leaf_value(world, observation, node, timings, leaf_work,
                                                     started + self.config.time_limit)
                            if time.perf_counter() - started >= self.config.time_limit:
                                cutoff = 'search_time_budget'
                        kind = ('tree_terminals' if observation is None else
                                'leaf_terminals' if leaf_work['terminals'] > leaf_terminals_before else
                                'critic_bootstraps')
                        evidence[actions[index].ref][kind] += 1
                        evidence[actions[index].ref]['value_sum_squares'] += value * value
                        for owner, edge in path:
                            owner.counts[edge] += 1
                            owner.sums[edge] += value
                        completed += 1
                    if cutoff:
                        break
                scores = root.scores()
                values = root.completed()
                considered.sort(key=lambda i: (scores[i] + noise[i], -i), reverse=True)
                tree_work['root_rounds'].append(dict(
                    simulations_before=round_started, simulations_after=completed,
                    ranked=[actions[i].ref for i in considered],
                    visits={actions[i].ref: root.counts[i] for i in considered},
                    values={actions[i].ref: values[i] for i in considered},
                    scores={actions[i].ref: scores[i] + noise[i] for i in considered}))
                finalists = [i for i in considered if root.counts[i]]
                selected = considered[0]
                if cutoff:
                    break
                if self.config.method == 'gumbel':
                    # Keep the final two competing until the budget is spent.
                    # Collapsing to one early would make later evidence unable
                    # to change the winner (especially for small odd budgets).
                    considered = considered[:max(2, len(considered) // 2)]
            if not completed:
                reason = 'no_completed_simulation'
            elif self.config.final_selection == 'max_value':
                # Experimental final choice only: allocation, interior selection
                # and policy targets retain the same prior/value rule. Never
                # resurrect eliminated edges or compare unvisited imputations.
                selected = max(finalists, key=lambda i: (
                    root.sums[i] / root.counts[i], scores[i] + noise[i], -i))
        except UnsupportedSearch as error:
            reason = str(error)
        if reason:
            selected, probabilities = fallback, root.priors
        else:
            probabilities = root.improved()
        result = SearchResult(actions[selected].ref, {a.ref: p for a, p in zip(actions, probabilities)},
            {a.ref: q for a, q in zip(actions, root.completed())},
            {a.ref: n for a, n in zip(actions, root.counts)}, completed,
            time.perf_counter() - started, reason, timings, cutoff,
            leaf_work if self.config.leaf_rollout_steps else {}, tree_work)
        self.last_result = result
        self._last_decision = decision
        self.results.append(result)
        return result

    def __call__(self, decision):
        result = self.choose(decision)
        return next(a for a in decision.candidates if a.ref == result.action_ref)

    def summary(self):
        durations = sorted(r.seconds for r in self.results)
        result = dict(decisions=len(durations), searched=sum(r.reason is None for r in self.results),
                    fallbacks=dict(Counter(r.reason for r in self.results if r.reason)),
                    cutoffs=dict(Counter(r.cutoff for r in self.results if r.cutoff)),
                    simulations=sum(r.simulations for r in self.results),
                    seconds=sum(durations), p95_seconds=durations[min(len(durations)-1, math.ceil(.95*len(durations))-1)] if durations else 0.,
                    timings={k: sum(r.timings.get(k, 0.) for r in self.results)
                             for k in ('inference', 'reconstruction', 'sampling', 'transition', 'projection', 'conditioning')})
        if self.config.uses_belief:
            updates = self.belief.updates if self.belief is not None else []
            result['belief'] = dict(model=self.config.model_version, updates=len(updates),
                seconds=sum(u.elapsed for u in updates), proposals=sum(u.proposals for u in updates),
                replay_steps=sum(u.replay_steps for u in updates), recoveries=sum(u.recovered for u in updates),
                failures=dict(Counter(u.reason for u in updates if u.reason)))
        if self.config.leaf_rollout_steps:
            result['leaf_work'] = {key: sum(r.leaf_work.get(key, 0) for r in self.results)
                                   for key in ('steps', 'terminals', 'bootstraps', 'time_bootstraps')}
        return result

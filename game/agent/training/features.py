"""Versioned public graph features with frozen names and exact action mappings.

Opaque references only join graph nodes; their spelling/ordinals never become
features. The lossless encoding is retained separately from learned scalars.
"""
from dataclasses import dataclass, field
import hashlib
import json
import math

import numpy as np

from game.agent.contracts import full as f
from game.agent.action_policy import ALL_LEGAL, action_mask, validate_policy
from game.agent.encoding.full import FullRunEncoder

SCHEMA = 'sts_learned_public_graph_v1'
_FEATURE_ARRAYS = ('nodes', 'parents', 'positions', 'fields', 'numbers', 'links',
                   'link_positions', 'candidates')


@dataclass(frozen=True, slots=True)
class Vocabulary:
    names: tuple[str, ...]
    _identity: str = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        if (type(self.names) is not tuple or len(self.names) > 65536 or
                any(type(n) is not str or len(n.encode('utf-8')) > 256 for n in self.names) or
                self.names != tuple(sorted(set(self.names)))):
            raise ValueError('Expected a bounded, sorted, unique public vocabulary')
        object.__setattr__(self, '_identity', SCHEMA + ':' + hashlib.sha256(json.dumps(
            self.to_dict(), sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest())

    @classmethod
    def fit(cls, decisions, *, split):
        if split != 'train':
            raise ValueError('Fit vocabulary on training data only')
        names = set()
        for decision in decisions:
            if type(decision) is not f.PublicDecision:
                raise f.ContractError('Terminal outcomes have no policy vocabulary')
            f.require_ready(decision)
            for root in (decision.run, decision.context):
                for node in f.walk(root):
                    names.update((node.kind, node.definition_id))
                    names.update(v.key for v in node.fields)
                    names.update(v.value for v in node.fields if type(v.value) is str)
                    names.update(v.key for v in node.links)
        return cls(tuple(sorted(names)))

    def to_dict(self):
        return {'schema': SCHEMA, 'unknown_id': 0, 'names': list(self.names)}

    @classmethod
    def from_dict(cls, value):
        if (type(value) is not dict or set(value) != {'schema', 'unknown_id', 'names'} or
                value['schema'] != SCHEMA or type(value['unknown_id']) is not int or value['unknown_id'] != 0 or
                type(value['names']) is not list):
            raise ValueError('Unsupported feature vocabulary')
        return cls(tuple(value['names']))

    @property
    def identity(self):
        return self._identity


def _number(value):
    # The packed public graph keeps the exact integer; these two continuous
    # model features are explicitly lossy, without clipping large values.
    return float(value) / 100, math.copysign(math.log1p(abs(value)), value)


@dataclass(frozen=True, slots=True)
class RolloutFeatures:
    """Current learner inputs, without the duplicate lossless public encoding.

    Public observations and their full recordings remain model independent.
    Exact ordered references and the original legal mask retain PPO's mapping
    checks independently of the narrower policy mask.
    """
    vocabulary: str
    nodes: np.ndarray
    parents: np.ndarray
    positions: np.ndarray
    fields: np.ndarray
    numbers: np.ndarray
    links: np.ndarray
    link_positions: np.ndarray
    candidates: np.ndarray
    roots: tuple[int, int]
    action_policy: str
    policy_mask: tuple[bool, ...]
    candidate_refs: tuple[str, ...]
    legal_mask: tuple[bool, ...]

    @property
    def nbytes(self):
        return sum(getattr(self, key).nbytes for key in _FEATURE_ARRAYS)


@dataclass(frozen=True, slots=True)
class GraphFeatures:
    vocabulary: str
    graph: object
    nodes: np.ndarray
    parents: np.ndarray
    positions: np.ndarray
    fields: np.ndarray
    numbers: np.ndarray
    links: np.ndarray
    link_positions: np.ndarray
    candidates: np.ndarray
    roots: tuple[int, int]
    action_policy: str
    policy_mask: tuple[bool, ...]

    @property
    def nbytes(self):
        return (sum(getattr(self, key).nbytes for key in _FEATURE_ARRAYS) +
                sum(a.nbytes for a in self.graph.observation.values()))

    def for_rollout(self):
        return RolloutFeatures(self.vocabulary,
            *(getattr(self, key) for key in _FEATURE_ARRAYS),
            self.roots, self.action_policy, self.policy_mask, self.graph.candidate_refs,
            tuple(bool(v) for v in self.graph.observation['action_mask']))


class FeatureEncoder:
    def __init__(self, vocabulary, *, action_policy=ALL_LEGAL):
        if type(vocabulary) is not Vocabulary:
            raise ValueError('Expected frozen Vocabulary')
        self.vocabulary = vocabulary
        self.action_policy = validate_policy(action_policy)
        self.names = {name: i + 1 for i, name in enumerate(vocabulary.names)}
        self.public = FullRunEncoder()

    def encode(self, decision):
        return self._features(decision, self.public.pack(decision))

    def from_fixed(self, observation):
        decision = self.public.decode(observation)
        return self.encode(decision)

    def _features(self, decision, graph):
        if type(decision) is not f.PublicDecision:
            raise f.ContractError('Terminal observations have no policy features')
        # encode() supplies the graph from pack(), which fully validates this
        # decision before feature extraction. Do not repeat that round trip.
        nodes, parents, positions, refs = [], [], [], {}
        fields, numbers, links, link_positions = [], [], [], []

        def visit(node, parent, position):
            index = len(nodes)
            nodes.append(node)
            parents.append(parent)
            positions.append(_number(position))
            if node.ref is not None:
                refs[node.ref] = index
            for i, child in enumerate(node.children):
                visit(child, index, i)
            return index

        roots = (visit(decision.run, -1, 0), visit(decision.context, -1, 1))
        token = lambda name: self.names.get(name, 0)
        for index, node in enumerate(nodes):
            for field in node.fields:
                kind = {type(None): 0, bool: 1, int: 2, str: 3}[type(field.value)]
                fields.append((index, token(field.key), kind, token(field.value) if kind == 3 else 0))
                numbers.append(_number(field.value if kind in (1, 2) else 0))
            for link in node.links:
                # An empty link is observable and differs from an absent link.
                for order, target in enumerate(link.targets or (None,)):
                    namespace = f.NAMESPACES.index(target.split(':')[0]) + 1 if target else 0
                    links.append((index, token(link.key), refs.get(target, -1), namespace))
                    link_positions.append((*_number(order), float(target is not None)))
        by_ref = {a.ref: a for a in decision.candidates}
        permissions = dict(zip((a.ref for a in decision.candidates), action_mask(decision, self.action_policy)))
        candidates = []
        for ref in graph.candidate_refs:
            action = by_ref[ref]
            candidates.append((f.ACTIONS.index(action.kind),
                               refs[action.subject] if action.subject else -1,
                               refs[action.target] if action.target else -1))
        def array(rows, width, dtype=np.int64):
            result = np.array(rows, dtype=dtype).reshape(-1, width)
            result.flags.writeable = False
            return result
        return GraphFeatures(self.vocabulary.identity, graph,
            array([(token(n.kind), token(n.definition_id)) for n in nodes], 2),
            array(parents, 1), array(positions, 2, np.float32), array(fields, 4),
            array(numbers, 2, np.float32), array(links, 4), array(link_positions, 3, np.float32),
            array(candidates, 3), roots, self.action_policy,
            tuple(permissions[ref] for ref in graph.candidate_refs))


class _RolloutEncoder(FullRunEncoder):
    """Share one freshly packed decision inside the standard PPO environment.

    The fixed Gym arrays are separate allocations. The retained graph never
    accepts caller-supplied arrays, and belongs only to the exact decision that
    passed pack(). Standalone FeatureEncoder.encode() still validates its input.
    """

    def __init__(self, features):
        super().__init__(features.public.profile)
        self._features = features
        self.clear()

    def clear(self):
        self._decision = self._graph = self._prepared = None

    def encode(self, decision):
        self.clear()
        return self._remember(decision, self.pack(decision))

    def encode_prepared(self, decision, prepared):
        self.clear()
        return self._remember(decision, self._pack_prepared(decision, prepared), prepared)

    def _remember(self, decision, graph, prepared=None):
        fixed = self._pad(graph)
        if type(decision) is f.PublicDecision:
            self._decision, self._graph, self._prepared = decision, graph, prepared
        return fixed

    def prepared_for(self, decision):
        return self._prepared if decision is self._decision else None

    def features_for(self, decision):
        if self._decision is None or decision is not self._decision:
            raise f.ContractError('Prepared graph does not belong to this decision')
        return self._features._features(decision, self._graph)

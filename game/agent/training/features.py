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
from .combat_features import GRAPH, COMBAT_REPRESENTATIONS, feature_identity
from game.agent.input_views import RAW, apply_view, validate_view
from .catalog import ENTITY_KINDS, PublicCatalog

SCHEMA = 'sts_learned_public_graph_v1'
CATALOG_SCHEMA = 'sts_learned_public_graph_v2'
_FEATURE_ARRAYS = ('nodes', 'parents', 'positions', 'fields', 'numbers', 'links',
                   'link_positions', 'candidates')


@dataclass(frozen=True, slots=True)
class Vocabulary:
    names: tuple[str, ...]
    catalog: PublicCatalog | None = None
    _identity: str = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        if (type(self.names) is not tuple or len(self.names) > 65536 or
                any(type(n) is not str or len(n.encode('utf-8')) > 256 for n in self.names) or
                self.names != tuple(sorted(set(self.names)))):
            raise ValueError('Expected a bounded, sorted, unique public vocabulary')
        if self.catalog is not None:
            if type(self.catalog) is not PublicCatalog or not set(self.catalog.names) <= set(self.names):
                raise ValueError('Vocabulary must include its frozen public catalog')
        schema = CATALOG_SCHEMA if self.catalog is not None else SCHEMA
        object.__setattr__(self, '_identity', schema + ':' + hashlib.sha256(json.dumps(
            self.to_dict(), sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest())

    @classmethod
    def fit(cls, decisions, *, split, include_catalog=True):
        if split != 'train':
            raise ValueError('Fit vocabulary on training data only')
        if type(include_catalog) is not bool:
            raise ValueError('Expected a boolean catalog choice')
        from .catalog import public_catalog
        catalog = public_catalog() if include_catalog else None
        names = set(catalog.names) if catalog is not None else set()
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
        return cls(tuple(sorted(names)), catalog)

    def with_names(self, names):
        """Explicit new-learner expansion, retaining the frozen feature semantics."""
        return type(self)(tuple(sorted(set(self.names) | set(names))), self.catalog)

    def to_dict(self):
        result = {'schema': CATALOG_SCHEMA if self.catalog is not None else SCHEMA,
                  'unknown_id': 0, 'names': list(self.names)}
        if self.catalog is not None:
            result['catalog'] = self.catalog.to_dict()
        return result

    @classmethod
    def from_dict(cls, value):
        versioned = type(value) is dict and value.get('schema') == CATALOG_SCHEMA
        keys = {'schema', 'unknown_id', 'names'} | ({'catalog'} if versioned else set())
        if (type(value) is not dict or set(value) != keys or
                value['schema'] not in (SCHEMA, CATALOG_SCHEMA) or type(value['unknown_id']) is not int or value['unknown_id'] != 0 or
                type(value['names']) is not list):
            raise ValueError('Unsupported feature vocabulary')
        return cls(tuple(value['names']), PublicCatalog.from_dict(value['catalog']) if versioned else None)

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
    combat: np.ndarray | None = None
    roles: np.ndarray | None = None
    action_previews: np.ndarray | None = None
    preview_mode: int = 0
    input_view: str = RAW

    @property
    def nbytes(self):
        return sum(getattr(self, key).nbytes for key in _FEATURE_ARRAYS) + (
            self.combat.nbytes + self.roles.nbytes if self.combat is not None else 0) + (
            self.action_previews.nbytes if self.action_previews is not None else 0)


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
    combat: np.ndarray | None = None
    roles: np.ndarray | None = None
    action_previews: np.ndarray | None = None
    preview_mode: int = 0
    input_view: str = RAW

    @property
    def nbytes(self):
        return (sum(getattr(self, key).nbytes for key in _FEATURE_ARRAYS) +
                sum(a.nbytes for a in self.graph.observation.values()) +
                (self.combat.nbytes + self.roles.nbytes if self.combat is not None else 0) +
                (self.action_previews.nbytes if self.action_previews is not None else 0))

    def for_rollout(self):
        return RolloutFeatures(self.vocabulary,
            *(getattr(self, key) for key in _FEATURE_ARRAYS),
            self.roots, self.action_policy, self.policy_mask, self.graph.candidate_refs,
            tuple(bool(v) for v in self.graph.observation['action_mask']), self.combat, self.roles,
            self.action_previews, self.preview_mode, self.input_view)


def canonical_records(decision):
    """Whether canonical traversal can preserve this caller's reference order."""
    def canonical(node, depth=0):
        return (depth <= 24 and type(node) is f.Node
            and type(node.fields) is tuple and type(node.links) is tuple and type(node.children) is tuple
            and all(type(v) is f.Field for v in node.fields)
            and all(type(v) is f.Link for v in node.links)
            and all(canonical(v, depth + 1) for v in node.children))
    return (type(decision) is f.PublicDecision and canonical(decision.run) and canonical(decision.context)
            and type(decision.candidates) is tuple and all(type(v) is f.Candidate for v in decision.candidates))


class FeatureEncoder:
    def __init__(self, vocabulary, *, action_policy=ALL_LEGAL, representation=GRAPH, input_view=RAW):
        if type(vocabulary) is not Vocabulary:
            raise ValueError('Expected frozen Vocabulary')
        self.vocabulary = vocabulary
        self.input_view = validate_view(input_view, action_policy=action_policy)
        self.identity = feature_identity(vocabulary, representation, self.input_view)
        self.representation = representation
        self.action_policy = validate_policy(action_policy)
        self.names = {name: i + 1 for i, name in enumerate(vocabulary.names)}
        self.catalog_fields = ({(e.kind, e.definition_id): e.fields for e in vocabulary.catalog.entries}
                               if vocabulary.catalog is not None else {})
        self.public = FullRunEncoder()

    def encode(self, decision):
        if type(decision) is not f.PublicDecision:
            raise f.ContractError('Terminal observations have no policy features')
        decision = apply_view(decision, self.input_view)
        return self._features(decision, self.public.pack(decision))

    def encode_inference(self, decision):
        """Validated learned inputs with exactly the ordinary encoder's mapping.

        Keep lossless tables for their existing consumers. Structural caller
        records can declare fields in a different order, so they retain the
        original wire traversal rather than silently changing reference order.
        """
        if type(decision) is not f.PublicDecision:
            raise f.ContractError('Terminal observations have no policy features')
        if (type(self) is not FeatureEncoder or type(self.public) is not FullRunEncoder
                or 'encode' in vars(self) or '_features' in vars(self)
                or set(vars(self.public)) != {'profile'}
                or not canonical_records(decision)):
            return self.encode(decision).for_rollout()
        owner = f.PreparedPublic(apply_view(decision, self.input_view))
        mapping = self.public.mapping_prepared(owner.value, owner)
        return self._features(owner.value, mapping, compact=True)

    def encode_prepared(self, decision, owner):
        """Reuse exact immutable public ownership; never trust an equal copy."""
        if type(owner) is not f.PreparedPublic:
            raise f.ContractError('Expected a prepared public observation')
        owner.require(decision)
        if (type(self) is not FeatureEncoder or type(self.public) is not FullRunEncoder
                or 'encode' in vars(self) or 'encode_inference' in vars(self) or '_features' in vars(self)
                or set(vars(self.public)) != {'profile'}):
            return self.encode_inference(decision)
        viewed = apply_view(decision, self.input_view)
        if viewed is not decision:
            owner = f.PreparedPublic(viewed)
        mapping = self.public.mapping_prepared(owner.value, owner)
        return self._features(owner.value, mapping, compact=True)

    def from_fixed(self, observation):
        decision = self.public.decode(observation)
        return self.encode(decision)

    def validate_entity(self, node):
        if (self.vocabulary.catalog is not None and node.kind in ENTITY_KINDS
                and node.definition_id not in self.names):
            raise ValueError('Unknown learned entity identity: ' + node.kind + '/' + node.definition_id +
                             '; audit representation coverage before training')

    def _features(self, decision, graph, *, compact=False):
        if type(decision) is not f.PublicDecision:
            raise f.ContractError('Terminal observations have no policy features')
        # Both entry points validate before feature extraction: pack() for
        # lossless encoding, PreparedPublic plus bounded mapping for inference.
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
            self.validate_entity(node)
            # Learned enrichment only. The canonical graph/observation and all
            # physical references remain unchanged, including for recordings.
            metadata = self.catalog_fields.get((node.kind, node.definition_id), ())
            for field in node.fields + metadata:
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
        from .combat_features import channels
        combat, roles = channels(nodes, parents) if self.representation in COMBAT_REPRESENTATIONS else (None, None)
        from .action_features import channels as action_channels, mode
        preview_mode = mode(self.representation)
        previews = action_channels(decision, graph.candidate_refs, self.representation) if preview_mode else None
        common = (self.vocabulary.identity,
            array([(token(n.kind), token(n.definition_id)) for n in nodes], 2),
            array(parents, 1), array(positions, 2, np.float32), array(fields, 4),
            array(numbers, 2, np.float32), array(links, 4), array(link_positions, 3, np.float32),
            array(candidates, 3), roots, self.action_policy,
            tuple(permissions[ref] for ref in graph.candidate_refs))
        extra = (combat, roles, previews, preview_mode, self.input_view)
        if compact:
            return RolloutFeatures(*common, graph.candidate_refs, graph.legal_mask, *extra)
        return GraphFeatures(common[0], graph, *common[1:], *extra)


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
        if self._features.input_view != RAW:
            # The cached graph describes the original recorded observation.
            return self._features.encode(decision)
        return self._features._features(decision, self._graph)

"""Lossless public semantics in fixed tables, separate from action bindings.

References are replaced by local table indexes and candidates are sorted by
semantics. Raw reference ordinals and candidate names/order are not features.
Visible list order, duplicate physical entities and every public value survive.
"""
from dataclasses import dataclass, fields as dataclass_fields
import re

import numpy as np

from game.agent import contracts as c
from .schema import (ACTIONS, ARRAY, BOOLEAN, CapacityError, DEFAULT_PROFILE,
                     EncodingError, EncodingProfile, FIELDS, INTEGER, INTEGER_MAX,
                     NAMESPACES, NULL, OBJECT, OUTCOMES, REASONS, REFERENCE, TEXT)

_REF = re.compile(r'(' + '|'.join(NAMESPACES) + r'):[0-9]+\Z')


@dataclass(frozen=True, slots=True)
class EncodedDecision:
    observation: dict[str, np.ndarray]
    # Control-side correspondence only; never concatenate these names to features.
    candidate_refs: tuple[str, ...]
    reference_refs: tuple[str, ...]


class PublicEncoder:
    contract = c
    expected_format = 1
    tree_depth = 32
    fields = FIELDS
    actions = ACTIONS
    namespaces = NAMESPACES
    reference_pattern = _REF
    decision_schema = 'sts_public_decision_v1'
    decision_profile = 'combat_reward_map_v1'

    def __init__(self, profile: EncodingProfile = DEFAULT_PROFILE):
        if not isinstance(profile, EncodingProfile):
            raise TypeError('Expected EncodingProfile')
        if profile.layout[0] != self.expected_format:
            raise TypeError('Profile format differs from encoder vocabulary')
        self.profile = profile

    def empty(self):
        p = self.profile
        return self._tables(p.nodes, p.references, p.strings, p.candidates)

    def _tables(self, nodes, references, strings, candidates):
        p = self.profile
        return {
            'layout': np.array(p.layout, dtype=np.int64),
            'nodes': np.zeros((nodes, 5), dtype=np.int64),
            'node_mask': np.zeros(nodes, dtype=np.int8),
            'references': np.zeros((references, 2), dtype=np.int64),
            'reference_mask': np.zeros(references, dtype=np.int8),
            'strings': np.zeros((strings, p.string_bytes), dtype=np.uint8),
            'string_lengths': np.zeros(strings, dtype=np.int64),
            'string_mask': np.zeros(strings, dtype=np.int8),
            'candidates': np.zeros((candidates, 3), dtype=np.int64),
            'action_mask': np.zeros(candidates, dtype=np.int8),
            'outcome': np.zeros(2, dtype=np.int64),
        }

    def space(self):
        """Gymnasium is imported only when the consumer asks for Gym spaces."""
        from gymnasium import spaces
        arrays = self.empty()
        result = {}
        for key, array in arrays.items():
            if key.endswith('_mask'):
                result[key] = spaces.MultiBinary(array.shape)
            elif key == 'layout':
                result[key] = spaces.Box(array, array, dtype=array.dtype)
            else:
                low = -INTEGER_MAX if key == 'nodes' else 0
                high = 255 if key == 'strings' else INTEGER_MAX
                result[key] = spaces.Box(low, high, array.shape, dtype=array.dtype)
        return spaces.Dict(result)

    def collate(self, observations):
        """Stack a nonempty batch of this exact layout, without clipping rows."""
        observations = list(observations)
        if not observations:
            raise EncodingError('Cannot collate an empty batch')
        for observation in observations:
            self.decode(observation)
        return {key: np.stack([item[key] for item in observations]) for key in observations[0]}

    def encode(self, decision: c.PublicDecision | c.RunOutcome) -> EncodedDecision:
        return self._pad(self.pack(decision))

    def _pad(self, packed):
        """Pad a graph produced by this encoder's validated pack() call."""
        obs = self.empty()
        for key, value in packed.observation.items():
            obs[key][:len(value)] = value
        return EncodedDecision(obs, packed.candidate_refs, packed.reference_refs)

    def _ready_wire(self, decision):
        wire = self.contract.to_dict(decision)
        if not isinstance(decision, c.RunOutcome):
            self.contract.require_ready(decision)
        return wire

    def pack(self, decision: c.PublicDecision | c.RunOutcome) -> EncodedDecision:
        """The same validated traversal/canonicalization, allocating populated rows only.

        Capacity checks and exact integer/text/reference values are unchanged.
        Use encode() for fixed Gym shapes; pack() is for compact consumer storage.
        """
        return self._pack(decision, self._ready_wire(decision))

    def _pack(self, decision, wire, *, record_types=()):
        """Pack validated wire data, or canonical records from a prepared owner.

        Record traversal is private and opt-in: ordinary pack() still validates
        and traverses its wire value. Both paths emit the same ordered tables.
        """
        p = self.profile
        if isinstance(decision, c.RunOutcome):
            obs = self._tables(0, 0, 0, 0)
            obs['outcome'][:] = (OUTCOMES.index(decision.kind) + 1, REASONS.index(decision.reason) + 1)
            return EncodedDecision(obs, (), ())
        nodes, strings, references, definitions = [], {}, {}, {}
        field_ids = {}
        for index, name in enumerate(self.fields, 1):
            field_ids.setdefault(name, index)
        record_fields = {cls: tuple((field.name, field_ids.get(field.name))
                                   for field in dataclass_fields(cls))
                         for cls in record_types}
        node_capacity = p.nodes
        matches_reference = self.reference_pattern.fullmatch

        def check(dimension, required, capacity):
            if required > capacity:
                raise CapacityError(dimension, required, capacity)

        def reference(name):
            if name not in references:
                check('references', len(references) + 1, p.references)
                references[name] = len(references) + 1
            return references[name]

        def string(value):
            if value not in strings:
                data = value.encode('utf-8')
                check('string_bytes', len(data), p.string_bytes)
                check('strings', len(strings) + 1, p.strings)
                strings[value] = len(strings) + 1
            return strings[value]

        def visit(value, parent=0, field=0, position=0):
            index = len(nodes) + 1
            if index > node_capacity:
                raise CapacityError('nodes', index, node_capacity)
            row = [parent, field, position, 0, 0]
            nodes.append(row)
            if type(value) is dict:
                row[3] = OBJECT
                if value.get('ref') is not None:
                    reference(value['ref'])
                    definitions[value['ref']] = index
                for order, (key, child) in enumerate(value.items()):
                    field_id = field_ids.get(key)
                    if field_id is None:
                        raise EncodingError('Unsupported public field: ' + key)
                    visit(child, index, field_id, order)
            elif type(value) is list or (record_types and type(value) is tuple):
                row[3] = ARRAY
                for order, child in enumerate(value):
                    visit(child, index, 0, order)
            elif value is None:
                row[3] = NULL
            elif type(value) is bool:
                row[3:] = (BOOLEAN, int(value))
            elif type(value) is int:
                check('integer_magnitude', abs(value), INTEGER_MAX)
                row[3:] = (INTEGER, value)
            elif type(value) is str:
                row[3:] = (REFERENCE, reference(value)) if matches_reference(value) else (TEXT, string(value))
            else:
                attributes = record_fields.get(type(value))
                if attributes is None:
                    raise EncodingError('Unsupported public value type')
                row[3] = OBJECT
                ref = getattr(value, 'ref', None)
                if ref is not None:
                    reference(ref)
                    definitions[ref] = index
                for order, (name, field_id) in enumerate(attributes):
                    if field_id is None:
                        raise EncodingError('Unsupported public field: ' + name)
                    visit(getattr(value, name), index, field_id, order)

        visit({'run': wire['run'], 'context': wire['context']})
        return self._finish_pack(decision, nodes, strings, references, definitions)

    def _finish_pack(self, decision, nodes, strings, references, definitions):
        """Shared final tables and action ordering for both public traversals."""
        p = self.profile
        if len(decision.candidates) > p.candidates:
            raise CapacityError('candidates', len(decision.candidates), p.candidates)
        # Candidate order/opaque names carry no policy semantics. All arguments
        # must already have appeared in the complete public entity graph.
        rows = []
        for action in decision.candidates:
            try:
                rows.append(((self.actions.index(action.kind) + 1,
                              references[action.subject] if action.subject else 0,
                              references[action.target] if action.target else 0), action.ref))
            except KeyError as error:
                raise EncodingError('Candidate argument absent from public graph') from error
        rows.sort(key=lambda item: item[0])
        obs = self._tables(len(nodes), len(references), len(strings), len(rows))
        for value, index in strings.items():
            data = value.encode('utf-8')
            obs['strings'][index - 1, :len(data)] = np.frombuffer(data, dtype=np.uint8)
            obs['string_lengths'][index - 1] = len(data)
        obs['nodes'][:len(nodes)] = nodes
        obs['node_mask'][:len(nodes)] = 1
        obs['reference_mask'][:len(references)] = 1
        for name, index in references.items():
            obs['references'][index - 1] = (self.namespaces.index(name.split(':')[0]) + 1,
                                           definitions.get(name, 0))
        obs['string_mask'][:len(strings)] = 1
        obs['action_mask'][:len(rows)] = 1
        obs['candidates'][:len(rows)] = [row for row, _ in rows]
        return EncodedDecision(obs, tuple(name for _, name in rows), tuple(references))

    def decode(self, observation: dict[str, np.ndarray]) -> c.PublicDecision | c.RunOutcome:
        """Reconstruct public semantics with canonical local reference names.

        A strict canonical re-encoding checks masks, links, padding and vocabulary.
        This decodes observation data; it does not retain the original decision.
        """
        expected = self.empty()
        if type(observation) is not dict or observation.keys() != expected.keys():
            raise EncodingError('Encoding keys differ from this format')
        for key, value in observation.items():
            if (type(value) is not np.ndarray or value.shape != expected[key].shape or
                    value.dtype != expected[key].dtype):
                raise EncodingError('Encoding shape/dtype mismatch: ' + key)
        if not np.array_equal(observation['layout'], expected['layout']):
            raise EncodingError('Unsupported encoding version or capacities')
        obs = observation

        def count(key):
            mask = obs[key]
            n = int(np.count_nonzero(mask))
            if not np.all(mask[:n] == 1) or not np.all(mask[n:] == 0):
                raise EncodingError('Noncanonical mask: ' + key)
            return n

        try:
            if obs['outcome'][0]:
                kind, reason = map(int, obs['outcome'])
                if not 1 <= kind <= len(OUTCOMES) or not 1 <= reason <= len(REASONS):
                    raise EncodingError('Invalid outcome')
                result = c.RunOutcome('sts_run_outcome_v1', OUTCOMES[kind-1], REASONS[reason-1])
            else:
                nn, nr, ns, na = (count(key) for key in
                                  ('node_mask', 'reference_mask', 'string_mask', 'action_mask'))
                names = []
                for i, (namespace, _) in enumerate(obs['references'][:nr]):
                    if not 1 <= namespace <= len(self.namespaces):
                        raise EncodingError('Invalid reference namespace')
                    names.append(f'{self.namespaces[namespace - 1]}:{i}')
                texts = []
                for i in range(ns):
                    size = int(obs['string_lengths'][i])
                    if not 0 <= size <= self.profile.string_bytes:
                        raise EncodingError('Invalid text length')
                    texts.append(obs['strings'][i, :size].tobytes().decode('utf-8'))
                values, depths = [], []
                for i, node in enumerate(obs['nodes'][:nn], 1):
                    parent, field, order, kind, payload = map(int, node)
                    if not (0 <= parent < i and 0 <= field <= len(self.fields) and order >= 0):
                        raise EncodingError('Invalid public tree link')
                    depth = depths[parent-1] + 1 if parent else 0
                    if depth > self.tree_depth:
                        raise EncodingError('Public tree too deep')
                    depths.append(depth)
                    if kind == OBJECT:
                        value = {}
                    elif kind == ARRAY:
                        value = []
                    elif kind == NULL:
                        value = None
                    elif kind == BOOLEAN and payload in (0, 1):
                        value = bool(payload)
                    elif kind == INTEGER:
                        value = payload
                    elif kind == TEXT and 1 <= payload <= ns:
                        value = texts[payload-1]
                    elif kind == REFERENCE and 1 <= payload <= nr:
                        value = names[payload-1]
                    else:
                        raise EncodingError('Invalid public tree value')
                    if parent:
                        container = values[parent-1]
                        if type(container) is dict and field and order == len(container):
                            key = self.fields[field-1]
                            if key in container:
                                raise EncodingError('Duplicate public field')
                            container[key] = value
                        elif type(container) is list and not field and order == len(container):
                            container.append(value)
                        else:
                            raise EncodingError('Invalid public tree child')
                    elif i != 1 or field or order:
                        raise EncodingError('Invalid public tree root')
                    values.append(value)
                candidates = []
                for i, row in enumerate(obs['candidates'][:na]):
                    kind, subject, target = map(int, row)
                    if not (1 <= kind <= len(self.actions) and 0 <= subject <= nr and 0 <= target <= nr):
                        raise EncodingError('Invalid candidate link')
                    candidates.append({'ref': f'action:{i}', 'kind': self.actions[kind-1],
                                       'subject': names[subject-1] if subject else None,
                                       'target': names[target-1] if target else None})
                root = values[0]
                if type(root) is not dict or set(root) != {'run', 'context'}:
                    raise EncodingError('Invalid public tree root')
                result = self.contract.from_dict({'schema': self.decision_schema, 'profile': self.decision_profile,
                                      **root, 'candidates': candidates})
            canonical = self.encode(result).observation
        except (c.ContractError, IndexError, KeyError, UnicodeError, TypeError) as error:
            raise EncodingError('Malformed public encoding') from error
        if any(not np.array_equal(obs[key], canonical[key]) for key in expected):
            raise EncodingError('Noncanonical values, references, padding or masks')
        return result

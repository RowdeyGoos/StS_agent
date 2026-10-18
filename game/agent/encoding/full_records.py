"""Exact v2 table traversal for records owned by PreparedPublic.

The canonical public graph remains the source of truth. This only specializes
its fixed record layout; standalone inputs still use the validating wire path.
"""
from dataclasses import dataclass

import numpy as np

from .schema import (ARRAY, BOOLEAN, CapacityError, INTEGER, INTEGER_MAX, NULL,
                     OBJECT, REFERENCE, TEXT)


@dataclass(frozen=True, slots=True)
class DecisionMapping:
    """Public correspondence for learned inputs, without lossless tables."""
    candidate_refs: tuple[str, ...]
    reference_refs: tuple[str, ...]
    legal_mask: tuple[bool, ...]


def pack_records(encoder, decision, *, mapping_only=False):
    p = encoder.profile
    node_capacity, reference_capacity = p.nodes, p.references
    string_capacity, string_bytes = p.strings, p.string_bytes
    # Rows are five flat integers each; every row is reserved (counted and
    # capacity-checked) before its value is interned, as the table order requires.
    flat, strings, references, definitions = [], {}, {}, {}
    record = not mapping_only
    count = 0
    fields = {name: i for i, name in enumerate(encoder.fields, 1)}
    kind_field, definition_field, ref_field = fields['kind'], fields['definition_id'], fields['ref']
    fields_field, links_field, children_field = fields['fields'], fields['links'], fields['children']
    key_field, value_field, targets_field = fields['key'], fields['value'], fields['targets']
    matches_reference = encoder.reference_pattern.fullmatch
    is_reference = {}  # Pure per-text regex result; texts repeat heavily.

    def row(parent, field, position, kind, payload=0):
        nonlocal count
        count += 1
        if count > node_capacity:
            raise CapacityError('nodes', count, node_capacity)
        if record:
            flat.extend((parent, field, position, kind, payload))
        return count

    def reference(name):
        index = references.get(name)
        if index is None:
            index = len(references) + 1
            if index > reference_capacity:
                raise CapacityError('references', index, reference_capacity)
            references[name] = index
        return index

    def text(value, parent, field, position):
        nonlocal count
        count += 1
        if count > node_capacity:
            raise CapacityError('nodes', count, node_capacity)
        matched = is_reference.get(value)
        if matched is None:
            matched = is_reference[value] = matches_reference(value) is not None
        if matched:
            payload = references.get(value)
            if payload is None:
                payload = len(references) + 1
                if payload > reference_capacity:
                    raise CapacityError('references', payload, reference_capacity)
                references[value] = payload
            if record:
                flat.extend((parent, field, position, REFERENCE, payload))
        else:
            payload = strings.get(value)
            if payload is None:
                size = len(value.encode('utf-8'))
                if size > string_bytes:
                    raise CapacityError('string_bytes', size, string_bytes)
                payload = len(strings) + 1
                if payload > string_capacity:
                    raise CapacityError('strings', payload, string_capacity)
                strings[value] = payload
            if record:
                flat.extend((parent, field, position, TEXT, payload))

    def scalar(value, parent, field, position):
        if type(value) is str:
            text(value, parent, field, position)
        elif value is None:
            row(parent, field, position, NULL)
        elif type(value) is bool:
            row(parent, field, position, BOOLEAN, int(value))
        else:
            row(parent, field, position, INTEGER, value)
            if abs(value) > INTEGER_MAX:
                raise CapacityError('integer_magnitude', abs(value), INTEGER_MAX)

    def node(value, parent, field, position):
        index = row(parent, field, position, OBJECT)
        if value.ref is not None:
            reference(value.ref)
            if record:
                definitions[value.ref] = index
        text(value.kind, index, kind_field, 0)
        text(value.definition_id, index, definition_field, 1)
        scalar(value.ref, index, ref_field, 2)
        entries = row(index, fields_field, 3, ARRAY)
        for order, entry in enumerate(value.fields):
            item = row(entries, 0, order, OBJECT)
            text(entry.key, item, key_field, 0)
            item_value = entry.value
            if type(item_value) is str:
                text(item_value, item, value_field, 1)
            else:
                scalar(item_value, item, value_field, 1)
        links = row(index, links_field, 4, ARRAY)
        for order, link in enumerate(value.links):
            item = row(links, 0, order, OBJECT)
            text(link.key, item, key_field, 0)
            targets = row(item, targets_field, 1, ARRAY)
            for target_order, target in enumerate(link.targets):
                text(target, targets, 0, target_order)
        children = row(index, children_field, 5, ARRAY)
        for order, child in enumerate(value.children):
            node(child, children, 0, order)

    root = row(0, 0, 0, OBJECT)
    node(decision.run, root, fields['run'], 0)
    node(decision.context, root, fields['context'], 1)
    if mapping_only:
        rows = encoder._candidate_rows(decision, references)
        return DecisionMapping(tuple(name for _, name in rows), tuple(references), (True,) * len(rows))
    return encoder._finish_pack(decision, np.array(flat, dtype=np.int64).reshape(-1, 5), strings, references, definitions)

"""Exact v2 table traversal for records owned by PreparedPublic.

The canonical public graph remains the source of truth. This only specializes
its fixed record layout; standalone inputs still use the validating wire path.
"""
from dataclasses import dataclass

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
    nodes, strings, references, definitions = [], {}, {}, {}
    count = 0
    fields = {name: i for i, name in enumerate(encoder.fields, 1)}
    matches_reference = encoder.reference_pattern.fullmatch

    def row(parent, field, position, kind, payload=0):
        nonlocal count
        count += 1
        index = count
        if index > p.nodes:
            raise CapacityError('nodes', index, p.nodes)
        if not mapping_only:
            nodes.append([parent, field, position, kind, payload])
        return index

    def reference(name):
        index = references.get(name)
        if index is None:
            index = len(references) + 1
            if index > p.references:
                raise CapacityError('references', index, p.references)
            references[name] = index
        return index

    def text(value, parent, field, position):
        # Reserve the row before interning, preserving capacity-error ordering.
        index = row(parent, field, position, TEXT)
        if matches_reference(value):
            payload = reference(value)
            if not mapping_only:
                nodes[index - 1][3:] = REFERENCE, payload
        else:
            payload = strings.get(value)
            if payload is None:
                size = len(value.encode('utf-8'))
                if size > p.string_bytes:
                    raise CapacityError('string_bytes', size, p.string_bytes)
                payload = len(strings) + 1
                if payload > p.strings:
                    raise CapacityError('strings', payload, p.strings)
                strings[value] = payload
            if not mapping_only:
                nodes[index - 1][4] = payload

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
            if not mapping_only:
                definitions[value.ref] = index
        text(value.kind, index, fields['kind'], 0)
        text(value.definition_id, index, fields['definition_id'], 1)
        scalar(value.ref, index, fields['ref'], 2)
        entries = row(index, fields['fields'], 3, ARRAY)
        for order, entry in enumerate(value.fields):
            item = row(entries, 0, order, OBJECT)
            text(entry.key, item, fields['key'], 0)
            scalar(entry.value, item, fields['value'], 1)
        links = row(index, fields['links'], 4, ARRAY)
        for order, link in enumerate(value.links):
            item = row(links, 0, order, OBJECT)
            text(link.key, item, fields['key'], 0)
            targets = row(item, fields['targets'], 1, ARRAY)
            for order, target in enumerate(link.targets):
                text(target, targets, 0, order)
        children = row(index, fields['children'], 5, ARRAY)
        for order, child in enumerate(value.children):
            node(child, children, 0, order)

    root = row(0, 0, 0, OBJECT)
    node(decision.run, root, fields['run'], 0)
    node(decision.context, root, fields['context'], 1)
    if mapping_only:
        rows = encoder._candidate_rows(decision, references)
        return DecisionMapping(tuple(name for _, name in rows), tuple(references), (True,) * len(rows))
    return encoder._finish_pack(decision, nodes, strings, references, definitions)

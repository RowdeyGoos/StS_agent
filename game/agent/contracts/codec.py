"""Strict JSON boundary. The schema is an allowlist, never an engine snapshot."""
from dataclasses import fields, is_dataclass
from functools import lru_cache
import json
from types import UnionType
from typing import Literal, TypeVar, Union, get_args, get_origin, get_type_hints

from . import models as m


class ContractError(ValueError):
    """Malformed or unsupported public wire data; no action may be dispatched."""


MESSAGES = {
    'sts_public_decision_v1': m.PublicDecision,
    'sts_run_outcome_v1': m.RunOutcome,
    'sts_execution_report_v1': m.ExecutionReport,
}


@lru_cache(maxsize=128)
def _dataclass_schema(cls):
    """Cache only static class metadata, never input values or validation results.

    Resolve lazily so recursive forward references are available. TypeVars stay
    unresolved here: their substitutions belong to each individual parse.
    """
    return (frozenset(f.name for f in fields(cls)), tuple(get_type_hints(cls).items()),
            tuple(getattr(cls, '__parameters__', ())))


def _read(value, annotation, path, substitutions=None):
    return _reader(id(annotation), annotation)(value, path, substitutions or {})


def _invalid(path):
    raise ContractError(f'{path}: invalid value or type')


@lru_cache(maxsize=128)
def _record_readers(cls):
    # Resolve children lazily: recursive Node schemas must finish preparing their
    # own reader before asking for readers of their fields.
    return tuple((key, _reader(id(kind), kind)) for key, kind in _dataclass_schema(cls)[1])


@lru_cache(maxsize=128)
def _reader(identity, annotation):
    """Prepare schema work only; every call still checks its input values.

    Annotation identity is part of the key because unions compare equal even
    when their member order differs. Retaining the annotation prevents id reuse.
    Generic substitutions remain local to each parse, never captured here.
    """
    if isinstance(annotation, TypeVar):
        def variable(value, path, substitutions):
            kind = substitutions[annotation]
            if isinstance(kind, TypeVar):
                _invalid(path)
            return _reader(id(kind), kind)(value, path, substitutions)
        return variable
    if annotation in (str, int, bool, type(None)):
        def primitive(value, path, substitutions):
            if type(value) is annotation:
                return value
            _invalid(path)
        return primitive
    origin, args = get_origin(annotation), get_args(annotation)
    if origin is Literal:
        def literal(value, path, substitutions):
            if any(type(value) is type(v) and value == v for v in args):
                return value
            _invalid(path)
        return literal
    if origin in (Union, UnionType):
        readers = tuple((member, _reader(id(member), member)) for member in args)
        def union(value, path, substitutions):
            for member, read in readers:
                # Preserve member order without raising for scalar mismatches.
                if member in (str, int, bool, type(None)):
                    if type(value) is member:
                        return value
                    continue
                try:
                    return read(value, path, substitutions)
                except ContractError:
                    pass
            _invalid(path)
        return union
    if origin is tuple and len(args) == 2 and args[1] is Ellipsis:
        read = _reader(id(args[0]), args[0])
        def sequence(value, path, substitutions):
            if type(value) is list:
                return tuple(read(v, f'{path}[{i}]', substitutions) for i, v in enumerate(value))
            _invalid(path)
        return sequence
    if is_dataclass(origin or annotation):
        cls = origin or annotation
        names, _, parameters = _dataclass_schema(cls)
        def record(value, path, substitutions):
            if type(value) is not dict or value.keys() != names:
                raise ContractError(f'{path}: missing or extra {cls.__name__} fields')
            mapping = {**substitutions, **dict(zip(parameters, args))} if parameters else substitutions
            return cls(**{key: read(value[key], f'{path}.{key}', mapping)
                          for key, read in _record_readers(cls)})
        return record
    def unsupported(value, path, substitutions):
        _invalid(path)
    return unsupported


def from_dict(value):
    """Read one complete JSON-shaped message; unknown versions fail closed."""
    if type(value) is not dict or type(value.get('schema')) is not str or value['schema'] not in MESSAGES:
        raise ContractError('Unsupported or missing schema')
    result = _read(value, MESSAGES[value['schema']], '$')
    from .validation import validate_semantics
    validate_semantics(result)
    return result


@lru_cache(maxsize=128)
def _wire_fields(cls):
    return tuple(field.name for field in fields(cls))


def _wire(value):
    # Exact builtin values cannot be dataclass instances. Subclasses still take
    # the structural path below, as they did before this fast path.
    if type(value) in (str, int, bool, type(None)):
        return value
    if type(value) is tuple:
        return [_wire(v) for v in value]
    if is_dataclass(value) and not isinstance(value, type):
        return {name: _wire(getattr(value, name)) for name in _wire_fields(type(value))}
    raise ContractError('Expected immutable public values')


def to_dict(value):
    if type(value) not in MESSAGES.values():
        raise ContractError('Expected a public message')
    wire = _wire(value)
    from_dict(wire)
    return wire


def dumps(value):
    return json.dumps(to_dict(value), sort_keys=True, separators=(',', ':'), allow_nan=False)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ContractError(f'Duplicate JSON key: {key}')
        result[key] = value
    return result


def _invalid_constant(value):
    raise ContractError(f'Non-finite JSON constant: {value}')


def loads(text):
    try:
        wire = json.loads(text, object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
    except (TypeError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ContractError('Invalid JSON') from exc
    return from_dict(wire)

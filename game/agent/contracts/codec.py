"""Strict JSON boundary. The schema is an allowlist, never an engine snapshot."""
from dataclasses import fields, is_dataclass
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


def _read(value, annotation, path, substitutions=None):
    substitutions = substitutions or {}
    if isinstance(annotation, TypeVar):
        annotation = substitutions[annotation]
    origin, args = get_origin(annotation), get_args(annotation)
    if origin is Literal:
        if any(type(value) is type(v) and value == v for v in args):
            return value
    elif origin in (Union, UnionType):
        for member in args:
            try:
                return _read(value, member, path, substitutions)
            except ContractError:
                pass
    elif origin is tuple:
        if type(value) is list and len(args) == 2 and args[1] is Ellipsis:
            return tuple(_read(v, args[0], f'{path}[{i}]', substitutions) for i, v in enumerate(value))
    elif is_dataclass(origin or annotation):
        cls = origin or annotation
        if type(value) is not dict or set(value) != {f.name for f in fields(cls)}:
            raise ContractError(f'{path}: missing or extra {cls.__name__} fields')
        mapping = {**substitutions, **dict(zip(getattr(cls, '__parameters__', ()), args))}
        return cls(**{key: _read(value[key], kind, f'{path}.{key}', mapping)
                      for key, kind in get_type_hints(cls).items()})
    elif annotation in (str, int, bool, type(None)) and type(value) is annotation:
        return value
    raise ContractError(f'{path}: invalid value or type')


def from_dict(value):
    """Read one complete JSON-shaped message; unknown versions fail closed."""
    if type(value) is not dict or type(value.get('schema')) is not str or value['schema'] not in MESSAGES:
        raise ContractError('Unsupported or missing schema')
    result = _read(value, MESSAGES[value['schema']], '$')
    from .validation import validate_semantics
    validate_semantics(result)
    return result


def _wire(value):
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: _wire(getattr(value, f.name)) for f in fields(value)}
    if type(value) is tuple:
        return [_wire(v) for v in value]
    if type(value) in (str, int, bool, type(None)):
        return value
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

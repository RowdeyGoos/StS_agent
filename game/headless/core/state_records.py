"""Detached dataclass records for private engine snapshots.

Keep the default dataclasses.asdict copy semantics while avoiding deepcopy and
schema inspection for every immutable scalar. No state or result is cached.
"""
from copy import deepcopy
from dataclasses import fields, is_dataclass
from functools import lru_cache


@lru_cache(maxsize=128)
def _field_names(cls):
    return tuple(field.name for field in fields(cls))


def _copy_value(value):
    cls = type(value)
    # Exact builtins only: subclasses may be dataclasses or customize copying.
    if cls in (str, int, bool, float, type(None)):
        return value
    if cls is list:
        return [_copy_value(v) for v in value]
    if cls is tuple:
        return tuple(_copy_value(v) for v in value)
    if cls is dict:
        return {_copy_value(k): _copy_value(v) for k, v in value.items()}
    if is_dataclass(value) and not isinstance(value, type):
        return {key: _copy_value(getattr(value, key)) for key in _field_names(cls)}
    if isinstance(value, tuple) and hasattr(value, '_fields'):
        return cls(*(_copy_value(v) for v in value))
    if isinstance(value, (list, tuple)):
        return cls(_copy_value(v) for v in value)
    if isinstance(value, dict):
        return cls((_copy_value(k), _copy_value(v)) for k, v in value.items())
    return deepcopy(value)


def state_record(value):
    """Read current fields and return independently owned mutable containers.

    Preserve tuples, namedtuples, container subclasses and custom leaf copying.
    Validation remains with each snapshot owner, before/after this conversion.
    """
    if not is_dataclass(value) or isinstance(value, type):
        raise TypeError('Expected a dataclass instance')
    return _copy_value(value)

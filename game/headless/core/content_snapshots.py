"""Detached JSON for immutable content; never caches mutable game state."""

from dataclasses import fields, is_dataclass
import json


def immutable_content(value):
    if type(value) in (str, int, float, bool, type(None)):
        return True
    if type(value) is tuple:
        return all(immutable_content(item) for item in value)
    return (not isinstance(value, type) and is_dataclass(value)
            and value.__dataclass_params__.frozen
            and all(immutable_content(getattr(value, item.name)) for item in fields(value)))


class ContentJson:
    """One catalog-owned immutable representation with detached output containers.

    Callers supply ordered definition objects, not their mutable registry. Replacing,
    adding, removing or reordering a definition invalidates the entry. Mutable
    custom definitions (including lists inside frozen records) bypass caching.
    Retaining the source objects also prevents object-ID reuse from aliasing entries.
    """

    def __init__(self):
        self._entry = None

    def read(self, sources, build):
        sources = tuple(sources)
        entry = self._entry
        if self._current(sources):
            return json.loads(entry[1])
        result = build()
        if immutable_content(sources):
            encoded = json.dumps(result)
            # The decoded copy serves comparisons only; it is never returned.
            self._entry = (sources, encoded, json.loads(encoded))
            return json.loads(encoded)
        # Never return a cached result for mutable definitions, even when their
        # identities match a previous call. The builder provides fresh containers.
        return result

    def shared(self, sources, build):
        """The cached decoded value for read-only use (comparison or serialization).

        Never mutate it. Mutable definitions still get a fresh build."""
        sources = tuple(sources)
        if self._current(sources):
            return self._entry[2]
        return self.read(sources, build)

    def matches(self, value, sources, build):
        """`value == read(sources, build)` without detaching a fresh copy."""
        sources = tuple(sources)
        if self._current(sources):
            return value == self._entry[2]
        return value == self.read(sources, build)

    def _current(self, sources):
        entry = self._entry
        return (entry is not None and len(sources) == len(entry[0])
                and all(a is b for a, b in zip(sources, entry[0])))

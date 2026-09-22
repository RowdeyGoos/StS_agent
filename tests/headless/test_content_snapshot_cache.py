"""Content caching preserves exact values, isolation and compatibility rejection."""

from dataclasses import asdict, dataclass, replace
from copy import deepcopy

import pytest

from game.headless.core.content_snapshots import ContentJson
from game.headless.run import snapshots
from game.headless.run.engine import RunEngine
from game.headless.events import catalog as events
from game.headless.shops import catalog as shops


@pytest.mark.parametrize('module,read,builder,cache_name', [
    (snapshots, '_item_definitions', '_build_item_definitions', '_ITEM_JSON'),
    (events, 'fingerprint', '_build_fingerprint', '_CATALOG_JSON'),
    (shops, 'fingerprint', '_build_fingerprint', '_CATALOG_JSON'),
])
def test_frozen_content_reuses_build_and_returns_detached_json(monkeypatch, module, read, builder, cache_name):
    monkeypatch.setattr(module, cache_name, ContentJson())
    expected = getattr(module, builder)()
    value = getattr(module, read)()
    assert value == expected
    monkeypatch.setattr(module, builder, lambda: pytest.fail('Unchanged content rebuilt'))
    if module is snapshots:
        value['relics'][0]['definition_id'] = 'changed'
    elif module is events:
        value[0]['definition_id'] = 'changed'
    else:
        value['slots'][0]['items'][0][0] = 'changed'
    assert getattr(module, read)() == expected


@dataclass(frozen=True)
class Frozen:
    value: object


@dataclass
class Mutable:
    value: object


@pytest.mark.parametrize('definition', [Mutable(1), Frozen([1]), Frozen({'x': 1})])
def test_mutable_definitions_bypass_cache(definition):
    cache = ContentJson()
    build = lambda: asdict(definition)
    before = cache.read([definition], build)
    if isinstance(definition, Mutable):
        definition.value = 2
    elif isinstance(definition.value, list):
        definition.value.append(2)
    else:
        definition.value['x'] = 2
    assert cache.read([definition], build) == build() != before


def test_replacements_membership_and_order_invalidate_cache():
    cache = ContentJson()
    values = [Frozen(1), Frozen(2)]
    build = lambda: [asdict(v) for v in values]
    expected = cache.read(values, build)
    for change in (lambda: values.reverse(), lambda: values.append(Frozen(3)),
                   lambda: values.pop(0), lambda: values.__setitem__(0, Frozen(9))):
        change()
        actual = cache.read(values, build)
        assert actual == build() != expected
        expected = actual


@pytest.mark.parametrize('kind', ['relic', 'potion', 'event', 'shop', 'native_shop'])
def test_changed_catalog_rejects_previous_snapshot_atomically(monkeypatch, kind):
    run = RunEngine()
    original = run.snapshot()
    with monkeypatch.context() as patch:
        if kind in ('relic', 'potion'):
            attribute = 'RELICS' if kind == 'relic' else 'POTIONS'
            definitions = dict(getattr(snapshots, attribute))
            first = next(iter(definitions))
            patch.setattr(snapshots, attribute, definitions)
            # Warm against the same mutable registry before replacing a value.
            snapshots._item_definitions()
            definitions[first] = replace(definitions[first], definition_id='changed')
        elif kind == 'event':
            definitions = dict(events.EVENTS)
            patch.setattr(events, 'EVENTS', definitions)
            events.fingerprint()
            first = next(iter(definitions))
            definitions[first] = replace(definitions[first], definition_id='changed')
        else:
            from game.headless.generation import merchant
            module = shops if kind == 'shop' else merchant
            slots = module.SLOTS
            patch.setattr(module, 'SLOTS', (replace(slots[0], kind='changed'), *slots[1:]))
        current = run.snapshot()
        assert current != original
        with pytest.raises(ValueError):
            run.restore(original)
        assert run.snapshot() == current
    run.restore(original)
    assert run.snapshot() == original


def test_mutating_one_run_snapshot_cannot_change_another():
    first, second = RunEngine(), RunEngine()
    expected = second.snapshot()
    changed = first.snapshot()
    changed['items']['potions'][0]['effects'].clear()
    changed['events'][0]['definition_id'] = 'changed'
    changed['shops']['slots'][0]['items'].clear()
    assert second.snapshot() == expected
    second.restore(deepcopy(expected))
    assert second.snapshot() == expected

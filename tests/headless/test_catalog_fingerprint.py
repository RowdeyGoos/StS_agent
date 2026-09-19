"""Fingerprint reuse preserves custom-content changes and restore rejection."""

from dataclasses import dataclass, replace
from types import MappingProxyType

import pytest

from game.headless.cards import catalog
from game.headless.cards.base import CardDefinition, CardSpec
from game.headless.enchantments import base as enchantments
from game.headless.run.engine import RunEngine


def test_frozen_catalog_reuses_serialization_without_changing_equality(monkeypatch):
    cards = catalog.CardCatalog(catalog.DEFAULT_CARDS.definitions)
    other = catalog.CardCatalog(reversed(cards.definitions))
    expected = cards.snapshot_fingerprint()
    assert other.snapshot_fingerprint() == expected
    untouched = catalog.CardCatalog(cards.definitions)
    assert cards == untouched  # A warmed cache is not content identity.

    def unexpected_serialization(value):
        pytest.fail('An unchanged catalog was serialized again')

    monkeypatch.setattr(catalog, 'asdict', unexpected_serialization)
    assert cards.snapshot_fingerprint() == expected


@dataclass
class MutableEffect:
    amount: int = 1


@dataclass(frozen=True)
class NestedMutableEffect:
    amounts: list


@pytest.mark.parametrize('effect', [MutableEffect(), NestedMutableEffect([1])])
def test_mutable_custom_effects_never_leave_a_stale_fingerprint(effect):
    definition = CardDefinition('custom', (CardSpec('Custom', 0, 'skill'),), (effect,))
    cards = catalog.CardCatalog((definition,))
    before = cards.snapshot_fingerprint()
    if isinstance(effect, MutableEffect):
        effect.amount += 1
    else:
        effect.amounts.append(2)
    after = cards.snapshot_fingerprint()
    assert before != after
    assert after == catalog.CardCatalog((definition,)).snapshot_fingerprint()


def test_changed_values_and_effects_reject_old_snapshots_after_cache_warmup():
    original = catalog.DEFAULT_CARDS.definition('strike')
    first = catalog.CardCatalog((original,))
    run = RunEngine(cards=first, card_ids=['strike'])
    saved = run.snapshot()
    for changed in (
        replace(original, levels=(replace(original.levels[0], base_damage=999), *original.levels[1:])),
        replace(original, effects=()),
    ):
        cards = catalog.CardCatalog((changed,))
        other = RunEngine(cards=cards, card_ids=['strike'])
        before = other.snapshot()
        assert cards.snapshot_fingerprint() != first.snapshot_fingerprint()
        with pytest.raises(ValueError, match='card definitions'):
            other.restore(saved)
        assert other.snapshot() == before


def test_enchantment_changes_invalidate_warmed_fingerprint(monkeypatch):
    cards = catalog.CardCatalog((catalog.DEFAULT_CARDS.definition('strike'),))
    run = RunEngine(cards=cards, card_ids=['strike'])
    saved = run.snapshot()
    original = cards.snapshot_fingerprint()
    with monkeypatch.context() as patch:
        patch.setattr(enchantments, 'ENCHANTMENTS', MappingProxyType({
            **enchantments.ENCHANTMENTS,
            'custom': enchantments.EnchantmentDefinition('custom'),
        }))
        assert cards.snapshot_fingerprint() != original
        with pytest.raises(ValueError, match='card definitions'):
            run.restore(saved)
    assert cards.snapshot_fingerprint() == original
    run.restore(saved)
    assert run.snapshot() == saved


def test_unsupported_effect_still_fails_when_snapshotting():
    definition = CardDefinition('custom', (CardSpec('Custom', 0, 'skill'),), (object(),))
    cards = catalog.CardCatalog((definition,))
    with pytest.raises(ValueError, match='dataclass'):
        cards.snapshot_fingerprint()

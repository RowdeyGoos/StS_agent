"""Immutable content lookup; no global registration or name-based dispatch."""

from types import MappingProxyType
from dataclasses import asdict, is_dataclass, dataclass, field
from hashlib import sha256
import json
from game.headless.core.content_snapshots import immutable_content as _immutable_content
from game.headless.cards.base import Card, CardDefinition
from game.headless.cards.ironclad import DEFINITIONS as IRONCLAD
from game.headless.cards.status import DEFINITIONS as STATUSES
from game.headless.cards.curses import DEFINITIONS as CURSES
from game.headless.cards.ironclad_rare import DEFINITIONS as RARES
from game.headless.cards.ironclad_extended import DEFINITIONS as EXTENDED, GIANT_ROCK
from game.headless.cards.colorless import DEFINITIONS as COLORLESS
from game.headless.cards.event_cards import DEFINITIONS as EVENT_CARDS
from game.headless.cards.extended_events import DEFINITIONS as EXTENDED_EVENTS
from game.headless.cards.ancient import DEFINITIONS as ANCIENT


@dataclass(frozen=True, slots=True, init=False)
class CardCatalog:
    _definitions: object
    _cacheable: bool = field(compare=False, repr=False)
    _snapshot_cache: tuple[str, str] | None = field(compare=False, repr=False)

    def __init__(self, definitions) -> None:
        definitions = tuple(definitions)
        by_id = {definition.definition_id: definition for definition in definitions}
        if len(by_id) != len(definitions):
            raise ValueError("Duplicate card definition ID.")
        object.__setattr__(self, "_definitions", MappingProxyType(by_id))
        object.__setattr__(self, "_cacheable", _immutable_content(definitions))
        object.__setattr__(self, "_snapshot_cache", None)

    @property
    def definitions(self) -> tuple[CardDefinition, ...]:
        return tuple(self._definitions.values())

    def definition(self, definition_id: str) -> CardDefinition:
        try:
            return self._definitions[definition_id]
        except KeyError as error:
            raise ValueError(f"Unsupported card definition: {definition_id!r}.") from error

    def create(self, definition_id: str, *, upgrade_level: int = 0, instance_id: str | None = None) -> Card:
        return Card(self.definition(definition_id), upgrade_level=upgrade_level, instance_id=instance_id)

    def snapshot_fingerprint(self) -> str:
        """Bind values/effect composition automatically, without per-card profiles.

        Snapshots still require the same game-rule implementation; this is not
        an executable-source provenance certificate or a release manifest.
        """
        from game.headless.enchantments.base import fingerprint

        enchantments = fingerprint()
        enchantment_key = json.dumps(enchantments, sort_keys=True, separators=(",", ":"))
        cached = self._snapshot_cache
        if cached is not None and cached[0] == enchantment_key:
            return cached[1]
        rows = []
        for definition in sorted(self.definitions, key=lambda d: d.definition_id):
            effects = []
            for effect in definition.effects:
                if not is_dataclass(effect):
                    raise ValueError("Snapshotable card effects must be immutable dataclass values.")
                effects.append([type(effect).__module__ + "." + type(effect).__qualname__, asdict(effect)])
            rows.append([definition.definition_id, [asdict(level) for level in definition.levels], effects, definition.combat_lifetime, definition.rarity, definition.pool, definition.strike, definition.defend, definition.generate_in_combat])
        result = sha256(json.dumps({"cards": rows, "enchantments": enchantments}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if self._cacheable:
            # Derived content only: no run state, global cache or snapshot-format change.
            object.__setattr__(self, "_snapshot_cache", (enchantment_key, result))
        return result

    def __deepcopy__(self, memo):
        return self


from game.headless.cards.hive import DEFINITIONS as HIVE

IRONCLAD_CARDS = CardCatalog((*IRONCLAD, *HIVE, *STATUSES, *CURSES, *RARES, *EVENT_CARDS, *EXTENDED_EVENTS, *COLORLESS, *EXTENDED, GIANT_ROCK, *(d for d in ANCIENT if d.pool in ('colorless','status'))))

# Explicit family subsets remain useful for restricted fixtures.
from game.headless.cards.silent import DEFINITIONS as SILENT
SILENT_CARDS = CardCatalog((*IRONCLAD_CARDS.definitions, *SILENT, *(d for d in ANCIENT if d.pool == 'silent')))

from game.headless.cards.regent import DEFINITIONS as REGENT
REGENT_CARDS = CardCatalog((*SILENT_CARDS.definitions, *REGENT, *(d for d in ANCIENT if d.pool == 'regent')))

from game.headless.cards.necrobinder import DEFINITIONS as NECROBINDER
NECROBINDER_CARDS = CardCatalog((*REGENT_CARDS.definitions, *NECROBINDER, *(d for d in ANCIENT if d.pool == 'necrobinder')))

from game.headless.cards.defect import DEFINITIONS as DEFECT
DEFECT_CARDS = CardCatalog((*NECROBINDER_CARDS.definitions, *DEFECT, *(d for d in ANCIENT if d.pool == 'defect')))

# Complete ordinary solo content, including cards acquired from other characters.
DEFAULT_CARDS = DEFECT_CARDS

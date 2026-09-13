"""Immutable content lookup; no global registration or name-based dispatch."""

from types import MappingProxyType
from dataclasses import asdict, is_dataclass, dataclass
from hashlib import sha256
import json
from game.headless.cards.base import Card, CardDefinition
from game.headless.cards.ironclad import DEFINITIONS as IRONCLAD
from game.headless.cards.status import DEFINITIONS as STATUSES
from game.headless.cards.ironclad_rare import DEFINITIONS as RARES


@dataclass(frozen=True, slots=True, init=False)
class CardCatalog:
    _definitions: object

    def __init__(self, definitions) -> None:
        definitions = tuple(definitions)
        by_id = {definition.definition_id: definition for definition in definitions}
        if len(by_id) != len(definitions):
            raise ValueError("Duplicate card definition ID.")
        object.__setattr__(self, "_definitions", MappingProxyType(by_id))

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
        rows = []
        for definition in sorted(self.definitions, key=lambda d: d.definition_id):
            effects = []
            for effect in definition.effects:
                if not is_dataclass(effect):
                    raise ValueError("Snapshotable card effects must be immutable dataclass values.")
                effects.append([type(effect).__module__ + "." + type(effect).__qualname__, asdict(effect)])
            rows.append([definition.definition_id, [asdict(level) for level in definition.levels], effects, definition.combat_lifetime])
        from game.headless.enchantments.base import fingerprint
        return sha256(json.dumps({"cards": rows, "enchantments": fingerprint()}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def __deepcopy__(self, memo):
        return self


DEFAULT_CARDS = CardCatalog((*IRONCLAD, *STATUSES, *RARES))

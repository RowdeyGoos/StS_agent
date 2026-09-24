"""Immutable, backend-independent public values for the first decision profile.

No native tokens, engine commands, seeds or private continuation records belong
here. Validate at serialization boundaries with the package's codec.
"""
from dataclasses import dataclass
from typing import Generic, Literal, TypeVar

T = TypeVar('T')
Character = Literal['ironclad', 'silent', 'regent', 'necrobinder', 'defect']


@dataclass(frozen=True, slots=True)
class Observed(Generic[T]):
    status: Literal['known', 'unknown', 'not_applicable']
    value: T | None = None


def known(value: T) -> Observed[T]:
    return Observed('known', value)


def unknown() -> Observed:
    return Observed('unknown')


def not_applicable() -> Observed:
    return Observed('not_applicable')


@dataclass(frozen=True, slots=True)
class Counter:
    key: str
    amount: int


@dataclass(frozen=True, slots=True)
class Cost:
    energy: Observed[int]
    energy_x: bool
    stars: Observed[int]
    stars_x: bool


@dataclass(frozen=True, slots=True)
class Card:
    ref: str
    definition_id: str
    upgrade_level: int
    cost: Cost
    # Resolved public dynamic values/modifiers; labels are vocabulary keys.
    values: Observed[tuple[Counter, ...]]
    modifiers: Observed[tuple[Counter, ...]]
    origin: Observed[str]  # Known deck original, otherwise N/A or unknown.


@dataclass(frozen=True, slots=True)
class Relic:
    ref: str
    definition_id: str
    counters: Observed[tuple[Counter, ...]]


@dataclass(frozen=True, slots=True)
class Potion:
    ref: str
    definition_id: str


@dataclass(frozen=True, slots=True)
class PotionSlot:
    index: int
    potion: Potion | None  # An explicitly known empty slot.


@dataclass(frozen=True, slots=True)
class Intent:
    kind: str
    damage: Observed[int]
    hits: Observed[int]


@dataclass(frozen=True, slots=True)
class Power:
    ref: str
    definition_id: str
    amount: int
    counters: Observed[tuple[Counter, ...]]


@dataclass(frozen=True, slots=True)
class Enemy:
    ref: str
    definition_id: str
    hp: int
    max_hp: int
    block: int
    powers: Observed[tuple[Power, ...]]
    intents: Observed[tuple[Intent, ...]]


@dataclass(frozen=True, slots=True)
class Osty:
    hp: int
    max_hp: int
    block: int
    powers: Observed[tuple[Power, ...]]


@dataclass(frozen=True, slots=True)
class OstyState:
    creature: Osty | None  # Known absence before a summon is not missing data.


@dataclass(frozen=True, slots=True)
class Orb:
    ref: str
    kind: str
    passive: int
    evoke: int


@dataclass(frozen=True, slots=True)
class CharacterResources:
    stars: Observed[int]
    sovereign_blades: Observed[tuple[str, ...]]  # Damage belongs to each card.
    osty: Observed[OstyState]
    orb_slots: Observed[int]
    orbs: Observed[tuple[Orb, ...]]  # Native queue order is meaningful.


@dataclass(frozen=True, slots=True)
class MapNode:
    ref: str
    row: int
    column: int
    kind: Literal['combat', 'elite', 'boss', 'event', 'unknown', 'rest', 'shop', 'treasure', 'ancient']
    next_nodes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Map:
    current: Observed[str]
    nodes: tuple[MapNode, ...]


@dataclass(frozen=True, slots=True)
class HistoryEvent:
    kind: Literal['card_played', 'end_turn', 'card_selected', 'selection_confirmed', 'reward_opened', 'reward_claimed',
                  'reward_skipped', 'map_selected', 'combat_ended']
    subject: Observed[str]
    target: Observed[str]
    values: tuple[Counter, ...]


@dataclass(frozen=True, slots=True)
class History:
    coverage: Literal['run_start', 'attachment']
    events: tuple[HistoryEvent, ...]


@dataclass(frozen=True, slots=True)
class Run:
    character: Character
    ascension: int
    act: int  # One-based act number.
    floor: int
    hp: int
    max_hp: int
    gold: int
    deck: Observed[tuple[Card, ...]]
    relics: Observed[tuple[Relic, ...]]
    potions: Observed[tuple[PotionSlot, ...]]
    map: Observed[Map]
    history: Observed[History]


@dataclass(frozen=True, slots=True)
class Pile:
    kind: Literal['hand', 'draw', 'discard', 'exhaust', 'in_play', 'powers']
    count: int
    cards: Observed[tuple[Card, ...]]
    order: Literal['visible', 'canonical']  # Draw order is always canonical.


@dataclass(frozen=True, slots=True)
class Combat:
    kind: Literal['combat']
    round: int
    block: int
    energy: int
    powers: Observed[tuple[Power, ...]]
    resources: CharacterResources
    enemies: tuple[Enemy, ...]
    piles: tuple[Pile, ...]


@dataclass(frozen=True, slots=True)
class CardSelection:
    kind: Literal['card_selection']
    combat: Combat  # Preserve combat context while its parent action is pending.
    source: Observed[str]
    pile: Literal['discard', 'exhaust']
    options: tuple[str, ...]  # References into the indicated public pile.
    selected: tuple[str, ...]
    minimum: int
    maximum: int
    manual_confirmation: bool
    cancelable: bool


@dataclass(frozen=True, slots=True)
class Reward:
    ref: str
    kind: Literal['gold', 'card', 'potion', 'relic']
    presentation: Literal['summary', 'choice']
    amount: Observed[int]
    cards: Observed[tuple[Card, ...]]
    potion: Observed[Potion]
    relic: Observed[Relic]
    resolved: bool


@dataclass(frozen=True, slots=True)
class Rewards:
    kind: Literal['rewards']
    entries: tuple[Reward, ...]


@dataclass(frozen=True, slots=True)
class MapChoice:
    kind: Literal['map']
    reachable: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Candidate:
    ref: str
    kind: Literal['play_card', 'end_turn', 'select_card', 'deselect_card',
                  'confirm_selection', 'cancel_selection', 'claim_reward', 'open_card_reward',
                  'choose_reward_card', 'skip_reward', 'leave_rewards', 'choose_map_node']
    subject: str | None = None
    target: str | None = None


@dataclass(frozen=True, slots=True)
class PublicDecision:
    schema: Literal['sts_public_decision_v1']
    profile: Literal['combat_reward_map_v1']
    run: Run
    context: Combat | CardSelection | Rewards | MapChoice
    candidates: tuple[Candidate, ...]


@dataclass(frozen=True, slots=True)
class RunOutcome:
    schema: Literal['sts_run_outcome_v1']
    kind: Literal['victory', 'defeat', 'abandoned', 'truncated']
    reason: Literal['none', 'decision_budget', 'time_budget', 'slice_complete', 'act_complete', 'external_stop']


@dataclass(frozen=True, slots=True)
class ExecutionReport:
    schema: Literal['sts_execution_report_v1']
    status: Literal['pending', 'reconciled', 'rejected', 'unsupported', 'uncertain', 'faulted']
    mutation: Literal['none', 'queued', 'applied', 'unknown']
    reason: Literal['none', 'stale_decision', 'invalid_action', 'missing_public_fields',
                    'unsupported_version', 'unsupported_capability', 'transport_failure',
                    'cleanup_failure', 'deadline']

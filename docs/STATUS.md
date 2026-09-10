# Current integration status

Updated 2026-09-10. This page owns current capability and operational evidence;
[roadmap](../ROADMAP.md) owns priorities and [AGENTS.md](../AGENTS.md) owns workflow.

## Checkout and current operation

Use the current checkout. The representative September 9–10 live batch is complete
and **no test bridge remains installed**. Normal quit, owned quarantine/purge and
**429 unchanged base files with zero overlays** passed. Earlier installations were
also cleaned up. Exact attempts, corrections, timings and cleanup identities stay
in the [combined live record](evidence/COMBINED_BRIDGE_LIVE_2026_09_09.md), rather
than being repeated as a development queue here.

The retained accepted release is
`c6670ae435c0d1ba33af202d89b693fa7bfd469da988a2b3462d09e1cdfd0eb5`, built from
`23cbff0d38a18b866c94531f8b23a57b3bb030e0` (314 verified source/test inputs).
Its final **71 release groups passed in 371.191 seconds**: 7,896 native assertions,
125 host tests, 450 C#/Python cases (388 native), 809 shared checks, reproducible
packaging and owned installation/cleanup fixtures. The
[current release record](../bridge/Sts2AgentBridge/releases/current/README.md)
retains manifest and validation evidence. Later checkout changes do not repin
those accepted build inputs. The event-combat
features below are not in this retained release.

## Current capability and evidence

Live evidence below is representative, not all-branch coverage or an autonomous
full-run result. Automatic parent effects generally remain unverified even when
the selected child effect and map return are verified.

| Capability | Evidence and practical limit |
| --- | --- |
| Combat → rewards → map | Both gold/card choose and Skip policies passed live; bounded combat/choice/reward counts and map checks; no complete autonomous run |
| Combat discard/exhaust choices | Neow's Fury zero and two-card choices plus resumed victories passed; other fixed/exhaust callers remain fixture-only |
| Rest and shop | Heal/Proceed, Smith upgrade-one and bounded purchase/close/map demonstrated |
| Generic options and repeated pages | Shared parent/children; Abyssal Baths two Lingers and exit passed |
| Changes around selectors | Grave/Confront append-before-selection and Amalgamator two removals plus one separate grant passed; broader compositions remain open |
| Upgrades | Single off-screen upgrade at slot 20 in a 23-card domain passed; fixed counts 1–8 have fixtures, multi-upgrade live remains open |
| Enchantment | Sapphire Seed/Sown and Grave/SoulsPower single selection, Prickly Sponge fixed-two Steady passed; other counts/callers remain narrower |
| Transformation | Allocated off-screen input, Wood Carvings/Bird and Claws zero/three/six passed; Torus remains a branch candidate |
| Add-card grids | Cheese add-two and Sea Glass zero/three/fifteen passed |
| Ordinary card rewards | Brain Leech singleton and Colorful Philosophers three menus with choose/Skip/choose and final dismissal passed |
| Potion/relic rewards | Singleton collection and Potion Courier three-potion set passed; full inventories and nested pickup interactions remain unsupported |
| Mixed card/item sets | Lost Coffer potion→card choose and Skip/final-dismissal passed; native/host fixtures cover 2–8 entries and other orders |
| Ancient options and dialogue | Console-selected ancient options and map return passed; dialogue before/after pickup has fixtures, natural entry/dialogue and normal Darv pool eligibility retain narrower evidence |
| Optional card offers | Lead Paperweight choose/Skip without extra cards passed; Hefty Tablet choose/Skip plus Injury passed on preceding release `c73fde6c` |
| Required card offers | `card_offer_v1` has fixtures; no required-choice caller identified in the bounded retained inspection (Lead Paperweight/Massive Scroll allow Skip and use v2) |
| Bundles | Scroll Boxes three-card bundle, native preview/Confirm and map return passed |
| Inactive combat layout | Punch Off/Nab and Meal Ticket collection passed; this does not demonstrate its combat branch |
| Non-resuming event combat | Implemented offline in the checkout; exact combat ownership transfer, protocol v9 destination and event/combat/reward/map host composition; not released or live-demonstrated |
| Event combat resumption | Implemented offline: exact resume Task/new event node, retained cleanup ownership, training expiry as event return, and combat/event/map composition; no interactive resume children or live acceptance |
| Initial event-option policy | `--event-option` chooses an exact legal first option and stops if absent/illegal; subsequent actions use first-legal policy |
| Results acknowledgment | Pandora's Box nine-card screen Confirm/map passed; preceding automatic transformations are not certified |
| Reduced headless/actor stack | Structural backend and cloning pipeline accepted; no target-game fidelity or learned live-policy claim |

One production bridge in `apps/bridge/` combines shared components and original
core adapters. Modules remain exclusive until native reconciliation and successful
disposal; uncertain mutations or failed disposal stop the host. There are no
mutation retries. `event-map`, `combat-map` and `event-combat-map` preserve prior
stage evidence if a later stage fails. The legacy public-screen reader is not a map-readiness probe.

Checkout validation for event-combat resumption and option targeting passed:
15 focused event groups in 311.784 seconds (7,987 native assertions, 128 host
tests, 450 C#/Python cases), 10 host groups in 10.2 seconds (856 shared assertions,
38 client tests and socket integration including event resume), and the production
build in 1.582 seconds. The focused resume suite contributes 66 native checks,
including callback timing, wrong identities, failure/cancellation and cleanup
interference. An independent semantic review found no remaining blockers after
the cleanup correction. These are offline development results, not a new release
or live acceptance. [The contract](GENERIC_EVENTS.md#implemented-offline-event-combat-resumption)
describes ownership, host composition and remaining limits.

## Next work and remaining limits

The user prioritizes generic event coverage before longer-run orchestration.
Pending live cases: Dense Vegetation’s Fight page after Rest through rewards/map,
and Battleworn Dummy Setting2/training expiry through resumed Proceed/map.
Next implementation: interactive resume children, such as Setting1’s potion
offer; extra-reward event entries also remain unsupported. Further work includes
full potion inventories, nested pickups, broader deck changes around selectors,
custom screens (Crystal Sphere/Fake Merchant), special rewards, abandonment
confirmation and terminal progression. See the [research map](EVENT_INTERACTION_MAP.md)
and [roadmap](../ROADMAP.md) for callers and priorities.

Separate validation from implementation: multi-upgrades, additional enchantment
counts, held-out callers, natural ancient entry/dialogue, elite continuation and
longer room/run composition still need representative evidence. Unallocated-card
input, variable upgrades, native cancellation and enchantment stacking/replacement
need a concrete caller/setup before new infrastructure. Optional zero selection
is confirmation, not cancellation.

One earlier startup `invalid_response` remains unexplained. Later live failures
from reward ordering and singleton indices were corrected in test policies; the
production bridge supported the observed shapes. Reusable policies and precise
failure diagnostics remain useful tooling work. Historical failures and exact
successful evidence remain in the live record.

Profile/save/preference/history/Cloud filesystem access and unpinned builds are
outside ordinary development; see the [live guide](LIVE_DEVELOPMENT.md).

## Relevant code and semantic references

Paths in the first column are relative to `bridge/Sts2AgentBridge/`.

| Location | Responsibility |
| --- | --- |
| `apps/bridge/client/reward_host.py`, `run_live.py` | Bounded reward resolution and combat/reward/map composition |
| `components/cards/combat/`, `components/cards/combat_native/`, `apps/bridge/client/combat_host.py` | Combat selector protocol, native binding and bounded combat/choice host |
| `components/events/native/GenericEventV7Hooks.cs`, `GenericEventV7Binding.cs` | Owned native discovery and parent/child identity |
| `components/events/native/PinnedGenericEventV7NativeAdapter.cs` | Parent capture and child integration |
| `components/events/native/GenericEventV7TransformState.cs` | Native transformation effect observations |
| `components/events/host/generic_event_host.py`, `card_transform_host.py` | Bounded orchestration and replaceable decisions |
| `components/events/native/GenericEventV7TransformAdapter.cs` | Generalized direct input for eligible allocated holders |
| `components/events/direct_input_tests/`, `apps/bridge/client_tests/` | Actual adapter and shared-client cases |
| `apps/bridge/production/Sts2AgentBridge.csproj`, `check.py` at the bridge root | Single production composition and focused/current release checks |

- [G7 semantics](archive/phase-1/PHASE_1_GENERIC_EVENT_V7_CONTRACT.md) and
  [functional evidence](archive/phase-1/research/PHASE_1_GENERIC_EVENT_V7_ACCEPTANCE.md).
- [V10 test contract](archive/phase-1/PHASE_1_GENERIC_EVENT_RELEASE_V10_CONTRACT.md),
  [current bridge guide](../bridge/Sts2AgentBridge/README.md)
  and [acceptance](archive/phase-1/research/PHASE_1_GENERIC_EVENT_RELEASE_V10_ACCEPTANCE.md).
- [Event coverage matrix](EVENT_COVERAGE.md),
  [card-reward live evidence](archive/phase-1/research/PHASE_1_GENERIC_EVENT_RELEASE_V5_ACCEPTANCE.md)
  and [potion live evidence](archive/phase-1/research/PHASE_1_GENERIC_EVENT_V6_POTION_COURIER_LIVE.md).
- [Earlier live/headless integration evidence](archive/phase-1/research/PHASE_1_NEXT_INCREMENT_ACCEPTANCE.md)
  and [actor-ready/diagnostic evidence](archive/phase-1/research/PHASE_1_ACTOR_READY_ACCEPTANCE.md).
- [Shop/event evidence](archive/phase-1/research/PHASE_1_SHOP_MAP_PERMISSION_V1_ACCEPTANCE.md)
  and [card-selection evidence](archive/phase-1/research/PHASE_1_CARD_SELECTION_COMPLETION_V1_ACCEPTANCE.md).

For builds, locate the existing Python environment and the selected checker's
pinned SDK inputs (current releases use .NET SDK 9.0.303). Temporary tool paths
may have expired. The pinned game is v0.107.1, Steam build23811903, macOS arm64;
verify through its manifest before live work. Do not provision or launch the game
merely to update documentation.

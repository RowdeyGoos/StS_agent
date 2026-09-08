# Current integration status

Updated 2026-09-08. This is the single current capability/evidence and operational
handoff page. [AGENTS.md](../AGENTS.md) owns workflow; [roadmap](../ROADMAP.md) owns
priorities. Historical acceptance ledgers retain exact artifact identities.

## Checkout and current operation

Main includes the integrated generic-handler work. Use the user's current checkout
and inspect Git state; do not switch to the historical 23cf worktree.

The unified module smoke is complete and all three installations are cleaned up.
Representative paths covered combat (one UI-assisted chooser), rewards, map, shop,
Smith/card selection, a singleton potion and a generic event/card child. Two real
integration bugs were corrected: safe stale combat rejections stopped the host,
and the shared client rejected valid shop action names. A console-created Smith
setup was rejected; native map entry passed with unchanged card code.
The [active live record](research/PHASE_1_UNIFIED_BRIDGE_LIVE.md) owns the exact
artifact/state identities, bounded results, assistance and cleanup evidence.

The preceding successful feature campaign is release v10, implementation `6978943`,
successful result and cleanup `dc5dbfc`. It selected native holder slot15
(card16) in the user's controlled 20-card Aroma of Chaos/Let Go setup without
scrolling, verified the exact original in preview, confirmed transformation and
returned to the map. One invocation resolved with one completed card child,
two parent and two child actions, six reads and `map_ready`.
[Exact result](research/PHASE_1_GENERIC_EVENT_RELEASE_V10_ACCEPTANCE.md#live-result-direct-card16-selection-passed-campaign-closed).

That campaign is closed. Its final checks found the game stopped, listener closed,
429 unchanged base files, zero overlays and four generated files removed.
These are historical observations; verify current runtime state before new live
operations. Old credentials, campaign hashes and readiness cannot be reused.

## Current capability and evidence

| Capability | Evidence and practical limit |
| --- | --- |
| Combat, rewards and map | Bounded live observation/control, combat completion, reward progression and fresh reward/map entry; no complete autonomous run |
| Rest and shop | Standalone heal/Proceed, older Smith upgrade-one, one bounded shop purchase/close/map path live-demonstrated |
| Generic event parent/children | Shared native discovery and orchestration; successful bounded paths through Dense Vegetation, Cheese, Potion Courier and Aroma |
| Card rewards | Positive variable counts up to eight in native/controller fixtures; Cheese/Gorge add-two live in release v5 |
| Removal | Positive variable counts up to eight in native/controller fixtures |
| Upgrades | Fixed counts 1–8 in native/controller fixtures; older Smith single-upgrade live |
| Transformation | Fixed and positive variable counts up to eight in G7 fixtures; fixed-one card16 live in release v10 |
| Singleton potion/relic rewards | G6/G7 native/controller fixtures; Potion Courier/Ransack potion live in release v6 |
| Allocated off-screen transform holder | Direct selection demonstrated in the controlled v10 setup; other selector families and unallocated cards are separate questions |
| Reduced headless/actor stack | Deterministic backend, public encoder, trusted datasets, masked candidate scorer and cloning smoke accepted on structural data; no target-game parity or learned live-policy claim |

Event identities supply ownership and test coverage, not a production admission
list for each supported shared interaction. No event has complete all-branch
evidence. Choice strategy remains a replaceable host decision provider.

The current production artifact is **Sts2AgentBridgeUnified 1.0.0**. It combines
core combat/reward/map/rest, item collection, room flows, card selection and
generic events in one mod, listener and owner-frame queue. Native modules are
created lazily and remain exclusive through reconciliation and successful cleanup.
A failed/uncertain mutation or failed disposal stops the shared host. Confirmed
no-mutation stale rejections allow a fresh decision. Clean completion
allows the next capability without replacing or restarting the mod.

The canonical transformation adapter now offers all eligible allocated holders
using the successful direct-input mechanism. The card16-only restriction is gone;
identity, legality, preview, deferred-input and completion checks remain.
Direct-input fixtures exercise different slots and invalid/deferred targets.
The [current release evidence](../bridge/Sts2AgentBridge/releases/current/README.md)
records offline native/host regressions, shared socket handoff and failure cases,
actual Python clients, reproducible packaging and owned cleanup fixtures.
The unified package demonstrated the representative paths above. The successful
shop client correction is now in the maintained source. Generic orchestration
resolved with one completed card child, but its final `effects` summary remained
`unverified`; the legacy public-screen probe reported unsupported/unknown after
that controlled event/map setup. These limits remain explicit in the live record.

Only `apps/bridge/` is a production composition. The old four feature apps and
separate original production project are retired. Use one checker with focused
`--component` selection, one package identity and one client/operational entry
point. Historical sources and earlier release records remain in Git; original
identities remain in [release history](../bridge/Sts2AgentBridge/releases/history/README.md).

## Next bounded target

Close an actual smoke-test gap: the optional in-combat card chooser or legacy
public-screen coverage after generic event entry. Clarify the generic summary's
final effect-verification distinction before broadening its claim. Reuse the
completed module evidence; a further native test should answer a different question.
Do not repeat V7/V8/V9 geometry admission work:
those attempts stopped before input, and V10 answered the direct-selection question.
The [generic plan](PHASE_1_GENERIC_EVENT_HANDLER_PLAN.md) distinguishes implemented
behavior from remaining native coverage.

## Current exclusions

Optional/zero selection, variable upgrades, multiple-item sets, incomplete holder
coverage, custom/repeated interactions and event combat remain generic gaps.
Variable transformation has offline evidence but no variable-count live case.
Elite continuation and complete room/run composition remain broader open evidence
targets. A successful fixed-one event does not certify all selectors or deck sizes.

Profile/save/preference/history/Cloud filesystem access, retained live corpora,
unpinned builds and a near-optimal/full-run claim are outside ordinary development.
The [live guide](LIVE_DEVELOPMENT.md) owns operational and user-data boundaries.

## Relevant code and semantic references

Paths in the first column are relative to `bridge/Sts2AgentBridge/`.

| Location | Responsibility |
| --- | --- |
| `components/events/native/GenericEventV7Hooks.cs`, `GenericEventV7Binding.cs` | Owned native discovery and parent/child identity |
| `components/events/native/PinnedGenericEventV7NativeAdapter.cs` | Parent capture and child integration |
| `components/events/native/GenericEventV7TransformState.cs` | Native transformation effect observations |
| `components/events/host/generic_event_host.py`, `card_transform_host.py` | Bounded orchestration and replaceable decisions |
| `components/events/native/GenericEventV7TransformAdapter.cs` | Generalized direct input for eligible allocated holders |
| `components/events/direct_input_tests/`, `apps/bridge/client_tests/` | Actual adapter and shared-client cases |
| `apps/bridge/production/Sts2AgentBridge.csproj`, `check.py` at the bridge root | Single production composition and focused/current release checks |

- [G7 semantics](PHASE_1_GENERIC_EVENT_V7_CONTRACT.md) and
  [functional evidence](research/PHASE_1_GENERIC_EVENT_V7_ACCEPTANCE.md).
- [V10 test contract](PHASE_1_GENERIC_EVENT_RELEASE_V10_CONTRACT.md),
  [current bridge guide](../bridge/Sts2AgentBridge/README.md)
  and [acceptance](research/PHASE_1_GENERIC_EVENT_RELEASE_V10_ACCEPTANCE.md).
- [Event coverage matrix](research/PHASE_1_EVENT_COVERAGE_MATRIX.md),
  [card-reward live evidence](research/PHASE_1_GENERIC_EVENT_RELEASE_V5_ACCEPTANCE.md)
  and [potion live evidence](research/PHASE_1_GENERIC_EVENT_V6_POTION_COURIER_LIVE.md).
- [Earlier live/headless integration evidence](research/PHASE_1_NEXT_INCREMENT_ACCEPTANCE.md)
  and [actor-ready/diagnostic evidence](research/PHASE_1_ACTOR_READY_ACCEPTANCE.md).
- [Shop/event evidence](research/PHASE_1_SHOP_MAP_PERMISSION_V1_ACCEPTANCE.md)
  and [card-selection evidence](research/PHASE_1_CARD_SELECTION_COMPLETION_V1_ACCEPTANCE.md).

For builds, locate the existing Python environment and the selected checker's
pinned SDK inputs (current releases use .NET SDK 9.0.303). Temporary tool paths
may have expired. The pinned game is v0.107.1, Steam build23811903, macOS arm64;
verify through its manifest before live work. Do not provision or launch the game
merely to update documentation.

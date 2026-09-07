# Generic event v3

Shared native handling for event upgrades, deck removal and reward-card offers
whose selected originals are added to the deck. Interaction rules come from owned
game requests and screen creation, with no event-name or option-key registrations.

| Family | Selection limits | Native completion |
| --- | --- | --- |
| Upgrade | Exactly one | Preview and confirm |
| Remove | 1 <= min <= max <= 8 | Preview, then confirm |
| Reward add, automatic | 1 <= min <= max <= 8 | Final select at exactly max; no early confirmation |
| Reward add, manual | 1 <= min <= max <= 8 | Confirm at min through max; no preview |

All domains are complete, visible, larger than max and at most 64 cards. All modes
are noncancelable. Optional zero, scrolling, repeated-key choices, transformations,
multi-upgrades, item children, custom screens and event combat remain unsupported.
This component preserves v2 behavior and all sixteen predecessors byte for byte.

The [contract](../../../../docs/PHASE_1_GENERIC_EVENT_V3_CONTRACT.md) specifies two-
stage admission. Reserve exact parent context and complete baseline deck before
choosing an option. Capture authoritative request originals/preferences and owned
screen/task identities before publishing an immutable child description. Clients
and decision providers cannot create native rules. Stops after dispatch preserve
attempts, receipts and unverified effects, without retries after uncertainty.

For reward offers, capture exact CardCreationResult entries and their effective
Card references, keys and levels. These originals must be absent from the baseline
deck and remain unchanged through creation and control. Native sorting may change
slot order; exact membership stays bound. Both task results must identify the same
selected original set, and the parent callback must complete successfully. The
actual frozen card session verifies only those originals were added and every
baseline card retained identity, order, key and level. Partial additions can progress
while completion is pending. Changed or extra cards cannot produce success.

The reward request selects cards; it does not itself add them. This family verifies
the selected-card postcondition. It does not separately bind CardPileCmd.Add tasks,
certify all animations or unrelated HP/gold effects, or prove global card novelty.

## Components and protocol

- `core/`: bounded event parent, immutable admission and actual frozen card session.
- `native/`: seven exclusive observational hooks and native family adapters. Original
  methods always run; no private fields or argument/result replacement are used.
- `wire/`: exact publications, child descriptors, receipts and mode-specific checks.
- `host/`: Python 3.10+ controller with an immutable injected decision provider.
- Test directories: inert hook fixtures, malformed protocol cases and production
  native-to-Python composition, including mixed interaction families.

Outer protocol: `generic_event_v3`. Routes:
`/probe/generic-event-v3/public/decision` and
`/probe/generic-event-v3/public/action`. Child payloads remain `card_selection_v1`.
Python entry point: `run_event(request, provider=...)`; `first_legal` is an explicit
fixture policy. There is no listener or installation entry point.

## Offline validation

Use SDK 9.0.303, pinned target references and the exact Harmony 2.4.2 package in
`dependency.json`. The checker validates sixteen predecessors and the original
bridge, exact derivation diffs and explicit project inputs. It runs inert fixtures
and compares compile-only native builds. It downloads nothing, executes no target
assemblies and writes outputs only into fresh disposable snapshots.

```sh
python -B bridge/Sts2AgentBridge/successors/generic_event_v3/check.py \
  --dotnet /absolute/path/to/dotnet \
  --game-data-dir /absolute/path/to/pinned/game/data \
  --harmony-package /absolute/path/to/lib.harmony.2.4.2.nupkg \
  --scratch /private/tmp/generic-event-v3-new-check
```

The scratch directory must not exist. Exact evidence is retained in the
[acceptance ledger](../../../../docs/research/PHASE_1_GENERIC_EVENT_V3_ACCEPTANCE.md).
No third-party binary is committed; retain Harmony's MIT license in any future
distribution. No package or live release is provided. Real EventSynchronizer
context preservation remains a live acceptance gate; lost ownership stops safely.

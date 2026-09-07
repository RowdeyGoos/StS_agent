# Generic event lifecycle v1

Native correction for event option buttons that the game removes after dispatch.
The final predispatch reservation validates the live button; later hooks and card
adapters retain it only as an opaque action receipt. All logical parent, scoped
Chosen/request/creation, task, deck, offer and selector ownership checks remain.
No event-name admission rules or global ownership fallback are introduced.

The component derives four native files from frozen generic_event_v3, preserving
their type names as explicit source replacements. Core, wire, hooks, parent adapter
and card rules/session are source-linked unchanged. Do not reference the old
native assembly alongside this replacement assembly. All eighteen predecessors
and their source identities remain frozen.

The retained game metadata establishes the lifecycle mismatch. Reproduction with
old sources and corrected native/host fixtures establishes the offline correction;
neither identifies the only cause of the previous live failure nor establishes
actual EventSynchronizer scope preservation. See the
[contract](../../../../docs/PHASE_1_GENERIC_EVENT_LIFECYCLE_V1_CONTRACT.md),
[evidence](../../../../docs/research/PHASE_1_GENERIC_EVENT_LIFECYCLE_V1_EVIDENCE.md)
and [acceptance ledger](../../../../docs/research/PHASE_1_GENERIC_EVENT_LIFECYCLE_V1_ACCEPTANCE.md).

## Offline validation

```sh
python -B bridge/Sts2AgentBridge/successors/generic_event_lifecycle_v1/check.py \
  --dotnet /absolute/path/to/dotnet \
  --game-data-dir /absolute/path/to/pinned/game/data \
  --scratch /private/tmp/a-new-lifecycle-gate
```

Requires Python3.10+, SDK9.0.303 and the exact pinned game dependency files.
The checker uses disposable offline snapshots. It verifies all predecessor source
identities, exact derivation and Compile closures, reproduces the old rejection,
runs the preserved native assertions plus lifecycle regressions, drives corrected
native code through frozen wire/Python with retired buttons, and compares two
compile-only native builds. Inert fixtures execute the pinned game Harmony with
stubs; sts2.dll and GodotSharp.dll are never executed. No download, installation,
credential, profile/save, game launch or live request is part of this checker.

This functional component is not an installable bridge. A new release composition
and verified fresh campaign are needed for another live test. The prior campaign
was cleaned up; do not reuse its state hashes or retry its controller invocation.

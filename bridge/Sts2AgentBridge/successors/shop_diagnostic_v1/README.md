# Passive shop diagnostic V1

This separate successor identifies the first rejected predicate in the existing
shop reader. It does not repair shop behavior or execute gameplay actions. The
selected scope is [the diagnostic contract](../../../../docs/PHASE_1_SHOP_DIAGNOSTIC_V1_CONTRACT.md).
All seven predecessor source trees and the old 48 bridge inputs remain frozen.

The production assembly contains a passive native reader, initial projector,
fixed enum recorder/codec, and a single-observation transport. It never compiles
the original full shop session, purchase dispatch or pending reconciliation.
The reference session and native adapter appear only in tests with authored
stubs; target assemblies and the production candidate are never executed by
offline checks. The derivation manifest binds original/derived source hashes,
ordered predicates, readiness substitutions and omitted action methods.

Exactly one authenticated GET is available:
`/probe/shop-diagnostic-v1/public/diagnostic`. The owner frame captures once;
all delivery outcomes terminalize the transport, which settles network work
before owner-frame service disposal and Godot detachment. There is no action
route, POST, polling or retry. The response is five canonical fields:

```json
{"schema_version":1,"status":"passed","shop_status":"unsupported","stage":"native_offers","reason":"cost_text_invalid"}
```

This is an illustrative enum combination, not a live result. `status=passed`
means the diagnostic completed. `shop_status` describes ready, waiting or
unsupported. No content, card names, keys, prices, gold, identifiers, exception
text, logs or counts leave the reader. A transport failure claims no diagnosis.

## Offline release gate

Use Python 3.10+ and the pinned .NET SDK 9.0.303:

```text
python -B -I -S check.py --dotnet /absolute/path/to/dotnet --game-data-dir /absolute/path/to/pinned/data --scratch /private/tmp/absent-diagnostic-check
```

The gate verifies all frozen inventories, old bridge identities, exact reviewed
project inputs and shared build properties. It makes two physical source and
reference snapshots and requires byte-identical production builds. Pure tests
cover actual reader/getter-order and frozen-projector parity, strict enum and
wire behavior, actual C#/Python ephemeral sockets, one-observation cleanup,
operator reads, transactional operations, predecessor conflicts and source
derivations. A whole-assembly metadata/IL verifier and actual PE mutations
check the passive surface, source closure and exact policy. Package checks and
synthetic base/overlay checks exercise the actual final candidate. Offline
success establishes fixture and artifact evidence, not live shop success.

`source_identity.json` freezes this tree. `policy/shop_diagnostic_policy.json`
binds the 24 production source inputs and complete metadata/IL projection.
`package/release_package.py` pins the canonical DLL, manifest and deterministic
ZIP. Publishing is exclusive under `/private/tmp/sts-shop-diagnostic-v1-release`
and is separate from the offline gate; existing artifacts are never adopted or
overwritten. Only the coordinator publishes or starts a campaign after acceptance.

## Bounded live procedure

Standing user authorization covers a fresh diagnostic campaign when needed.
Confirm availability and keep the game closed for installation. Validate the
exact package/source, clean 429-file base, stopped game/closed port and absence
of predecessor/current operator, state and overlay conflicts. Use only the
fixed diagnostic manager; it writes fresh state and credential under its own
scope, with no flow option. Never read profile/save files or change Steam Cloud.

Ask the user to launch Profile 3, continue Ironclad Ascension 0 and stop at the
merchant inventory with untouched offers and no popup. The saved shop from the
prior zero-action rejection is acceptable; this is a new read-only observation.
Inspect the supported game UI, then invoke `client/run_live.py` exactly once with
`--expected-state-sha256` set to the newly installed state hash. Do not retry on
any uncertain delivery or reuse a historical campaign state.

Record only the bounded enum result and sanitized campaign evidence. Quit the
game normally through supported UI, verify stopped/closed, quarantine code
first, purge the exact four generated files, then verify the unchanged base and
fixed absences. Complete cleanup within 30 minutes of installation. The user
waived repeated unmodded relaunch checks; all other cleanup remains required.
No campaign or retained live corpus is created by the offline gate.

# Card selection v1

Isolated successor for parent-bound event card selection and ordinary rest-site
smithing. All nine predecessor components and the original 0.8.0 bridge remain
unchanged. This is development code; it is not an installed or live-tested release.

The shared pure core supports add, remove, upgrade and transform with explicit
selection cardinalities, complete deck witnesses and operation-specific effect
reconciliation. Events can require multiple cards. Rest accepts upgrade only,
with exactly one card. Initial native policies are narrowly bound to:

- Room Full of Cheese / Gorge: choose exactly two of eight offered cards; the
  second selection commits automatically, followed by the event's Proceed.
- Ordinary rest-site Smith with SmithCount=1: select one eligible deck card,
  confirm its upgrade preview, then use the restored Proceed.

Other event callers, native removal/transform, multi-card native upgrade,
scrolling/paging, deselection, cancellation and unexpected overlays are unsupported.
The complete eligible domain must be visible. Duplicate card definitions are
supported through distinct retained card identities and stable slots.

`core/` owns immutable public values and selection/effect state. `native/` reads
only statically witnessed public game/UI state and dispatches retained public
controls. `parents/` owns begin → bound child → restored parent → Proceed → map.
`parent_native/` supplies the exact native parent bindings. `wire/` implements the
four bounded in-process routes in [schema.md](wire/schema.md); `host/` consumes
those routes through injected transport. Tests use synthetic values or native
source compiled against test stubs. The real game/Godot assemblies are reference
inputs only and are never executed by the offline gate.

The controller verifies selection counts, receipts, action histories, final deck
effects and the separate parent map handoff. It reserves before each dispatch,
never retries an uncertain action, and has finite action, read and time limits.
It selects the first available legal cards for conformance testing; strategic
card selection is a future host policy concern.

The offline gate verifies exact source inventories, reviewed project bytes,
compile closure and all frozen predecessors; runs the pure suites and actual
C#/Python composition; and compiles the native adapters twice in fresh physical
scratch directories with deterministic output comparison. Run from this checkout:

```sh
python3 -B -I -S bridge/Sts2AgentBridge/successors/card_selection_v1/check.py \
  --dotnet /absolute/path/to/pinned/dotnet \
  --game-data-dir /absolute/path/to/pinned/game/data \
  --scratch /private/tmp/a-new-card-selection-gate
```

Requires the accepted offline .NET SDK 9.0.303 and the exact pinned game assemblies
listed in the [development scope](../../../../docs/PHASE_1_CARD_SELECTION_DEVELOPMENT.md).
The scratch directory must not exist. No package sources are contacted. The
checker has no install, launch, profile, save, Cloud, credential or live-client path.

Release composition, owner-frame transport, secure operator lifecycle, exact
artifact verifier, package and campaign tooling must be completed and reviewed
before live testing. A compile pass or a synthetic flow is not live evidence.
The [contract](../../../../docs/PHASE_1_CARD_SELECTION_V1_CONTRACT.md) and
[acceptance ledger](../../../../docs/research/PHASE_1_CARD_SELECTION_V1_ACCEPTANCE.md)
record the precise scope and current evidence.

The initial source manifest is generated deterministically by `freeze_sources.py`
only after exact project review and predecessor preservation checks. It uses
exclusive creation and refuses to replace an existing identity or include build
outputs. This source freeze is separate from later package/release acceptance.

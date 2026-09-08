# Phase 1 event coverage census scope

- Date: 2026-09-06
- Status: proposed; synthetic census tooling is fixture-passing, but no target census has run
- Baseline: `7e57bb668f838cb39aa782c6d9edf05c7fdd6d36`
- Evidence boundary: repository evidence and disposable synthetic metadata only

## Purpose and current boundary

The user requested progress toward coverage of all events. Before selecting more
native callers, establish a mechanical denominator for the pinned build's event
models, custom event nodes and event layouts. Names are inventory, not semantic
classification. This packet does not infer a capability from an event name,
inspect any target method body, execute either target assembly, or change a
runtime, package, operator state or live campaign.

Existing evidence proves ordinary standard-event choices and final Proceed/map,
one bound potion/relic reward child, RoomFullOfCheese/Gorge add-two, and ordinary
Smith upgrade-one. It does not prove another event card caller, multi-card event
upgrade, removal, transformation, embedded-combat continuation, a custom event,
or a minigame. The accepted card core can fixture-test add/remove/upgrade/
transform at multiple cardinalities; that is not native event coverage.

## Exact census input and tool

A new disposable tool is derived from the accepted card-selection v2 inspector's
bounded file-image and PEReader pattern. Its only target mode accepts a file named
`sts2.dll`, reads one regular non-symlink/reparse image of 1..100,000,000 bytes,
zeros that image on every post-read path, and compares SHA-256 to the fixed pinned
identity before constructing `PEReader`:

`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.

The target path must be the coordinator's manifest-bound installed path. The
fixture mode accepts only a physical child of the executable's disposable
`fixtures` directory and still requires a caller-supplied lowercase SHA-256.
It exists only to validate metadata classification without opening the target.
Failures emit a fixed schema/code and no exception, path, metadata or content.

Tool source identities:

- `Program.cs`: `bba9b372c6f911e944aa57c7a8ff0bd7132acb2bf6666761ae64ac3430be0b1b`
- `EventCensus.csproj`: `14c2b17719a82cc63e0bbcb76760ff5af20b710ab3f295b5ae825c1f7b3d4adc`
- `NuGet.Config`: `5256a7e3e07d2c5c94f7a1e6c45f39aab011c659c5e2d53e452dea525ce04575`
- `run_fixtures.py`: `2b6e91bda6ae535c07593ff12dc50da643aaf64373b34490bf0ceac3c390b034`
- complete disposable source manifest: `d14e9fa142843840ae419782b8093c8e51f50f4cd9396116b195e66392ab8ab1`

Build only with the existing isolated .NET SDK 9.0.303, an explicit NuGet
configuration containing only `<packageSources><clear/></packageSources>`, isolated
CLI/package/artifact directories and certificate generation disabled. The tool
uses `System.Reflection.Metadata`/`PEReader`; it never loads the inspected image
as an assembly, invokes a target method, initializes Godot, or resolves a runtime
dependency.

## Mechanical census definitions and bounds

The tool requires exactly one local metadata definition for each anchor:

- `MegaCrit.Sts2.Core.Models.EventModel`;
- `MegaCrit.Sts2.Core.Nodes.Events.ICustomEventNode`;
- `MegaCrit.Sts2.Core.Nodes.Events.NEventLayout`.

It follows only TypeDef/TypeRef/TypeSpec ancestry and interface metadata. An
external same-name anchor, missing local anchor, duplicate type identity, cycle,
or unresolved same-module ancestry fails closed. It emits sorted rows containing
only category, full type name, immediate base name, declared interface names and
the abstract bit.

- **event:** non-nested types in the exact namespace
  `MegaCrit.Sts2.Core.Models.Events` whose local base chain reaches the exact
  local `EventModel`; maximum 128 rows;
- **custom:** non-nested types whose local base/interface chain reaches the exact
  local `ICustomEventNode`; maximum 64 rows, independent of namespace;
- **layout:** non-nested types whose local base chain reaches the exact local
  `NEventLayout`; maximum 64 rows;
- maximum 256 aggregate category rows. A type in multiple categories produces
  one row in each and consumes each applicable bound. No truncation is allowed.

The summary reports total and concrete counts for every category. The concrete
`event` count is the denominator for this pinned build. It is not a count of
supported events. Raw target strings, method signatures, fields, attributes
other than abstract, IL, resources, localization and game content are absent.

## Synthetic acceptance

The disposable fixture gate builds inert managed assemblies only. Eleven checks
must pass:

1. exact direct/inherited event, custom-interface and layout classification,
   including exact output/row keys, base/interface rows, abstract/concrete counts
   and deterministic ordering;
2. a repeated census is byte-identical;
3. a malformed image with the wrong hash stops at `pin_mismatch` before PE read;
4. the same malformed image with its correct hash reaches fixed
   `internal_failure`, proving hash verification precedes PE parsing;
5. 129 event descendants fail `event_limit` without output truncation;
6. an event candidate deriving from an external same-name `EventModel` while a
   different local anchor exists fails `ambiguous_ancestry`;
7. patched assembly metadata containing a local base cycle fails
   `ambiguous_ancestry`;
8. patched assembly metadata containing a local interface cycle fails
   `ambiguous_ancestry`, while the positive fixture's legitimate shared interface
   ancestry remains accepted;
9. a TypeDef base patched to an array TypeSpec fails `ambiguous_ancestry` rather
   than coercing the array to its element type;
10. a TypeDef base patched to a pinned TypeSpec also fails
    `ambiguous_ancestry`, proving modifier/pinned wrappers are not unwrapped;
11. a linked fixture path fails `symlink`.

Accepted fixture command:

```text
<saved-python> -B -E -s -S run_fixtures.py --dotnet <sdk-9.0.303-dotnet>
```

Expected fixed output:

```json
{"schema_version":1,"status":"passed","suite":"event_coverage_census","check_count":11}
```

## Target census and later explicit IL selection

After independent review binds this exact scope/tool hash, the coordinator may
run exactly one pinned target census. Preserve its canonical one-line JSON and
SHA-256, then freeze the exact emitted type list before any member or IL pass.
A count or ancestry failure ends the packet without a looser rerun.

A separate reviewed selector may then emit declared member signatures for the
frozen census types, capped at 4,096 signatures without bodies. Freeze exact
body selectors before each IL invocation. The first body set is each concrete
event type's exact declared `GenerateInitialOptions` method, maximum 128. Direct
follow-up is limited to same-event option callbacks, their attribute-bound state
machines, and exact child-family calls reached from those callbacks. The total
follow-up ceiling is 512 actual bodies, with 2,500 instructions per body. Any
overflow, ambiguous generated ownership or unresolved callback remains unknown;
there is no truncation or name-based fallback.

Shared lifecycle follow-up is limited to exact `EventModel` methods `BeginEvent`,
`GenerateInitialOptionsWrapper`, `ReplaceNullOptions`, `OnEventFinished`, both
`EnterCombatWithoutExitingEvent` overloads, `CreateCombatRoomVisuals`,
`GenerateInternalCombatState`, `ResetInternalCombatState`, and `Resume`, plus
`NEventRoom.Create`, `_Ready`, `SetupLayout`, and `OnEnteringEventCombat`.
Reuse already hash-bound `SetOptions`, `OptionButtonClicked`,
`BeforeOptionChosen`, `RefreshEventState`, `Proceed`, and
`OnActiveScreenUpdated` evidence rather than rereading it without need.

Classification is by exact referenced APIs, never type or option prose:
`CardSelectCmd.FromSimpleGridForRewards`, `FromSimpleGrid`,
`FromDeckForUpgrade`, `FromDeckForTransformation`, `FromDeckForRemoval`;
`CardPileCmd.Add`/`RemoveFromDeck`; `CardCmd.Upgrade`/`Transform*`; known
`Reward`/`NRewardsScreen` types; the exact embedded-combat methods above; and
census-proved custom node/layout types. Other known card selectors such as
choose-card, bundle, enchantment, combat-pile and hand selectors remain
unclassified until an event callback references them.

Profiles, saves, history, Cloud, seeds/RNG internals, platform/network identity,
localization internals, combat implementation, reward synchronizers and arbitrary
hooks remain stopped dependencies. Raw names/IL may exist only in disposable
analysis output. The sanitized result retains the denominator, exact selected
method identities, mechanically observed family references, output hashes and
unknowns. It must not retain IL, string dumps, event prose or inferred event IDs.

## Implementation eligibility rule

For every concrete event census row, later evidence may label only:
`ordinary_only`, `item_child_eligible`, `typed_card_parent`,
`typed_combat_parent`, `typed_custom_parent`, or `unclassified`. A method
reference alone does not make a family executable. The accepted ordinary event
adapter supports only a sole topmost `NRewardsScreen` child and rejects card
selectors, embedded combat and custom nodes. Card cardinality/domain/effect
witnesses must be bound to an exact parent option before reservation; a modal
observed after a generic click cannot be retrofitted into a native policy.

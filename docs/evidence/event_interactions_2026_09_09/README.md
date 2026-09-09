# Pinned event interaction research, 2026-09-09

The [current research map](../../EVENT_INTERACTION_MAP.md) owns the readable
findings and planning implications. [inventory.json](inventory.json) is the
structured companion: all event identities, branch groups, static pool references,
required families, identified bridge gaps and positive source anchors. This
record is static research, not release or live acceptance.

## Inputs and method

- Game: v0.107.1, Steam build 23811903, macOS arm64.
- Assembly: `sts2.dll`, SHA-256
  `e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
- Bridge source inspected at commit
  `4d3516ffd0f205a261ca2f32f13490da5430b4d1`.
- Existing verified reference used:
  `/private/tmp/sts-current-release-final/references/sts2.dll`.
- Toolchain: existing .NET SDK 9.0.303; existing Python 3 for data checks.

[scan.cs](scan.cs) checks the exact assembly hash before using `PEReader`; it never
loads or executes the target assembly. It scans the exact event namespace,
excluding `Events.Mocks`, and nested types, plus the finite
[selector list](selectors.txt). `ModelDb` is restricted to `get_AllSharedEvents`.
The scanner reuses the repository's existing metadata-name and IL decoders through
[scan.csproj](scan.csproj). It preserves constructed generic method arguments,
method tokens, IL offsets, integer operands and branch targets. No external
packages or network access are needed. The build outputs are disposable.

The final scan contains 731 selected types and 3,651 method bodies, including
ancillary UI/API code. These are scan totals, not event totals. Event-model roots
match the earlier census's 68 identities exactly. Inspected extras include 135
named event-referenced relic types and 17 referenced enchantment types. Static
pool getters identify 57 ordinary and seven ancient types. Darv, The Architect
and two deprecated types account for the remaining four; this is not a current-run
unlock/eligibility audit.

Research followed event-local callbacks, nested async bodies and helper calls,
then inspected shared selector forwarding and immediate named relic pickup paths.
For example, `RelicCmd.Obtain` calls `AfterObtained`; `AncientEventModel.RelicOption`
awaits that acquisition before finishing. The inventory's `shared_source_methods`
contains positive ancillary callsites, including some later combat callbacks;
only the explicitly curated `immediate_relic_interactions` are classified as
pickup work. Arbitrary random relics, modifiers and global hooks are not an
exhaustive transitive closure. Branch descriptions and gap classifications are
human-reviewed research conclusions, not automatically inferred reachability.

## Reproduce the bounded inspection

From the repository root, set `DOTNET` to the existing SDK executable and
`PINNED_STS_DLL` to a verified reference copy, then use a fresh scratch directory:

```bash
research_scratch=$(mktemp -d /private/tmp/sts-event-research.XXXXXX)
"$DOTNET" build docs/evidence/event_interactions_2026_09_09/scan.csproj \
  --configfile docs/evidence/event_interactions_2026_09_09/NuGet.Config \
  --artifacts-path "$research_scratch/build" --nologo
"$DOTNET" "$research_scratch/build/bin/scan/debug/scan.dll" \
  "$PINNED_STS_DLL" docs/evidence/event_interactions_2026_09_09/selectors.txt \
  > "$research_scratch/il.json"
```

The exact raw JSON output (including trailing newline) was 12,614,251 bytes,
SHA-256 `87a8f2847f841403d7963c929e34bcef1eb24a8ec51c592c8db3881c942d8390`.
The disposable working scanner and retained scanner emitted byte-identical data.
The original result remains at
`/private/tmp/sts-event-research-20260909/retained-il.json` while that scratch
workspace exists. The full IL dump is deliberately not checked into the repo;
the retained scanner and finite selectors reproduce it. Source-file hashes are
in `inventory.json`; the reused decoder files are bound there as well.

## Bridge compatibility findings

The source findings were compared against these current bridge boundaries:

- [Native parent](../../../bridge/Sts2AgentBridge/components/events/native/PinnedGenericEventV7NativeAdapter.cs):
  exact `NEventLayout`, no custom/embedded-combat room, one pending child,
  rejection of selectorless completed requests, pre-dispatch deck equality and map-oriented completion.
- [Parent session](../../../bridge/Sts2AgentBridge/components/events/core/GenericEventV7Session.cs):
  a stamp based on IDs/enabled/dangerous/Proceed flags, not changed rendered text;
  structurally unchanged transitions wait and revisited structures stop.
- [Binding](../../../bridge/Sts2AgentBridge/components/events/native/GenericEventV7Binding.cs):
  deck captured before option input; child completion waits for the complete
  chosen-option task, so surrounding deck mutations matter.
- [Hooks](../../../bridge/Sts2AgentBridge/components/events/native/GenericEventV7Hooks.cs):
  specific request/screen pairs, one request per binding and fixed-one enchantment.
- [Item state](../../../bridge/Sts2AgentBridge/components/events/native/GenericEventV7ItemState.cs):
  exactly one `PotionReward` or `RelicReward`; not a card or multi-entry reward set.
- [Card session](../../../bridge/Sts2AgentBridge/components/cards/core/CardSelectionV1Session.cs):
  selected-only deck reconciliation; unrelated additions are not silently accepted.

These checks were not weakened. Static incompatibilities are not fabricated live
failures; candidate paths still require their applicable native/live evidence.

## Validation and limits

- All 68 event names match the original pinned census; no duplicates or omissions.
- 105 curated branch groups and 27 immediate relic interaction paths are present.
- All 875 retained callsite anchors match the raw scan's exact method token,
  instruction offset, opcode and target signature.
- Gap-to-event lists were recalculated from branch rows; all source hashes match.
- Retained scanner build passed with zero warnings/errors in 1.20 seconds.
- The retained scan reproduces the working scan exactly. A deliberately wrong
  disposable image was rejected at the pin check before metadata inspection.
- Relevant Markdown links, map rows, source bindings and documentation diffs
  were checked. Production bridge source and the current release manifest are
  unchanged; no gameplay matrix, package rebuild or live launch was needed.
- Observed elapsed research time from scratch-directory creation through the
  inventory validation was 1,058.2 seconds (17.6 minutes), including inspection,
  author review and document preparation. Separate phase timings were not tracked.
  No user readiness wait or release preparation occurred.

No profile, save, preference, history or Cloud files were opened. Referenced game
methods that ordinarily access those systems were read as static assembly bytes
only; they were not invoked. No hidden runtime state or private live corpus was
collected. This research adds no production capability and certifies no full event,
full branch set, complete run or encounter frequency.

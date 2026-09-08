# Generic transformation — bounded static discovery scope

2026-09-08. Proposed for independent review before one new metadata-only read.
The user requested remaining generic-handler development. Fixed multi-upgrade
is separately implemented and frozen as generic_event_v4; all 24 predecessors
and the original bridge are preserved. This discovery does not enable transform
or start another live campaign.

## Questions and retained evidence

The frozen card core requires exact original-to-final-replacement witnesses,
unchanged deck length during observed commit steps, replacement at each selected
original's original deck index, unchanged unselected cards and monotone progress.
Existing transform fixtures deliberately synthesize that positional behavior and
are not native compatibility evidence. The bridge must never reorder observations
or invoke a transformation function/RNG merely to discover replacements.

B rehashed retained declarations and control bodies against the saved API selection:

- CardSelectCmd members: `d3daf5216cc1e33cf086a79b907f1196805acb267636ed56dc1bebc8d2b34195`.
- CardCmd members: `f9a9e7b3421adf47315b56fef3070205393754d867972a6a996d298bc9fa2644`.
- CardTransformation members: `320906a2d7c6c7a827b63f56543b7cb93b278ef840d33c035dff1f062da8bffc`.
- Transform OpenPreviewScreen: `4dee0cc5dbbc0737e1bc2d4298a1ee27925d1e3d251507c174999edab8696492`.

These prove wrapper state-machine identities and an Initialize call with
IEnumerable<CardTransformation>. CardTransformation is a value type; reference
identity of a boxed entry is not an ownership witness. The preview input is lazy
Enumerable.Select of the transformation function, so a second bridge enumeration
would execute behavior and is prohibited. No retained request/command state-machine
bodies, NTransformPreview declarations or CardPileAddResult declaration set were
found. The known callbacks capture's add-result references concern Brain reward
addition, not transformation.

Inspect the exact missing boundaries to determine authoritative prefs/domain,
request result identity, preview mapping, final replacement identity, task/effect
ownership, final ordering and intermediate states across awaits. Record missing
facts honestly. An unsupported private helper or unmatched returned shape requires
a separate reviewed follow-up; this scope cannot recursively expand itself.

## Exact target and selection

One read of the fixed physical pinned image:
`/Users/rowdeygoos/Library/Application Support/Steam/steamapps/common/Slay the Spire 2/SlayTheSpire2.app/Contents/Resources/data_sts2_macos_arm64/sts2.dll`.
Size 9363456 bytes; SHA256
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
Verify nonsymlink ancestry, regular-file shape and unchanged pre/post metadata,
size and hash before PEReader/MetadataReader. Never load or execute target code.
Target mode accepts no caller-selectable target path. Synthetic fixture mode
accepts only canonical nonsymlink absolute inputs under /private/tmp.

Select exactly these nine method bodies, with exact parameter and return types:

1. `MegaCrit.Sts2.Core.Commands.CardSelectCmd+<FromDeckForTransformation>d__19.MoveNext()` → `System.Void`.
2. `MegaCrit.Sts2.Core.Commands.CardCmd+<Transform>d__11.MoveNext()` → `System.Void`.
3. `MegaCrit.Sts2.Core.Commands.CardCmd+<Transform>d__13.MoveNext()` → `System.Void`.
4. `MegaCrit.Sts2.Core.Nodes.Cards.NTransformPreview.Initialize(System.Collections.Generic.IEnumerable<MegaCrit.Sts2.Core.Entities.Cards.CardTransformation>)` → `System.Void`.
5. `MegaCrit.Sts2.Core.Entities.Cards.CardTransformation.GetReplacement(MegaCrit.Sts2.Core.Random.Rng)` → `MegaCrit.Sts2.Core.Models.CardModel`.
6. `MegaCrit.Sts2.Core.Entities.Cards.CardTransformation.get_Original()` → `MegaCrit.Sts2.Core.Models.CardModel`.
7. `MegaCrit.Sts2.Core.Entities.Cards.CardTransformation.get_Replacement()` → `MegaCrit.Sts2.Core.Models.CardModel`.
8. `MegaCrit.Sts2.Core.Entities.Cards.CardTransformation.get_ReplacementOptions()` → `System.Collections.Generic.IEnumerable<MegaCrit.Sts2.Core.Models.CardModel>`.
9. `MegaCrit.Sts2.Core.Entities.Cards.CardTransformation.get_IsInCombat()` → `System.Boolean`.

Additionally emit only the immediate base identity, declared method signatures,
attributes, returns/body-presence and explicit MethodImpl mappings for these two
types: `MegaCrit.Sts2.Core.Nodes.Cards.NTransformPreview` and
`MegaCrit.Sts2.Core.Entities.Cards.CardPileAddResult`. At most256 method declarations
and64 MethodImpl rows per type. No other declaration catalog or field/property
values. Resolution may enumerate metadata names internally but emits only the
fixed selected projection. No recursive callees or generated-state-machine
following beyond the three exact explicitly named MoveNext bodies above.

Each body is bounded to2500 IL instructions, total22500. Replace user strings
with the fixed user_string marker; emit symbolic metadata operands only. No
resources, assets, localization, source extraction, game logs, profile/save/Cloud,
network, registry, launch, listener, package or live-operation access.

## Tooling and execution gates

Prepare a new inspector under `/private/tmp/generic-transform-inspector-a`, derived
from the already reviewed fixed-selection inspector without modifying historical
tooling. Root owns this scope and execution/result records; B owns the new scratch
scanner/capture/fixtures; R independently reviews the exact scope and frozen tools.
Only the root invokes target mode after that review. SDK use remains serialized.

Preserve at most1MiB stdout,4096-byte stderr and30-second subprocess duration.
Use create-only private output directory mode0700 and0600 output files, with
bounded stdout/stderr draining, output/deadline failure and sanitized errors.
Record unsuccessful/partial results separately; never retry or relabel a failed
capture as successful without a separately reviewed scope and invocation.
Planned fresh output root: `/private/tmp/generic-transform-target-a`.

Offline build and synthetic fixtures precede source/bundle freeze and independent
review. Test exact nine-body/two-declaration selection, missing/ambiguous/bodyless
and overflow rejection, return/parameter shape, no body following, string redaction,
nested/generic metadata and canonical serialization, malformed image, wrong pins,
symlink and argument rejection, output/deadline limits and create-only capture.
Record exact source/bundle/test identities in an appended acceptance section
before the single target invocation. No target access during these preparation
gates. Successful static discovery supplies evidence for a later implementation
contract; it does not by itself authorize or prove a transform adapter.

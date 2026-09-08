# Generic transformation — ordering and binding metadata scope

2026-09-08. Proposal for independent review. The user asked to continue generic
handler development after the completed G4 checkpoint. All24 successors and the
original bridge remain frozen. This scope does not implement transformation,
change a card contract, package/install a release or authorize any live campaign.

## Questions and retained basis

The preceding [native evidence](PHASE_1_GENERIC_TRANSFORM_NATIVE_EVIDENCE.md)
proves that the command removes all originals before insertion, may await between
insertions, and may replace the initial generated card through
ModifyCardBeingAddedToDeck. The frozen transform effect rule is incompatible with
legitimate multi-card intermediate lengths. This inspection resolves the remaining
insertion-order facts, exact public final-card observation boundary, request
predicate/default factory, and public preview control paths before a new
implementation contract is proposed. It does not infer final order from -1 or
assign the name Deck to numeric value6 without metadata evidence.

Retained sources were rehashed, with no target reinspection:

| Input | SHA256 |
| --- | --- |
| CardPile member output | `2ae7d184f359da161aa2ecb0e6e1348d750c118af832a5450a3a005a33290500` |
| CardCmd member output | `f9a9e7b3421adf47315b56fef3070205393754d867972a6a996d298bc9fa2644` |
| CardSelectCmd+<>c member output | `d0a06d1e26bd1bc7d08aee123add970b30003fc1f641328e81adb259c4ac4d15` |
| Prior transformation capture | `fe6402573e251c2229fe615c38f3d11fbf760ef3fccb5443cee83d6c6adc485e` |

The first three files remain in `/private/tmp/card-selection-static-qfocay2o/outputs/`
and are hash-bound in the saved API selection. The last is
`/private/tmp/generic-transform-target-a/stdout.bin`,204926 bytes. It establishes
NTransformPreview._Ready's declared signature, exact _before/_after Control field
identities used by Initialize, the ModifyCardBeingAddedToDeck call at IL804 with
its returned CardModel assignment at IL814/831, and the three result field operand
types. No retained Hook declaration establishes public/static access flags.

## One fixed target image

The sole target is the same physical file:
`/Users/rowdeygoos/Library/Application Support/Steam/steamapps/common/Slay the Spire 2/SlayTheSpire2.app/Contents/Resources/data_sts2_macos_arm64/sts2.dll`.
Require size9363456 bytes and SHA256
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
Verify nonsymlink ancestry, regular-file shape, pre/post metadata stability, exact
size and hash before PEReader/MetadataReader. No target assembly loading,
reflection invocation or code execution. Target mode accepts no selectable image
path. Fixture mode permits only raw canonical absolute nonsymlink paths under
/private/tmp, rejecting invalid spelling before image metadata or output creation.

## Exact five bodies

Select only these complete method identities, with the stated return types:

1. `MegaCrit.Sts2.Core.Entities.Cards.CardPile.AddInternal(MegaCrit.Sts2.Core.Models.CardModel,System.Int32,System.Boolean)` → `System.Void`.
2. `MegaCrit.Sts2.Core.Commands.CardCmd.PileIndexSort(System.ValueTuple<MegaCrit.Sts2.Core.Entities.Cards.CardTransformation,MegaCrit.Sts2.Core.Entities.Cards.CardPile,System.Int32,MegaCrit.Sts2.Core.Models.CardModel>,System.ValueTuple<MegaCrit.Sts2.Core.Entities.Cards.CardTransformation,MegaCrit.Sts2.Core.Entities.Cards.CardPile,System.Int32,MegaCrit.Sts2.Core.Models.CardModel>)` → `System.Int32`.
3. `MegaCrit.Sts2.Core.Nodes.Cards.NTransformPreview._Ready()` → `System.Void`.
4. `MegaCrit.Sts2.Core.Commands.CardSelectCmd+<>c.<FromDeckForTransformation>b__19_0(MegaCrit.Sts2.Core.Models.CardModel)` → `System.Boolean`.
5. `MegaCrit.Sts2.Core.Commands.CardSelectCmd+<>c.<FromDeckForTransformation>b__19_1(MegaCrit.Sts2.Core.Models.CardModel)` → `MegaCrit.Sts2.Core.Entities.Cards.CardTransformation`.

Resolve exact signatures uniquely, reject missing/ambiguous/bodyless methods,
and cap each body at2500 instructions and all bodies at12500. Emit only symbolic
metadata operands, offsets, bounded scalar constants and branches as in the
reviewed fixed-selection scanner. Do not recursively follow any callee, generated
method, constructor or state machine. Any new unresolved helper is a separately
reviewed follow-up, never automatic scope expansion.

## Exact declaration and constant projections

Emit exactly one method declaration, without its body:

`MegaCrit.Sts2.Core.Hooks.Hook.ModifyCardBeingAddedToDeck(MegaCrit.Sts2.Core.Runs.IRunState,MegaCrit.Sts2.Core.Models.CardModel,System.Collections.Generic.List<MegaCrit.Sts2.Core.Models.AbstractModel>&)`
→ `MegaCrit.Sts2.Core.Models.CardModel`.

Emit its exact signature, method attributes, return type, metadata token and
body-presence only. These establish whether the proposed observational hook is
public/static and match the returned-final-card call identified by the previous
capture. No catalog of other Hook methods or Hook bodies is included.

Emit exact declared field metadata only for:

- `MegaCrit.Sts2.Core.Entities.Cards.PileType.value__`: field type and attributes,
  with the type's immediate base identity to establish enum shape; no value read.
- `MegaCrit.Sts2.Core.Entities.Cards.PileType.Deck`: field type/attributes and its
  metadata literal constant's primitive integer type and exact bounded scalar value.
- `MegaCrit.Sts2.Core.Entities.Cards.CardPileAddResult.success`: Boolean field
  type and access/other attributes.
- `MegaCrit.Sts2.Core.Entities.Cards.CardPileAddResult.cardAdded`: CardModel field
  type and access/other attributes.
- `MegaCrit.Sts2.Core.Entities.Cards.CardPileAddResult.modifyingModels`:
  `List<AbstractModel>` field type and access/other attributes.

Require each exact field uniquely. The enum constant is a static metadata literal,
not a runtime value. Emit no other field values, constants, properties, field
catalogs or declaration sets. The result fields are needed to distinguish a
successful final card result from a default result wrapped in Nullable. AddInternal
and the exact Modify hook together are candidate observational boundaries for
correlating post-modification card identity with insertion while a command is still
in flight; this scope supplies facts only and does not accept that future design.

## Narrow public node-path exception

All ldstr instruction operands in every emitted IL body remain the fixed
`user_string` marker. A separate bounded projection may emit exactly two static
ASCII node-path constants, only for the _before and _after assignments in the
selected NTransformPreview._Ready body. Root selected this narrow exception
explicitly; it requires independent reviewer acceptance as part of this scope.

Require exactly one unique straight-line instruction chain for each assignment:

`ldarg.0; ldarg.0; ldstr; call Godot.NodePath.op_Implicit(System.String); call/callvirt Godot.Node.GetNode(Godot.NodePath); stfld`

The GetNode call may be a generic MethodSpecification whose underlying method is
that exact Node.GetNode identity. Its single generic type argument must resolve to
Godot.Control. The stfld must refer to the exact corresponding
`MegaCrit.Sts2.Core.Nodes.Cards.NTransformPreview._before` or `_after` field of
type Godot.Control. No intervening instructions, different receiver, wrapper,
GetNodeOrNull, other field or other method is accepted. Both chains must be found
uniquely or the inspection fails closed. There is no broader literal fallback.

Each projected path must be ASCII,1..96 characters, and match the restrictive
node-path grammar `%?[A-Za-z_][A-Za-z0-9_]*(/[A-Za-z_][A-Za-z0-9_]*)*`.
Emit only the role, exact field identity, string/store offsets and path value for
these two bindings. Do not output any other string literal, localization value,
asset, resource, private/runtime field value or scene content. This is code-level
proof of public GetNode paths, not observation of live Godot state.

## Tool preparation, bounds and execution gate

B owns only new scratch tooling under `/private/tmp/generic-transform-ordering-inspector-a`,
derived from the reviewed fixed-selection scanner/capture with the corrected raw
fixture preflight. Preserve all prior inspectors, captures and scopes. Root owns
scope/result records and the sole target invocation; R independently reviews the
exact scope and then the frozen source, bundle and synthetic results. SDK use is
serialized. No target bytes are read during tooling preparation or synthetic tests.

Preserve maximum1MiB stdout,4096-byte stderr and30-second subprocess duration,
create-only private output directory0700 and output files0600, bounded draining,
explicit deadline/output failures and sanitized errors. Planned fresh target output
is `/private/tmp/generic-transform-ordering-target-a`. Record unsuccessful output
separately; no automatic retry or relabeling a failed capture.

Test exact five-body/one-method/five-field/two-path selection, missing/ambiguous/
bodyless/wrong signature cases, per-body and output limits, nested/generic metadata,
field access/constant types, and deterministic canonical serialization. Add inert
node-path cases for exact positive bindings, duplicate/missing assignment, wrong
field/receiver/return type, intervening instruction, overlong/non-ASCII/invalid
path, and secret literals in all other locations. Preserve pin, malformed-image,
symlink, lexical argument, create-only output, stderr, stdout and deadline checks.
Freeze exact source/bundle/test identities before R's final tooling review. Only
then may root invoke the fixed target command once. No live/profile/save/Cloud,
network, registry, game launch, package, install or listener action is included.

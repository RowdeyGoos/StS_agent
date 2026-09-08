# Generic transformation — native compatibility evidence

2026-09-08. The reviewed capture establishes that native multi-card transformation
cannot generally use the frozen card_selection_v1 transform reconciliation rule.
Native code removes every selected original before reinsertion and can suspend
after each inserted replacement. The frozen rule requires constant deck length
and positional replacement at every observed effect step. Final replacement
identity can also change after the initial transformation choice through the
native deck-add modification hook. No transform adapter has been implemented.

## Capture identity and limits

The one root-owned invocation under the independently reviewed
[scope](PHASE_1_GENERIC_TRANSFORM_SCOPE.md) completed with exit0 and empty stderr.
The exact retained file is `/private/tmp/generic-transform-target-a/stdout.bin`,
204,926 bytes, SHA256
`fe6402573e251c2229fe615c38f3d11fbf760ef3fccb5443cee83d6c6adc485e`.
Its bytes were rehashed before this analysis. It binds pinned sts2.dll SHA256
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.

The output contains exactly nine bodies and1,395 instructions. Body counts are:
request MoveNext236; single Transform MoveNext74; collection Transform MoveNext830;
NTransformPreview.Initialize207; GetReplacement36; each of four getters3.
The two immediate type projections contain16 NTransformPreview method declarations,
zero CardPileAddResult method declarations, and zero MethodImpl rows.
The scope intentionally omitted fields, so the absence of result methods is not
proof of the accessibility of its fields.

Only this retained capture and previously retained selector metadata were analyzed.
No additional target read, SDK build, target execution, profile/live/network work,
or change to the24 frozen successors occurred during analysis. A follow-up
inspection needs its own reviewed exact scope; this document does not authorize it.

## Request and native selection

The exact request remains
`CardSelectCmd.FromDeckForTransformation(Player,CardSelectorPrefs,Func<CardModel,CardTransformation>)`
returning `Task<IEnumerable<CardModel>>`. Its d__19 body loads raw PileType value6,
calls GetPile for the supplied Player, obtains Cards and filters through the
specific generated predicate b__19_0 before copying to a List (IL25–78). The
predicate body was not selected, so its exact rule is not inferred here.

Empty input returns empty. When candidate count is at most MinSelect and manual
confirmation is false, it returns the candidate list without opening a selector
(IL103–137). Otherwise the TestSupport selector branch is separate. The ordinary
local branch reserves a choice id for the supplied Player, chooses the local
player path, supplies default transformation function b__19_1 when the caller's
function is null, invokes the retained ShowScreen API at IL384 and awaits
CardsSelected at IL393–481. It synchronizes and returns the selected original
cards. The remote branch awaits a remote choice instead. Neither request branch
performs the transformation effect itself.

Previously retained ShowScreen binds the exact candidate list, transformation
function and preferences before pushing the screen. Its retained OnCardClicked
opens the preview at MaxSelect. CompleteSelection resolves its TaskCompletionSource
with the original `_selectedCards` set before removing the overlay. These bodies
were rehashed against the saved API selection. A request/task/screen admission
can therefore remain based on original-card identity and native count semantics;
it cannot establish what final replacement will later enter the deck.

## Preview identity and lazy input

The retained OpenPreviewScreen passes
`_selectedCards.Select(_cardToTransformation)` directly to
`NTransformPreview.Initialize(IEnumerable<CardTransformation>)`. Initialize copies
that enumerable to a List at IL24. The bridge must not enumerate the same lazy
input a second time: doing so would invoke the native transformation function again.
CardTransformation is a value type, so boxed-entry reference identity is not a
usable ownership witness. Its four captured getters are direct backing-field
reads for Original, Replacement, ReplacementOptions and IsInCombat.

For each transformation value, Initialize creates a before-side NCard from the
exact Original (IL137–143), creates its NPreviewCardHolder (IL158), and adds it
to the before control (IL173). This provides an original-card display path,
consistent with the previously proved NCard/preview-holder reference projection.
Actual public node paths to the before/after controls remain unproved because
NTransformPreview._Ready was not selected. Field names in metadata are not an
implementation license to read private fields.

When Replacement is non-null, the after-side NCard is created from that exact
replacement (IL294–309). Otherwise it initially displays Original (IL320–326).
For the null-Replacement branch, Initialize chooses ReplacementOptions or obtains
default transformation options and calls CycleThroughCards with the after holder,
the original pile and those options (IL458–542). It passes that Task to RunSafely.
This proves an asynchronous preview-options path exists; the unselected cycle
body is needed before making exact claims about how or when displayed models
change or stop. A displayed option is not evidence of the eventual RNG result.
Even an explicit Replacement is not yet the final post-hook deck-card identity.

## Initial replacement versus final replacement

GetReplacement immediately returns an explicit non-null Replacement (IL0–14).
Otherwise it requires a non-null Rng, returns null if Original is no longer
transformable, and calls one of two CreateRandomCardForTransform overloads using
the original, combat flag, RNG, and optional ReplacementOptions (IL15–95).
These factories were not followed. The method's observed return is an
authoritative initial choice, but not an unconditional final replacement.

The single-card `CardCmd.Transform(original,replacement,style)` d__11 body creates
a CardTransformation value from its two arguments, calls Yield and delegates to
the collection Transform overload with null RNG. It awaits that command and returns
FirstOrDefault of its results wrapped in Nullable. It is not an independent
in-place mutation path. A non-null Nullable/HasValue does not itself certify success:
an empty aggregate can still produce the default result value wrapped in Nullable,
so any future witness must validate the actual success and card identity fields.

The collection Transform d__13 copies its input enumerable to an array (IL54–64).
For each transformation it checks original mutability/transformability and pile,
records the current pile/index, calls GetReplacement (IL302), removes the original
from its current pile (IL382), and stores a tuple of transformation, original pile,
index and initial replacement (IL401–406). The entire original-removal loop ends
before the reinsertion loop. It sorts those tuples through PileIndexSort (IL460);
that comparator body was not selected.

During reinsertion it starts a CardPileAddResult with success=true and cardAdded
set to the initial replacement (IL622–659), and checks replacement versus original
owner. For raw pile value6, it calls
`Hook.ModifyCardBeingAddedToDeck(IRunState,CardModel,List<AbstractModel>&)` at IL804.
The returned card replaces the command's replacement variable (IL814) and the
result's cardAdded field (IL831). The result also stores the modifying-model list.
Thus a command-result or in-flight mutation witness must use the post-hook card;
preview identity and GetReplacement identity alone are insufficient.

Results are collected in the sorted tuple-processing order. The later animation
loop pairs each tuple's Original with the same-index result.cardAdded
(IL1425–1467), independently demonstrating that this internal sorted association
is used by native code. The aggregate return exposes results, not those original
references. Public field accessibility and any external original-to-result pairing
mechanism remain separate requirements, rather than inferred from result order.

## Ordering and observable intermediate states

For raw PileType value6, the command calls
`pile.AddInternal(replacement,-1,false)` at IL973. For the other branch it supplies
the captured index at IL998. Existing retained declarations prove AddInternal is
public and has that exact signature; its body was not found in retained evidence.
Likewise no retained enum constant declaration establishes the name associated
with raw value6. This report therefore does not label -1 as append, assert a final
deck order, or infer that the saved index is the original pre-command deck index.
Those indices were captured while earlier originals had already been removed.

After inserting each replacement, the command awaits AfterCardChangedPiles
(IL1176–1264) before invoking CardAddFinished, original.AfterTransformedFrom,
replacement.AfterTransformedTo and appending the result (IL1275–1314). The non6
branch additionally awaits AfterCardEnteredCombat before that common hook.
Only after all replacements are processed does it perform animation/wait work,
including Cmd.Wait at IL2115. It later removes the originals from run state
(IL2430) and returns the result list at IL2481/2580.

Consequently a multi-card call may suspend after only its first replacement has
entered the pile while all selected originals have already been removed. With n
selected originals, a visible intermediate length of baseline−n+1 is possible at
that first common await. For example, baseline `[A,B,C,D]` with selected originals
`{B,D}` can reach a three-card pile containing A, C and the first replacement
(in an order not proved here), while the frozen core still requires four cards.
This alone contradicts the frozen constant-length
transform rule, regardless of final ordering. The first inserted replacement can
also be present before its result is appended or the command Task completes.
A future model of legitimate partial progress therefore cannot rely solely on
completed aggregate results to identify that in-flight replacement. It must not
fabricate deck rows or reorder actual observations to satisfy the old rule.

This is static capability evidence: the capture does not establish which concrete
hooks yield for any live event, nor does it assert that every transform invocation
will expose every possible intermediate state.

## Exact remaining facts, without another inspection

Before defining a compatible transformation core/adapter contract, the smallest
remaining ordering and result-access questions are:

1. The body of public
   `MegaCrit.Sts2.Core.Entities.Cards.CardPile.AddInternal(CardModel,System.Int32,System.Boolean)`
   returning System.Void, especially -1 semantics, insertion order, and callbacks.
2. The body of private static `MegaCrit.Sts2.Core.Commands.CardCmd.PileIndexSort`
   taking two identical
   `System.ValueTuple<CardTransformation,CardPile,System.Int32,CardModel>` values
   and returning System.Int32. It determines the result/processing order.
3. The declared underlying enum shape and the exact constant for
   `MegaCrit.Sts2.Core.Entities.Cards.PileType.Deck`; current evidence contains
   numeric operands, not the declaration binding that label to6.
4. Only the exact field declarations/access flags/types of
   `MegaCrit.Sts2.Core.Entities.Cards.CardPileAddResult.success`, `cardAdded`, and
   `modifyingModels`. Their operand types are Boolean, CardModel and
   `List<AbstractModel>` respectively, but method-only projection omitted access flags.

For a later native preview implementation, additional exact missing facts are
`NTransformPreview._Ready()` for public control paths and the
`CardSelectCmd+<>c.<FromDeckForTransformation>b__19_0(CardModel) -> System.Boolean`
predicate and `b__19_1(CardModel) -> CardTransformation` default factory. If that implementation needs
to validate changing after-side preview identities or cancellation, it must first
establish the exact body and whether an attributed state machine exists (and its
exact identity/body if so) for `NTransformPreview.CycleThroughCards(NPreviewCardHolder,CardPile,IEnumerable<CardModel>)`,
and any selected cleanup methods it relies on. No implicit recursive-following
request is made here.

Relevant retained signature inputs were rehashed: CardPile members SHA256
`2ae7d184f359da161aa2ecb0e6e1348d750c118af832a5450a3a005a33290500`;
CardCmd members `f9a9e7b3421adf47315b56fef3070205393754d867972a6a996d298bc9fa2644`;
CardSelectCmd members `d3daf5216cc1e33cf086a79b907f1196805acb267636ed56dc1bebc8d2b34195`.
They remain under `/private/tmp/card-selection-static-qfocay2o/outputs/` and are
bound by [the saved API selection](PHASE_1_CARD_SELECTION_API_SELECTION.json).

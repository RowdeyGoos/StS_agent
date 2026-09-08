# Card selection v1 static evidence

2026-09-06. Pinned game 0.107.1/build23811903, arm64. Metadata/selected IL only;
no target assembly execution, user profile/save read, live campaign or retained
live corpus. The exact 47-type/142-body selection, inspector/history/output hashes
and one failed name selection are in [the record](PHASE_1_CARD_SELECTION_API_SELECTION.json).
The failed inferred generated type produced no target metadata/body output;
the actual getter's referenced lambda was then selected explicitly. SDK9.0.303
rebuilt the inspector offline with the pinned-image-before-PEReader checks intact.

## Proven selector behavior

The native prefs support minimum/maximum cardinality and manual confirmation,
but the screens keep their prefs and selected sets private. Rendered localized
prompts cannot recover an authoritative numeric policy. Production therefore
binds the exact parent callsite, accepted receipt and screen. No private-field
read, reflection, prompt parsing or guessed confirm threshold is selected.

`NCardGridSelectionScreen.CardsSelected()` only awaits the existing completion
source and returns the selected original models. Retain one task per admitted
child, snapshot its unordered result once, and reject completion/cancellation at
admission. Success precedes overlay removal and proves selection publication,
not the deck effect. Exit cancels an incomplete task.

`NCardHolder._GuiInput(select, pressed)` checks native clickability/CardNode and
defers the retained holder's pressed signal. This is the selected per-control
entry; direct signal emission would bypass those guards. The grid's pressed
handler uses the exact holder.CardModel. `NGridCardHolder.CardModel` returns its
base card even when showing an upgraded preview. Model/holder/CardNode identities
must all be retained and revalidated.

The visible selected outline is driven by `NCard.CardHighlight.Material`, a
ShaderMaterial. Its public `GetShaderParameter("width").AsSingle()` is the same
read used by native animation. Unselected settles at0; selected settles at
single-precision bits1033476506 (about0.075). Intermediate values are transient.
Public material and control size/position getters use normal native getters.
No shader state is written by the adapter.

## Initial parent policies

- RoomFullOfCheese/GORGE passes8 to reward creation and prefs exact2, which
  defaults to no manual confirmation. `NSimpleCardSelectScreen` auto-submits
  at2. The Create projection maps each creation result through its pure Card
  getter; grid SetCards copies those models. Gorge awaits selection and adds
  each selected original through CardPileCmd.Add, then calls SetEventFinished
  after both awaited additions. That finished flag plus exact deck additions
  and task/overlay witnesses is the completion gate.
- SmithRestSiteOption's public SmithCount feeds exact prefs; the initial policy
  requires SmithCount1 and manual confirmation. The source deck domain is
  exactly Where(IsUpgradable). One card opens the single preview, whose public
  NUpgradePreview.Card getter returns that original. Preview confirmation
  publishes selection. Smith upgrades each returned original, then awaits
  AfterRestSiteSmith. Rest Proceed restoration is an additional completion
  witness; it enables map travel before explicit Proceed opens the map. The
  child must permit that exact intermediate map state.

UpgradeInternal raises CurrentUpgradeLevel before finalization/after-hooks.
CardPileCmd.Add mutates the deck before awaited AfterCardChangedPiles. The child
therefore requires a typed effect-completion witness as well as exact deck
changes; an early matching delta cannot finish reconciliation. Hook/RNG/history
callees are not followed or invoked by the bridge. A blocked/altered effect stops
without retry.

## Complete-domain guard

Reward modifiers can alter the offered list after initial creation, so the
argument8 alone does not prove the complete runtime domain. For Cheese the
adapter requires exactly8 bound holders plus a proved complete-grid layout.
The pinned base NCardGrid uses card size NCard.defaultSize * NCardHolder.smallScale,
padding40, and columns trunc((scrollWidth+40)/(cardWidth+40)). Native InitGrid
sets scroll content height to rows*cardHeight+(rows-1)*40+80+320+YOffset; the
assignment is deferred. Require exact expected height for8 and positive finite
geometry, nonnegative YOffset, and the card area plus top80/offset fitting the
grid viewport. CalculateRowsNeeded allocates ceil((gridHeight+40)/(cardHeight+40))
plus2, capped by total rows; these conditions prove every row is allocated.
An extra ninth card either appears in those rows (count rejection) or contradicts
the height/fit proof. Require the initial top/center scroll position and retain
layout/holder bindings through the child. Base CenterGrid is true. A stale
deferred height, partial page, resize/scroll, subclass layout or overflow cannot
be accepted as a complete domain. Smith additionally compares the entire eligible
master-deck reference set to the holder domain.

## Remaining evidence boundary

The shared engine can fixture-test event add/remove/upgrade/transform at multiple
counts. Initial native policies cover only Cheese add2 and ordinary smith1.
Deck removal, transform and multi-upgrade screens have separate preview behavior;
some previews clear highlights, and transform returns originals rather than a
replacement receipt. Those production callers remain unselected until exact
parent policy and effect witnesses are proven. This report is static evidence;
synthetic integration, native compilation, release verification and live tests
are separate gates.

## Ordinary rest player's public binding

The native parent needed a public Player source because RestSiteOption.Owner
is inaccessible. Additional exact selectors were frozen before inspection: the
NRestSiteCharacter members and get_Player/set_Player/Create bodies, NRestSiteRoom
get_Characters/Create/_Ready/UpdateRestSiteOptions/get_Options, and the reached
RestSiteRoom model get_Options. Totals are 47 actual types, 142 actual method
bodies and 175 hashed outputs, within the existing 80/200 ceilings.

NRestSiteCharacter.Player and NRestSiteRoom.Characters getters are field-only.
Character.Create assigns the exact input Player through a field-only setter.
The room's _Ready loops every run-state Player, creates its character and adds
it to the public Characters list before populating option buttons. Therefore
ordinary single-player Smith can bind the one valid, visible character's public
Player while requiring exactly one character, the exact retained room and stable
character/player references. Multiple characters or later changes reject.

NRestSiteRoom.Options delegates to its room model; the model delegates to
GetLocalOptions or returns an empty list. The pre-existing public option getter
remains the native option source. No multiplayer/network helper body was followed,
and no private owner field or global player discovery is introduced.

# Generic event v2 — upgrade and removal discovery

2026-09-07. Accepted functional contract for a successor to frozen generic_event_v1. Preserve all fifteen
predecessor trees and their contracts plus the original 48-file bridge. This
increment extends by shared interaction family, never by named event rows.

## Scope and compatibility

Keep standard noncancelable upgrade-one with native preview confirmation.
Add noncancelable standard deck removal with authoritative selection limits
1 <= min <= max <= 8, complete domains <=64 and strictly larger than max to
exclude command auto-shortcuts. Removal uses native preview confirmation, with
an explicit preview action after min selections and automatic preview at max.
Optional zero, scrolling, repeated-key choices, generated adds, transformation,
multi-upgrade, items, custom screens and event combat remain unsupported here.

Use new GenericEventV2 types, generic_event_v2 envelope/routes and host. Frozen
card_selection_v1 payloads and the actual frozen card session remain unchanged.
Both families share one bounded parent, descriptor contract and provider seam.
No release, installation, listener or live campaign is included in this gate.

## Authoritative discovery

Preserve the v1 observational EventOption.Chosen, FromDeckForUpgrade and upgrade
screen ShowScreen hooks. Add exactly CardSelectCmd.FromDeckForRemoval(Player,
CardSelectorPrefs, Func<CardModel,bool>) and NDeckCardSelectScreen.Create(
IReadOnlyList<CardModel>, CardSelectorPrefs). Original calls always execute;
no private-field reads, transpilers, changed arguments/results or event catalogs.
The removal wrapper supplies family identity and filters the actual original-card
domain; the owned creation call supplies the complete ordered domain and prefs.

Reserve exact parent/controller/run/player/room/map/IRunState and the complete
pre-dispatch deck. Require inherited dispatch -> Chosen -> request -> creation
causality, same player and preferences, one request/screen per parent and
unchanged entire deck at admission. Capture actual request and Chosen Tasks,
reject substituted/reused tasks/screens, preserve lifetime tombstones and reject
selectorless shortcuts. Capture removal predicate identity as a request witness;
never evaluate a caller filter again or infer its rules from card labels.

Creation originals must be unique exact baseline-deck members with valid keys
and levels, and meet the family's public eligibility predicate. The frozen
upgrade binding also retains exact run-state at ShowScreen. Removal Create has
no run-state argument; its enclosing owned request and reserved context must
remain exact. Revalidate full ContextValid at removal Create entry and after
binding its returned screen, including after asynchronous request setup.
Failure after dispatch preserves attempts/receipts and unverified
effects. Lost real EventSynchronizer context remains a live acceptance residual.

## Immutable admission and child control

Native capture publishes an immutable admitted descriptor containing operation,
min/max, commit mode, domain count and opaque admission identity. Parent validates
the supported family combination, retains this exact descriptor, and supplies
its identity to CreateChild. Child creation rejects changed or foreign admission;
the frozen card context must exactly match all descriptor fields. Clients and
providers cannot inject native rules. Public child lineage and descriptor remain
constant for the child lifetime.

Removal preview membership must be obtained from actual preview holder/card
original references, with an exact public API mapping established before native
implementation. Selection may clear grid highlights when preview opens; derive
the preview-phase selection flags only from this verified original set. Before
advertising Confirm, require exact set equality with cumulative reconciled
selection receipts (also enforced by the actual frozen card session). Validate
complete unique preview membership, bound controls/geometry/foreground and
unchanged candidate identity/key/level before every mutation. Never map by title,
position alone, clone similarity or eventual effects. Preview cancellation is
not exposed by this controller.

Snapshot each completed request/selector result once, bounded by max+1. Reject
duplicates, foreign originals and counts outside min/max. Both tasks must return
the same exact original set; order is not semantic. Effect completion additionally
requires exact Chosen Task success and selector closure. Frozen reconciliation
proves only selected originals removed, every remaining baseline original retains
order/key/level, and no other deck delta. Upgrade retains its exact level delta.
Do not claim other parent HP/gold effects are certified.

## Host, budgets and acceptance

Preserve12 parent actions,4 children,52 total actions,10 actions per card child,
2048 reads and one30-second monotonic host deadline. Retain no retries after
uncertain mutation, immutable provider observations and exact correlated history.
Host compares selected slots as duplicate-free sets while retaining receipt order;
candidate slots and immutable shape remain in their original order. Validate
family/count/mode and exact descriptor agreement on every ready/resolved payload.
Preview-confirm completion requires observed preview, final confirm, legal count
and exact selected-card membership. An automatic preview at max does not require
an explicit preview action. Other modes remain unsupported in this increment.

Required evidence: preserve all upgrade fixtures; two unrelated removal identities
and one held-out identity through production hooks/native/card/core/wire/Python;
select more than one card, select in reverse slot order, variable min/max with
explicit and automatic preview, delayed creation/completion, early matching deck
delta, wrong or duplicate task originals, unrelated deck mutations, changed
admission, wrong family/count/mode, preselected/replaced preview, stale lineage,
cleanup failure and bounded uncertain action accounting. Compile the real pinned
target without execution and reproduce native bytes in disposable snapshots.

## Ownership and acceptance gates

Root owns this contract, core, wire, checker, source identities and living docs.
Native lane owns native/ and native_tests/ only after independent contract review
and complete public preview mapping evidence. Host/review lane owns host/ and
host_tests/ after review and independently reviews native and checker changes.
Integration lane owns integration/, integration_tests/ and wire_tests/ after
interface publication. One SDK build lane at a time; all output is disposable.
Final source identity freezes only after integrated checks, staged whitespace
validation and independent source review pass, then the frozen aggregate repeats.

Independent design review accepted these semantics with the explicit preview-set
and removal-creation context checks above. Native implementation remains dependent
on the bounded public preview mapping evidence; core/host/wire may now implement.

## Accepted preview mapping evidence

The independently reviewed six-body metadata-only check passed with exact result
SHA-256 `f9404d721c4ba8824938ee0684ccf7fe21a885eda974bc986b825b986a82cf56`.
It proves NCard.Create assigns the input model, PreviewHolder.Initialize binds
that card via SetCard/CardNode, and no PreviewHolder override/shadow changes the
inherited CardModel/CardNode mapping. Read current exact holder/card types and
original references each capture; never follow unexpected mappings. See the
[scope](research/PHASE_1_GENERIC_EVENT_V2_PREVIEW_SCOPE.md) and
[result](research/PHASE_1_GENERIC_EVENT_V2_PREVIEW_RESULT.md). No target assembly
was loaded or executed by that inspection. Native implementation gate is satisfied.

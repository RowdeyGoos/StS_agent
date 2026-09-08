# Generic event release v5: native reward hitbox compatibility

2026-09-08. User requested continuation after the single v4 live test identified
`candidate_hitbox_type` and completed cleanup. All22 predecessors remain frozen.
Independent contract review precedes implementation. Game stays closed until the
new release gates and fresh installation pass.

## Evidence and exact repair

The [v4 ledger](research/PHASE_1_GENERIC_EVENT_RELEASE_V4_ACCEPTANCE.md) records
one parent action, no child actions,258reads and the exact hitbox-type diagnostic.
The concrete runtime subtype was not captured. The earlier successful reward
path in `card_selection_v1` uses the declared native `NClickableControl` contract
and liveness while retaining exact object-reference bindings. The reviewed
static holder projection retains original cards; it supports no other relaxation.

Derive `generic_event_release_v5` from frozen v4. Change only the reward adapter's
hitbox validation during initial candidate creation and subsequent bound capture:
accept the already statically typed `NClickableControl` instance, including its
subclasses, when `GodotObject.IsInstanceValid` succeeds. Remove only those two
exact-runtime-type equality requirements. A dedicated typed helper may express
this once. Preserve initial null rejection and the later exact captured-reference
comparison, so replacing a hitbox with another compatible object still fails.

Retain visibility,enabled,selection/material state,card/model identity,request and
parent ownership,geometry,limits,exception behavior and all other exact-runtime-
type checks. Preserve the original getter/evaluation order except for the removed
hitbox GetType check and the newly reachable remainder of valid subtype paths.
The helper reports existing CandidateHitboxInvalid on failed liveness; successful
helper checks reset to the same broad diagnostic as v4. No extra game getter,
reflection,type-name capture,target inspection,gameplay command or fallback.

The enum and both transport mappings remain exactly78 values0..77. Code48
CandidateHitboxType and its wire string remain reserved historical vocabulary;
do not renumber,remove,reinterpret or manufacture an emission to retain coverage.
Other40 candidate rejection leaves remain active and tested. Runtime sampling,
HTTP routes and schema remain gameplay generic_event_v3. No wire-body,host,
controller,action accounting or timeout change.

## Source and release boundaries

Inherit the [v4 contract](PHASE_1_GENERIC_EVENT_RELEASE_V4_CONTRACT.md) and its
v3 inherited operational boundaries except for the precise hitbox change above
and this release's identities. All other production changes are mechanical
release namespace/operator/assembly changes. Parent,upgrade and removal native
replacements remain namespace-only; core,hooks,lifecycle binding,card session,
wire and Python host remain frozen source links. No event-name registration,
new interaction family,profile/save/Cloud access,foreign-mod mutation,network
dependency or target-game execution offline.

Namespace `Sts2AgentBridge.Successors.GenericEventReleaseV5`; native classes keep
their existing GenericEventV3 names. Assembly/manifest/overlay
`Sts2AgentBridgeGenericEventV5`,version1.0.0; stored two-entry package
`Sts2AgentBridgeGenericEventV5-1.0.0.zip`; canonical root
`/private/tmp/sts-generic-event-v5-release`; campaign `GENERIC-EVENT-V5-SMOKE-V1`;
state `Sts2AgentBridgeCampaign-generic-event-v5-smoke-v1`; operator leaf
`generic_event_v5`. Preserve all existing conflict rejection and add v4 state,
overlay and operator remnants. The operator directory's existing exact-shape rule
may reject old operator siblings without a new traversal. No prior state,artifact
identity or credential may be reused.

Root owns contract,checker,production closure,client,package,operations,derivation
and living documentation. B owns native replacements,native/diagnostic fixtures
and mechanical enum namespace. A owns runtime except enum,transport,runtime and
transport tests,and socket integration. R owns independent review and verifier/
policy/mutations. One SDK lane; use disposable offline snapshots. No predecessor
edits. Exact derivation and source freeze follow acceptance.

## Required evidence

Preserve the13 project categories and existing suites. The differential baseline
now source-links frozen v4 native replacements and enum, using the same inert
trace stubs and inputs as v5. Keep all14 unchanged-path traces equal in observable
getter/validity/enumeration order/counts, candidate snapshots and outcomes.

Explicitly reproduce the measured mismatch with a controlled valid derived
hitbox: frozen v4 must return code48; v5 must admit that same fixture input. This
fixture does not claim the live subtype's name. Cover both creation and recapture.
Keep40 active rejection-leaf cases plus the explicit reserved-code reproduction
and positive subtype case. Preserve original745 lifecycle assertions,168 older
diagnostic assertions and38 release-native assertions unless an exact reviewed
expectation is directly affected by this repair; report changes honestly.

Add native subtype cases for initial null/dead/invisible/all-disabled hitboxes,
partly disabled legal masking, retained instance invalidation,and replacement
with another compatible derived instance after admission. Invalid/replaced
instances must stop before extra child dispatch. Preserve all non-hitbox subtype
rejection checks and exact selected-original/deck reconciliation.

Add one actual native-hooks→session→wire→owner-frame runtime→Python successful
reward scenario using retained derived hitboxes on every offered card. Verify
exact selected originals added,baseline deck preserved,unchanged hitbox references,
normal Proceed/map completion and owner cleanup. Expected normal fixed fixture
accounting:2parent actions,2child actions,6reads. Retain all16 old socket scenarios,
including candidate-card-type rejection. No controller fake substitutes for this
composition. Preserve all78 mappings and reserved48 transport acceptance.

Independent source review must establish that only hitbox type equality changes.
Two byte-identical compile-only production builds,exact source/metadata/IL policy,
verifier mutations and full candidate aggregate must pass. Preserve existing91
verifier checks; add focused policy evidence for required hitbox liveness and
unchanged non-hitbox type checks as useful. Freeze the new source identity and
repeat the full aggregate, including frozen-client source validation. Only pinned
game-owned Harmony with inert stubs executes offline; production,sts2 and Godot
remain compile-only. No new target inspection is implied by missing test data.

## Fresh bounded live test

After independent acceptance and both release gates,publish the exact package,
verify stopped game/closed port and the429-file clean base,install fresh,and
verify protected metadata without credential-content reads plus exact overlay.
Then tell the user to launch manually: Profile3,single-player,fresh Room Full of
Cheese initial options,Gorge untouched,no selector/console/map/popup. Verify UI
and require-running before exactly one new client invocation. No retry/adoption
or manual child selection after uncertainty. Success requires two original cards
added followed by explicit Proceed/map; otherwise preserve only bounded result
and finite diagnostic,without overclaiming downstream guards or effects.

Normal quit,stopped/closed,code-first quarantine,exact owned purge,clean base and
stopped/closed close the campaign. Repeated unmodded launch remains waived.
Persistent user authority covers this bounded repair and fresh live test after
all gates; no new permission flow or automatic game launch is introduced.

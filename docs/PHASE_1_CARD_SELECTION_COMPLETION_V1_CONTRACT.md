# Card selection completion v1 repair contract

Proposed 2026-09-06 at clean integration source `14d32b5`, in the selected 23cf
checkout. This document becomes accepted only when its exact hash is recorded
in the new acceptance ledger after independent review. The user's standing
request covers continued development and later bounded live tests. No additional
capability or new target inspection is selected.

## Problem and exact correction

The Smith live prefix and complete cleanup are recorded in
[the release ledger](research/PHASE_1_CARD_SELECTION_RELEASE_V1_ACCEPTANCE.md).
The raw response was not retained. This repair addresses an independently
proven source mismatch; it does not claim the historical hidden rejection.

The frozen native adapter is SHA256
`bdf25e398b9ff2e589db17eee066a38c7fe347a5e0282d2b0f8a1bddc4158290`.
Its CaptureCore caches preview identity/originals and labels a closed selector
Submitted without clearing them. The unchanged core (SHA256
`6621da8f4fc9e83d3ffd566005e639a86cf9e531475b982d90718b30c6be353e`)
requires Submitted to have no selector top, preview-open flag, preview identity
or preview originals. The adapter also labels task completion while the selector
remains top Submitted, which violates the same shape. Previously approved static
IL establishes selection completion before overlay removal.

Create only `bridge/Sts2AgentBridge/successors/card_selection_completion_v1`.
Derive `native/PinnedCardSelectionV1NativeAdapter.cs` from the exact frozen source
with only these two checked replacements inside CaptureCore:

1. In the selectorClosed branch, retain phase Submitted and explicitly set
   previewIdentity=null, previewOriginals=Array.Empty<object>(), and
   confirmControl=null. previewOpen already initializes false. Cached candidate,
   task, context, original-model and deck identities remain unchanged.
2. In the branch where the completion task is no longer Incomplete while the
   selector remains visible, change phase Submitted to Transient. Preserve the
   cached preview-open value and all other projected facts. The unchanged core
   handles this bounded monotonic prefix without publishing new actions.

All other adapter bytes remain identical. Do not modify the core validator or
completion prerequisites. Preserve canceled/faulted-task rejection, exact selected
originals and counts, complete domain/deck, exact upgrade/add delta, effect witness,
map/room/foreground/context/reference guards, late stale revalidation, timeout,
reservation, no retry and disposal. In particular, map travel/Proceed guards
remain unchanged; no unrelated mixed state is newly permitted. Cheese add-two
and ordinary Smith upgrade-one remain the only selected native policies.

## Composition, ownership and preservation

All eleven accepted successors, their manifests, contracts, packages and the old
48-file bridge remain byte-exact. The new production assembly has exactly the
same 30 source inputs as card_selection_release_v1, with one substitution: the
new derived child adapter replaces the frozen child adapter. The other 29 inputs
are linked byte-exact. No new target member, getter, action, reference, runtime,
wire route, schema, host, learner, profile access or API capability is added.

Keep assembly/manifest identity Sts2AgentBridgeCardSelectionV1 version1.0.0 and
the exact 370-byte manifest. Keep the existing production namespaces/types,
protected card_selection_v1 config, both selected-flow enums, fixed endpoint,
credentials, request framing and budgets. A new candidate hash, source policy,
package identity and operational state distinguish this corrective revision.

- A owns native/, native_tests/ and derivation/: exact derived adapter, inert
  target stubs, actual-adapter/actual-core regression projects and executable
  original-to-derived byte proof. Original controls must source-link the frozen
  adapter and demonstrate both rejected prefixes. No real target assembly is
  referenced or executed by the fixture. Define any original-control symbol in
  a separately pinned test project only.
- B owns production/ and independent A review: the exact 30-input substitution,
  two fresh deterministic compile-only candidates and source/metadata change
  review. No new source or target behavior may be inferred from this ownership.
- R owns verifier/, verifier_tests/ and policy/, plus independent contract and
  aggregate review. Derive the accepted shipping verifier and mutation harness
  with only final source/artifact/policy pins and one source-path substitution.
  Preserve all 57 semantic/PE mutations and 10 CLI negatives. Shipping verification
  has no policy-generation mode; extraction remains in the test harness.
- The coordinator owns properties, client/operations/package, aggregate/checker,
  freeze helper, manifests and docs. No two writers share a path.

## Operational identities

Use a separate artifact root `/private/tmp/sts-card-selection-completion-v1-release`,
campaign ID `CARD-SELECTION-COMPLETION-V1-SMOKE-V1`, and state directory
`Sts2AgentBridgeCampaign-card-selection-completion-v1-smoke-v1`.
The fixed overlay remains Sts2AgentBridgeCardSelectionV1. Reject and preserve
all previously closed conflict paths, including the card-selection-release
campaign state, the new state and any existing operator parent or overlay.

Derive the accepted operational/client/package tools with an executable exact
source/hash/replacement manifest. Preserve descriptor/ACL/UID/inode validation,
protected selection and fresh credentials, publish-code-last, code-first
quarantine, immutable state lineage and exact four-file purge. Keep all existing
fault fixtures and add the new prior-state conflict. Never overwrite or adopt
an existing package, overlay, state, operator unit or previous source identity.
All artifact/policy/project/check counts remain explicitly pending until measured,
reviewed and pinned; no preliminary candidate is accepted as final.

## Required gates and live boundary

Use the actual derived native adapter and actual frozen core with inert target
stubs to cover at least: ordinary selection/preview; accepted confirmation;
task-success while overlay remains => bounded wait; closed selector with empty
preview metadata => bounded wait; exact deck upgrade before parent completion
=> continued wait; final Proceed/travel witness => resolved with correlated
history and no retry. Include immediate-close, canceled/faulted/wrong-original,
context/overlay replacement, incomplete or altered deck, invalid foreground/map,
and double-effect/replay negatives. Preserve Cheese's exact-two commitment and
late-effect wait; exercise the shared completed-task/top transition there too.
The old adapter must reject the two original malformed shape cases in the same
harness. Do not manufacture or reconstruct any discarded live response.

Require exact derivation, all eleven predecessor and old48 identity checks,
explicit project/source closure and no production test seams. Run the frozen
operator/bootstrap/runtime/Python host/transport/client/socket suites, the new
native regressions, package and synthetic installation checks, fault/conflict
fixtures, whole-assembly metadata/IL verifier, all 57 mutations and 10 CLI cases.
Use SDK9.0.303 offline, two pinned compile-only references, fresh physical source
snapshots and two identical production builds with independent reproduction.
No candidate or target assembly is executed. Freeze and exclusively publish only
after complete aggregate and independent review pass. Run relevant regression;
unchanged existing full repository evidence remains identified as such.

Live testing requires a fresh campaign after acceptance. Keep the game closed
for source/package/base429/stopped/closed/conflict preflight and installation.
The previous rest site has an uncertain completed action and is unsuitable for
retry. Ask the user for another untouched ordinary rest site on Profile3
Ironclad A0, with Smith untouched and no selector/map/popup. Verify supported UI,
then invoke the fixed client exactly once with the new installed-state hash.
No preliminary authenticated read or replay is allowed. Report the sanitized
prefix exactly; no upgrade or map handoff is proven without full reconciliation.

Always quit normally, confirm stopped/closed, quarantine code first, purge
exactly owned objects and verify unchanged base429/zero overlay/fixed absences.
Unmodded relaunch remains waived. No profile/save filesystem, Steam Cloud change,
retained live corpus, remote Git or broader capability work is authorized.

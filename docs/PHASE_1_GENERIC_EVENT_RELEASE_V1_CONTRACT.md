# Generic event release v1 contract

2026-09-07. Independently accepted production composition of frozen generic_event_v3. User
has authorized preparation/installation and bounded live testing, and is waiting
for an explicit launch instruction. Preserve all17 predecessor trees/contracts
and original48 bridge files. New root: successors/generic_event_release_v1.
No game launch until packaging, independent review, aggregate and stopped/base/
closed-port preflight pass and exact installation succeeds.

## Production composition

Link actual frozen generic_event_v3 core/wire/native plus frozen card_selection_v1
core/wire/native rules, without modifying them. Derive the prior card release's
transport, operator loader, lifecycle and frame connector under new GenericEvent
names. Exactly one generic event session is created on the game owner frame.
No named-event admission catalog; first live target Cheese is a campaign test
policy only. Constructor failure must retain a cleanup-only runtime if failed
Harmony installation rollback left hooks. Keep the owner-frame connection until
RecoverFailedInstallation succeeds. Service disposal must be retryable after
exceptions; do not mark service disposed or drop its reference before successful
native hook removal. Disposal of frozen wire/session/native already retries.
Transport stops first; no cleanup thread may touch Godot or unpatch hooks.

Production uses the game's existing exact0Harmony.dll,2328064bytes,SHA256
 ef1898322c9f5c86dc1b0758b272a9c440823b4a41ca9a0b82a3aa6b3d206387,
at the fixed pinned game data directory. Assembly0Harmony,version2.4.2.0,
culture neutral,unsigned,MVID6b813929-656e-4f25-9e34-f25e7084505d. No embedded second copy or loader.
Compile actual frozen v3 sources against that exact game dependency. Before
constructing hooks, verify actual typeof(Harmony).Assembly file path/hash/assembly
identity/MVID and intended load-context binding; reject unverifiable or competing
Harmony instances. Guard runs only after valid operator/credential/pinned build.
No Assembly.Load/LoadFromStream, arbitrary probing or network dependency loading.
The frozen v3 fixture's NuGet2.4.2 dependency remains unchanged and is separately
identified. Its550 native assertions are prior NuGet-library evidence, not proof
of the game's Harmony runtime behavior. New production API compile and live
results remain distinct. New inert hook fixtures may execute this pinned third-
party Harmony library against target stubs; sts2,GodotSharp and production candidate
assemblies are never executed offline. No dependency bytes are redistributed.

Factory failure seam: public GenericEventTransportFactoryFailure(Action
ownerFrameCleanup) carries cleanup ownership after failed native construction.
Runtime Create catches it distinctly and returns a retained nonnull cleanup-only
runtime. Start returns false; StopTransportAndJoin settles transport; owner-frame
DisposeServiceOnOwnerFrame retries the delegate. Preserve it after exceptions,
mark ServiceDisposed only after successful return, detach frame only afterward.
Ordinary exception/null factory results may return null only with no retained
native ownership. Network/timer/process-exit workers never run cleanup.

## Wire transport and Python controller

Canonical config is exact UTF8 without newline:
{"schema_version":"generic_event_v3_transport_config_v1","enabled":true,"flow_kind":"generic","bind_address":"127.0.0.1","port":43117,"token_file":"credential.hex"}

Runtime enum GenericEventReleaseSelection.Generic=1. Runtime factory API follows
predecessor: Create(byte[] config,Func<byte[]> reader,
Func<GenericEventReleaseSelection,string,GenericEventV3WireService> factory).
Namespace Sts2AgentBridge.Successors.GenericEventReleaseV1; class prefixes
GenericEventTransport, GenericEventBootstrap. Actual frozen wire routes only:
GET /probe/generic-event-v3/public/decision and
POST /probe/generic-event-v3/public/action, HTTP/1.1. One authenticated exchange
at a time, exact127.0.0.1:43117, fixed64lowerhex credential, no HTTP request body.
Keep prior exact header order Host,Authorization,Accept; POST adds
X-Sts2-Decision-Id and X-Sts2-Action-Id. Child POST additionally adds, in order,
X-Sts2-Child-Ordinal (canonical1..4), X-Sts2-Parent-Decision-Id (64lowerhex),
X-Sts2-Parent-Action-Id (choose:0..7). Finish Connection: close and CRLFCRLF.
GET5 lines, parentPOST7 lines, childPOST10 lines including request line.
Action choose:0..7 is parent-only; child select:0..63,preview,confirm only.
Parent body reconstructed as decision_id,action_id,child:null in that order;
child body includes ordinal,parent_decision_id,parent_action_id in that order.
Header cap1024, response cap65536. Reject duplicates, extra/trailing bytes,
malformed lineage/headers, cross-route actions and noncanonical numbers.

Keep owned byte queue, bounded workers/authentication/rate limits, deadline and
zeroing semantics. Reserve every POST identity before owner-frame dispatch;
cap12 parent,40 child,52 total,2048reads; frozen core enforces4children10actions
perchild. Timeout/partial write after uncertain action is terminal and never
retried. Final successful parent decision (status complete/phase map_handoff) is terminal;
unsupported/errors/rejected actions are terminal. A resolved child alone is not
terminal. Runtime classification validates protocol, nonce and bounded canonical
envelope; actual frozen wire is sole semantic producer and host fully validates
all descriptors/actions/results before progressing. Response always canonical200
JSON only for valid wire output, using retained security/cache headers.

Python transport mirrors exact request grammar and retained bounded pacing,
one30second host deadline, mutable credential transfer/zeroing. Invoke frozen
run_event once with an explicit deterministic first_legal conformance provider;
no strategic claim. Generic first-legal session starts only on the user-prepared
initial event, after verifying requested campaign choice visible. Return only
bounded fixed status/code/count summary, no raw decisions, labels or credentials.

## Fixed deployment and operational boundaries

Assembly/manifest leaf Sts2AgentBridgeGenericEventV1; version1.0.0;
manifest describes restricted generic event control, has_dll true,has_pck false,
affects_gameplay true,min_game_version0.107.1,dependencies[]. Canonical2entry
stored ZIP, DLL then JSON, epoch1980,mode0644, no extras/links/overwrites.
Artifact root /private/tmp/sts-generic-event-v1-release.
Campaign GENERIC-EVENT-V1-SMOKE-V1; state root
Sts2AgentBridgeCampaign-generic-event-v1-smoke-v1; operator leaf generic_event_v1;
overlay Sts2AgentBridgeGenericEventV1. One fresh canonical generic config only.
New narrow operational copies derive from card_selection_completion_v1.
Retain descriptor/inode ownership, no grants/links, exclusive install, code-last
publication, durable state generations, conservative fault rollback, code-first
quarantine and exact purge. Reject all prior known campaign/overlay conflicts,
including card-selection-v1 and card-selection-completion-v1 states and the shared
Sts2AgentBridgeCardSelectionV1 overlay. No adoption/overwrite/co-installation.
Client CLI only --expected-state-sha256; fixed paths/UID/home/platform, verify
source/contract/package/state before credential transfer. No generic path/port.
No profile/save/Cloud access, foreign mods, remote Git or retained live corpus.

## Validation and ownership

A runtime lane owns runtime/,runtime_tests/,integration/ socket fixture and
transport/ plus transport_tests/. B native lane owns operator/,operator_tests/,
lifecycle/,lifecycle_tests/,native/,native_tests/,production/. Root owns client/,
client_tests/,operations/,package/,check.py,identities,derivation,docs. Reviewer
owns verifier/,verifier_tests/,policy/ after contract acceptance and final source
candidate. One SDK lane, disposable offline snapshots, no compiled outputs in
source trees. Production tests use inert target stubs; target/candidate production
assemblies compile only until installed game launch.

Tests must cover real v3 wire/core-to-socket-to-frozen Python (upgrade/removal/add,
completion versus child completion, lineage, lost responses), malformed requests,
auth/rate/budget/deadline, queue races/zeroing, cleanup retry and failed-install
recovery, operator config/descriptor failures, resolved game-Harmony identity/conflicts,
manager transactional fault matrix, predecessor conflicts, package mutation and
source/project closure. Build two identical candidates, then independently review
metadata/IL and exact dependency policy; reflection allowed only in exact frozen
hook owner and bounded Harmony identity guard, not globally. Freeze only after integrated gate
and review, repeat against frozen identity, publish verified artifact, preflight
read-only then install. Tell user to launch only after installation verifies.

## First bounded campaign

Profile3,single-player,Room Full of Cheese initial choices,Gorge untouched,no
selector/console/map/popup. First verify intended visible choice and no unrelated
manual interaction. One controller invocation only; expected two original cards
added then explicit Proceed/map. Unknown/uncertain result ends invocation without
retry. Keep sanitized summary and necessary identities only. After campaign quit
normally, verify stopped/closed, quarantine code first,purge owned material,verify
base. Repeated unmodded launch remains waived, not reported passed. Live success
requires actual evidence; offline acceptance never establishes it.

Independent design review accepted map_handoff terminal semantics, exact game-owned
Harmony binding and retained cleanup-only runtime/retry ownership before implementation.

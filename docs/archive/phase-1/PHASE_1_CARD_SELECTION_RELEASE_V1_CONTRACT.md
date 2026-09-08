# Card Selection V1 release and live-readiness contract

- Date: 2026-09-06
- State: proposed for independent review; implementation is not authorized by
  this draft until the coordinator records the exact accepted SHA256
- Baseline: selected `23cf` integration checkout, implementation commit `8fc1db7`;
  the accepted card component identity is recorded below
- Outcome: compose the frozen card-selection component into one independently
  verified, authenticated loopback release for bounded Cheese and Smith live
  campaigns

This is a new isolated successor under
`bridge/Sts2AgentBridge/successors/card_selection_release_v1`. It does not edit
or replace old `0.8.0`, any of the nine predecessor successor trees, or the
card-selection component after that component is source-frozen. The release
adds no card operation beyond the accepted Cheese Gorge add-two and ordinary
Smith upgrade-one parent paths. It exposes the component's four frozen routes,
uses one owner-frame queue, and packages one self-contained production DLL.

The user's standing authorization covers development and later bounded live
campaigns for this selected capability. Repository work needs no new permission
step. No implementation result, fixture, package, or preflight result is live
evidence. A campaign still follows the operational boundary below: exact
preflight, transactional install, user-assisted screen preparation, one client
controller invocation, and complete teardown. Nothing here authorizes profile
or save reads, Cloud changes, retained live payloads, target execution during
build or verification, new target inspection, remote Git, or broader game
actions.

## Frozen dependency and identity gate

The hard dependency is the accepted `card_selection_v1` component at `8fc1db7`:

- contract SHA256 `af8125ba2dd7bd8d7df85144f5a275d20a347ca7d4fe5bd5e666e53b3f57186c`;
- source manifest SHA256 `ca4e18dbb66520481881ea86a91925162593f8496c7abccc061a31f1c319a0ac`;
- 40-file inventory SHA256 `51135dfb6749d58b897bb4670ffa709ca5b756873464c9e045f2ba80f87bfc64`.

The aggregate gate and independent review passed. Implementation packets must
verify this manifest and every file before compiling or copying card sources.
No card component source may change during release composition.

The release's candidate DLL, source projection, metadata projection, policy,
manifest, ZIP, package root inventory, and successor source manifest are also
**pending reproducible build and review**. They must not be invented, learned by
the shipping verifier, or recorded as accepted from a preliminary build. The
coordinator fills them only after two deterministic builds from the frozen
source closure are byte-identical and the independent verifier review accepts
the extracted policy.

## Exact operator configuration

The protected operator subtree is exactly:

`~/Library/Application Support/Sts2AgentBridge/card_selection_v1`

It contains exactly `config.json` and `credential.hex`. The credential is a
fresh mutable buffer containing exactly 64 lowercase hexadecimal ASCII bytes.
The only enabled configuration documents are the following exact ASCII byte
strings, with no BOM, whitespace, or trailing newline:

Cheese, 164 bytes, SHA256
`56d2698f87dc4b82e61d3a0eca57ea524c6c3397a0cc082f1500b42a00bccec6`:

```json
{"schema_version":"card_selection_v1_transport_config_v1","enabled":true,"flow_kind":"cheese","bind_address":"127.0.0.1","port":43117,"token_file":"credential.hex"}
```

Smith, 163 bytes, SHA256
`c78c22d0f4732e89a35bd0a34024cb31daf8a4bbca815157ac4b7a266171d93f`:

```json
{"schema_version":"card_selection_v1_transport_config_v1","enabled":true,"flow_kind":"smith","bind_address":"127.0.0.1","port":43117,"token_file":"credential.hex"}
```

Any other bytes, a disabled document, unknown flow, path, port, token name,
additional field, alternate order, or stale schema returns null before reading
the credential, invoking the service factory, or generating a nonce. The secure
Darwin descriptor policy, UID ownership, modes, no-follow traversal, bounded
reads, deny-only ACL handling, revalidation, and truthful close behavior are the
accepted item/room loader rules. Configuration and credential arrays transfer
once and are zeroed on every success, rejection, exception, stop, and cleanup
path.

Configuration is the sole policy selector. No public constructor argument,
environment value, command-line option, request field, or first observed room
may override it.

## Runtime and owner-frame contract

The production namespace is
`Sts2AgentBridge.Successors.CardSelectionReleaseV1`. The public runtime surface
is:

```csharp
public enum CardSelectionReleaseSelection
{
    Cheese = 1,
    Smith = 2,
}

public sealed class CardSelectionTransportRuntime : IDisposable
{
    public static CardSelectionTransportRuntime? Create(
        byte[]? configuration,
        Func<byte[]?> credentialReader,
        Func<CardSelectionReleaseSelection, string,
            CardSelectionV1WireService> factory);

    public bool Start();
    public bool DrainFrame();
    public bool StopTransportAndJoin();
    public bool TransportStopped { get; }
    public bool DisposeServiceOnOwnerFrame();
    public bool ServiceDisposed { get; }
    public bool IsTerminalOrStopping { get; }
    public bool IsFullyStopped { get; }
    public void Dispose();
}
```

`Create` runs on the captured owner frame. It validates and copies the exact
configuration, constructs the authenticator, queue, buckets, cancellation and
settlement primitives, and generates one 16-byte random lowercase-hex session
nonce before invoking the factory exactly once. It never invokes the factory
for invalid configuration or credential. After the factory returns a non-null
service, ownership remains in the runtime until definitive owner-thread
disposal; no failure may lose or expose that service.

`Start` binds only IPv4 loopback `127.0.0.1:43117`, once. Test listeners are
ephemeral loopback only, are compiled under a test symbol, and the seam and its
endpoint predicate are absent from production metadata. `DrainFrame` and
`DisposeServiceOnOwnerFrame` accept only the captured owner thread. `Dispose`
requests and joins transport stop only. Truthful full cleanup is:

1. stop accepting and cancel or retire all queued/unclaimed work;
2. settle the accept task, workers, active sockets, queue slots, and retained
   canceled tombstones;
3. publish `TransportStopped` only after every transport primitive's last use;
4. call `CardSelectionV1WireService.Dispose` once on the owner frame and outside
   `Handle`;
5. publish `ServiceDisposed` only after that cleanup succeeds;
6. detach the Godot frame callback only after service disposal.

`IsFullyStopped` means `TransportStopped && ServiceDisposed`. A stop/join false
result defers disposal; it never reports completion early. Start/bind/accept
failure enters the same owner cleanup. The accepted bootstrap lifecycle's
five-second timer bounds only pending frame attachment/startup. There is no
active runtime TTL because user navigation can take minutes.

## Selected-policy wrapper

The frozen parent native adapter recognizes both supported parent surfaces.
Therefore the new release owns one capability-reducing wrapper,
`ConfiguredCardSelectionParentV1NativeAdapter`, around exactly one
`PinnedCardSelectionParentV1NativeAdapter`.

The wrapper may forward `Missing` and `Unsupported` captures. Before forwarding
any `Available` capture, it requires:

- Cheese configuration: `CardSelectionParentV1PolicyKind.CheeseGorgeAddTwo`;
- Smith configuration: `CardSelectionParentV1PolicyKind.RestSmithUpgradeOne`.

A mismatch throws into the frozen parent session's fail-closed capture boundary,
latches unsupported, publishes no ready decision, and disposes through the
normal owner cleanup. The wrapper cannot call an action, manufacture a capture,
change a policy, or inspect new target state. It rechecks every available
capture; the frozen parent session separately binds all identities and policy
fields.

The production factory constructs, in order, the configured wrapper, one
`CardSelectionParentV1Session(nonce, adapter)`, and one
`CardSelectionV1WireService(nonce, session)`. Every ownership edge has exact
unwind disposal. The runtime classifier independently rejects a ready parent
pair that does not match the protected configuration:

- Cheese: `parent_kind=event`, `policy=cheese_gorge_add_two`;
- Smith: `parent_kind=rest`, `policy=rest_smith_upgrade_one`.

A mismatched body is never sent and requests terminal stop. This second check is
defense in depth, not authority to reinterpret a capture.

## Four-route authenticated transport

The only service routes are the frozen component strings:

- `GET /card-selection-v1/parent`
- `POST /card-selection-v1/parent/action`
- `GET /card-selection-v1/child`
- `POST /card-selection-v1/child/action`

The outer socket protocol deliberately retains the accepted room transport's
bounded EOF/half-close request form. It accepts one exact ASCII HTTP/1.1 request
head of at most 1024 bytes, with CRLF after every line and in this exact order:

1. `<method> <frozen-route> HTTP/1.1`;
2. `Host: 127.0.0.1:43117`;
3. `Authorization: Bearer <64lowerhex>`;
4. `Accept: application/json`;
5. for POST only, `X-Sts2-Decision-Id: <64lowerhex>`;
6. for POST only, `X-Sts2-Action-Id: <canonical-action>`;
7. `Connection: close`;
8. an empty line, followed immediately by request-direction EOF/half-close.

GET has no decision or action headers. POST has exactly the two listed headers. Parent actions are `begin` or `proceed`; child actions are
`select:<0..63>` without leading zero, `preview`, or `confirm`. Duplicate,
reordered, extra, folded, non-ASCII, body-bearing, unterminated, or trailing
request bytes are rejected by silent close.

After authentication and POST reservation, the runtime constructs this exact
canonical UTF-8 service body in a newly owned mutable buffer:

```json
{"decision_id":"<64lowerhex>","action_id":"<canonical-action>"}
```

GET passes null. The frame callback invokes exactly
`CardSelectionV1WireService.Handle(method, frozenRoute, body)` once. The body is
at most the frozen 256-byte service limit and is zeroed after the call. The
Python socket adapter performs the inverse: it accepts the frozen host's exact
canonical mutable POST body, validates and extracts only those two fields,
writes the exact header form, and zeroes request, response, and intermediate
buffers. Round-trip fixtures prove that header adaptation reconstructs the
exact service bytes. This adapter does not define a second gameplay protocol.

Every response is exactly `HTTP/1.1 200 OK` with canonical content type,
decimal Content-Length, `no-store`, `nosniff`, and close headers. All four route
bodies are bounded to 65536 bytes. Only an actual frozen service body with a valid internal status/body pair can
be returned. Internal `CardSelectionV1WireResponse.StatusCode` must be 200 for
validated module values, 400 only for the exact `invalid_request` error, or 500
only for the exact `internal_failure` error. The outer transport deliberately
wraps those two legitimate fixed error bodies as HTTP 200 so the frozen host can
read the fixed error code, then stops terminally. Every other internal
status/body pair closes silently and terminally. Parser, authentication,
reservation, queue, classifier, or transport failures also close silently; they
do not synthesize a wire response.

## Budgets, reservation, and uncertainty

The release has one authenticated exchange in flight across all routes. Limits
are global per runtime:

- 1024 GET submissions total;
- 2 parent POST attempts total;
- 10 child POST attempts total;
- 4 concurrent unauthenticated socket handlers and backlog 8;
- pre-authentication bucket 32/second, burst 16;
- authenticated bucket 20/second, burst 16;
- header read and response write 1 second each;
- connection lifetime and shutdown join 2 seconds each.

The fixed client uses a 3-second exchange deadline, one shared minimum 50 ms
interval across parent and child exchanges, and a monotonic finite 30-second
controller deadline. A backwards, non-finite, or invalid clock fails closed.

GET reserves its count before queue submission. POST validates canonical
route/decision/action, rejects every duplicate route/decision/action identity,
and reserves both identity and route budget before the authenticated bucket and
before frame submission. The permanent identity is the exact tuple
`(route, decision_id, action_id)`. The frozen service separately enforces decision
correlation and the host enforces global accepted-decision non-reuse. Reservation is permanent. A competing authenticated
request requests terminal stop; it cannot invoke the service or replay later.
Timeout after claim, callback fault, invalid service body, serializer failure,
lost receipt, partial/failed response write, or any exception after POST
reservation requests terminal stop with no retry and no synthesized outcome.
Canceled queue entries retain capacity until actually dequeued and retired.

The runtime may publish terminal intent only after the current response send
attempt, request/body/response zeroing, socket shutdown, and exchange release.
The lifecycle may observe stopping then begin the stop sequence; it cannot
dispose the service while `Handle` is active.

## Exact route-aware terminal table

Classification parses canonical JSON and exact ordered envelope fields. It
checks schema, kind, version, nonce, ordinal, route, internal status/body pair,
and the configured parent policy pair. Observations and resolved values use
`status`; POST receipts and failures use `outcome` and have no `status` property.
Fixed errors use `status=error`. It never searches raw text or event/card keys.

| Route | Allowed nonterminal service values | Terminal service values |
| --- | --- | --- |
| parent GET | `parent_observation` `ready` or `waiting` | `parent_observation` `unsupported`; `parent_resolved` `resolved`; fixed error |
| parent POST | `parent_receipt` `outcome=accepted` | `parent_failure` `outcome=rejected`, `unsupported`, or `uncertain`; fixed error |
| child GET | `child_observation` `ready` or `waiting`; `child_resolved` `resolved` | `child_observation` `unsupported`; fixed error |
| child POST | `child_receipt` `outcome=accepted` | `child_failure` `outcome=rejected`, `unsupported`, or `uncertain`; fixed error |

Child resolution is not parent terminal. The controller must return to parent
GET, obtain the separately correlated `proceed`, and finish only at exact parent
`map_handoff`. Any kind/status/route complement, malformed nesting, duplicate
property, wrong order, wrong nonce/version/ordinal, selected-policy mismatch,
or unknown fixed error is invalid and terminal without sending the body.

The controller retains the frozen card host invariants: choose the first legal
unselected slot until exact maximum, use preview/confirm only when advertised,
never confirm one card for the exact-two Cheese policy, validate every receipt,
candidate order, selected set, monotonic prior-results prefix, required commit
sequence, child result, and final begin/proceed correlation. Summary output is
only schema/version status, optional fixed code, and the six attempted,
accepted, and reconciled parent/child counts.

## Exact production source closure

The production project uses `EnableDefaultCompileItems=false`, no project or
package references, and exactly the following 30 C# inputs. Paths are relative
to `successors/card_selection_release_v1/production`.

Frozen card component, 11:

1. `../../card_selection_v1/core/CardSelectionV1Contracts.cs`
2. `../../card_selection_v1/core/CardSelectionV1Session.cs`
3. `../../card_selection_v1/parents/CardSelectionParentV1Contracts.cs`
4. `../../card_selection_v1/parents/CardSelectionParentV1Session.cs`
5. `../../card_selection_v1/native/CardSelectionV1NativeRules.cs`
6. `../../card_selection_v1/native/PinnedCardSelectionV1NativeAdapter.cs`
7. `../../card_selection_v1/parent_native/CardSelectionParentV1NativeRules.cs`
8. `../../card_selection_v1/parent_native/PinnedCardSelectionParentV1NativeAdapter.cs`
9. `../../card_selection_v1/wire/CardSelectionV1WireProtocol.cs`
10. `../../card_selection_v1/wire/CardSelectionV1WireCodec.cs`
11. `../../card_selection_v1/wire/CardSelectionV1WireService.cs`

Exact reusable predecessor inputs, 6:

12. `../../item_transport_v1/runtime/kernel/FixedTimeAuthenticator.cs`
13. `../../item_transport_v1/runtime/kernel/MonotonicTokenBucket.cs`
14. `../../item_bootstrap_v1/operator/DarwinReadOnly.cs`
15. `../../item_bootstrap_v1/operator/ItemOperatorConfiguration.cs`
16. `../../item_bootstrap_v1/operator/ItemPinnedFileIdentity.cs`
17. `../../item_bootstrap_v1/native/PinnedItemBuildGuard.cs`

New release inputs, 13:

18. `../runtime/OwnedByteFrameQueue.cs`
19. `../runtime/CardSelectionTransportConfiguration.cs`
20. `../runtime/CardSelectionTransportContracts.cs`
21. `../runtime/CardSelectionTransportProtocol.cs`
22. `../runtime/CardSelectionTransportRuntime.cs`
23. `../operator/CardSelectionOperatorFiles.cs`
24. `../lifecycle/CardSelectionBootstrapLifecycle.cs`
25. `../native/ConfiguredCardSelectionParentV1NativeAdapter.cs`
26. `../native/ProductionCardSelectionRuntimeFactory.cs`
27. `../native/CardSelectionBootstrapHost.cs`
28. `../native/CardSelectionBootstrapSupport.cs`
29. `../native/CardSelectionGodotFrameConnector.cs`
30. `../native/CardSelectionModEntry.cs`

The only external compile references are the exact pinned `sts2.dll` and
`GodotSharp.dll`, both compile-only. The resulting package contains no
dependency DLL, PDB, PCK, config, credential, source, or test seam. Existing
accepted native adapters and bootstrap/build-guard calls are the whole target
API surface; this release adds no target getter or action.

## Whole-assembly verifier and policy

The verifier is a framework-only .NET 9 metadata program using `PEReader`. It
never loads or resolves the candidate or target assemblies. It has one verify
mode and no learn, update, generate, override, package, install, or execution
mode.

It verifies exact candidate identity, exact 30-source closure, complete metadata
inventory, decoded method bodies and control flow, assembly references, native
imports and flags, sole initializer and entry method, route literals, and
sensitive call routes. Unknown rows, bodies, references, attributes, resources,
initialized data, native calls, or sources fail closed. Reflection, emit,
dynamic loading, process creation, filesystem writes, pipes, HTTP/WebSocket/
QUIC, and candidate reachability to production-excluded test methods are
forbidden.

The generic metadata-name and IL-decoder helpers may be exact source links to
the independently accepted room-release helpers. The route extractor must be
newly reviewed: the room verifier's `/probe/...` pattern does not recognize the
four `/card-selection-v1/...` routes. The new extractor accepts exactly those
four full strings and no prefix family. It also proves the configured-policy
wrapper lies on the sole factory-to-parent-adapter path and that owner-frame
dispatch reaches only `CardSelectionV1WireService.Handle`. Production contains
no `ForTests`, `Synthetic`, `StartForTests`, or test endpoint member.

Exactly the 13 read-only `/usr/lib/libSystem.B.dylib` imports from the accepted
Darwin loader are allowed, with exact owner, signatures, Cdecl and SetLastError
flags. No other P/Invoke or native loader is accepted.

The reviewed policy is extracted offline from the final deterministic candidate
and readable source inventory, then independently checked and pinned. The
shipping verifier embeds only its accepted policy SHA256 and expected scalar
counts; it does not generate or emit policy. Semantic mutation tests alter real
PE metadata/IL and cover route literals, wrapper bypass, service/frame call
edges, terminal classification, native flags, initializer shape, test-seam
reachability, external members/signatures, sources, symlink ancestors, policy
bytes, and artifact bytes.

## Canonical package and transactional operations

The canonical package names are:

- `Sts2AgentBridgeCardSelectionV1.dll`
- `Sts2AgentBridgeCardSelectionV1.json`
- `Sts2AgentBridgeCardSelectionV1-1.0.0.zip`
- ZIP root and game overlay directory `Sts2AgentBridgeCardSelectionV1/`
- disposable release root `/private/tmp/sts-card-selection-v1-release`

The manifest uses the accepted fixed two-space/LF form, version `1.0.0`, no
dependencies, `has_dll=true`, `has_pck=false`, `affects_gameplay=true`, and the
pinned game minimum version. Exact manifest text, description, lengths and all
three artifact SHA256 values remain pending reproducible build review. ZIP
layout remains two stored files, DLL then JSON, timestamp 1980-01-01, mode 0644,
no extras, comments, directories, Zip64, overwrite, or adoption.

Operational tools are new narrow copies of the accepted room-release tools;
they never import mutable predecessor operations. Fixed names are:

- campaign ID `CARD-SELECTION-V1-SMOKE-V1`;
- state root `Sts2AgentBridgeCampaign-card-selection-v1-smoke-v1`;
- operator leaf `card_selection_v1`;
- overlay leaf `Sts2AgentBridgeCardSelectionV1`.

The durable state binds the selected Cheese or Smith config identity. Only one
campaign is active; complete cleanup is required before changing selection or
starting the other campaign. Modes remain install, quarantine, and purge with
code-first quarantine, exact generated-object ownership, inode/device binding,
exclusive publication, durable state generations, fault checkpoints, and
conservative rollback. No arm/disarm, repair, recovery, adoption, overwrite,
co-installation, profile/save access, or generic path/port option is added.

Install requires the stopped game, closed port 43117, exact clean base, absent
new overlay/state/operator wrapper, and absence of this closed conflict set:

| Application Support state directory | Game mods overlay directory |
| --- | --- |
| `Sts2AgentBridgeCampaign-r0i-batched-bridge-smoke-v1` | `Sts2AgentBridge` |
| `Sts2AgentBridgeCampaign-item-v1-collection-smoke-v1` | `Sts2AgentBridgeItemV1` |
| `Sts2AgentBridgeCampaign-room-flows-v1-smoke-v1` | `Sts2AgentBridgeRoomFlowsV1` |
| `Sts2AgentBridgeCampaign-shop-diagnostic-v1-smoke-v1` | `Sts2AgentBridgeShopDiagnosticV1` |
| `Sts2AgentBridgeCampaign-shop-map-permission-v1-smoke-v1` | `Sts2AgentBridgeRoomFlowsV1` (same fixed leaf) |

Absence of the whole `Application Support/Sts2AgentBridge` operator parent also
covers all predecessor operator leaves. These checks reject and preserve any
existing object at the fixed path; they do not discover through wildcards,
inspect arbitrary foreign contents, or mutate predecessor objects.
It writes the selected exact config and fresh credential transactionally, then
publishes verified code last. Runtime checks remain require-running,
require-stopped, and sample-base-port-closed; port state alone never proves code
identity. Clean-install verification accepts only the pinned base or the exact
new overlay pair.

The production client accepts exactly
`--expected-state-sha256 <64lowerhex>`. It validates fixed UID/home, state,
source manifests, overlay, package and selected config before transferring one
descriptor-bound mutable credential. It invokes the frozen
`card_selection_v1.host.card_selection_host.run_card_selection` exactly once
through the new fixed socket adapter. One controller invocation may perform its
bounded sequence of GET/POST exchanges; no wrapper retries it. Client output is
only the frozen bounded six-count summary or a fixed preflight/interrupted
failure. It never emits nonce, decision, action, card key, path, credential,
body, or raw response.

## Packet ownership and dependency graph

All writers use disjoint paths. The coordinator owns this contract, final
integration, source identities, checker, Python transport/client/operations,
package, campaign execution and documentation. Exact packet ownership is:

| Packet | Owner | Writable scope | Hard dependency | Output |
| --- | --- | --- | --- | --- |
| A-runtime | A | `card_selection_release_v1/runtime/`, `runtime_tests/` | accepted contract and frozen card wire API | C# transport/runtime and pure plus ephemeral-loopback fixtures |
| B-bootstrap | B | `operator/`, `operator_tests/`, `lifecycle/`, `lifecycle_tests/`, `native/`, `production/` | A public runtime API and frozen card native/parent APIs | secure loader, selected wrapper, owner lifecycle, explicit production project, compile-only candidates |
| R-verifier | R | `verifier/`, `verifier_tests/`, `policy/` | accepted source list; final policy waits for B candidate | default-deny verifier, real-PE mutations, independently reviewed policy |
| root-Python | coordinator | `transport/`, `transport_tests/`, `client/`, `client_tests/`, `operations/`, `package/`, integration/checker/manifests/docs | frozen schemas; final identities wait for deterministic candidate | socket adapter, controller composition, transactional tools, canonical artifacts and aggregate gate |

A publishes exact APIs before B composes them. B produces two deterministic
candidates from one verified source snapshot. R extracts and reviews policy
only from that final pair. The coordinator then pins package and operational
identities, runs cross-language socket composition against actual C# runtime and
frozen host, and performs the aggregate and independent reproduction gates.
Any contract change stops affected consumers until a new reviewed contract hash
is recorded.

Required evidence includes parser/header/body round trips; every route/status
combination; selected-policy mismatch before decision; budget reservation and
duplicate rejection; competing exchange; timeout before and after claim; lost
receipt and partial write; late byte zeroing; start/stop/accept races; owner-only
service disposal; cleanup fault truthfulness; absence of production test seams;
Cheese and Smith real frozen service sequences; hostile/tampered histories;
Python pacing/deadline; descriptor/ACL/link/config failures; manager fault
matrix; package mutations; two identical candidate builds; verifier PE
mutations; exact project/source closure; and relevant full repository tests.

## Live readiness and bounded campaigns

Only after implementation, deterministic packaging, aggregate checks and
independent review pass may the coordinator run read-only preflight. A live
campaign uses the exact selected config, fixed overlay and fixed client. The
user prepares the requested fresh untouched screen and does not click the
relevant option or selector:

- Cheese: the supported Room Full of Cheese Gorge option leading to the exact
  two-of-eight add selector;
- Smith: an ordinary rest-site Smith option leading to the exact one-card
  upgrade selector.

Each campaign has at most one client invocation. Any uncertain transport or
action outcome ends that campaign with no retry, replay, adoption, dismissal,
or manual continuation by the tool. The other policy is tested only in a new
fully cleaned campaign. User-assisted launch/quit is allowed within the
authorized campaign; no tool launches the game unless separately directed by
the coordinator's accepted operational procedure.

Retain only the sanitized fixed summary and necessary artifact/state identities.
Do not retain response bodies, decisions, card keys, screenshots as a corpus,
credentials, or profile/save data. Cleanup quits normally through supported UI,
waits for stopped game and closed port, quarantines code first, purges exactly
owned campaign objects, and verifies the clean base. The previously waived
unmodded relaunch check remains waived and must never be reported as passed.

## Acceptance boundary

This document remains a proposal until an independent reviewer accepts its
exact SHA256 and the coordinator records that disposition. Only the status line
and appended evidence ledger may change after semantic freeze. Artifact and
source identities marked pending are later append-only acceptance facts; filling
them does not authorize semantic drift. Implementation, package readiness and
fixture success do not establish live Cheese or Smith success. Each live result
requires its own one-invocation evidence and complete cleanup record.

# Phase 1 live-bridge candidate dossiers

Status: static audit complete at the pinned revisions below. No candidate was
cloned, installed, built, loaded, or executed during that audit. A separately
authorized compile-only probe later built the exact STS2MCP pin in disposable
storage; it was not installed, loaded, or executed. No game profile or save data
was inspected.

The target for this project is the sanitized build identity in
[`sts2-steam-main-build-23811903-macos-universal.json`](../../../../manifests/game-builds/sts2-steam-main-build-23811903-macos-universal.json):
STS2 `v0.107.1`, Steam build `23811903`, release commit `59260271`, macOS
universal. The acceptance rules come from
[`PHASE_1_INTEGRATION_SPIKE.md`](../PHASE_1_INTEGRATION_SPIKE.md): observations
must be passive and public-only; mutations must be expected-state checked,
idempotent, recoverable, and exclusively controlled.

## Evidence key and limits

- **Source fact**: visible in code, manifests, or license text at the exact
  revision. This does not prove that the behavior works in the pinned game.
- **Upstream claim**: stated in a README, changelog, commit message, or upstream
  live-test note. It was not independently reproduced here.
- **Unknown**: static inspection cannot settle it; an exact future test is
  specified.

This audit grants no candidate permission to cross the project's public-state
firewall. In particular, a game is not fully observable merely because a mod can
read its process memory: draw order, RNG/seed state, unrevealed minigame cells,
and future outcomes remain privileged even when reflection makes them available.

## Current post-audit decision

| Rank | Candidate | Static disposition | Hard gate before any policy use |
|---|---|---|---|
| 1 | Project-maintained `live_probe_v0` | **Selected first restricted live path; design only.** Small staged surface owned by the project boundary. | Must finish preflight, compile/package reproducibly, then pass separately approved load, security, passivity, and teardown gates. |
| reference | STS2MCP | **Compile gate passed; compatibility donor/coverage reference, not the runtime foundation.** Closest stated game version and MIT reuse eligibility. | Any reused snippet needs file-level provenance and must sit behind the project public/lifecycle/transaction boundary; the upstream service is not loaded unchanged. |
| 2 | `netcan/slay-the-spire2-agent` | **Protocol-design reference; optional second spike only.** Best expected-state skeleton and safest write default. | No license grant; older Windows-only evidence; possible ordered-draw leak; timeout/retry can duplicate a queued mutation. |
| 3 | `CharTyr/STS2-Agent` | **Comparator/reference, not the default integration base.** Broadest surface and recent upstream maintenance. | Raw seed and unrevealed Crystal Sphere data reach the agent view; no idempotency/lease; AGPL adoption requires an explicit project decision. |
| precedent | STS1 CommunicationMod | **Protocol precedent only.** Useful stable-snapshot/single-child ideas. | STS1-only; raw seed and ordered draw pile; no transactional recovery. |

No third-party candidate is safe to expose unchanged to training, evaluation,
or autonomous play. The selected project bridge is not yet an executable
candidate and has passed no live gate.

## 1. STS2MCP

**Identity and game-build assumption**

- Exact revision:
  [`55e064850a68f3b4cde7e5fd525bf9b2dec4e885`](https://github.com/Gennadiyev/STS2MCP/commit/55e064850a68f3b4cde7e5fd525bf9b2dec4e885)
  ([tree](https://github.com/Gennadiyev/STS2MCP/tree/55e064850a68f3b4cde7e5fd525bf9b2dec4e885)).
- **Upstream claim:** the pinned commit is titled “Fix game API compatibility
  with STS2 v0.107” and says combat, combat-state, and merchant integration were
  updated for `v0.107.1`. The pinned
  [README](https://github.com/Gennadiyev/STS2MCP/blob/55e064850a68f3b4cde7e5fd525bf9b2dec4e885/README.md)
  still says it was tested against `v0.103.2`; the documentation and commit are
  therefore internally stale, not independent corroboration.
- **Unknown:** runtime loading on Steam build `23811903`, release commit
  `59260271`, macOS universal, and every action path on that exact build remain
  unverified.
- **Direct compile evidence (2026-08-29):** the exact upstream tree passed two
  unchanged-source compiles against the pinned arm64 assemblies, including .NET
  SDK/runtime `9.0.303/9.0.7` parity, with zero MSBuild/compiler warnings or
  errors. See the
  [`compile-only probe`](PHASE_1_STS2MCP_COMPILE_PROBE.md). This establishes
  type/member signature compatibility, not loading or behavior.

**Actual protocol and coverage**

- **Source fact:** the in-game C# mod exposes JSON over unauthenticated HTTP.
  Routes in
  [`McpMod.cs`](https://github.com/Gennadiyev/STS2MCP/blob/55e064850a68f3b4cde7e5fd525bf9b2dec4e885/McpMod.cs)
  are `GET|POST /api/v1/singleplayer`, `GET|POST /api/v1/multiplayer`,
  `GET /api/v1/profile`, `GET /api/v1/compendium`, `GET /api/v1/wiki`, and
  `GET|POST /api/v1/profiles`. The optional Python/FastMCP layer is a facade over
  this REST service, not a separate authoritative state source.
- **Source fact:** the action dispatcher and state builder cover main/profile and
  character selection, tutorials/popups, Timeline/unlock interactions, combat
  card play/end turn/potions, map, events, rest, merchant purchase/removal,
  rewards/card rewards, deck selection with confirm/cancel, bundles, relic
  selection, treasure, Crystal Sphere, game-over dismissal, and single-/multi-
  player flows. See
  [`McpMod.Actions.cs`](https://github.com/Gennadiyev/STS2MCP/blob/55e064850a68f3b4cde7e5fd525bf9b2dec4e885/McpMod.Actions.cs),
  [`McpMod.StateBuilder.cs`](https://github.com/Gennadiyev/STS2MCP/blob/55e064850a68f3b4cde7e5fd525bf9b2dec4e885/McpMod.StateBuilder.cs),
  and the pinned
  [raw API reference](https://github.com/Gennadiyev/STS2MCP/blob/55e064850a68f3b4cde7e5fd525bf9b2dec4e885/docs/raw-full.md).
- **Upstream limitation:** the generic unknown-overlay state may require manual
  intervention, and the normal single-player endpoint does not provide a clean
  seeded-embark action. Coverage breadth is not proof of exhaustive legality or
  correct state transitions.

**Public versus privileged information**

- **Source fact:** combat state is read through internal `DebugOnlyGetState`, but
  the exported draw-pile contents are deliberately sorted rather than exposing
  internal order, and Crystal Sphere item details are gated on revealed cells.
  Those are useful public-projection precedents.
- **Source fact / blocker:** the same raw API also exposes profile switching and
  deletion, current-run/history reads, local history paths, raw seed values, and
  multiplayer platform identity. There is no separate public actor endpoint.
  These operational/profile fields must never enter a policy observation or
  certification trace. Synthetic entity IDs and internal combat IDs also need a
  field-by-field UI/public-basis audit.
- **Source fact / passivity blocker:** some nominal reads open UI state—for
  example, querying merchant state can open its inventory and querying treasure
  can open the chest. An observation call is therefore not reliably read-only.

**Transaction, idempotency, and recovery**

- **Source fact / blocker:** actions use mutable list indices and synthetic IDs,
  and return success after enqueue/click dispatch. Requests contain no
  `decision_id`, expected state hash/version, idempotency key, mutation sequence,
  controller lease, or result cache. A lost response followed by retry can apply
  twice; shifted indices can select a different object.
- **Source fact:** main-thread queuing avoids some direct thread-affinity errors,
  but it is not a transaction boundary. Concurrent HTTP clients are not given a
  single-writer lease, and no restart journal or ambiguous-commit reconciliation
  exists.
- **Unknown:** whether every handler's “success” implies only input dispatch,
  queue admission, or an observed durable state change varies by path and needs
  live fault injection.

**Security defaults and exposure**

- **Source fact / blocker:** `HttpListener` binds `localhost:15526` and
  `127.0.0.1:15526`, permits mutation without authentication or an arming token,
  and responds with `Access-Control-Allow-Origin: *`. Profile switch/delete uses
  the same trust boundary. Error responses may disclose exception types and
  stack traces.
- **Source fact / lifecycle blocker:** initialization writes `STS2_MCP.conf` in
  the mod directory when it is absent and applies Harmony settings-UI patches.
  No explicit listener stop/dispose, Harmony unpatch, or mod-unload hook was
  found in the pinned
  [`McpMod.cs`](https://github.com/Gennadiyev/STS2MCP/blob/55e064850a68f3b4cde7e5fd525bf9b2dec4e885/McpMod.cs#L33-L114).
  A read-only probe must precreate/hash configuration, remove or declare the
  load-time patch, and prove teardown or clean process-exit isolation.
- Loopback reduces remote reachability but does not protect against other local
  processes or a browser-origin attack. The profile endpoints also create a
  much larger damage/privacy surface than an agent bridge requires.

**Dependencies, license, and reuse**

- **Source fact:** C#/.NET 9 with local `sts2.dll`, `GodotSharp`, and Harmony
  references; optional MCP service requires Python 3.11+, `uv`, FastMCP, and
  `httpx`. The
  [project file](https://github.com/Gennadiyev/STS2MCP/blob/55e064850a68f3b4cde7e5fd525bf9b2dec4e885/STS2_MCP.csproj)
  contains Windows, macOS, and Linux paths, but this is not runtime validation.
- Exact project license: [MIT](https://github.com/Gennadiyev/STS2MCP/blob/55e064850a68f3b4cde7e5fd525bf9b2dec4e885/LICENSE),
  SPDX `MIT`. **Reuse category:** compatible for project-authored code with the
  notice preserved, subject to dependency/game-file review. No license blocker.

**Compatibility gap and knockout risks**

- Smallest stated version gap: the pinned commit explicitly targets `v0.107.1`
  and exact-build arm64 signature compilation now passes, but loading and macOS
  behavior remain unknown.
- Knock out unchanged adoption if any of these hold: load failure on the pinned
  build; GET changes game/UI state; raw seed/history/platform data reaches the
  actor; duplicate or concurrent request can double-mutate; profile mutation is
  reachable from the controller boundary; an unsupported screen remains
  ambiguous rather than failing closed.

**Required future tests**

1. `MCP-BOOT-1071-MAC`: on a disposable profile, verify the clean base-build
   projection plus separately hashed bridge/config overlay, load/unload,
   loopback bind, unchanged precreated config, declared load-time patch set,
   listener/port release, and clean base-control restart on build `23811903`.
2. `MCP-PHASE-MATRIX`: capture before/actions/after for every listed phase and
   nested selector; require unsupported states to emit zero mutations and a
   typed reason.
3. `MCP-PUBLIC-DIFF`: compare runs with identical visible UI/history but different
   seed, draw order, and unrevealed Sphere layout; actor JSON must be identical.
4. `MCP-PASSIVE-GET`: repeat every GET in shop, treasure, rewards, and transitions;
   game-state/UI hashes and screenshots must not change.
5. `MCP-EXACTLY-ONCE`: drop the response after dispatch, resend one idempotency
   key, race two clients, and restart the bridge; observe exactly one mutation
   and a replayable terminal result.
6. `MCP-SECURITY`: require loopback-only binding, deny wildcard origins, require
   auth + explicit write arming, and prove profile/history/delete routes are not
   present on the agent-facing server.

## 2. CharTyr/STS2-Agent

**Identity and game-build assumption**

- Exact revision:
  [`9f99876d8dd11416aec13273956902d58a231ccb`](https://github.com/CharTyr/STS2-Agent/commit/9f99876d8dd11416aec13273956902d58a231ccb)
  ([tree](https://github.com/CharTyr/STS2-Agent/tree/9f99876d8dd11416aec13273956902d58a231ccb)),
  release `v0.9.1`.
- **Upstream claim:** the pinned
  [changelog](https://github.com/CharTyr/STS2-Agent/blob/9f99876d8dd11416aec13273956902d58a231ccb/CHANGELOG.md)
  says `v0.9.1` was verified against STS2 `v0.111.0`; the earlier `v0.8.0`
  entry says it was verified against `v0.107.1` and `v0.108.0`.
- **Unknown:** backwards behavior of the pinned `v0.9.1` code on exact build
  `23811903`, macOS universal loading, and whether later reflection changes are
  compatible with `v0.107.1`.

**Actual protocol and coverage**

- **Source fact:** the mod's HTTP surface is `GET /health`, `GET /state`,
  `GET /actions/available`, `GET /data/<collection>`, `GET /events/stream`
  (server-sent events), and `POST /action`; see
  [`HttpServer.cs`](https://github.com/CharTyr/STS2-Agent/blob/9f99876d8dd11416aec13273956902d58a231ccb/STS2AIAgent/Server/HttpServer.cs)
  and
  [`Router.cs`](https://github.com/CharTyr/STS2-Agent/blob/9f99876d8dd11416aec13273956902d58a231ccb/STS2AIAgent/Server/Router.cs).
  A Python FastMCP facade and an in-game LLM/vision overlay are additional
  surfaces, not needed for our minimal bridge.
- **Source fact:** the dispatcher includes menu/character/embark/ascension and
  multiplayer lobby operations; combat play/end turn/potions and combat
  selectors; rewards; map; events; rest; shops/removal; chest/relic, bundles,
  capstone, Crystal Sphere, unlock/Timeline, modals, and game-over flows. Debug
  console execution is separately environment-gated. See
  [`GameActionService.cs`](https://github.com/CharTyr/STS2-Agent/blob/9f99876d8dd11416aec13273956902d58a231ccb/STS2AIAgent/Game/GameActionService.cs).
- **Upstream claim:** the README advertises broad full-run driving. The pinned
  [mechanic matrix](https://github.com/CharTyr/STS2-Agent/blob/9f99876d8dd11416aec13273956902d58a231ccb/docs/mechanic-coverage-matrix.md)
  is older than the pin and explicitly rates character/rare-hook completeness
  below full coverage; it must not be treated as proof of current completeness.

**Public versus privileged information**

- **Source fact / hard blocker:**
  [`GameStateService.cs`](https://github.com/CharTyr/STS2-Agent/blob/9f99876d8dd11416aec13273956902d58a231ccb/STS2AIAgent/Game/GameStateService.cs)
  derives `run_id` from `Rng.StringSeed` and passes the raw seed into the agent
  view. It also exports every Crystal Sphere item, `is_good`, geometry, and cell
  set including unrevealed cells. Both directly violate the public-only actor
  contract.
- **Source fact:** there is no distinct public and privileged observation
  endpoint. Internal/network IDs and underlying enemy move identity also need an
  explicit visible-UI basis before use.

**Transaction, idempotency, and recovery**

- **Source fact:** an action response can be `completed` or `pending` and can
  include post-state; SSE supplies event IDs. That is better acknowledgement
  detail than fire-and-forget only.
- **Source fact / blocker:** the request has action/index parameters and optional
  client context, but no expected decision/hash/version, idempotency key/result
  cache, controller lease, or deduplication. HTTP request IDs and SSE event IDs
  do not identify an exactly-once commit. A `pending` result is ambiguous after
  disconnect, and process restart provides no reconciliation journal.
- **Unknown:** whether concurrent `/action` requests serialize every handler and
  whether all “completed” paths wait for observable post-state.

**Security defaults and exposure**

- **Source fact:** the mod HTTP service defaults to `127.0.0.1:8080`, moves to
  another port if occupied, has no authentication, and exposes normal writes.
  Debug-console execution requires `STS2_ENABLE_DEBUG_ACTIONS=1`. No CORS grant
  was found in the reviewed server source.
- **Source fact:** the optional MCP network service defaults to loopback port
  `8765`; bearer authentication is optional and can be absent. Any non-loopback
  binding must be rejected unless strong auth is mandatory. Broad LLM, vision,
  profile/data, multiplayer, and debug functionality increases the trusted code
  and data surface.

**Dependencies, license, and reuse**

- **Source fact:** C#/.NET 9 with local `sts2.dll`, `GodotSharp`, and Harmony;
  Python 3.11+, `uv`, FastMCP `>=3.1,<4`, plus optional model/vision integration.
  The pinned [README](https://github.com/CharTyr/STS2-Agent/blob/9f99876d8dd11416aec13273956902d58a231ccb/README.md)
  describes cross-platform build commands, not exact-build runtime proof.
- Exact project license:
  [GNU Affero General Public License v3.0 only](https://github.com/CharTyr/STS2-Agent/blob/9f99876d8dd11416aec13273956902d58a231ccb/LICENSE),
  SPDX `AGPL-3.0-only`. **Reuse category:** reference or separately isolated
  dependency until the project consciously accepts and satisfies AGPL terms.
  Do not copy or fork its code into this repository by accident. This is a hard
  license decision gate, not a claim that evaluation of the unmodified program
  is forbidden.

**Compatibility gap and knockout risks**

- There is relevant upstream `v0.107.1` history, but the pinned code targets a
  later `v0.111.0`; exact backwards and macOS compatibility is unknown.
- Knock out unchanged adoption due to the proven seed and Sphere leaks. Also
  knock it out if action retries duplicate, auth-free mutation cannot be removed,
  or AGPL obligations are not deliberately accepted.

**Required future tests**

1. `CTA-BOOT-1071-MAC`: exact-build load/route/action smoke on a disposable
   profile, recording the selected dynamic HTTP port.
2. `CTA-PUBLIC-GOLDEN`: assert the actor schema contains no seed-derived value,
   unrevealed Sphere cell/item, hidden draw order, history path, or platform ID.
3. `CTA-SPHERE-DIFF`: hold revealed cells constant while varying hidden layout;
   actor observations and legal actions must be byte-identical.
4. `CTA-TXN-FAULTS`: disconnect before/after `pending`, duplicate the request,
   race controllers, and restart; require one commit and queryable reconciliation.
5. `CTA-COVERAGE`: run the full phase/nested-selector matrix with debug action,
   MCP, vision, and multiplayer disabled; unsupported states must fail closed.
6. `CTA-SECURITY-LICENSE`: verify fixed loopback bind, mandatory write arming and
   auth, then record the explicit AGPL go/no-go before any source reuse.

## 3. netcan/slay-the-spire2-agent

**Identity and game-build assumption**

- Exact revision:
  [`3ac97a1d7a1eaa73bcacc8b04daaf1181e142b60`](https://github.com/netcan/slay-the-spire2-agent/commit/3ac97a1d7a1eaa73bcacc8b04daaf1181e142b60)
  ([tree](https://github.com/netcan/slay-the-spire2-agent/tree/3ac97a1d7a1eaa73bcacc8b04daaf1181e142b60));
  commit message “fix: enqueue potion game action through run manager.”
- **Upstream claim:**
  [`sts2-mod-upgrade-notes.md`](https://github.com/netcan/slay-the-spire2-agent/blob/3ac97a1d7a1eaa73bcacc8b04daaf1181e142b60/docs/sts2-mod-upgrade-notes.md)
  says the current verified game was Windows `v0.99.1 (7ac1f450)`; the pinned
  [prototype validation log](https://github.com/netcan/slay-the-spire2-agent/blob/3ac97a1d7a1eaa73bcacc8b04daaf1181e142b60/docs/prototype-validation.md)
  records earlier live combat/reward tests on `v0.98.3 (cb602cef)`.
- **Source fact:** the pinned
  [README](https://github.com/netcan/slay-the-spire2-agent/blob/3ac97a1d7a1eaa73bcacc8b04daaf1181e142b60/README.md)
  requires a Windows STS2 install. **Unknown:** `v0.107.1`, build `23811903`, and
  macOS universal compatibility.

**Actual protocol and coverage**

- **Source fact:** JSON/HTTP endpoints are `GET /health`, `GET /snapshot`,
  `GET /actions`, `POST /apply`, and `GET|POST|DELETE /agent-status`; see
  [`LocalBridgeServer.cs`](https://github.com/netcan/slay-the-spire2-agent/blob/3ac97a1d7a1eaa73bcacc8b04daaf1181e142b60/mod/Sts2Mod.StateBridge/Server/LocalBridgeServer.cs).
- **Source fact:** exported phases are only `menu`, `combat`, `reward`, `map`,
  `event`, `shop`, and `terminal`. The pinned dispatcher handles continue/start,
  character select/start confirm; card play, potion use, end turn and combat card
  selection/cancel; reward choose/skip/advance; map node; event option/continue;
  shop card/relic/potion purchase, opening purge, and leaving. See
  [`Models.cs`](https://github.com/netcan/slay-the-spire2-agent/blob/3ac97a1d7a1eaa73bcacc8b04daaf1181e142b60/mod/Sts2Mod.StateBridge/Contracts/Models.cs)
  and
  [`Sts2RuntimeReflectionReader.cs`](https://github.com/netcan/slay-the-spire2-agent/blob/3ac97a1d7a1eaa73bcacc8b04daaf1181e142b60/mod/Sts2Mod.StateBridge/Providers/Sts2RuntimeReflectionReader.cs).
- **Source fact / coverage gap:** rest/campfire, treasure/chest, Timeline/unlocks,
  bundles/capstone/Crystal Sphere, potion discard, game-over actions, and explicit
  post-purge card selection are absent. Unrecognized active-run windows fall back
  to combat classification. The compatibility doc's shorter “not covered” list
  is stale relative to the pinned source, so source wins over prose.

**Public versus privileged information**

- **Source fact:** no raw run-seed field was found in the reviewed contracts or
  runtime exporter. The API nevertheless has no public/privileged projection.
- **Source fact / likely blocker:** the player schema exports full
  `draw_pile_cards`, and the reader preserves the reflected `DrawPile.Cards`
  enumeration order rather than sorting it; see
  [`WindowExtractors.cs`](https://github.com/netcan/slay-the-spire2-agent/blob/3ac97a1d7a1eaa73bcacc8b04daaf1181e142b60/mod/Sts2Mod.StateBridge/Extraction/WindowExtractors.cs).
  Whether that runtime collection order equals future draw order is **unknown**,
  but the actor projection must canonicalize it before any use. Enemy move names,
  internal type diagnostics, instance/network identifiers, and response metadata
  also require a visible-UI basis audit.
- **Unknown:** observational passivity. Capture is reflection-heavy and invokes
  some runtime validation/text methods; static inspection cannot prove that every
  getter/probe is side-effect free.

**Transaction, idempotency, and recovery**

- **Source fact / positive:** snapshots carry random `session_id`, monotonic
  `state_version`, fingerprint-derived `decision_id`, and legal `action_id`.
  `/apply` rejects a stale decision and re-resolves the action against the current
  legal set. Writes are queued onto the game thread and responses distinguish
  `accepted`, `rejected`, and `failed`; see
  [`BridgeSessionState.cs`](https://github.com/netcan/slay-the-spire2-agent/blob/3ac97a1d7a1eaa73bcacc8b04daaf1181e142b60/mod/Sts2Mod.StateBridge/Core/BridgeSessionState.cs)
  and
  [`InGameRuntimeCoordinator.cs`](https://github.com/netcan/slay-the-spire2-agent/blob/3ac97a1d7a1eaa73bcacc8b04daaf1181e142b60/mod/Sts2Mod.StateBridge/Providers/InGameRuntimeCoordinator.cs).
- **Source fact / blocker:** `request_id` is generated/carried but never used as
  an idempotency key or result-cache lookup. If the 3-second wait times out, the
  pending action remains in the queue. Retrying can enqueue a second copy; the
  original may still execute. `accepted` can mean a reflected game action was
  enqueued, not that a new post-state was observed.
- **Source fact:** the in-process queue serializes handlers, but there is no
  controller lease, mutation ownership, durable journal, cancellation-on-timeout,
  or restart reconciliation. Restart creates a new session and loses outcomes.

**Security defaults and exposure**

- **Source fact / positive:** in-game defaults are loopback `127.0.0.1:17654`
  and read-only. Gameplay writes require `STS2_BRIDGE_ENABLE_WRITES=true`, and
  in-game debug phase override is disabled; see
  [`Sts2InGameModEntryPoint.cs`](https://github.com/netcan/slay-the-spire2-agent/blob/3ac97a1d7a1eaa73bcacc8b04daaf1181e142b60/mod/Sts2Mod.StateBridge/InGame/Sts2InGameModEntryPoint.cs).
- **Source fact / blocker:** host is environment-configurable and the server has
  no authentication, authorization, Origin check, or controller lease. A
  non-loopback override would expose reads and armed mutations. No CORS grant was
  found, but absence of CORS is not authentication.

**Dependencies, license, and reuse**

- **Source fact:** .NET SDK `9.0.300`/`net9.0`, local `sts2.dll`, `GodotSharp`,
  Harmony, Python 3.11+, and Godot 4.5.1/PCK packaging. See
  [`Sts2Mod.StateBridge.csproj`](https://github.com/netcan/slay-the-spire2-agent/blob/3ac97a1d7a1eaa73bcacc8b04daaf1181e142b60/mod/Sts2Mod.StateBridge/Sts2Mod.StateBridge.csproj),
  [`global.json`](https://github.com/netcan/slay-the-spire2-agent/blob/3ac97a1d7a1eaa73bcacc8b04daaf1181e142b60/global.json),
  and
  [`pyproject.toml`](https://github.com/netcan/slay-the-spire2-agent/blob/3ac97a1d7a1eaa73bcacc8b04daaf1181e142b60/pyproject.toml).
- **Source fact / hard license blocker:** the exact tree has no `LICENSE`,
  `COPYING`, or package license declaration. Exact upstream SPDX: none declared
  (`NOASSERTION` for this audit). **Reuse category:** reference-only; do not copy,
  modify, vendor, or redistribute source without a license grant/clarification.

**Compatibility gap and knockout risks**

- Largest explicit gap: upstream evidence stops at Windows `v0.99.1`, while the
  target is macOS `v0.107.1`. The bridge depends on thousands of reflective type,
  member, and UI-name assumptions, so this is a high-risk port rather than a
  presumed-compatible candidate.
- Knock out source adoption while the license is absent. Knock out policy use if
  draw order leaks, timeout retry duplicates, an unknown window is mislabeled as
  combat, or exact-build/macOS loading fails.

**Required future tests**

1. `NET-PORT-1071-MAC`: compile/load only after the license/use decision; record
   every missing/renamed reflection member on exact build `23811903`.
2. `NET-PUBLIC-PILE`: construct equal public draw-pile multisets with different
   internal orders; actor JSON must be canonical and byte-identical.
3. `NET-TIMEOUT-DUP`: stall game-thread consumption beyond three seconds, resend
   the same request ID, then resume; exactly one action may execute and both
   callers must receive the same terminal result.
4. `NET-LEASE-RACE`: two clients and manual input race one decision; only the
   lease owner may mutate, one mutation may be in flight, and stale clients must
   fail before dispatch.
5. `NET-PHASE-FAIL-CLOSED`: visit every missing/nested phase, especially rest,
   chest, purge selection, game over, and transitions; none may fall back to a
   combat action set.
6. `NET-PASSIVE-REFLECTION`: repeatedly capture each screen while hashing public
   game state and visual state; no probe/getter may trigger UI or RNG changes.

## 4. STS1 CommunicationMod precedent

**Identity and assumption**

- Exact revision:
  [`5e417eb189530986b9047a3c9426889fb261d146`](https://github.com/ForgottenArbiter/CommunicationMod/commit/5e417eb189530986b9047a3c9426889fb261d146)
  ([tree](https://github.com/ForgottenArbiter/CommunicationMod/tree/5e417eb189530986b9047a3c9426889fb261d146)).
- **Source fact:** Java/Maven STS1 mod; its
  [manifest](https://github.com/ForgottenArbiter/CommunicationMod/blob/5e417eb189530986b9047a3c9426889fb261d146/src/main/resources/ModTheSpire.json)
  targets STS1 `11-30-2020`, ModTheSpire `3.18.1`, and BaseMod `5.27.0`.
  **Upstream claim:** its changelog carries fixes through STS1 `v2.2`.
  It provides no STS2 compatibility evidence.

**Protocol, coverage, and information boundary**

- **Source fact:** no listening socket. The mod starts one configured child
  process and exchanges newline-delimited messages over redirected stdio. The
  [README](https://github.com/ForgottenArbiter/CommunicationMod/blob/5e417eb189530986b9047a3c9426889fb261d146/README.md)
  says the child sends `ready`; the implementation accepts any nonempty line
  within ten seconds. Stable snapshots advertise legal commands and
  `ready_for_command`; after mutation a handwritten stability detector emits a
  new state. See
  [`CommunicationMod.java`](https://github.com/ForgottenArbiter/CommunicationMod/blob/5e417eb189530986b9047a3c9426889fb261d146/src/main/java/communicationmod/CommunicationMod.java)
  and
  [`GameStateListener.java`](https://github.com/ForgottenArbiter/CommunicationMod/blob/5e417eb189530986b9047a3c9426889fb261d146/src/main/java/communicationmod/GameStateListener.java).
- **Source fact:** semantic commands cover start/class/ascension/seed; card/end
  turn/potions; choices across event/chest/shop/rest/rewards/map/boss/grid/hand;
  proceed/confirm/skip/cancel/leave; plus generic in-run key/click/wait and forced
  `STATE`. No semantic save/quit/resume/abandon command exists. See
  [`CommandExecutor.java`](https://github.com/ForgottenArbiter/CommunicationMod/blob/5e417eb189530986b9047a3c9426889fb261d146/src/main/java/communicationmod/CommandExecutor.java).
- **Source fact / hard public-info failure:** there is no public/privileged split;
  every run snapshot emits raw `Settings.seed`, and combat emits
  `drawPile.group` in internal order. It also exposes card UUIDs, event IDs, and
  monster move IDs/history; forced `STATE` can expose transitions. Runic Dome
  intent redaction shows selective filtering is possible, but the seed and draw
  order alone disqualify the raw serializer. See
  [`GameStateConverter.java`](https://github.com/ForgottenArbiter/CommunicationMod/blob/5e417eb189530986b9047a3c9426889fb261d146/src/main/java/communicationmod/GameStateConverter.java).

**Transactions, recovery, security, and license**

- **Source fact / useful precedent:** one child channel gives practical transport
  ownership; legal-command advertisement and stable post-action snapshots are
  worth preserving.
- **Source fact / blocker:** no session/decision/request ID, expected-state
  precondition, idempotency cache, mutation sequence, commit status, journal, or
  restart reconciliation. The dispatcher does not enforce `ready_for_command`;
  multiple input lines, manual UI changes, shifted indices, or loss after commit
  remain ambiguous. Generic key/click bypasses semantic legality.
- **Source fact:** no remote auth/CORS surface, but the configured child command
  is arbitrary trusted local code running with the game user's privileges. There
  is no explicit observation/write arming or protection from human input.
- **Source fact:** Java 8/Maven, artifact `1.2.1`, Gson `2.8.9` shaded; see
  [`pom.xml`](https://github.com/ForgottenArbiter/CommunicationMod/blob/5e417eb189530986b9047a3c9426889fb261d146/pom.xml).
  Exact license: [MIT](https://github.com/ForgottenArbiter/CommunicationMod/blob/5e417eb189530986b9047a3c9426889fb261d146/LICENSE),
  SPDX `MIT`. **Reuse category:** concepts and project-authored code may be reused
  with notice, but STS1 APIs/code are not an STS2 bridge base.

**Known limitations and precise precedent tests**

- **Upstream claim:** Match and Keep is incomplete; full potion belts can fail
  without feedback; hand selections cannot always be unselected; some manual
  state changes are missed; only fast mode was tested. Static inspection does not
  prove exhaustive card/relic/event correctness or cross-platform behavior.
- `PRECEDENT-HANDSHAKE`: reject anything except a versioned literal handshake.
- `PRECEDENT-STABILITY`: compare emitted decision-ready state to visual stability
  across animation, reward, and nested-selector transitions.
- `PRECEDENT-LOSS`: kill the child after mutation but before the next snapshot;
  the STS2 design must recover the committed result without replay.
- `PRECEDENT-EXCLUSIVITY`: flood commands and inject manual input; the STS2 design
  must enforce one lease owner, one mutation in flight, and semantic-only actions
  on certification paths.

## Recommendation after the bridge-boundary decision

The disposable STS2MCP compile probe has passed. Use its exact pin only as
target-build compatibility/coverage evidence and as a possible source of
individually audited MIT snippets; do not load its unchanged service or inherit
its API. The first runtime path is the staged project-maintained bridge in
[`PHASE_1_RESTRICTED_BRIDGE_DESIGN.md`](../PHASE_1_RESTRICTED_BRIDGE_DESIGN.md).
Treat netcan's
decision/state/action identifiers and read-only default as design input, not
reusable code while unlicensed. Treat CharTyr's broad phase coverage as a
coverage checklist, not an actor-state contract. Carry forward
CommunicationMod's stable legal-action snapshot and single-controller channel
ideas, but not its serializer or retry semantics.

Before the first model is connected, the bridge-facing adapter must make the
following independently testable and swappable: raw capture, public projection,
legal-action enumeration, at-most-once dispatch with fail-closed
reconciliation, controller lease, and recovery journal. This preserves the
ability to compare candidates—or run with search versus without search—without
changing the policy-facing contract.

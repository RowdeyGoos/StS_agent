# Phase 1 — 2026-09-04 integration and bounded live acceptance

## Scope and starting state

Development resumed under the user's coordinator authorization, including
ordinary bounded live bridge verification on dedicated Profile 3. No remote
writes, direct profile/save access, Steam Cloud changes, or retained live
payload corpus were authorized or performed. The separately scoped retained
input for `H4-LIVE-DIFF-02` remains unapproved.

The clean local starting point was `1424ecd7b590f063156f6fed607e157c37f2c4a7`
on `codex/phase1-parallel-integration`, containing planning baseline `d93395c`.
The existing user checkout and worktrees were preserved. Implementation used
five persistent project worktree tasks; independent read-only reviewers
checked the high-risk joins. No implementation worker operated the game.

## Packet ledger

Earlier accepted packets remain in the verified starting baseline. This table
lists their initial integrated commit and significant final hardening anchor;
intermediate corrective commits remain in local history. It does not upgrade
their evidence labels.

| Packet | Integrated anchors | Disposition |
| --- | --- | --- |
| `R0I-DIAG-01` | `1cf8aa4` | Fixture-tested failure classification |
| `R0I-MAP-02` | `7589c3b`, `813bd4a` | Fixture-tested map transport and bounded retry |
| `R0I-RUN-03` | `b0824f9`, `cb14cf5` | Fixture-tested one-room handoff; live completion remains open |
| `R0I-RUN-04` | `a607677` | Fixture-tested post-room ordinary-combat continuation |
| `R0I-ROUTE-05` | `71807a6` | Deterministic supported-room coverage ranking |
| `R0I-VECTORS-06` | `73283b1` | Canonical synthetic wire vectors |
| `H0-CONTRACT-01` | `33bfcba` through `de402a3` | Accepted canonical `headless_v0` |
| `H0-RNG-02` | `4febddb` | Synthetic named RNG and snapshot service |
| `H0-SCENARIOS-03` | `1763d3c`, `fec8bae` | Serializable `combat_v0` scenario definitions |
| `H0-CHARACTERIZE-04` | `c79c51c` | Legacy combat characterization |
| `H0-BOUNDARY-REVIEW-05` | no write commit | Read-only boundary review; current conformance is the executable gate |
| `H1-STATE-01` | `dcbaaf2` through `d9d96a5`, `c41654b` | Synthetic private state/snapshots |
| `H1-PROJECTION-02` | `6a98718` | Public combat projection |
| `H1-CANDIDATES-03` | `22f314f` | Advertised combat candidate mapping |
| `H1-FIXTURE-04` | `facaa63` through `2789325` | Frozen fixture playback, not a rules simulator |
| `H1-RUNNER-05` | `c0e9de0` | Bounded backend-neutral episode loop |
| `H1-TRACE-06` | `aabc32c` through `2702987` | Bound, separate replay/target/audit streams |
| `H1-CONTENT-07` | `a3cf8ec` | Reduced structural content |
| `H2-COMBAT-BACKEND-01` | `95b6144`, `fde922e` | Accepted legacy combat adapter, `combat_v0` evidence |
| `H2-REWARD-02` | `b8c766a` through `027b588` | Synthetic transactional reward progression |
| `H2-MAP-03` | `11e72bf` through `c2d2a38` | Synthetic deterministic map progression |
| `H2-ROOM-04` | `c3125cc` through `c19fc1e` | Synthetic room effects/progression |
| `H3-REDUCED-BACKEND-01` | `1a0ea8f` through `e853d98` | Composed reduced run with restore-time history validation |
| `H3-CONFORMANCE-04` | `16575c4`, `3a12af7` | Independent 66-test conformance gate |
| `H4-LIVE-WIRE-01` | `324bd76`, `b08205d` | Strict separate live-wire parser; not a `GameBackend` |

### Work in this resumed session

| Packet | Worker commits → integrated commits | Review and evidence |
| --- | --- | --- |
| `H3-BASELINE-02` | `8754d12`, `3b613c5` → `2ff9340`, `04c045c` | Accepted public-only first-legal, explicitly seeded random, structural heuristic; 162 focused/shared tests passed |
| `R0I-RUN-04` readiness repair | `8a6e5c0`, `f7d5b21` → `2b2fd07`, `f74cf26` | Accepted bounded polling of validated inactive completion; only expected-kind ready succeeds; 14 run and 16 room fixtures passed |
| `H4-LIVE-DIFF-02`, offline portion | `06466e4`, `621c5c3` → `6fbc0ca`, `8fda7da` | Accepted synthetic common-subset comparator and build-safe identity inventory; live portion blocked |
| `H3-ROLLOUT-03` | `f43cb58`, `b9f3393`, `2040322`, `8bf7ccb` → `d85448b`, `f2b7f7c`, `fdc2c33`, `feda7d6` | Accepted after real-spawn cancellation review and escalation; 280 focused/shared tests and 829 full repository tests passed |
| `R0I-ROOM-LIFECYCLE-07` | `1a3aebf`, `be6c7a1` → `966b8ba`, `b86d1b4` | Reviewed foreground eligibility and rest-only completion; first candidate rejected for replay regression, correction independently accepted; live acceptance pending |

The readiness repair explicitly owns the two run-client files plus the two
room-client files for this correction; only three of those files changed.
No production C#, wire schema, accepted contract fingerprint, or bridge
artifact changed before the first campaign. The subsequently approved C#
lifecycle packet was reviewed separately as recorded below.

## Accepted headless rollout consumer

The accepted collector invokes the generic episode runner, not an independent
rules loop. Its serializable reduced-backend descriptor and chooser registry
work in spawned processes. Game seeds, chooser seeds, and collector scheduling
seeds remain separate. Results preserve component evidence and independent
replay, hindsight-target, and audit streams. Explicit reasons include defeat,
route completion, unsupported state, budget exhaustion, interruption, and
failure; route completion is not a target-game win.

The first implementation lost completed batches on parent interruption and did
not close its backend. The first correction fixed iteration cancellation but
still lost received results on SIGINT during join; benchmarks also continued
repetitions after cancellation. Independent real spawned-process reproductions
justified escalation to Sol/high. The accepted correction covers collection,
close, join, and repeated SIGINT during cleanup, restores the caller's signal
handler, stops benchmark repetitions, and leaves zero workers alive. Received
results survive; unreceived results are named as pending, never fabricated.
Forced cancellation cannot recover unpublished state inside a worker.

All 280 focused/shared tests passed in 32.32 seconds; the integrated whole
repository passed **829 tests in 36.45 seconds**. A nonthrowing sealed backend
is the supported factory; richer reporting of hypothetical cleanup failures
remains nonblocking hardening, not an additional backend capability.

Coordinator benchmark at `feda7d6`, Python 3.11.15, Darwin arm64:
`simple__starter`, structural heuristic, game seed panel `[7, 8]`, policy seed
11, collector seed 17, transition budget 300 per episode, one repetition.
Both modes returned two `route_complete` episodes and 57 transitions without
interruption, retaining `combat_v0`/`structural_fixture` evidence.

| Mode | Seconds | Episodes/s | Transitions/s |
| --- | ---: | ---: | ---: |
| Sequential | 0.447908 | 4.465 | 127.258 |
| Spawned, 2 workers | 0.977980 | 2.045 | 58.283 |

These are single bounded local samples including recording, snapshots, and
process startup, not pure stepping rates, scaling claims, or performance
promises. No learned training or large compute campaign was run.

## Offline differential interpretation

The 19 project-authored cases yield **3 passed, 14 divergent, 2 unobserved**.
All remain `structural_fixture` comparisons with `live_capture=unobserved`.
The passes establish only selected common vitals/category matches; room/map
passes do not establish healing effects, entity identity, or destination
identity. Missing fields and post-states remain unobserved. Queued receipts
never prove a post-state. Diagnostics retain field paths/reasons, not values.

Identity checks bind declared game/wire/headless inputs, an explicit bridge
source inventory, synthetic bodies, and selected source files. The initial
whole-repository run exposed generated `obj` C# files contaminating that
inventory: **751 passed, 56 identity-gate errors**. Independent review proved
all other identities unchanged. The corrective commit excludes exact `bin` and
`obj` directory components before content reads, preserves the reviewed
**48-file** digest, and adds seven disposable ignore/drift tests. It does not
repin generated output as authored source. The rebuilt root then passed
**814 repository tests** in **87.90 seconds**.

The corrected offline manifest SHA-256 is
`ffdec1b4fe2454176dc6e0bc9179f2f197573dd07ecf3afdfc6aaa09c04694e7`.
The bridge-source inventory SHA-256 remains
`feed6d91adbc5568a48c2ebdd0a1d6f2a904c8c1c35ac1750a6aa4f4e53c4876`.

## Exact bridge artifact and preflight

Campaign source checkout: `6fbc0ca249b700bda131b5f19cc582c9aa18de59`;
the production C# is unchanged from the accepted `4a8a0b3` artifact source.
Pinned target: `v0.107.1`, Steam build `23811903`, macOS arm64.
The isolated official .NET SDK `9.0.303` archive was SHA-512 verified and its
executable reproduced the prior pinned identity. No base-game file was edited.

| Artifact | SHA-256 |
| --- | --- |
| `Sts2AgentBridge.dll` | `befe5a90d538032d7a89ec5075b5259b95bb6d8b20bfa75a3e00dca509dcdbbc` |
| Loader manifest | `498e815fc742e85112e43823b3b2e291e60efe03353a22e263d316e6fb67b971` |
| `Sts2AgentBridge-0.8.0.zip` | `7f4194ece6bda1e7f2979f4a1b0aebb8bcae88c127af66bcf69a7e4325dc6dd0` |

Acceptance before live launch:

- two independent builds reproduced identical DLL/manifest/ZIP;
- all 12 C# test groups passed; the synthetic loopback suite required the
  environment's technical sandbox permission, not a code repair;
- full final surface gate passed **70 fixtures**;
- package negative fixtures **7**, campaign lifecycle fixtures **34**, runtime
  fixtures **17**, and all eight focused controller/probe fixture suites passed;
- protected operator configuration and exact two-file overlay verified;
- clean base projection verified **429 files**, SHA-256
  `d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.

An earlier surface invocation failed because the coordinator moved the verified
artifact before that invocation's final source-negative test. It was discarded
as failed, not called a pass; a fresh complete gate ran against the stable final
artifact location. One base-verifier invocation rejected a relative manifest
argument before inspection; the corrected absolute invocation passed.

## Sanitized live campaign result

Only the coordinator operated the game. Profile 3 was visibly selected before
resuming its existing run. The campaign retained no raw response log,
credential, control identity, profile-content artifact, or differential corpus.
Steam Cloud was not changed; its previously established disabled state was not
given a fresh idle/synchronization claim. No other profile or multiplayer was
used. There was no crash.

| Check | Observed result | Evidence |
| --- | --- | --- |
| Authenticated main menu and Settings | Both passed, three routes each; no settings changed | Live-demonstrated |
| Existing multi-step standard event | Controller caused visible advancement, then `room_interaction_timeout`; normal UI Exit Baths → Proceed recovered to map | Live failure; completion not accepted |
| Room endpoint while map was visible after UI recovery | Still reported ready/event with one candidate | Live-demonstrated stale underlying-room projection |
| Coverage map provider | Selected advertised `rest_site` destination and reconciled arrival | Live-demonstrated |
| Reviewed rest readiness preflight | Expected-kind ready in one attempt | Live-demonstrated standalone check; does not prove the delayed-completion race live |
| Bounded rest interaction | Healing occurred and map opened, but controller timed out; room endpoint reported waiting/unknown with zero candidates | Live-demonstrated action effect, failed completion reconciliation |
| Underlying rest room | Closing map revealed the room and its Proceed control still present | Live UI observation supporting overlay/room-lifetime investigation |

No further bridge action was attempted after the rest timeout. No full batched
combat-room-combat acceptance was obtained in this campaign. Prior combat and
reward evidence is preserved, not attributed to this launch.

The reader checks underlying room visibility and the general overlay stack,
but not the separate foreground map screen. The action applier rereads that
same projection, so foreground action eligibility also needs review. The stale
advertisement is proven; application of a behind-map action is not.

Content-derived room IDs and pending-ID suppression remain possible causes of
the event-step timeout, not a proven root cause. The waiting response's empty
candidates are a fail-closed projection, not proof that the underlying room has
no options. A future completion predicate must distinguish inspection-only map
opening from a correctly bound completed room; map visibility alone is not
sufficient. Do not reset replay protection, retry ambiguous POSTs, or promote
a timeout to success.

`R0I-RUN-03/04` explicitly exclude C# changes. After this campaign, the user
approved a separate narrow `R0I-ROOM-LIFECYCLE-07` foreground-room/map repair,
with replay protections unchanged, independent review, and another bounded
live check. Event-step identity redesign remains outside that new packet.

## Teardown acceptance

Normal Save and Quit returned to the Profile 3 menu; the game then quit normally.
The runtime guard observed the process absent and port closed. The post-campaign
overlay verifier still matched all 429 base files and the exact two overlay
files. The manager quarantined the exact installation and temporary operator
files; base-only verification passed with zero overlay files.

A clean unmodded base-game launch reached the Profile 3 main menu. The runtime
guard observed the game running with the bridge port closed. Normal quit then
passed the stopped guard. The manager purged exactly **four generated files**,
including the temporary credential. Final base verification again passed with
429 files and no overlay. Installed campaign state is absent; reproducible
build outputs remain outside the game installation. No live campaign is active.

## Execution telemetry and open work

| Task | Allocation | Observed task-turn elapsed seconds |
| --- | --- | --- |
| Baseline | Luna / medium | 251.881 + 157.062 |
| Room preflight repair | Terra / high | 326.959 + 25.832 + 126.150 |
| Offline differential | Sol / high | 768.128 + 199.347 |
| Rollout | Terra / high, then Sol / high | 711.178 + 359.654 + 279.400 |
| Room lifecycle | Sol / high | 834.211 + 470.202 |

These are tool-reported wall-clock durations, not active compute time or a cost
estimate. Aggregate input/output/reasoning token counts and coordinator elapsed
usage are unavailable. Rollout escalated after independent real-spawn SIGINT
tests proved the same cancellation acceptance failure persisted at cleanup,
and benchmark repetitions continued after cancellation. This was an
outcome/evidence defect across consumers, not an escalation for task length.
Only aggregate telemetry is recorded; no hidden reasoning or task
transcripts are retained here.

Open items: bounded live acceptance of the reviewed C# repair; separately
authorized retained live differential input. None permits claiming full-game
fidelity or autonomous-run completion.

## Reviewed C# lifecycle repair and second artifact

Two independent read-only reviewers rejected the initial `1a3aebf` candidate:
a missing room sample could allocate a fresh ordinal on return, bypassing the
existing replay dictionary through a new hash. The worker reproduced this with
public `Apply`: unchanged event projection, ordinal 0 → 1, and two clicks.
The coordinator approved a bounded identity registry, and both reviewers
accepted corrective `be6c7a1` after fresh-returned-request regression coverage.

At most 1,000 numeric run/room pairs retain immutable first kind/ordinal without
eviction or reset. Known returns work at capacity; new pairs and conflicting
kinds fail closed. Missing/unsupported/travel/changed-current-room samples clear
volatile completion evidence, not replay identity. The same guarantee covers
A → B → A. An unchanged accepted projection may later be advertised ready but
still rejects application; automatic event continuation is not claimed.

The accepted completion predicate is deliberately rest-only: accepted literal
rest `proceed` in the same current run/room, map open and travel-enabled, not
traveling, and no unsupported content/overlay. Foreground map suppresses all
room candidates and immediate pre-dispatch revalidation prevents stale clicks.
Inspection alone never proves completion. Event-to-map remains fail-closed;
embedded-combat completion requires an accepted same-event action. Wire schemas,
hash algorithm, encoders, reservations, and action caps are unchanged.

Coordinator validation of the immutable corrected source passed all 12 C#
groups and the full 70-fixture surface gate. The only policy changes are these
independently reproduced release fingerprints (source count remains 43):

- source projection: `62a8e459a21540214d3e840cda1014388124be88205bd5d5cfe5fa5606b3381a`;
- normalized assembly structure: `bd182eb0e5eb802f3341a4d39c420d2535ef95d55d6f57ed22549c86a0bb5570`.

No game/API, reflection, route, filesystem, or networking allowance widened.
The expected unchanged-policy rejection was `release_source_projection`, not
a waived failure. Two independent builds reproduced identical outputs:

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| DLL | 202240 | `a586aa99b9deeeb04b22596340dcccd0c6894b59db27625dfa1a1a8c2508c285` |
| Loader manifest | 323 | `498e815fc742e85112e43823b3b2e291e60efe03353a22e263d316e6fb67b971` |
| ZIP | 202879 | `c97f3a0cd094523c769065fc921c3758569575c8dd5e754c5d2597ab7ee5a595` |

All 7 package-negative, 34 manager, 17 runtime, 16 room, 14 run, 14 map, and
18 Python wire tests passed. The offline inventory deliberately changes only
`bridge.source_inventory_sha256` to
`a0ca37bb2d0ad36fcb68eafe5163ac8174074b0e6f861c69c2ac357873f75f2a`;
48 authored files remain, with only the two reviewed production C# files
changed. All other calculated identities remain unchanged. Synthetic comparison
labels remain 3 passed, 14 divergent, 2 unobserved.

A transient inspection-map rejection harness passed independent review and
9 fully mocked tests, including its bounded 45-second operator handshake,
single snapshot-bound POST, exact stale/no-mutation receipt, and credential
buffer clearing. It logs no raw payloads or control identities. Live evidence
for this second artifact is still pending at this checkpoint.

Environment caveat: an isolated measurement-build SDK startup emitted a
`CSSM_ModuleLoad` error plus its generic development-certificate setup message.
Whether a certificate was installed was not investigated; no intentional
keychain action occurred. Subsequent SDK invocations explicitly disabled
development-certificate generation. This is not evidence of a game/profile
mutation or a verified keychain state.

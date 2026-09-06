# Card selection release v1 acceptance ledger

Date: 2026-09-06. Functional baseline: `8fc1db7` in the selected 23cf integration
checkout on `codex/phase1-actor-ready-integration`.

## Accepted scope and current state

The coordinator accepts the [release contract](../PHASE_1_CARD_SELECTION_RELEASE_V1_CONTRACT.md)
with exact SHA256 `0d66520d5f7f14a78f9d6e3b35fd4438f7811661a5e8a399b33920da4f2fd0f6`.
The independent reviewer accepted this exact amended contract after checking
frozen APIs, framing, selected policy, owner disposal, production closure and
predecessor conflicts. This disposition supersedes the draft status within the
frozen document without changing its bytes.

The release is implemented, independently reviewed, source-frozen and published
for bounded live testing. Initial native support is Room Full of Cheese/Gorge
(add exactly two of eight cards) and ordinary rest Smith (upgrade exactly one).
The shared pure core models variable-cardinality add/remove/upgrade/transform;
other native event callers, scrolling and incomplete visible candidate domains
remain unsupported. The host selects first legal cards for conformance, without
a strategic policy.

The first Smith campaign is now installed and awaiting the user's untouched
rest-site screen. No client has been invoked and no gameplay action has been
attempted. Its active state is recorded below. The previous Dense Vegetation
campaign and its cleanup remain closed.
No historical uncertain action or closed state may be retried or adopted. No
profile/save filesystem, Steam Cloud, retained live corpus, target execution
during verification, remote Git or unrelated capabilities were used.

## Source and artifact identities

All ten predecessors and the original 48-file bridge inventory remain byte-exact.
The final release contains 57 source files plus its manifest:

- source manifest SHA256 `67cb5073c9a39542677a806064d829a8595331f39665fc6a7bfa7ba71666f16c`;
- source inventory SHA256 `39fd9535446de173af6d065d7d70e2a5f010923ad2a356363b04e133d73d62fe`;
- checker SHA256 `f819157b538a3921d7dd30de56e4086bbcf7187de95c1ce3048c901bfbb728c0`;
- freeze helper SHA256 `321aded5df1055846a21258a5e7359da445c616799ea65c0caecdae340e0f1f8`.

The canonical artifacts are published and reread-verified at
`/private/tmp/sts-card-selection-v1-release`:

| Artifact | Bytes | SHA256 |
| --- | ---: | --- |
| `Sts2AgentBridgeCardSelectionV1.dll` | 202240 | `61e5617a744587479ef7f9346b8f5d7f9356f695b536d333beff046bd367689b` |
| `Sts2AgentBridgeCardSelectionV1.json` | 370 | `a1995763b15143a87bb4effc42fdb55ebeb818fed2dce543fea2be51db50ffb2` |
| `Sts2AgentBridgeCardSelectionV1-1.0.0.zip` | 203046 | `f1cb2208b9a3d13b3f660ce1c716b0e75f5713de24a4ecd42e244145c02ae27f` |

B independently compiled two fresh physical snapshots, and the coordinator's
complete gate compiled two more. All four outputs match. The production closure
contains exactly 30 reviewed sources and only the two pinned compile references.
No candidate or target assembly was executed or emitted as a pure dependency.

The final policy is 829192 bytes, SHA256
`0c55a880b7d146ce5e3171223173337c70131f403792426f22f80ecbde590548`.
Its canonical 30-source projection is
`0179b77fd1afb0b10c59dd85664a38447d7f97523db904f4e53f3897b942335d`;
its 7500-row metadata projection is
`90f60033fba351a731a7a0516b08edd66ac26783933d3ed0b0a1150cc88c4257`.
It covers 1037 decoded method bodies. B's separately labelled JSON build-record
digest `2986fff64d9e25ca21d573f9283cd9d30cb33d77196052cb72d9f75bcfd6a983`
is not the verifier's canonical source projection.

## Validation and independent review

The final complete gate is
`/private/tmp/card-selection-release-root-final-a2/result.json`, SHA256
`dff53a6ce2fd56aa7391d971b4ff30f446a91a65cd2247a838d7119c49ea0a50`.
Its exact evidence is:

| Suite | Passing checks |
| --- | ---: |
| Secure operator | 5 authored groups |
| Owner bootstrap/lifecycle | 14 authored groups |
| C# transport/runtime | 13 authored groups |
| Actual C# runtime and frozen Python host socket composition | 3 scenarios |
| Project/source boundary | 15 cases |
| Python client | 13 tests |
| Python transport | 14 tests |
| Campaign manager | 39 groups |
| Runtime operations | 17 groups |
| Predecessor conflicts | 18 cases |
| Exact source derivation | 13 files |
| Whole-assembly verifier | 1037 decoded bodies |
| Real PE/semantic mutations | 57 cases |
| Shipping verifier CLI rejection | 10 cases |
| Canonical package | 5 groups and 9 mutations |
| Clean-install verifier | 7 groups |

Full repository regression passed **1206 tests in 106.62 seconds**. Subsequent
changes were confined to artifact literals, a manifest mutation fixture, verifier
serialization, the aggregate snapshot and documentation; the complete release
gate covers those changes. No unrelated implementation changed.

A owned runtime and its fixtures; B owned operator/lifecycle/native/production;
R owned verifier/tests/policy; the coordinator owned Python/client/operations,
package, aggregate, source identities and documentation. Disjoint ownership was
maintained. Reviews crossed the implementation lanes:

- B accepted the final runtime, Python transport, and 13 exact operational
  derivations. Final runtime SHA256 is
  `5f43adc366fc821813c51dc20a1f2eecc6b66cd03fb7edb5eed800f37114c753`.
- R accepted B's secure loader, selected-policy wrapper, owner lifecycle and
  production closure. A and R accepted the root composition/checker algorithms.
- B independently accepted the final compact policy and verifier. All 1085
  MethodDef tokens, 1037 body links and 1329 parameter rows retain unique,
  recoverable ownership with no orphan or collision. Exactly the accepted 13
  read-only native imports, four routes, factory and frame-call paths remain.
- A independently regenerated both candidate/package identities, checked all
  artifact joins and replayed all 13 derivations after the final fixture fix.
- R independently accepted the final 57-file manifest, checker correction,
  complete aggregate result and candidate/policy/source hash joins with no
  remaining blocker.

B build evidence is `/private/tmp/card-selection-release-b-final/result.json`;
R verifier evidence is `/private/tmp/card-selection-verifier-r.vv3G8j`. The
shipping verifier passed both independent candidates and all 57 mutations.

## Corrections completed before acceptance

Runtime review closed a shutdown race: terminal intent blocks new work
immediately, while externally visible stopping waits for every authenticated
worker to clear owned buffers and settle its socket. The paused-cleanup fixture
proves no extra native dispatch. POST input is created and cleared within its
owner-frame callback, including queue-timeout and late-result paths.

The first policy encoding exceeded the inherited 1 MiB source-file boundary.
MethodDef tokens now replace repeated owner strings in parameter/body rows;
complete identities and decoded metadata remain available. The limit and the
production candidate were preserved. The first clean-install fixture run found
an inherited old manifest-name needle; its exact recorded replacement now tests
the current canonical name.

The first aggregate attempt stopped because its isolated snapshot omitted the
48 original bridge files needed by the nested preservation check. The checker
now verifies their exact count and aggregate identity, copies only those files,
and verifies the copied inventory before any snapshot build. R accepted that
correction. The unaccepted draft manifest was explicitly hash-checked, removed
and regenerated; no accepted predecessor identity changed. The final fresh
aggregate passed completely.

## Live readiness and next operator setup

Read-only preparation on 2026-09-06 passed: game stopped, port43117 closed,
unchanged base429 with zero overlay. Supported computer-use selection of the
running Steam instance still returned ScreenCaptureKit `-3811`; the initial
short-name lookup selected a non-running duplicate application. The exact
running-app capture failure remains separate from controller behavior. No launch
or gameplay action occurred.

The user has been asked about availability for the first Smith campaign. Keep
the game closed for installation. After fresh stopped/base checks and exact
Smith installation, ask the user to launch on Profile3, continue Ironclad A0 and
reach an ordinary rest site with Smith/Upgrade available. Stop before clicking
Smith; no card selector or popup should be open. Prefer an early rest site so
the eligible-card grid can be completely visible.

Only after confirming that initial parent screen may the fixed client run once.
The separate Cheese campaign requires its initial Gorge option untouched and
complete cleanup of Smith first. Any uncertain result ends that invocation
without retry. Normal quit, code-first quarantine, exact owned purge and clean
base/stopped checks remain mandatory. The user's waiver of repetitive unmodded
relaunch checks remains in effect.

## Smith live campaign 1 — installed, awaiting user setup

The user explicitly requested live testing on 2026-09-06. The clean integration
source is `2739a326ce0c6f5f2c8f679dad2ee65ce667322e`. Fresh validation passed
all eleven successor source manifests, the exact three published artifacts,
game-stopped/port-closed checks and the unchanged base429/zero-overlay check.

Installation began after 14:11:55 UTC and returned passed for
`CARD-SELECTION-V1-SMOKE-V1`, protected selection `smith`. The manager created
the mods parent and published the exact overlay last. Active installed state
SHA256 is `a4f1eec0fa0974058707bf7802f0d9a604de5b3a4be749c22a30242f671c4b2a`.
Post-install verification passed unchanged base429 and exactly two overlay
files against the accepted canonical package. Credentials were neither emitted
nor inspected outside the reviewed manager. No game launch or client invocation
was performed by the coordinator.

The user was asked to launch manually on Profile3, continue Ironclad A0 and
reach an ordinary rest site with Smith/Upgrade visible and untouched, without a
card selector, map or popup. The next action is supported UI confirmation of that
exact initial parent, then require-running and one fixed client invocation using
the active state above. No readiness GET or preliminary gameplay request should
consume the fresh parent session. Record only the fixed sanitized summary.

This campaign is active and cleanup is outstanding. After the single invocation
or an aborted setup, quit normally, wait for stopped/closed, quarantine using
this installed state, then purge using the newly returned quarantine state.
Verify clean base429/zero-overlay/stopped/closed and the fixed absences. The
unmodded relaunch remains waived. Never reuse this state after cleanup.

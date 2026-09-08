# Generic event release v5 acceptance

2026-09-08. Accepted, frozen and installed; first v5 live test pending. Game closed;
v1/v2/v3/v4 campaigns closed. Authoritative 23cf baseline `526ad1b`.

## Evidence and reviewed repair

User requested continuation after v4's single live `candidate_hitbox_type`
failure and full clean teardown. The runtime subtype name remains unknown.
Frozen earlier reward code uses the native declared hitbox type plus liveness,
retaining the captured reference. This supports the narrow compatibility repair.
No new target inspection or profile/save/Cloud work was performed.

Independent review accepted the [v5 contract](../PHASE_1_GENERIC_EVENT_RELEASE_V5_CONTRACT.md),
SHA256 `9d82284abe3b35d861a2355259c5d88320e62aec523fc73989214bd1c79f4eb8`,
before implementation. Only two reward hitbox exact-type checks change to a
statically typed liveness helper. Initial null and later captured-reference
checks remain; all other exact-type,ownership,visibility,enabled and selection
checks remain. Existing78 diagnostic mappings persist with48 reserved.

Root owns release closure/checker/client/package/operations/docs;B native and
fixtures;A runtime/transport/socket;R independent verifier/policy/review. All22
predecessors remain frozen. SDK use is serialized; builds use disposable offline
snapshots. Only game-owned pinned Harmony plus inert stubs execute offline.

## Stable production and early validation

Root and R reviewed the native diff: exactly two callsites in existing positions
and the typed liveness helper,plus mechanical release namespace changes.
Two fresh compile-only candidates under
`/private/tmp/generic-release-v5-production-candidate-a/{first,second}` match:
DLL240128bytes SHA256 `01d5f309be035cc4b5a184db1a297bfad8c0151a2605c514e2ceff69da228cd0`.
The38 source inputs match the first snapshot,source projection
`728554490252d18167c01569e2a83587b857602754f07de5047c9baf910e795c`.
Manifest352bytes SHA256 `5536ad71b80d45a87901274d15b21527eb2bbe7a649bf8f79290e7ac8321df0a`;
ZIP240908bytes SHA256 `f309daf45a186e2ace0d543bd6b902d900aac8ab3556df4ade0e5c1da5aa821b`.
Package and operation pins use these new identities; final publication is recorded below.

Root focused tests passed: client13,manager41,predecessor conflicts44
(retained38+v4state/overlay/operator install/client rejection),clean-install7,
package5 plus9mutations. A Python transport19 and runtime542 assertions passed.
B's five focused projects passed: 745 preserved assertions, 168 older diagnostic
assertions across 36 codes, 38 release-native assertions, 154 candidate checks
covering 40 active rejection leaves and eight actual native subtype cases, plus
31 frozen-v4 baseline checks across 14 traces. All 14 unchanged-path traces match.
The separate repair comparison reproduces v4 code 48 and admits the same derived
hitbox input in v5. Invalid or replaced instances stop before extra child dispatch;
the successful case reconciles selected originals, baseline deck and Proceed/map.
Evidence: `/private/tmp/generic-release-v5-b`.

A's 17 native-to-client socket scenarios passed, retaining all 16 old scenarios.
The new `native_derived_hitbox` scenario passes through actual native hooks,
session, wire, owner-frame runtime and Python; it retains hitbox identities and
completes ChildReady to MapReady with two parent actions, two child actions and
six reads. Selected original additions, baseline deck and owner cleanup pass.
A's read-only audit of root-owned closure, pins, client and operations found no
blocker. Evidence: `/private/tmp/generic-release-v5-a`.

R independently accepted the narrow native diff and final subtype evidence.
All 100 verifier checks pass (91 preserved plus nine new checks); both candidate
assemblies verify and independent policy extraction is byte-identical. Static IL
proof binds the liveness-only helper, its two callsites and seven retained generic
non-hitbox exact-type checks. Policy: 1008283 bytes, SHA256
`97613f6771690cee77b26ac10c653e2990771ccbe5b63e938f7235c0ced77c1c`,
1223 bodies, 9139 rows and 38 production sources. Metadata projection:
`f37f062a4f27f36b4a8e9e92a3f00bb7ab5e1685f04cce171f4edefa480b29e0`.
Evidence: `/private/tmp/generic-release-v5-verifier-a`.

## Candidate gate and source freeze

The complete candidate aggregate passed in
`/private/tmp/generic-release-v5-root-candidate-a`; result SHA256
`2e7afeffd6925a49c875e6323d55ddd9f86c799dac8c0ff89108f7938a9ae7ad`.
It checked all 22 predecessor identities, 13 project categories, 38 production
sources, all required fixture suites, all 17 socket scenarios, 100 verifier checks,
and two byte-identical production builds. Both the frozen lifecycle suite and the
instrumented preserved suite passed 745 assertions. Runtime-tool 17, operator 4
and bootstrap 13 checks also passed. No production, sts2 or Godot assembly executed.

After staged whitespace validation passed, the exact 80-file v5 source inventory
was frozen as successor 23, plus `source_identity.json`:

- Inventory SHA256: `adade4736245aa9e61efdd8f926b5e4b9a209697bfc1dcf1009a3fb4b0c6d2fc`.
- Manifest SHA256: `dd0be8c5222ff27a10f179becb053d8c6218fd9ec2e9abb6f7b765002069f99e`.

All implementation owners closed their source lanes. The fresh frozen aggregate
passed in `/private/tmp/generic-release-v5-root-frozen-a`; result SHA256
`f2be77bb8d4742997a6c503e821e13060f3f8ad934ac93342fcfafbcd4550ecc`.
All candidate suites passed again, including frozen-client source validation
without credential reads. Source inventory and production DLL match the candidate
gate. The exact canonical three-file artifact set was then published under
`/private/tmp/sts-generic-event-v5-release` using the frozen gate's production DLL.

## Fresh installation and current state

Both release gates and independent acceptance preceded installation. Fresh
require-stopped passed with 3 process samples and 2 closed-port samples. Base
verification passed: 429 files, zero overlay files, projection SHA256
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
The one fresh manager install passed:

```json
{"schema_version":1,"status":"passed","campaign_id":"GENERIC-EVENT-V5-SMOKE-V1","mode":"install","phase":"installed","mods_parent_created":true,"state_sha256":"27ad96a07cb94509727aee99bc8eed4f6abc7d6291eb527a83716e52e15706ab"}
```

Post-install require-stopped passed with 3 process/2 port samples. Overlay mode,
using the exact v5 package, passed: unchanged 429-file base projection and exactly
two overlay files. `validate_installed_for_client` passed for the current state,
phase installed, with credential bytes unread. No v5 client, automatic game launch,
profile/save/Cloud work or foreign-mod change occurred. All older generic campaign
states remain closed and must not be reused.

## Next live step and remaining limits

The user may now manually launch Profile 3, single-player, fresh Room Full of
Cheese initial choices, Gorge untouched, with no selector/console/map/popup.
After user readiness, verify UI and require-running, then exactly one invocation:

```sh
/Users/rowdeygoos/code/github/RowdeyGoos/StS_agent/.venv/bin/python -B \
  /Users/rowdeygoos/.codex/worktrees/23cf/StS_agent/bridge/Sts2AgentBridge/successors/generic_event_release_v5/client/run_live.py \
  --expected-state-sha256 27ad96a07cb94509727aee99bc8eed4f6abc7d6291eb527a83716e52e15706ab
```

Preserve only its bounded summary and finite diagnostic. No retry/adoption or
manual child selection after uncertainty. Success requires selected original
card additions and explicit Proceed/map completion; downstream live predicates
and effects remain unverified until then. Quit normally and complete stopped/closed,
code-first quarantine, exact purge, clean-base and final stopped/closed checks.
The installed state above is not the later quarantine state: use each freshly
returned state hash for its next cleanup action. Repeated unmodded launch is waived.

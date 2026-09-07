# Generic event release v1 acceptance

2026-09-07. In progress, authoritative23cf integration worktree, baseline d661144.
The user authorized live testing, accepted that installation must come before
launch, and requested notification when to start the game. No launch requested yet.

[Contract](../PHASE_1_GENERIC_EVENT_RELEASE_V1_CONTRACT.md) independently reviewed.
Root owns Pythonclient/operations/package/checker/provenance/docs; A owns runtime/
transport/socket fixtures; B owns startup/operator/native/factory/production;
reviewer owns verifier/policy and independent source review. One SDK lane.

The game's existing Harmony library differs from frozen v3's NuGet artifact.
A fixed-path hash and PEReader metadata-only inspection established2328064bytes,
SHA256 ef1898322c9f5c86dc1b0758b272a9c440823b4a41ca9a0b82a3aa6b3d206387,
assembly0Harmony2.4.2.0,unsigned,MVID6b813929-656e-4f25-9e34-f25e7084505d.
No game code executed by this inspection. Temporary reader source is under
/private/tmp/generic-release-harmony-metadata-a. Its first SDK initialization
reported development-certificate setup; subsequent isolated build environments
explicitly disable certificate generation. No certificate trust command was run.

Production references this exact game-owned Harmony and verifies actual resolved
identity before hook construction; no second Harmony copy/resource/loader is used.
Prior NuGet-native tests remain separate evidence. New inert fixture executions
may use the pinned game Harmony with target stubs; production/target game binaries
remain compile-only until installed launch.

Review identified and corrected old runtime's nonretryable disposal latch,
failed native-constructor cleanup loss, final map_handoff status, and exact parent
rejection spellings. Live installation and launch remain pending final aggregate,
independent production policy review, source freeze and preflight.

## Integrated candidate gate

The complete candidate gate passed in
`/private/tmp/generic-release-root-candidate-c/result.json`. Candidate-a stopped
at an obsolete NuGet MVID fixture expectation; candidate-b passed all28 native
checks and stopped because the aggregate omitted the operator synthetic-root
argument. Both fixture wiring errors were corrected; no production change was
needed. Candidate-c passed with the pinned game Harmony against inert stubs.

Validation:280 runtime assertions,28 native release assertions,550 preserved v3
native assertions against game Harmony,13 lifecycle groups,4 operator groups,
10 Python transport tests,13 client tests,8 actual wire/socket/Python scenarios,
39 transactional manager groups,24 predecessor conflicts,17 runtime-tool groups,
7 clean-install groups,5 package tests with9 mutations,and63 verifier checks.
The verifier checked1,208 method bodies and the exact36-source production closure.
Two integrated production builds matched the two independently reviewed candidates.
All17 frozen predecessor source identities and original48 bridge files passed.

Production DLL:230400bytes,SHA256
`855160f4bccf499d5cb7f7f4ef60a0d3b9b18c9aa8083cc2df09f1bf7a4735a4`.
Manifest:352bytes,SHA256
`152de1222b1107dfc0bf173e3ec8ab733dc0c4060e47d7eba199cd5bd2d7a858`.
Canonical ZIP:231180bytes,SHA256
`a0ead61911ce3da14189edd66ec3c108d76cc81504cdd0f5b87d7cd54c4768e1`.
Policy:961274bytes,SHA256
`962bcc2e5cf6d504f5d7bbc20ae4118174219d7522c6da64fb61e70f9d379d19`.
Production metadata projection:
`ed41bbc67655dd332161a6eb96a6fd9e38ffb344c11f717eee0ba6ce49ef0e9b`.
Production source projection:
`742904f78e8ce2f2a4e1adcaa66ed3bed6404b6ddeb7c9c51e0baa05c85422a0`.
Contract SHA256:
`092736202c19ca667ee8e8227dcd169afc27be2ae7bec5941970031ab878e445`.

Independent production/runtime/native/client/operations/package review found no
remaining actionable issues before the aggregate; final fixture-wiring review
and frozen rerun follow. No game binary or production bridge was executed.

## Final source identity and preflight

The reviewer independently accepted both aggregate fixture corrections, confirmed
all36 production sources and policy unchanged, and reported no actionable findings.
The first manifest rerun passed. Staging additionally caught one trailing-space
line in an operator fixture; it was removed before final acceptance and the
manifest/provenance were regenerated. No production bytes changed. The final
61-file source identity is:

- Inventory:`cc3f4bc96d873b76f6835025d6c8bd81d1f55166b8b859cfed046e8eb163e207`.
- Manifest:`82202f06bfc0f12abcf6aa44bde435e95bb157e830e3365b6e3d094e72b7d282`.

Fresh read-only preflight passed: game stopped, port43117 closed with three
process samples and two port samples; base429files matched projection
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`,
with zero overlays. Final frozen-b gate and installation results follow.

## Accepted release and installed live setup

Final frozen gate passed at
`/private/tmp/generic-release-root-frozen-b/result.json`,SHA256
`1252e0583036120689b34921b2aac528c2dc1a8d00f45a4bed080de2781d7008`.
It included frozen client source validation without credential access and two
identical production builds. Staged whitespace validation passed. The final
61-file identity above is accepted and frozen; preserve it and all predecessors.
The verified three-file artifact set was published at
`/private/tmp/sts-generic-event-v1-release`.

User-authorized installation succeeded for GENERIC-EVENT-V1-SMOKE-V1, generic
flow. The manager created the mods parent and published the two-file overlay,
protected operator unit and owned campaign state. Installed state SHA256:
`27abbf7eefab4429666e3e98484a6ccca2742c89ef720d6219c240336bece907`.
Post-install verification passed:429 base files unchanged,exactly2 overlay files,
game stopped and port closed; client source and installed metadata validated
without reading credentials. No launch, controller invocation, game action or
profile/save/Cloud access occurred. The bridge is now installed awaiting manual
launch and the user-prepared initial Cheese event described in the contract.
Live success remains unproven. Cleanup is pending the campaign, using this
release's quarantine/purge tools and current state hash, never predecessor tools.

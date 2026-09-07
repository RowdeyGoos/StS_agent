# Generic event release v2 acceptance

2026-09-07. In progress, authoritative23cf, baseline05f768a. The user asked to
continue correction after the first generic release's failed live attempt and
completed cleanup. No campaign is active. The accepted lifecycle successor has
reproduced the old failure and passed its frozen gate; this release packages it.

The [release contract](../PHASE_1_GENERIC_EVENT_RELEASE_V2_CONTRACT.md) was
independently accepted. V2 retains the v1 protocol, authenticated transport,
owner-frame lifecycle, game-Harmony guard and cleanup/no-retry rules. New release,
operator, campaign and artifact names prevent reuse of prior state. All nineteen
predecessors remain frozen. Exactly four native sources come from the accepted
lifecycle successor; core/wire/hooks/parent/card semantics remain source-linked.

Root owns checker/client/runtime/transport/package/provenance/docs. Native reviewer
owns explicit generic-v1 conflict additions and startup/production review.
Independent verifier owner owns verifier/mutations/policy. One SDK lane.

## Candidate and focused evidence

Two compile-only production builds match at229888bytes,SHA256
`49fad4d399abaf2db7265b6649fcac05358342b79f83c44fefcfc58f7031bc02`,
under `/private/tmp/generic-release-v2-production-candidate-a/{first,second}`.
No target or production code executed. No dependency bytes copied into output.
Manifest352bytes,SHA256
`6d83702879ee9072d0bc9c2659407cc6645aa14950f4de1055ba2a869fc7744c`.
Canonical ZIP230668bytes,SHA256
`ed00a3b3fe47a9772b38c6d02ca346e35883378f3c31476353e4c9b864f51bbf`.
New fixed artifact root:/private/tmp/sts-generic-event-v2-release (not yet published).

All28 predecessor-conflict fixtures passed. New generic-v1 state/overlay checks
apply during install and retained-environment validation, including late client/
quarantine conflict retention. The full manager suite passed40 groups with new
artifact pins. Package tests passed5 cases and9 mutations. Native/startup review
confirmed exact scope:36 production sources, four lifecycle replacements exactly
once, no original counterparts, and preserved startup/Harmony cleanup behavior.
Independent metadata verification, aggregate, freeze and live installation follow.

## Independent production and consumer acceptance

Verifier63 checks passed. Both production candidates passed exact verification
and reproduced byte-identical policy:961314bytes,SHA256
`dab0da59c4600a76de74d8e134155bde18ed0659137ec73842dc71825151089e`.
Metadata projection:
`e25bac4c8c794fcdca59bb455e78735b709fed303b141243d28a9460f7583627`.
Source projection:
`8f1822ca955a123d3e65c8b1c8b3089e1d48adda891ee6981ce90a2c5613410f`.
The verifier checked1208method bodies,8785rows and36sources with lifecycle4
included and original4excluded; no forbidden/sensitive calls or resources,
retained13Darwin imports and exact game-Harmony dependency. Verifier outputs:
`/private/tmp/generic-release-v2-verifier-a`.

Independent client/runtime/transport/checker/package review found no regression.
Runtime/transport preserve v1 behavior; client verifies all19predecessors through
the exact lifecycle checker plus the new release contract. Production and native
fixtures contain the exact four corrected sources once each. New package pins
match canonical bytes. Staged whitespace validation passed. Fresh stopped/closed
preflight passed while the full aggregate ran. No game launch or live request.

## Candidate aggregate and source freeze

The full candidate aggregate passed at
`/private/tmp/generic-release-v2-root-candidate-a/result.json`:280 runtime
assertions,28 native release assertions,745 lifecycle native assertions,
13 lifecycle groups,4 operator groups,10 Python transport tests,13 client tests,
8 actual wire/socket/Python scenarios,40 manager groups,28 predecessor conflicts,
17 runtime-tool groups,7 clean-install groups,5 package tests with9 mutations,
and63 verifier checks. Two production builds matched the independently reviewed
candidate pair. All19 frozen predecessors passed their exact source checks.

The61-file new source identity is frozen after independent review and clean
staging. Inventory:
`57649f846f76a835325d19d448b55e2fa1d7d7ce907c5b8f5efee0110e09b15e`.
Manifest SHA256:
`69b513a698564dd2e2312a3270035792cd248fd6fe6ce30ac6c30a5472eb756a`.
Contract SHA256:
`f783b0b7fcd014fe6ba4c8f356a17fbcbb753ca0ec35a3d5cfafa1539b663b83`.
Fifty-nine source files have exact v1-to-v2 unified-diff provenance; production
policy is independently regenerated. Client source validation passed without
credential access. Frozen aggregate follows before publishing/installing.

Fresh base preflight passed429files,zero overlays,projection
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.

## Final acceptance and installed campaign

Frozen aggregate passed at `/private/tmp/generic-release-v2-root-frozen-a/result.json`,
SHA256`0d3eb0999fda5f926e581253396432f63d07ad542f7f6ecf9af08ed75f77f5ae`.
All counts above passed again, including frozen client source verification without
credential read. Two further production builds matched the reviewed candidates.
The release is accepted and frozen as the twentieth successor. All19predecessors
and the original bridge remain unchanged. Do not edit this accepted source tree.

The exact three-file artifact set was published at
`/private/tmp/sts-generic-event-v2-release`. Fresh stopped/closed preflight passed,
then authorized installation succeeded for GENERIC-EVENT-V2-SMOKE-V1,flow generic,
mods_parent_created true. Current installed state SHA256:
`29cc158b9ad351094c96ca7ec9dbd7f034d51fc50a498b46e943de9d5c9a9463`.
Post-install checks passed:429base files unchanged,exactly2overlay files matching
the new package,game stopped and port closed; client source and installed protected
metadata validation passed without credential access. No new game launch,
controller invocation or gameplay occurred in this increment.

The bridge is installed awaiting manual launch and a fresh Profile3,single-player
Room Full of Cheese at initial choices,Gorge untouched,no selector/console/map/
popup. An old open chooser cannot be adopted. Verify visible initial state, then
exactly one invocation of this release's client with the current state hash.
Keep effects unverified unless actual success is returned. The lifecycle fix is
proven offline; its effect on the original live failure remains a live gate.
Cleanup is pending after the campaign: normal quit, stopped/closed, this release's
code-first quarantine and exact purge using current state lineage, then clean base.
Never use predecessor tools, hashes or credentials. Repeated unmodded launch waived.

## First v2 live attempt and completed cleanup — 2026-09-07

The user reported ready. Supported computer-use observation verified fresh initial
Room Full of Cheese choices with Gorge untouched and no selector/console/map/popup.
The running-game check passed. Exactly one v2 client invocation used the installed
state identity above; it exited4 with this sanitized result:

```json
{"schema_version":1,"status":"failed","parent_attempted":1,"parent_accepted":1,"parent_reconciled":0,"child_episodes":0,"child_attempted":0,"child_accepted":0,"child_reconciled":0,"total_attempted":1,"reads":258,"effects":"unverified","code":"unsupported_state"}
```

UI observation during the invocation showed the eight-card chooser open with the
choose-two prompt and no selected cards. No second invocation, manual selection,
retry or raw bridge-response capture occurred. This differs from v1's immediate
unsupported second read: v2 waited through the parent pending-read allowance
(MaximumPendingReads256) before stopping. No child episode was established.
This is evidence of progress beyond the earlier immediate stop, not successful
child admission, card effects or event completion. The specific waiting predicate
was not reported. Incomplete captured binding/task readiness and native selector
surface readiness remain candidates; grid geometry is only a hypothesis.

Next increment should expose bounded fixed diagnostic reason codes for pending
binding versus selector preparation before another test, and reproduce any
identified mismatch with inert fixtures. Do not relax checks, extend the wait
budget without evidence, retry the closed client, or infer the reason solely from
the visually open chooser. Preserve all twenty accepted source identities.

Normal Cmd-Q quit succeeded (UI tool reported app quit). Wait-stopped/closed passed.
Code-first quarantine passed with state SHA256
`fa3acf00a2af9bab81adc4cc89776d424cf4e1ee454d0830baa3e40319c64ec0`.
Exact owned purge passed,phase absent,4generated files removed. Final base check
passed429files,zero overlays,projection
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
Final require-stopped passed with3process/2port samples. No active campaign or
cleanup remains. Do not reuse historical state hashes. No profile/save filesystem
or Cloud access occurred; no normal game-save progression was restored. Repeated
unmodded launch remains waived. Temporary release artifacts remain for audit.

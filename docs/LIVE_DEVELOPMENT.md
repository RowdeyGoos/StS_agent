# Live bridge development

[AGENTS.md](../AGENTS.md) owns the development process. Read
[current status](PHASE_1_CURRENT_STATUS.md) for the relevant implementation and
evidence, then the [bridge guide](../bridge/Sts2AgentBridge/README.md) and relevant semantic contract. Historical
packet procedures are not universal requirements for new work.

## First answer the behavior question

Name the operation, intended target and observable outcome before preparing a
test. Use retained native evidence or one bounded inspection when needed to
identify a real caller. Do not build speculative selector features and only then
look for a caller that exercises them.

For controlled experiments, user setup or UI inspection may establish a premise
such as "card 16 is outside this viewport." Code still verifies exact holder/card
identity, native eligibility, dispatch ownership and the resulting preview/effect.
A universal rendering proof is unnecessary for that question. If a precondition
blocks the action, first decide whether it protects execution or only broadens
the conclusion. Do not remove checks that prevent wrong-target or duplicate input.

Expose a useful bounded failure category before the first attempt. Preserve
attempted, accepted and reconciled actions separately, including completed children
before a later failure. Keep raw responses, credentials and private data out of logs.

Use the interaction's actual UI family: a chest relic and a standard reward list
are different native surfaces. Console room creation after a map handoff can retain
travel state; native map entry produced the supported Smith setup in the unified
smoke. Establish a matching setup before changing an ownership guard. When request
encoding changes, exercise a representative POST; GET-only socket checks do not
establish action compatibility.

## Prepare and run within the user's scope

- Use the user's actual authorization and launch preferences. Existing approval
  covers routine preparation and corrections within that scope; a new contract
  filename is not itself a reason to ask again.
- Prepare and validate the concrete build before requesting manual game setup.
  State only conditions necessary for the experiment, and verify the requested
  target before acting. The established test profile is Profile 3 and launch is
  manual unless the user changes that preference.
- Verify the pinned game/build, actual selected artifact, current stopped/running
  state and owned overlay/configuration using the applicable operational tools.
  Historical readiness, credentials and campaign state hashes cannot be reused.
- Use native supported controls with identity/legality/ownership revalidation and
  bounded actions. An accepted receipt does not establish effect completion.
  Never retry or adopt an uncertain mutation.
- Finish owned cleanup: normal quit, stopped process/closed listener, exact owned
  quarantine/purge and unchanged base installation. Repeated unmodded launch/quit
  was waived by the user; do not restore it by copying old campaign instructions.
- Report the narrow observed result and cleanup. One live path is not evidence of
  all branches, arbitrary deck sizes, simulator fidelity or strategic quality.

A historical cleanup result is a dated observation, not a current process check.
This guide does not authorize a live campaign outside the user's requested work.

## Develop once; release one package

Use the editable `bridge/Sts2AgentBridge/components/` source and the single
`apps/bridge/` production composition. Features share the listener, authenticated
configuration, client and installation/cleanup tools. Extend a capability module;
do not fork another deployment workflow. The [bridge guide](../bridge/Sts2AgentBridge/README.md) owns current
commands. Development suites test current code without requiring a frozen release
inventory. One release gate binds the stable source/test/toolchain inputs and
verified binary; its manifest and separately retained hash select the live client.

The old successor trees are available in Git; their original identities remain in
[release history](../bridge/Sts2AgentBridge/releases/history/README.md). They are
not current build dependencies. Keep important release packages and evidence,
not a new permanent source copy for every fix or diagnostic. Do not repin old
results. A new wire/schema version needs an actual semantic reason.

Use focused native-to-host checks for changed behavior and real failure paths.
Review changed mutation/transport/cleanup semantics once. Reuse trusted unchanged
dependency results with matching source/test/toolchain/settings identities.
Run one final release gate. Reuse exact accepted binary identity when unchanged;
otherwise perform one reproducibility pair and reuse it for packaging and review. Rerun only what a relevant change invalidates.
If a checker bundles unrelated suites, provide a verified narrow entry point in
maintained tooling instead of ignoring failures or claiming unrun checks passed.

## User-data boundary

Ordinary development does not authorize profile, save, preference, progress,
history or Cloud filesystem work, retained live corpora or Cloud setting changes.
Do not use historical approvals as current permission.

If that work is explicitly requested, first read the [profile fixture plan](PHASE_0_PROFILE_FIXTURE_PLAN.md)
and the exact applicable request/result. The [baseline fingerprint request](PHASE_0_PROFILE_BASELINE_HASH_REQUEST.md)
and [attempt-1 result](research/PHASE_0_PROFILE_BASELINE_HASH_ATTEMPT_1_RESULT.md)
remain preserved: attempt 1 stopped before target-content access and no corrected
invocation is authorized by those records. No ordinary bridge task needs to reread
the entire profile-discovery history.

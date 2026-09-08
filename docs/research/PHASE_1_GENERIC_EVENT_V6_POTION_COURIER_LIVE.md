# Generic release v6: Potion Courier live test

2026-09-08. The user selected Potion Courier → Ransack and explicitly requested
“so let's test it then” after being told that the exact reward-screen behavior
on the pinned build remains unconfirmed. This authorizes one exploratory test,
including a fresh installation of the already accepted, unchanged v6 package.
It supersedes the previous initial-event setup for this invocation only.

## Fresh instance and scope

The Cheese invocation is closed and is not resumed. Use the frozen manager's
fixed GENERIC-EVENT-V6-SMOKE-V1 label and fixed paths for a new installation
instance only after absent-state, absent-operator and absent-overlay checks.
The manager generates a new credential and binds new filesystem identities.
No historical installed/quarantine hash or credential is reused. The accepted
package is deliberately reused without rebuilding or modifying frozen sources.
The newly returned installed-state hash identifies this instance in this ledger.

Source manifest SHA256:
6430fed7761f5336ff61bc92b91229d6b75567175ce149d6834cbcf4e118ade5.
DLL SHA256:
96723ba26f9f64a74cd0f1d8ae4217191a13410c5629a1feedc26a44f3890c2f.
Package SHA256:
ecc08551b583fdc64e3fab87bbf6bf3a0ba09ef9e8d5521a824261ee6c97ddd3.
Preserve the independently reviewed release and offline evidence in
PHASE_1_GENERIC_EVENT_RELEASE_V6_ACCEPTANCE.md. No code changes or new native
inspection are needed or claimed. Root reviewed the unchanged fixed policy and
fresh-install preconditions and verified frozen client/predecessor source closure.

## Candidate and live entry

Public event documentation lists Grab Potions first (three Foul Potions), then
Ransack (one random Uncommon potion):
https://slaythespire.wiki.gg/wiki/Slay_the_Spire_2%3APotion_Courier
https://sts.gg/v2/events/PotionCourier
This is candidate evidence, not pinned native callback or reward-screen proof.
The user knowingly authorized an exploratory test despite that remaining gap.

After installation, manually launch the dedicated Profile3, single-player, and
prepare fresh Potion Courier initial choices with at least one empty potion slot.
Leave both choices untouched and close the console and every other popup.
Before dispatch, verify current UI shows exactly two options with Ransack second,
its single-potion outcome, and an empty belt slot. If this differs, do not invoke
the client or select a different branch. Require-running must also pass.

Exactly one frozen run_live.py invocation with this instance's fresh state hash.
The fixed policy selects choose:1 once, then first_legal for supported child and
later parent actions. The existing finite budgets and no-uncertain-retry rule apply.
Do not adopt an already-open reward screen or manually complete an uncertain child.
Success requires completed_item_children=1 and explicit Proceed/map handoff;
a resolved zero-child outcome is not item-handler success. Record the bounded
summary and UI corroboration without raw observations or credential disclosure.

Normal UI quit, stopped/closed checks, code-first quarantine with the fresh
installed hash, purge with the newly returned quarantine hash, then clean-base
and final stopped/closed checks close this instance. No automatic launch, profile
or save filesystem access, Cloud work, foreign-mod changes or force kill.
Repeated unmodded launch remains waived, not claimed as passed.

## Preparation evidence

Frozen source verification passed, including linked predecessor closure, without
credential access. Require-stopped passed with3 process/2 closed-port samples.
The first clean-base invocation rejected a relative manifest argument before
inspection; the corrected absolute-path invocation passed429 base files,
zero overlay, projection
d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0.

Fresh installation passed with mods_parent_created=true. Current installed-state
SHA256: `36db173d95bd97704415f33195b61af6d36d51cda5595e4376bbd1fe8d186d08`.
Post-install require-stopped passed3 process/2 closed-port samples. Exact overlay
verification passed2 files with the unchanged429-file base. Installed-state and
protected operator metadata validation passed without reading credential content.
No game launch or client invocation has occurred. Await manual setup and readiness.

Once current UI and require-running pass, invoke exactly once:

```sh
/Users/rowdeygoos/code/github/RowdeyGoos/StS_agent/.venv/bin/python -B \
  /Users/rowdeygoos/.codex/worktrees/23cf/StS_agent/bridge/Sts2AgentBridge/successors/generic_event_release_v6/client/run_live.py \
  --expected-state-sha256 36db173d95bd97704415f33195b61af6d36d51cda5595e4376bbd1fe8d186d08
```

This instance is installed; cleanup is required after the test or cancellation.

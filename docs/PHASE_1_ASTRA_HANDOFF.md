# Fresh Astra session handoff

Prepared 2026-09-05 at the user's request. The user will create the new session;
no new task, session or agent was created for this handoff.

## Later continuation status — 2026-09-05

Continue in the same 23cf checkout and integration branch. The historical
handoff below is preserved; current truth is in
[current status](PHASE_1_CURRENT_STATUS.md) and the
[missing-room acceptance ledger](research/PHASE_1_MISSING_ROOM_ACCEPTANCE.md).
All three shop/item/event proposals were recovered and reviewed. Static API
facts and a frozen one-action item contract are committed at `96969c0`; the
isolated item core/native adapter now pass independent review, ten synthetic
fixture groups and a compile-only reproducibility gate. Existing 1,112-test
regression and old 0.8.0 source identity pass. No new live route or package is
selected. The next dependency is reviewed item routing/wire/host/package
composition; shop control connections and event progression remain separate
gates. Do not repeat the stopped event choice or reclassify the old timeout.

The user renewed authority for bounded development and campaigns when needed,
and waived repeated unmodded launch checks; preserve the normal exact cleanup
requirements and report that check as waived. No campaign is active. No game
setup is needed for the next repository integration gate.

## Start from the integration checkout

- Repository: `StS_agent`.
- Existing checkout:
  `/Users/rowdeygoos/.codex/worktrees/23cf/StS_agent`.
- Branch: `codex/phase1-actor-ready-integration`.
- Pre-handoff documentation head:
  `6d48dfd07e81833fca76deeb032bc34ff1473678`.
  The commit adding this handoff follows that head without implementation edits.
- Accepted implementation head:
  `7a347853dcd4ada4b8f60a8c7f110546bce995a9`.
- Saved project checkout `/Users/rowdeygoos/code/github/RowdeyGoos/StS_agent`
  remains on local `main` at
  `cd3e3ebb97594067d3693dc30d725152dda4dcf9`. It does **not** contain the
  integrated increment. Do not start diagnosis against that older source.
- Verify branch, ancestry and working-tree status. Preserve user changes. Work
  in the existing integration checkout, or create an isolated local worktree
  from the current integration branch if the new session needs its own checkout.
  Do not reset, force-checkout the already checked-out branch, fetch, push,
  merge, prune worktrees or open a PR as part of this handoff.

Follow `AGENTS.md` and its reading order. The immediate current-truth documents
are [current status](PHASE_1_CURRENT_STATUS.md), the frozen
[actor-ready plan](PHASE_1_ACTOR_READY_EXECUTION_PLAN.md), its
[acceptance ledger](research/PHASE_1_ACTOR_READY_ACCEPTANCE.md), and the
[bridge guide](../bridge/Sts2AgentBridge/README.md). Earlier ledger sections are
historical stage records; the current-state header and final campaign closure
are authoritative for present status. No profile-filesystem work is needed.

## Distinguish the two problems

1. **Desktop integration:** native Steam-window inspection repeatedly returned
   ScreenCaptureKit `-3811` (audio/video capture failure), even after Steam
   restart and automation-session reset. Finder accessibility and an actual
   Finder screenshot worked. Game accessibility and screenshots also worked
   once the user launched the game manually. A fresh Astra session may retest
   Steam capture; there is no evidence that capture is broken system-wide.
2. **Live controller:** with working game capture, verified Profile 3 and the
   pinned bridge installed, one fresh-map controller invocation returned
   `{"schema_version":1,"status":"failed","code":"room_interaction_timeout"}`
   with exit 4. It produced **no accepted run summary**. A fresh model/session
   has not been shown to fix this separate controller/game interaction.

Do not infer exact action/floor counts, accepted map reconciliation, elite
combat, terminal outcome or room completion from the discarded intermediate
results or a cleanup screenshot. No raw response, transition dataset or
differential corpus exists for this run. The fixed timeout is live-observed;
the root cause and exact substeps are unclassified. The same timeout code has
historical room-controller residuals, but equality of codes does not prove the
same cause.

## What is already finished

- Bridge packets `22`-`25`: host-only elite continuation, independent actual-
  client fixtures and historical controls, strict capture-off acceptance
  wrapper, and independent whole-bridge review.
- Headless packets `04`-`07`: frozen public encoder, trusted actor dataset,
  masked candidate scorer, and deterministic CPU behavior-cloning smoke with
  provenance-bound report/checkpoint publication and loading.
- Independent reviews and focused/adjacent gates are recorded in the ledger.
  Final integrated suite: **1,108 passed in 105.86 seconds** at `7a34785`;
  compilation and diff checks passed. Subsequent commits only document results.
  No new full-suite run is claimed for handoff preparation.
- The headless smoke proves structural training plumbing only, not policy
  strength or target-game parity. Its accepted schema/model fingerprints and
  all component evidence remain frozen.
- Packet `26` was executed once. Its live acceptance gate **did not pass**;
  all campaign cleanup gates **did pass**. Do not redispatch completed worker
  packets or restart the whole increment merely to restore context.

## Current operational state

The resumed campaign ran from **09:30:19 to 09:46:42 UTC on 2026-09-05**,
including cleanup: **16 minutes 23 seconds**, within its 30-minute limit.
Normal Save and Quit, normal application quit, exact quarantine, one clean
unmodded launch/quit with the bridge port closed, and exact purge all passed.
Purge removed **four generated files**, including the transient credential.
Old install/quarantine state hashes in the ledger refer to this purged campaign;
do not reuse them for a new installation.

Read-only handoff checks completed at **10:14:48 UTC**:

- no game process and no accepting bridge port, using three process and two
  port samples;
- **zero overlay**, unchanged **429-file** base projection SHA-256
  `d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`;
- pinned two-entry bridge package still available and verified.

No live campaign is active and no cleanup is pending. These are timestamped
checks, not a guarantee of later user activity. Steam was left open. Ordinary
game/Steam profile and Cloud effects were not certified absent; no coordinator
profile/save filesystem read, edit, copy, parse or restore occurred, and no
Cloud setting was changed.

## Desktop and launch details

Use only the supported computer-use APIs for UI interaction. Discover current
applications and obtain fresh bindings; variables from the old session do not
carry over. Steam has duplicate launcher/client bundle IDs. The tool resolved
the running client to:

`/Users/rowdeygoos/Library/Application Support/Steam/Steam.AppBundle/Steam`

The launcher is `/Applications/Steam.app`; the shared ID is
`com.valvesoftware.steam`. The game's ID is `com.megacrit.SlayTheSpire2`.
If only testing capture, inspect whether the game is already running first:
`getApp` may automatically launch an application, so do not accidentally turn
a read-only check into a game launch.

The verified Steam launch URI is `steam://rungameid/2868840`. The browser tool
explicitly rejected it under its URL security policy and prohibited equivalent
workarounds. Do not route the blocked launch through another browser, raw browser
commands, shell execution or another indirect mechanism. The user successfully
performed the Steam launches manually. Ask for that manual action when a new
launch is authorized and needed, then verify the game window. A new session
does not erase the recorded browser-policy restriction.

Godot exposed only a minimal accessibility tree. Screenshots and fresh
coordinates were needed for game controls. Always inspect Quit confirmation and
confirm process shutdown before quarantine; do not confuse the dialog with a
completed quit. No controller/gameplay retry is authorized by a UI lookup error.

## Bounded next work and authorization

The user currently requested handoff preparation and a fresh session to test
whether it resolves the problem. This file itself grants no new live campaign.
Start with a fresh read-only capture check and independent repository diagnosis.
Do not assume that increasing a timeout fixes the underlying completion or
identity condition. Do not replay the previous uncertain action, resume its
run to manufacture acceptance, recover its discarded data, or silently expand
the bridge/observation contracts.

The opening task's **one bounded game run has been exercised**. A subsequent
live attempt needs fresh explicit bounded authority. Once provided, retain the
same plan's Profile 3-only boundary, 30-minute total including cleanup, maximum
three controller-selected destinations, capture off, exact stop conditions,
supported overlay manager and final cleanup. Do not alter Steam Cloud or wait
for an idle marker; stop mutation if unexpected enabled/syncing state is
observed. Direct profile/save/seed access, retained raw or sanitized transition
capture, and game/rule/C#/wire expansion remain excluded. Obtain a concrete
separate scope before a repair needs those changes.

For source diagnosis, begin at the timeout branch in
`bridge/Sts2AgentBridge/tools/apply_room_live.py` (`_run_apply_room`) and its
existing fixtures, then the room handoff in `apply_run_live.py`, the independent
run/entry/elite wire fixtures, and `verify_room_acceptance.py`. Review current
code and fixtures before claiming a root cause or proposing a fix. The passing
acceptance wrapper changes neither the discarded producer output nor the
production timeout semantics.

## Exact runtime and artifact references

- Python tests:
  `/Users/rowdeygoos/code/github/RowdeyGoos/StS_agent/.venv/bin/python`, with
  `PYTHONPATH=.` from the chosen integration checkout. Verify module origins;
  an editable installation must not silently test the older main checkout.
- Standalone bridge tools: `/usr/bin/python3 -B -E -s -S`.
- Pinned target: Steam build **23811903**, **v0.107.1**, macOS arm64.
- Repository manifest:
  `manifests/game-builds/sts2-steam-main-build-23811903-macos-universal.json`.
- Bridge **0.8.0**, protocol **live_probe_v0**, unchanged C# artifact.
- Current verified artifact root:
  `/private/tmp/sts-room-registry-repro-out.6XEHPp`.
  It is also the manager's fixed artifact root; check the source and bridge
  guide rather than substituting an arbitrary directory. Temporary artifacts
  may disappear later; rebuild/verify through the supported instructions if so.
- DLL SHA-256:
  `a586aa99b9deeeb04b22596340dcccd0c6894b59db27625dfa1a1a8c2508c285`.
- Loader manifest SHA-256:
  `498e815fc742e85112e43823b3b2e291e60efe03353a22e263d316e6fb67b971`.
- Package SHA-256:
  `c97f3a0cd094523c769065fc921c3758569575c8dd5e754c5d2597ab7ee5a595`.
- Operational tools: `check_live_runtime.py`, `verify_clean_install.py`,
  `verify_package.py`, `verify_operator_config.py`, `manage_live_campaign.py`.
  Read each current CLI before use. Do not use the historical hardcoded
  `verify_live_campaign_inputs.py` as a gate for this successor campaign.

The prior one-shot controller used exactly:

```text
apply_run_acceptance_live.py
  --user-profile /Users/rowdeygoos --effective-uid 501
  --combat-provider first-legal --reward-provider first-card
  --map-provider elite --room-provider safe
  --floor-limit 3 --entry-phase map
```

This is the historical invocation, not an instruction to execute it again.
Keep new findings in the actor-ready ledger and update current status/roadmap
when the next accepted disposition changes. Do not rewrite predecessor ledgers.

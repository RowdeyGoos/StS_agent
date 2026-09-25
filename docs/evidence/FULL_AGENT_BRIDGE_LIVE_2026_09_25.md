# Full-agent bridge live coverage, 2026-09-25

This controlled Profile 3 batch exercised the shared `agent_v2` interface on
the pinned macOS game 0.107.1 / Steam build 23811903. The user launched manually;
native Continue resumed the existing assisted Ironclad test run. This is bounded
interaction evidence, not an uninterrupted campaign or a policy-strength result.

## Tested artifact

- Source: `6c043278311dac931903e4dc110f43e8264bac2f`; feature `cc9fa81`.
- Manifest SHA-256: `32d721e8f6f680d6fc0eeccfe90eeb5926dcbe17ac605cab43b89b36561ec314`.
- DLL SHA-256: `470e6b75f5d57ceefa706c86ca62e5ad264de203f8b3300a3f183c6ffcac3fc8`.
- Release evidence: `/private/tmp/sts-bridge-d2n3wh6m`.
- Installed state SHA-256: `bb10686579d284b506e80cfd7191e1f7545eb8c0211aa1d8b97d78343161cd6f`.

Health, pinned-build compatibility and current process checks passed. An initial
client invocation used a relative manifest path and failed local preflight before
any gameplay action; the absolute-path invocation passed. All gameplay actions
below used the existing authenticated client, shared adapter and advertised
public candidates. Short test policies selected the intended alternatives.

Native console setup was performed only between settled cases: add Driftwood,
Fruit Juice, Gambler's Brew and two separate Skill Potions; later remove Driftwood
and add Pael's Wing. The existing assisted deck and HP were otherwise retained.
Only ordinary UI Save and Quit was used; no profile/save/history/Cloud content
was inspected, and public trajectory recording stayed disabled.

## Outcomes

Counts are cumulative attempted / accepted / reconciled within this bridge
process. Reads belong to the named controller segment; treasure and second-combat
reads exclude their separate initial map-entry observation.

| Case | Result | Counts | Reads |
| --- | --- | --- | --- |
| Rest → Dream Catcher reward → Reroll → choose card → Leave | Passed; actionable map, HP 45/83 → 69/83, deck 6 → 7, gold 399 unchanged | 5 / 5 / 5 | 30 |
| General potion discard at map | Passed; Regen Potion's exact slot became empty | 6 / 6 / 6 | 2 |
| Fruit Juice at map | Passed; HP 69/83 → 74/88, potion consumed | 7 / 7 / 7 | 2 |
| Connected treasure → Open → Claim → Leave | Passed; relic obtained, actionable map, gold 399 → 449 | 11 / 11 / 11 | 54 |
| Connected combat → Gambler's Brew → select one hand card → confirm | Passed; discard/redraw completed and combat became actionable | 15 / 15 / 15 | 53 |
| Skill Potion → select an offered card | Passed; Expect a Fight appeared in hand | 17 / 17 / 17 | 18 |
| Second Skill Potion → zero-selection confirmation | Passed; optional offer skipped, combat actionable | 19 / 19 / 19 | 16 |
| Finish combat → gold/potion → first Sacrifice → Leave | Passed; Pael's Wing counter 1, actionable map | 28 / 28 / 28 | 27 |
| Next connected combat → rewards → second Sacrifice | Failed `read_native_failed`; Whetstone visibly granted, card menu closed, one action remained pending | 36 / 36 / 35 | 107 |

Successful segments ended with no pending action. The final failed action was
not retried or adopted as reconciled. The UI showed HP 86/88, gold 485, deck 7,
Pael's Wing's displayed counter 0 and Whetstone; a Flex Potion reward remained.
The displayed counter is modulo two and is not evidence of an incorrect reset.

## Correction and its evidence boundary

The automatic-effect observer hooked the small single-card `CardCmd.Upgrade`
forwarder. Native Whetstone calls it, while the underlying mutation occurs in
`CardModel.UpgradeInternal`. Runtime inlining can bypass the former hook. The
old fixture suppressed inlining and omitted Whetstone's pickup behavior.

A native-shaped enumerable-command/model-upgrade regression failed against the
old observer with `reward_alternative_boundary`
(`/private/tmp/sts-bridge-9xof8ceh`). The correction observes the actual model
mutation, retaining exact ownership, scope, eligibility, +1 level and unchanged
survivor checks without enumerating a random target sequence. Cases cover zero,
one and two eligible originals, unscoped upgrades and sticky cleanup failure.
Alternatives, shop effects and shared event reward tests passed in 7.598 seconds
(`/private/tmp/sts-bridge-r_ry81oh`). Independent semantic review found no blocker
(14:13:45–14:14:26 UTC, 41 seconds), following an 86-second source investigation.
The original live failing predicate was not captured at this finer boundary;
inlining remains a source-supported explanation rather than a captured JIT trace.
The corrected saved-run retest below now demonstrates successful reconciliation.

## Cleanup and timing

Normal Save and Quit and game Quit were followed by verified stopped process and
closed listener. The exact owned files were quarantined and purged: four generated
files removed, zero overlays, all 429 base files unchanged. Base SHA-256 remained
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
Quarantine state was
`bf83d500d73bd79d5691340cdeeb956b1cbf97ffa48802bdf25d69d5466baa2d`.

Work resumed at 13:50:24 UTC; cleanup was verified by 14:09:44 UTC. This interval
includes setup, tests and initial diagnosis; exclusive execution and user-wait
times were not measured. Clean installation removal does not change the failed
gameplay reconciliation. Subsequent packages must retain this result under its
original artifact identity.

## Corrected Whetstone retest

The user manually reopened Profile 3. Native Continue restored the reward checkpoint
before the prior unresolved action: HP 86/88, gold 466, deck 7, Pael's Wing counter 1,
and no Whetstone. A read-only preflight established a new bridge session with
0/0/0 actions and no pending action. An initial automatic approval rejection
prevented execution because the preceding session had an uncertain mutation; the
fresh checkpoint and strict one-use preconditions established that the corrected
test would not duplicate that mutation. The subsequently approved invocation ran
once, without receipt retry or adoption.

- Source: `887c1da81cf36a0d524973e93dd8e20832595244`.
- Manifest SHA-256: `1f83ded88af136170f2c1191bf28371aa435c9ab1616c011357fa64140e6f7e6`.
- DLL SHA-256: `e796ec18a1244355734d431d62996357a29a930ba31839f411dd26614bdc929b`.
- Evidence root: `/private/tmp/sts-bridge-gbhdyd9q`; 85 release groups passed in 313.965 seconds.
- Installed state SHA-256: `446c391ed56282d22d1facc1886c4a6a93cbc92be965f3cb7b1b40f729392c6a`.

The exact sequence `claim_gold → open_reward → sacrifice_card_reward → leave_rewards`
passed: **4 attempted / 4 accepted / 4 reconciled**, five reads, zero stale rejections,
no pending action. The shared host stopped at the actionable map with
`truncated/external_stop`. Whetstone was present, Pael's Wing displayed 0, gold
was 485, HP remained 86/88, and the deck remained seven cards. No console setup
was needed for this retest and no public trajectory corpus was retained.

Normal Save and Quit, game Quit, stopped-process/closed-listener verification and
exact owned quarantine/purge completed by **14:34:33 UTC**. Four generated files
were removed, all 429 base files remained unchanged, and no overlays remained.
Quarantine state SHA-256 was
`32c7a1d2185f35d3fad6a7d6f0f795d9522e43431a6d5003a2539c87ebd50fc2`;
the base SHA-256 remained `d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
Live execution and user-wait durations were not measured separately. This is one
representative relic-granting Sacrifice, not all relic callbacks or a full campaign.

## Shop-removal preview cancellation

The same corrected package was reinstalled and the user manually launched Profile 3.
This is a separate process from the Whetstone retest, with its own action counts.
The release manifest remained `1f83ded88af136170f2c1191bf28371aa435c9ab1616c011357fa64140e6f7e6`;
installed state was `a5f0267b7f89d502220c4c98e86c7192d72dedf3c120795b370fc75d4eb3aa1d`.
Installation verification at 14:44:36 UTC found two exact owned overlays and all
429 base files unchanged.

Native Continue restored HP 86/88, gold 466 and the seven-card deck. The native
console command `room shop` established the test room before the first full-agent
observation. An initial mistyped `oom shop` was explicitly rejected by the game
without mutation; the correctly typed command then succeeded. No cards, gold or
HP were granted for this case.

The sequence `open_shop → choose_shop_removal → cancel_selection → close_shop → leave_shop`
passed: **5 attempted / 5 accepted / 5 reconciled**, seven reads, zero stale
rejections and no pending action. The exact public deck identities/definitions and
gold remained unchanged throughout cancellation. The host stopped at an actionable
map with `truncated/external_stop`; HP remained 86/88, gold 466 and deck count seven.
This establishes cancellation of the preselected removal preview, not arbitrary
interactive multi-selection. No live trajectory corpus was retained.

Normal Save and Quit, game Quit, stopped-process/closed-listener verification and
exact owned quarantine/purge completed by **14:54:07 UTC**. Four generated files
were removed, no overlays remained, and all 429 base files remained unchanged at
SHA-256 `d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
Quarantine state was `75cc3f0fac1937b700aacf07612dbb7a474d28ebdf601f2fbe433b2bac1cec92`.
Execution and user-wait durations were not measured separately. The planned Lost
Coffer check was deferred to a fresh bridge process because this process retained
its reconciled shop-to-map owner; no unrelated event was attached to that owner.

## Lost Coffer setup-only stop

The next manual-launch Profile 3 process used the same corrected manifest and
installed state `3098285400f093f2eeb9ca415c34bbe2a51d64cd41cfee21095eb1a454ca3a44`.
Native Continue restored the combat reward checkpoint. Direct
`ancient NEOW LOST_COFFER` entry left the old reward overlay present. A subsequent
`room shop` cleared that overlay, then another `ancient NEOW LOST_COFFER` created
the intended visible choice. Neither ancient option was selected. One setup UI
Power Potion discard click produced no observed inventory change and was not
repeated. Neow entry healed HP 86/88 to 88/88; gold remained 466 and the deck seven.

The full-agent host stopped with `read_native_failed` after 34 reads, **0 attempted /
0 accepted / 0 reconciled**, no decision and no pending action. The reward behavior
was not exercised. No policy mutation was dispatched or retried.

Pinned source identifies a setup mismatch: `NMerchantRoom._Ready` enables map
travel; `AncientConsoleCmd` enters a new event without clearing that flag, and the
ancient reader rejects enabled travel. This is a source-supported explanation;
the exact rejected predicate was not emitted. The next setup uses `room event`
to clear the restored overlay before creating Lost Coffer, in a new bridge process.
No production guard or package was changed to accommodate the invalid setup.

Normal Save and Quit/game Quit, stopped-process/closed-listener verification and
exact owned quarantine/purge completed by **15:13:49 UTC**. Four generated files
were removed, zero overlays remained, and all 429 base files were unchanged at
SHA-256 `d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
Quarantine state was `0b55bbb050c9ca21f8b24903697573c55aa000ed8936849f87b52ddc42931ef0`.
Work resumed at 15:07:23 UTC; setup, diagnosis, execution and cleanup overlapped,
and their separate durations were not measured. No user-data files or retained
public trajectory corpus were accessed.

## Lost Coffer event-room setup: same read stop

The next fresh Profile 3 process used the same manifest and installed state
`ca10969454347174e890d6e2eda7ccfdab0d4d59734724ca00ec09195664f3d2`.
Native Continue restored the checkpoint; `room event` cleared the old reward
overlay, then `ancient NEOW LOST_COFFER` displayed the intended option. No shop or
potion setup action occurred. Neow healed HP 86/88 to 88/88; gold stayed 466 and the
deck seven. No event choice or dialogue action was dispatched by the host.

The result was again `read_native_failed`, **0/0/0**, 34 reads, no decision and no
pending action. This shows the preceding shop-travel explanation is insufficient;
the exact live rejection remains unknown. Inspection found that the shared
`FullAgentWire.Read` boundary discards the terminal event reply's existing bounded
diagnostic. A separate correction will retain that reason without relaxing the
native guard. Neither attempt establishes Lost Coffer reward acceptance.

Normal Save and Quit/game Quit and verified exact cleanup finished by
**15:23:45 UTC**: stopped process/listener, four generated files removed, zero
overlays and all 429 base files unchanged at
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
Quarantine state was `1104f79a06f360e593c5d95a6954037d9fff003432f7c24c101bcab52c9409b5`.
Work resumed at 15:18:32 UTC; separate setup, execution and cleanup durations were
not measured. No profile/save/history/Cloud filesystem content was accessed, and
no public trajectory corpus was retained.

## Lost Coffer: retained travel flag identified

The diagnostic release `7b6bb85e09e5c10b07ccc2c6b016bea99c8c0a6fd3183a27e77f1fc6755106db`,
source `af80a77`, was manually launched on Profile 3. Installed state was
`3f601ed4551213f5453ca954379c370d7d8ae68ddac80cfd606ff2d728d7b642`.
Health and release identity passed. Native Continue restored the checkpoint;
`room event` cleared the reward overlay and `ancient NEOW LOST_COFFER` displayed
the intended option. No option was chosen. Neow entry healed HP 86/88 to 88/88;
gold stayed 466 and the deck seven.

The full producer stopped with **`read_native_event_parent_travel`**, **0 attempted /
0 accepted / 0 reconciled**, 34 reads, no decision and no pending action. This
directly identifies the existing guard observing enabled map travel. Debug event
entry retains that flag too; shop entry was not necessary. Neither event dialogue
nor relic/reward input ran. The diagnostic works live, while Lost Coffer reward
acceptance through the full producer remains open. No mutation was retried.

Normal Save and Quit/game Quit, stopped-process/closed-listener verification and
exact cleanup finished by **15:49:13 UTC**. Four generated files were removed,
zero overlays remained and all 429 base files were unchanged at SHA-256
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
Quarantine state was `172044dfa0335652903ca4ba505c110d56d8ba6e54df0b6b3bc066509c62353e`.
Live preflight was observed at 15:46:02 UTC; separate execution and cleanup
durations were not measured. No profile/save/history/Cloud filesystem content or
public live trajectory corpus was accessed.

The unchanged package was reinstalled and verified by **15:49:47 UTC**, with two
exact overlays and unchanged base files. Installed state is
`f8a6c2c5b9ff0bee71c4ee7b5a9b40c9e5ea37f5bec99fa14d366ee88f27739a`.
The corrected setup will use native `act 1` inside the saved campaign, then force
Lost Coffer before attaching the full agent. Pinned `ActConsoleCmd` invokes
`RunManager.EnterAct`, which clears screens and invokes `SetActInternal`; that
regenerates the act map and calls `SetTravelEnabled(false)`. No production guard
or package change is needed for that setup. This preparation is not yet live evidence.

## Lost Coffer: native admission passed; full projection stopped

The same `7b6bb85e…` release, source `af80a77`, was manually launched on Profile 3
under installed state `f8a6c2c5b9ff0bee71c4ee7b5a9b40c9e5ea37f5bec99fa14d366ee88f27739a`.
Health passed at **15:52:25 UTC**. Continue restored the combat reward checkpoint.
Native `act 1` rebuilt the act map inside the saved campaign and entered Neow;
`ancient NEOW LOST_COFFER` then displayed Lost Coffer, Neow's Torment and Cursed
Pearl. HP settled at 88/88, gold 466 and deck seven. The console was closed before
attaching the full producer. A native save notification was visible after act reset;
the next Continue must be inspected instead of assuming the previous checkpoint.

The test stopped with **`read_context_failed`**, **0 attempted / 0 accepted /
0 reconciled**, 34 reads, no decision and no pending action. Native event admission
now passed the travel guard. The remaining category covers run initialization and
event projection; it does not identify a particular formatting or binding failure.
No dialogue, relic or reward action ran, and no mutation was retried. Lost Coffer
reward acceptance remains open.

Normal Save and Quit/game Quit and exact owned cleanup finished by **15:56:14 UTC**.
The game process and listener were stopped, four generated files removed, zero
overlays remained and all 429 base files were unchanged at SHA-256
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
Quarantine state was `9ecc39d58f34b839df352f858c11ea0f67b34dbefa5bb303cdb2140b3fa6b695`.
Separate execution and cleanup durations were not measured. No profile/save/history/
Cloud filesystem content was accessed and no public trajectory corpus was retained.

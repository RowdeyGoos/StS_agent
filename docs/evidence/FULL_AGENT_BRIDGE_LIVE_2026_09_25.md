# Full-agent bridge live coverage, 2026-09-25–26

This controlled Profile 3 batch exercised the shared `agent_v2` interface on
the pinned macOS game 0.107.1 / Steam build 23811903. The user launched manually;
native Continue resumed the existing assisted Ironclad test run. This is bounded
interaction evidence, not an uninterrupted campaign or a policy-strength result.
Follow-up cases below retain their own dates, package and installation identities.

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

## Lost Coffer: relic accepted; full-reward classification stopped

Manifest `bc0767b1035808cf89020126cc727191526bf208d88d81e8c32b9b1f03b8a662`,
source `d9eda0d499ec1c6807abb8b3a7fadb575239cb4c`, was manually launched on Profile 3
under installed state `78efff693b3b5cbd42aa7cf48f07d055467cd317643680030624dbf683f05c04`.
Work resumed at **16:21:44 UTC**. Health passed. Continue restored Neow with HP
88/88, gold 466, deck seven and three potions; no new act reset was needed.
Native `ancient NEOW LOST_COFFER` visibly forced the intended relic option. The
console was closed before attaching the full producer.

The corrected description projection passed. The exact public `choose_ancient_relic`
action was accepted; Lost Coffer appeared in the relic bar and native Loot showed
Flex Potion and Add a card. The next read stopped with **`read_native_failed`**:
**1 attempted / 1 accepted / 0 reconciled**, one decision, 35 reads, zero stale
rejections and a pending parent action. No reward action ran and no uncertain
mutation was retried. This demonstrates parent projection and native relic input,
not reward completion or parent reconciliation.

Source inspection found that `GenericEventTerminalClassifier` omits the
`full_rewards` descriptor and its GET/POST payload branches. The wire service
already emits `full_rewards_v1`; the classifier rejects it before bounded event
diagnostics can be attached. Independent source review confirmed this integration
gap in **76 seconds**, from 16:25:42 to 16:26:58 UTC.

Normal Save and Quit/game Quit and exact owned cleanup finished by **16:26:04 UTC**.
The game process and listener were stopped, four generated files removed, zero
overlays remained and all 429 base files were unchanged at SHA-256
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
Quarantine state was `1757d938582b2bb979da4527d32dd6b0f6ce52ee0bd44694b059a3c7c8c8dba7`.
Separate execution and cleanup durations were not measured. No profile/save/history/
Cloud filesystem content was accessed and no public trajectory corpus was retained.

## Lost Coffer: full-producer reward completion passed

Manifest `2d9a256032206ea0117c6caef38fad54a7180a2b635f7821d2982660fcff9c23`,
source `b55c51d0ae8c22bc2f7654593f625aae05f5bf7b`, was manually launched on Profile 3
under installed state `2d1ba162ac4e9a7c3e8f73f4f4b0943cfb3ce97d003fbe8c94bee23a4135c157`.
Work resumed at **16:50:24 UTC**. Health passed and Continue restored Neow at HP
88/88, gold 466, deck seven and three potions. Native `ancient NEOW LOST_COFFER`
forced the visible option; no new act reset was needed. The console was closed
before the bounded full-producer test.

The run resolved at the map by **16:52:09 UTC**, with **6 attempted / 6 accepted /
6 reconciled**, six decisions, 42 reads, zero stale rejections and no pending
action. The exact semantic sequence was `choose_ancient_relic`, `discard_potion`,
`claim_potion`, `open_reward`, `choose_reward_card`, `leave_event`. The controlled
policy discarded the existing Power Potion to make room. Native effect and task
checks reconciled all six actions, including the event parent after its rewards.
The map was visibly open, Lost Coffer was in the relic bar, the deck had grown
seven to eight, and HP/gold remained 88/88 and 466. The final truncated
`external_stop` is the intentional stop at the map, not campaign victory.

### Subsequent shop setup did not exercise a purchase

After the settled map, native `room Shop` opened a shop in the same process. Its
visible stock lacked Cauldron/Orrery and offered Nunchaku at 222 gold. Inventory
was inspected and closed before a bounded full-producer purchase check. No
candidate was published and no shop action ran: **`time_limit`**, zero decisions,
900 reads and no pending action. Cumulative counters stayed **6/6/6** from Lost
Coffer, so the shop delta is **0/0/0**. Source inspection showed the existing
`FullNativeBackend` still tracked its map family after the external debug room
switch. This is a setup limitation and does not establish purchase acceptance or
a failure in the purchase executor. No mutation was retried.

Normal Save and Quit/game Quit, stopped-process/closed-listener verification and
exact owned cleanup finished by **16:58:22 UTC**. Four generated files were removed,
zero overlays remained and all 429 base files were unchanged at SHA-256
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
Quarantine state was `8029c09b85a11f51009dd986f280ec1211e40b3623b02c5a2e067204e2acc858`.
Separate execution and cleanup durations were not measured. No profile/save/history/
Cloud filesystem content was accessed and no public trajectory corpus was retained.

## Neow's Bones: compound rewards passed

Manifest `18169693a3ea87ca93c5513024e3e7dab9f62d2e1a0f2cc8a9fccf63c5394660`,
source `7bd3e09de0e262b3cb75c8854bb0456ad2fbb011`, was manually launched on Profile 3
under installed state `920640b5ab3231f5925feb91a5dd7b967dd5e0a395d412c7ef30d90efa273163`.
DLL SHA-256 was `03060d01d2086d10bf38a87fac2145b288e90de169a120db05af370be573bd64`
(1,792,512 bytes). Release checks and independent semantic review are recorded in
the current validation record; the release gate passed 85 groups in 361.201 seconds.

Work resumed at **20:40:20 UTC**. Runtime, authenticated health and release
compatibility checks passed. Native Continue restored the saved Neow checkpoint:
HP 88/88, gold 466, eight cards and a full three-potion belt. Lost Coffer and
Pael’s Wing were already owned; Neow’s Bones was not. Native
`ancient NEOW NEOWS_BONES` forced the visible option once before the full producer
attached. No act reset, fresh campaign or additional HP/card/potion assistance was
used for this case. The console was closed before policy execution.

The bounded shared-policy test resolved with **7 attempted / 7 accepted /
7 reconciled**, seven decisions, **53 controller reads**, zero stale rejections
and no pending action. The action sequence was `choose_ancient_relic`, `claim_relic`,
`claim_relic`, `open_reward`, `sacrifice_card_reward`, `leave_rewards`, `leave_event`.
The policy selected Neow’s Bones and the visible nested Sacrifice, otherwise using
the shared chooser. Native effects, pickup tasks, ordered child receipts and the
enclosing event all reconciled. `truncated/external_stop` was the intentional stop
at an actionable map; no next node was selected and no mutation was retried.

Neow’s Bones generated **Large Capsule and a second Lost Coffer**. Large Capsule
obtained **Toxic Egg and Whetstone**, then added **Strike and Defend+**; the newly
obtained Egg upgraded the basic Defend during its native addition. Lost Coffer
opened a card reward; nested **Sacrifice granted Regal Pillow**. The full potion
belt caused the remaining potion reward to be left unclaimed. No potion was used,
discarded or collected. The final **Decay** curse was added after the root rewards.
Deck size grew eight to eleven, relic count fifteen to twenty-one, and HP/gold
remained 88/88 and 466. Pael’s Wing’s visible counter changed one to zero.

One post-run observation and a later independent read-only inventory observation
confirmed 7/7/7, an actionable map and no pending action; these two reads are
separate from the 53 controller reads. Final public inventory and native UI checks
were complete by **20:45:00 UTC**. The public relic list confirmed both Lost Coffer
instances and all six appended relics; a helper’s name-set difference omitted the
duplicate and was not used as the full append list. Native deck inspection showed
Strike, Defend+ and Decay. Whetstone’s native upgrade checks passed; the final deck
display alone is not used to attribute every upgraded attack to this pickup.

This establishes one controlled compound chain, including nested automatic
pickups, add-time Egg behavior, nested Sacrifice, final curse and map handoff.
Other Neow relic outcomes, deck selectors, offers/bundles, potion procurement,
natural Ancient entry and full-campaign acceptance remain separate evidence limits.
No public live trajectory corpus was retained and no profile/save/history/Cloud
filesystem content was accessed.

Normal Save and Quit returned to the Profile 3 main menu with Continue available;
game Quit then stopped the process and listener. Exact owned quarantine/purge and
unchanged-base verification finished by **20:49:48 UTC**. Quarantine state was
`c8b9d217f8b6307a7937eaa67255c3e558fef65f6ee33fde732e065241cd7ebf`.
Four generated files were removed, zero overlays remained and all 429 base files
were unchanged at SHA-256
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
Separate setup, execution, cleanup and user-wait durations were not measured.

## Red Mask: shop purchase stopped before acceptance

The unchanged `18169693a3ea87ca93c5513024e3e7dab9f62d2e1a0f2cc8a9fccf63c5394660`
release, source `7bd3e09de0e262b3cb75c8854bb0456ad2fbb011`, was reinstalled under
state `c659a490f51a7767b6ace155679b91ef4ace9e85ec51b5e3f75979ed87270e84`.
Installation verification passed by **21:06:46 UTC**: two exact owned overlays
and all 429 base files unchanged. One read-only verification invocation used a
wrong package filename and stopped before checking; the corrected versioned
filename passed. The user manually launched Profile 3. Runtime, health and pinned
build/release compatibility checks passed.

Continue restored the completed Neow checkpoint at HP 88/88, gold 466, eleven
cards and three potions. Native `room shop` created a merchant before the first
full-producer read; the inventory was opened through the UI. No additional HP,
gold, cards or potions were granted. One public preflight read confirmed legal
Red Mask stock at 172 gold, with zero action counts and no pending action. Cauldron
and Orrery were absent from the visible stock. The bounded policy was prepared to
buy Red Mask once, verify its exact insertion and gold debit, close the inventory
and leave to the map.

The first `buy_shop_item` returned **`uncertain_dispatch`**, **1 attempted /
0 accepted / 0 reconciled**, one controller read, zero completed decisions and
zero stale rejections; the host reported pending work. The separate preflight
read is excluded from that read count. Native UI still showed 466 gold, Red Mask
for sale, HP 88/88 and eleven cards. This is an observation, not a successful
reconciliation or permission to retry. No further policy action ran.

Source inspection found that Red Mask inherits `RelicModel.AfterObtained` and
the shop observer tries to patch a method reflected through the derived type.
An added inherited-passive fixture reproduced Harmony's declared-method
`ArgumentException` before the inner purchase input at
`/private/tmp/sts-bridge-ldp5vk1s/log-003.txt`. The preceding fixture used the base
relic class directly and missed this boundary. This is a reproduced code defect
consistent with the live stop; the live exception itself was not retained. The
correction resolves the declaring method before checking hook ownership, patching
and retaining the cleanup target. Its new artifact and retest are separate evidence.

The focused correction check passed five groups in **8.34 seconds** under
`/private/tmp/sts-bridge-c8_on36z`, including the shop effect and shop core suites.
Cases cover inherited synchronous/delayed callbacks, the full shop owner,
declared-hook cleanup and foreign-hook rejection before purchase input.
Independent semantic review found no remaining blocker in **319 seconds**,
21:14:31–21:19:50 UTC. These source/fixture results do not resolve the old live
attempt or establish acceptance of the corrected package.

Normal Save and Quit returned to the Profile 3 menu with Continue available, then
normal Quit stopped the process and listener. Exact cleanup passed by
**21:13:24 UTC**. Quarantine state was
`522671646878aa25cbc046dfe49be9174f47af2a97a2a8d3e677f9be44d8a3d1`.
Four generated files were removed, zero overlays remained and all 429 base files
were unchanged at SHA-256
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
No profile/save/history/Cloud filesystem content was accessed, no live trajectory
corpus was retained and no uncertain mutation was retried. Separate setup,
execution, diagnosis, cleanup and user-wait durations were not measured.

## Red Mask: corrected shop purchase passed

The corrected release is
`e47f0514d5d7b142d247425f3aad227e9bdbe662b491f33809b36ab7c9e8e383`, source
`c599a9f65f755378ad69945e08481d8af93664d5`. The final release gate passed **85 groups
in 362.357 seconds**, binding 485 source/test inputs across 52 projects. Its DLL
is 1,793,024 bytes, SHA-256
`59a89110df5da538603b02e6b1a73796971e139ab6733d5490203a911c0e6f1b`.
Evidence is under `/private/tmp/sts-bridge-5hudfwrd`; the prior exact release record
and install inputs remain there. The focused regression and independent review
are recorded with the preceding failure above; no new broad Python run is claimed.

Installation was verified by **21:28:08 UTC** under state
`17a45939f15e3e376cdb8c782f061989d316415ce62993b3ba153e69e0cc66e7`, with two exact
owned overlays and all 429 base files unchanged. The user manually opened Profile 3.
Runtime, health and pinned release/build compatibility checks passed. Continue
restored the completed Neow checkpoint, not the debug-created merchant. Native
`room shop` recreated the same merchant before attaching the full producer; the
inventory was opened using the UI and the console closed. No new HP, gold, cards
or potions were granted. One public preflight read confirmed Red Mask at 172 gold,
zero action counts and no pending work. Cauldron/Orrery were absent from stock.

The bounded policy completed `buy_shop_item`, `close_shop`, `leave_shop` with
**3 attempted / 3 accepted / 3 reconciled**, three decisions, **four controller
reads**, zero stale rejections and no pending action. Its `truncated/external_stop`
outcome is the intended stop at an actionable map; no next node was selected.
Gold changed **466 to 294**, the exact original relic prefix was retained and
one Red Mask appended (21 to 22 relics). HP stayed 88/88, the eleven-card deck
retained its original identities, and all three original potions were unchanged.

One separate final public observation verified the same inventory, counts 3/3/3,
no pending action and the actionable map. This read and the preflight read are
excluded from the four controller reads. Native UI showed 294 gold, the appended
Red Mask, eleven cards and the map. Final verification was complete by
**21:31:43 UTC**. No uncertain mutation was retried; this new artifact/process
result does not reconcile the preceding failed artifact's 1/0/0 action.

Normal Save and Quit returned to the Profile 3 main menu with Continue available,
then normal Quit stopped the game and listener. Exact owned quarantine/purge and
unchanged-base verification passed by **21:33:04 UTC**. Quarantine state was
`bff9343b084ffc92e4f3dc02a1477513a665d7bc0d193b71b3241763a4d82c1d`.
Four generated files were removed, zero overlays remained and all 429 base files
were unchanged at SHA-256
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.

This demonstrates one inherited passive-relic purchase through the full producer,
including exact payment, pickup, inventory close and map handoff. Capacity changes,
Cauldron/Orrery rewards, pickup selectors and other automatic-effect families
remain separate cases. No profile/save/history/Cloud filesystem content was
accessed and no live trajectory corpus was retained. Separate setup, execution,
cleanup and user-wait durations were not measured.

## Kifuda: three-card shop pickup passed, 2026-09-26

The unchanged release manifest is
`e47f0514d5d7b142d247425f3aad227e9bdbe662b491f33809b36ab7c9e8e383`, source
`c599a9f65f755378ad69945e08481d8af93664d5`. Its DLL is 1,793,024 bytes, SHA-256
`59a89110df5da538603b02e6b1a73796971e139ab6733d5490203a911c0e6f1b`.
All bound sources, retained gate identity and the three published package files'
lengths/hashes were verified before reuse. The accepted 85-group gate in
362.357 seconds remains under `/private/tmp/sts-bridge-5hudfwrd`; no new build,
implementation change or gate run was needed.

Installation passed by **08:41:16 UTC** under state
`87507d8631b0f3fd0ff6af78528bc5ad711085097d0e2b6c32b14dc9d3d593c5`, with two exact
owned overlays and all 429 base files unchanged. The user manually opened Profile 3
at the main menu. Runtime, health and pinned release/build checks passed. Continue
restored the completed Neow checkpoint: HP 88/88, gold 466, eleven cards, 21 relics
and three potions. Yesterday's debug-shop Red Mask purchase was not present in
this restored checkpoint; its accepted in-process result remains unchanged.

A bounded UI-only search generated **sixteen native merchants** using `room shop`,
opening each inventory before any full-producer observation or policy attachment.
Neither Cauldron nor Orrery appeared. The sixteenth merchant offered Kifuda at
212 gold, so the test selected that available pickup-selector path and stopped
the setup search. One truncated console entry was rejected as an unknown command
before a corrected setup input; it caused no room mutation. No further console
room changes occurred after attachment, and no new HP, gold, cards or potions were
granted. One public preflight read confirmed the exact supported Kifuda offer,
zero action counts and no pending work.

The bounded public-only policy completed:

1. `buy_shop_item` for the unique Kifuda offer.
2. Three `choose_relic_card` actions for three distinct original Bludgeons, all
   initially unupgraded and unenchanted; each next observation verified the
   selected identities.
3. `confirm_relic_selection`, then `close_shop` and `leave_shop`.

The result was **7 attempted / 7 accepted / 7 reconciled**, seven decisions,
**25 controller reads**, zero stale rejections and no pending action. Exact payment
changed gold **466 to 254**. One Kifuda was appended to the original relic prefix
(21 to 22 relics). The three selected original cards each received **Adroit 3**,
with definitions and upgrade levels retained. The other eight public card nodes
were unchanged; all eleven original deck identities remained. Comparison used
card identity rather than public deck order, which can change after enchantment.
HP stayed **88/88** and the three original potion slots/references/definitions
were unchanged.

One separate post-run public observation confirmed the same effects, counts 7/7/7,
no pending work and an actionable map. The preflight and verification reads are
excluded from the 25 controller reads. Native UI showed the map, 254 gold,
appended Kifuda, eleven cards and unchanged HP/potions. `truncated/external_stop`
is the intended map stop; no next node was selected. Verification was complete
by **08:56:48 UTC**. No action was retried or manually assisted during the policy.

Normal Save and Quit returned to the Profile 3 main menu with Continue available,
then normal Quit stopped the game and listener. Owned quarantine/purge and base
verification passed by **08:57:37 UTC**. Quarantine state was
`1cae3a061f063ce7da1c910de5d7a1a5884dec153a9913cb65e102f52022c891`.
Four generated files were removed, zero overlays remained and all 429 base files
were unchanged at SHA-256
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.

This demonstrates one three-card Kifuda purchase through the full producer,
including its owned selector, exact enchantments and map return. It does not
establish zero/fewer-card selection, deselection, the other four shop pickup
selectors, capacity changes, Cauldron/Orrery rewards or persistence across reload.
The missing target offers are setup limits, not failed bridge actions. No
profile/save/history/Cloud filesystem content was accessed and no live trajectory
corpus was retained. Separate setup, execution, cleanup and user-wait durations
were not measured.


## Mirror, Potion Belt and Cook batch passed, 2026-09-26

The user manually launched Profile 3 with the unchanged package: source
`c599a9f65f755378ad69945e08481d8af93664d5`, manifest
`e47f0514d5d7b142d247425f3aad227e9bdbe662b491f33809b36ab7c9e8e383`, DLL
`59a89110df5da538603b02e6b1a73796971e139ab6733d5490203a911c0e6f1b`.
Source bindings, the retained 85-group gate result and all three published package
files matched `/private/tmp/sts-bridge-5hudfwrd`; no new build or gate is claimed.
Installed state was
`ffcc57456b57b82157b4397c57d98d36f8ca2798b850809dde98d00cc9ccf131`.
Installation checks passed by **09:29:26 UTC**, with two exact overlays and all
429 base files unchanged. Runtime, authenticated health and compatibility passed.

Continue restored the completed Neow checkpoint: HP 88/88, gold 466, eleven cards,
21 relics and three occupied potion slots. The prior debug-shop Kifuda was absent.
Three native `room shop` setups, all before full-producer attachment, found Dolly’s
Mirror at 208 gold. No HP, gold, cards or potions were granted for this batch.
After attachment, all travel used advertised legal map/gameplay actions; no
external room changes or manual policy intervention occurred.

Counts below are attempted / accepted / reconciled. Controller reads exclude
separate public preflight, route-inspection and final verification reads.

| Segment | Actions in segment | Cumulative counts | Controller reads |
| --- | --- | --- | --- |
| Dolly’s Mirror purchase, select Bludgeon, confirm, Close, Leave | 5 / 5 / 5 | 5 / 5 / 5 | 7 |
| Legal combat → unknown event → shop route | 17 / 17 / 17 | 22 / 22 / 22 | 189 |
| Potion Belt, Blood Potion, Skill Potion, Close, Leave | 5 / 5 / 5 | 27 / 27 / 27 | 6 |
| Legal unknown event → unknown event → rest route | 11 / 11 / 11 | 38 / 38 / 38 | 121 |
| Cook, two choices, deselect/reselect Decay, confirm, Leave | 7 / 7 / 7 | 45 / 45 / 45 | 38 |

Dolly’s Mirror completed by **09:35:22 UTC**. Gold changed **466 → 258**, relics
21 → 22, and deck size 11 → 12. The new Bludgeon had a new identity and exactly
the original upgrade-0 card’s public fields/children. All original card nodes,
HP and original potion references/definitions were unchanged; the prior relic
prefix was retained with exactly one Mirror appended.

Legal nodes combat (1,2), unknown (2,3), shop (3,4) then reached another merchant
with gold 276 and thirteen cards. Potion Belt cost 170, expanding the full belt
**3 → 5**, retaining all original slot nodes and exposing exactly two empty added
slots. Blood Potion cost 49 and filled index 3; Skill Potion cost 51 and filled
index 4. Gold ended at **6**, all five slots were occupied, and the exact original
three slots/potions, HP and all thirteen card nodes were unchanged. Relics grew
22 → 23 with one Belt appended. Completion preceded the 09:40:55 UTC map read.

Legal unknown (4,4), unknown (5,3), rest (6,3) travel then reached Meat Cleaver’s
Cook option. The policy selected Decay and Defend+, deselected Decay, selected
that same original again and confirmed. Exactly those two cards were removed;
HP changed **88/88 → 97/97**, deck size **13 → 11**, and gold stayed 6. Every
surviving card node and all relic/potion nodes stayed unchanged. Final public
verification completed by **09:44:24 UTC**; the native UI independently showed
97/97 HP, six gold, eleven cards, Mirror, Belt and five occupied potion slots.

All three target cases had zero stale rejections and returned to an actionable
map with no pending action, using the intentional `truncated/external_stop` bound.
Each had one separate preflight and one final public verification read. Two
additional map-route reads are excluded from controller totals. The first route
inspection’s helper fell through to an unrelated branch and raised a local
`KeyError` after its successful read; it performed no mutation. Fixing that local
branch did not retry an action. The route controllers used ordinary combat,
rewards and event card selection; event identities/whole-event branches were not
recorded and are not newly certified by this batch.

Normal Save and Quit, game Quit, stopped-process/closed-listener verification and
exact owned quarantine/purge finished by **09:50:50 UTC**. Four generated files
were removed, no overlays remained and all 429 base files retained SHA-256
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
Quarantine state was
`73699f6f3ee9331c301dd22152e5eeb71b38d913c0fb1c8ad7b38840278df1ea`.
Separate setup, execution, cleanup and user-wait durations were not measured.
No profile/save/history/Cloud files or live trajectory corpus were accessed.

These results cover one Mirror clone, shop capacity expansion with both added
slots filled, and Cook success with deselection/reselection. They do not establish
other pickup selectors, capacity-first terminal/event/resume reward ordering,
all card variants or persistence across reload. Dig/Lift/Clone/Kindle/Hatch
successful effects remain separate live cases.


## Remaining rest options and Smith toggle passed, 2026-09-26

The unchanged release was installed and verified by **09:55:58 UTC**, with two
exact overlays and all 429 base files unchanged. Installed state was
`fe129e4dff9a5c059771be88800e667ccf8d7486cdf3c25d41c3a61424b8f1bb`.
Source remains `c599a9f65f755378ad69945e08481d8af93664d5`, manifest
`e47f0514d5d7b142d247425f3aad227e9bdbe662b491f33809b36ab7c9e8e383`, DLL
`59a89110df5da538603b02e6b1a73796971e139ab6733d5490203a911c0e6f1b`.
The retained 85-group release evidence remains `/private/tmp/sts-bridge-5hudfwrd`;
no new build or release gate was needed or run.

Following the user's manual launch, live work resumed at **10:18:18 UTC**. Current
runtime, exact installed state, authenticated health and pinned-build compatibility
passed. Continue restored the rest-entry checkpoint: HP 88/88, gold 6, thirteen
cards and five occupied potion slots, retaining Mirror/Belt and the earlier route's
inventory. The preceding Cook effect was not part of that restored checkpoint.
This does not change its recorded successful in-process result.

Before full-producer attachment, native setup added Miniature Tent, Girya, Pumpkin
Candle, Shovel and Pael's Growth. The native Pael's Growth selector enchanted one
upgrade-0 Bludgeon with Clone. One Byrdonis Egg was added to the deck. `room rest`
was explicitly rejected without mutation; the source-confirmed `room RestSite`
then established the new visit. HP, gold and potions were not granted or changed
for setup. The first full preflight verified 0/0/0, no pending action, exactly one
Clone-enchanted Bludgeon, one egg and all five intended options enabled.

The public-only test policy completed `lift → use_rest_relic (Kindle) →
use_rest_relic (Clone) → hatch → dig → leave_rest`: **6 attempted / 6 accepted /
6 reconciled**, six decisions, **80 controller reads**, zero stale rejections,
no pending action and an actionable map. One preflight and one final public read
are separate. Completion was verified before **10:22:14 UTC**.

| Option | Verified effect |
| --- | --- |
| Lift (native UI: Train) | Girya counter 0 → 1; other inventory unchanged |
| Kindle | Pumpkin Candle counter 5 → 10; other inventory unchanged |
| Clone | Deck 14 → 15; one new identity exactly matched the selected original upgrade-0 Clone-enchanted Bludgeon; all originals and other inventory unchanged |
| Hatch | The one original egg became a new upgrade-0 Byrd Swoop; one Byrdpip appended, deck size retained, exact other card nodes and HP/gold/potions unchanged |
| Dig | Bag of Preparation appended to the exact original relic identity prefix; HP, gold, deck and potions unchanged |

Miniature Tent left each subsequent option available after native completion and
cleanup. Final HP was 88/88, gold 6, deck fifteen and relic count thirty. The native
UI confirmed the map, counters 1/10 and new relics. This covers one egg and one
Clone original; it does not establish multiple-egg/Tent combinations, add-time
clone upgrades or every Dig callback.

One separate public map read identified legal combat (7,2) → rest (8,3). The
shared chooser traveled there without external changes: **12/12/12** additional
actions, **93 controller reads**, cumulative **18/18/18**, no pending action.
Actions were map entry, six card plays, gold claim, card-reward open/choose/leave,
and the next map entry. HP stayed 88/88; gold became 17 and deck size sixteen.
The encounter and selected reward were not separately classified as new content
coverage. Pumpkin Candle's visible counter became 9 after that combat.

Smith then completed `smith → choose_upgrade → deselect_card → choose_upgrade →
confirm_selection → leave_rest`. The same original Bludgeon was selected,
deselected and reselected; its upgrade changed **0 → 1**, with every other card
node unchanged. HP 88/88, gold 17, deck sixteen, thirty relics and all five potion
slots remained unchanged during Smith. This added **6/6/6**, six decisions and
**38 controller reads**, with zero stale rejections, no pending action and map
return. One preflight and one final public read are separate. Verification
completed by **10:25:42 UTC**; the UI confirmed the final map and inventory counts.
Both target controllers intentionally stopped with `truncated/external_stop`.

The process finished at **24 attempted / 24 accepted / 24 reconciled**, with
211 controller reads across the three segments and five additional public reads.
No policy action was retried or manually assisted after attachment. Normal Save
and Quit, game Quit, verified stopped process/closed listener and exact owned
quarantine/purge finished by **10:27:28 UTC**. Four generated files were removed,
zero overlays remained, and all 429 base files retained SHA-256
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
Quarantine state was
`c6a6ab35b9ca88e2dbd17d6a2fdf5285b316b3d7da99e0526a2a788aedc324c1`.
The live-work interval includes setup, execution, inspection and cleanup; separate
exclusive durations and user-wait time were not measured. No profile/save/history/
Cloud filesystem content was accessed and no live trajectory corpus was retained.


## Yummy Cookie four-card upgrade passed, 2026-09-26

The unchanged release was installed and checked by **10:39:22 UTC**, with two
exact overlays and all 429 base files unchanged. Installed state was
`fe8375964bf2a0f45ff65d37a8dc7c593a004c685cb7f3dd0be12111604310dc`.
Source remains `c599a9f65f755378ad69945e08481d8af93664d5`, manifest
`e47f0514d5d7b142d247425f3aad227e9bdbe662b491f33809b36ab7c9e8e383`, DLL
`59a89110df5da538603b02e6b1a73796971e139ab6733d5490203a911c0e6f1b`.
The retained 85-group gate remains `/private/tmp/sts-bridge-5hudfwrd`; no new
production build, source change or release-gate run was needed or claimed.

After the user's manual Profile 3 launch, work resumed at **10:57:42 UTC**.
Runtime, exact installed metadata, authenticated health and compatibility passed.
Continue restored the rest-entry checkpoint with HP 88/88, gold 17, sixteen
cards, thirty relics and five occupied potion slots. Before full-producer
attachment, native `act 1` rebuilt the map within the saved campaign, then
`ancient TEZCATARA YUMMY_COOKIE` prepared the source-confirmed offer. The UI
showed Yummy Cookie and its four-card upgrade text. No direct HP, gold, card,
relic or potion grant was used in this setup; normal Ancient entry returned HP
to 88/88 before the test baseline.

The initial helper preflight stopped after its first read while the bridge was
settling, with `cookie_requires_fresh_settled_tezcatara`; it had issued no action.
A bounded read-only inspection settled after 33 reads and verified the exact
Cookie option, **0/0/0** and no pending action. The helper's initial-read handling
was adjusted to wait at most fifteen seconds for a settled decision. No bridge
guard changed and no mutation was retried. The successful controller then used
one separate preflight read and one final public verification read.

The public-only policy completed `choose_ancient_relic → choose_event_card × 4
→ confirm_selection → leave_event`: **7 attempted / 7 accepted / 7 reconciled**,
seven decisions, **31 controller reads**, zero stale rejections and no pending
action. The selector exposed minimum/maximum four and manual confirmation;
each returned selected set matched the exact original references. The deck
remained unchanged before confirmation.

| Selected original | Upgrade before | Upgrade after |
| --- | --- | --- |
| Bludgeon | 0 | 1 |
| Headbutt | 0 | 1 |
| Body Slam | 0 | 1 |
| Fiend Fire | 0 | 1 |

All sixteen card identities were retained, and all twelve unselected card nodes
were unchanged. Exactly one Yummy Cookie was appended to the unchanged thirty
original relic nodes. HP **88/88**, gold **17**, deck size **16** and the exact
five-slot potion inventory stayed unchanged. Final public verification and the
native UI both showed an actionable map. The intentional bounded outcome was
`truncated/external_stop`, not campaign completion. Total public reads were 67:
31 controller reads and 36 startup/inspection/preflight/final reads.

Normal Save and Quit, game Quit, stopped-process/closed-listener checks and exact
owned quarantine/purge passed by **11:02:11 UTC**. Four generated files were
removed, zero overlays remained, and all 429 base files retained SHA-256
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
Quarantine state was
`949e5f9070edc06d487a1a4901d9e4c0e4501d17998fd042e24fe3712f36457e`.
The measured live-work interval was **269 seconds**, including setup, inspection,
test execution and cleanup. Separate phase durations and user-wait time were not
measured. No profile/save/history/Cloud filesystem content was accessed and no
live trajectory corpus was retained.

This establishes one fixed-four upgrade selection through `agent_v2/full_run_v2`,
including its exact effects and event/map handoff. Natural Ancient entry,
other upgrade counts, Trial's conditional curse/upgrade path, selection reversal
and persistence across reload are not established by this case.

## Punch Dagger single-preview failure, 2026-09-26

The same release was installed and checked by **11:07:33 UTC**: source
`c599a9f65f755378ad69945e08481d8af93664d5`, manifest
`e47f0514d5d7b142d247425f3aad227e9bdbe662b491f33809b36ab7c9e8e383`, DLL
`59a89110df5da538603b02e6b1a73796971e139ab6733d5490203a911c0e6f1b`.
Installed state was
`c15b9396c759ddfcd5d12c0357ff7d201031f6abb69f60f7108fcdd1eb050742`.
After the user's manual Profile 3 launch, live work resumed at **11:39:45 UTC**.
Runtime, metadata, authenticated health and compatibility passed. Continue
restored the saved campaign. Before full-producer attachment, native `act 1`
rebuilt the map and `gold 1000` changed gold 17 → 1017. The second of two native
`room shop` setups offered Punch Dagger for 188; the UI opened its inventory.
One public read verified that exact supported, affordable offer at **0/0/0**,
with no pending action.

The bounded controller accepted `buy_shop_item` and `choose_relic_card` for the
original upgrade-1 Bludgeon, then stopped with **`read_native_failed`**:
**2 attempted / 2 accepted / 0 reconciled**, two decisions, three controller
reads, zero stale rejections and a pending action. **No confirmation was sent.**
The UI showed gold **829**, Punch Dagger appended, HP **88/88**, sixteen cards
and five occupied potion slots. Its open before/after preview showed the same
Bludgeon+ and Momentum 5 on the preview clone. These visible partial effects do
not establish completed purchase/selection reconciliation or a deck enchantment.
No action was retried and no preview was manually confirmed.

Normal application Quit closed the stopped game. Stopped-process/closed-listener
checks and exact owned quarantine/purge passed by **11:54:51 UTC**; four generated
files were removed, zero overlays remained and all 429 base files retained
SHA-256 `d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
Quarantine state was
`9650d28d5b2eda757c8ffd4edc4f0317b2561061a3e4fa017a63b7bf919704b7`.
This cleanup does not change the unresolved **2/2/0** result. Separate test,
investigation and user-wait durations were not measured. No profile/save/history/
Cloud filesystem content or live trajectory corpus was accessed.

Pinned source and scene inspection found a concrete same-frame mismatch.
`NEnchantPreview.Init` queues every old Before/After child for deletion, then
adds one new holder to each container. In `scenes/cards/enchant_preview.tscn`,
Before and After are preview-holder scene instances, each initially containing
a Hitbox. Those queued children remain until frame end. The shared shop selector
read its preview again within the same callback and required exactly one child
immediately. A fixture matching this scene reproduced rejection at that child
count check before the correction. Scene SHA-256 identities are
`d455678578a912bf2680fc1228154178dde651d2a6d3439c194511263c123bb6`
for the enchant preview and
`535237769fbd1d1d37acbc7d7ef5600180e4db7ea3092708a06c2073242f16ad`
for `scenes/cards/holders/preview_card_holder.tscn`. This offline reproduction
supports the correction; the exact live rejecting predicate was not exposed by
the old diagnostic. The separate corrected retest below establishes live success
for the new package without changing this failed attempt.

## Punch Dagger corrected preview passed, 2026-09-26

The retest used manifest
`289fabed66cddcd01003747383962f0c18f9a17395d2eb6c4a1b340bb4c5b302`, source
`7829456da1bb28471f4aa4c910d3b5ca6d693032`, including feature `338a076`, and DLL
`91182c7940b4ce420841eece40292213479838f9240a20add75523f250639405`
(1,793,024 bytes). Installation was verified by **12:08:59 UTC**, state
`9f39f9df0369eeb78dad20d865dbc6b523c588f0a9f3bd5c72ead49bd2356d8a`.
The accepted 85-group release gate took 355.485 seconds; focused pickup and
affected consumer checks passed, and independent semantic review found no blocker.

After the user's manual Profile 3 launch, live work resumed at **12:12:28 UTC**.
Runtime, metadata, authenticated health and compatibility passed. Continue
restored the saved campaign at Neow. Before full-producer attachment, native
`act 1` rebuilt the map and `gold 1000` changed gold 17 → 1017. The second of two
native `room shop` setups offered Punch Dagger for 188; the UI opened inventory.
No cards, relics, potions or HP were granted. One public preflight read verified
the exact supported affordable offer at **0/0/0**, with no pending action.

The bounded controller completed by **12:19:01 UTC**:
`buy_shop_item → choose_relic_card → deselect_relic_card → choose_relic_card →
confirm_relic_selection → close_shop → leave_shop`. All **7 attempted / 7 accepted /
7 reconciled** actions settled, with 19 controller reads, zero stale rejections
and no pending action. It stopped deliberately at the actionable map with
`truncated/external_stop`; this is a successful bounded case, not a campaign win.
One final public read independently rechecked the settled map and **7/7/7**
counts: **21 public reads** including preflight and final verification.

The same original upgrade-1 Bludgeon was selected, deselected and reselected.
Its preview settled before each next action; the original deck remained unchanged
before confirmation. Confirmation applied exactly **Momentum 5** to that original,
preserving its identity and upgrade. The other fifteen card nodes stayed exact.
Gold changed **1017 → 829**, exactly one Punch Dagger was appended to the 31
original relics, and HP **88/88**, deck size **16** and all five occupied potion
slots were preserved. The UI separately showed the returned map, 829 gold,
88/88 HP, sixteen cards and Punch Dagger. No external setup or manual game action
intervened between attachment and the settled map.

Normal Save and Quit returned to Profile 3's main menu, then normal game Quit
closed the process. Stopped-process/closed-listener checks, exact owned quarantine
and purge passed by **12:20:28 UTC**. Four generated files were removed, zero
overlays remained and all 429 base files retained SHA-256
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
Quarantine state was
`8c2fc6d2a50469d385189828cfe8ca1f31a4b5c6aa9a0640c98f3937f7b37618`.
Live preparation through verified cleanup spanned eight minutes; separate
controller/setup and user-wait durations were not measured. No profile/save/
history/Cloud filesystem content or live trajectory corpus was accessed.

This establishes the corrected Punch Dagger purchase, repeated preview and exact
effect through shop/map handoff. Royal Stamp, other deck shapes, persistence
across reload and the complete shared v2 ending remain separate acceptance cases.

## Gnarled Hammer and zero-purchase shop passed, 2026-09-26

This batch reused the accepted manifest
`289fabed66cddcd01003747383962f0c18f9a17395d2eb6c4a1b340bb4c5b302`, source
`7829456da1bb28471f4aa4c910d3b5ca6d693032` and DLL
`91182c7940b4ce420841eece40292213479838f9240a20add75523f250639405`.
Installation was checked by **12:22:32 UTC**, state
`ebd915dc46e0fde082b53da0b9f76f9b6fca667f80c7d0c48481f2cfb1a10830`.
No production source, binary, test or dependency changed; the accepted release
gate and review were reused, with fresh installed/runtime checks.

After manual Profile 3 launch, live work resumed at **12:25:17 UTC**. Runtime,
installed metadata, authenticated health and pinned compatibility passed.
Continue restored Neow with 17 gold, HP 88/88, sixteen cards, 31 relics and five
occupied potion slots. Before attachment, native `act 1` rebuilt the map and
`gold 1000` changed gold to 1017. The first console entry lost its leading
characters and was explicitly rejected as unknown command `t`; the corrected
`act 1` then succeeded. Nine native `room shop` preparations were inspected before
the last offered Gnarled Hammer for **204**. No cards/relics/potions/HP were
granted. One public read verified the supported affordable offer at **0/0/0**,
with no pending action. All subsequent gameplay used the shared producer.

The Hammer controller completed by **12:30:27 UTC** at **7 attempted / 7 accepted /
7 reconciled**, 26 controller reads, no stale rejection and no pending action.
It bought the relic, selected three distinct unenchanted originals, confirmed,
closed inventory and left. Two upgrade-1 Bludgeons and one upgrade-1 Headbutt each
received exactly **Sharp 3**, preserving identity and upgrade. The other thirteen
cards stayed exact, and the deck did not change before confirmation. Gold changed
**1017 → 813**, one Hammer was appended (**31 → 32 relics**), and HP **88/88**,
deck size **16** and all five potion slots stayed unchanged. One final public read
verified exact effects and the settled map; the UI separately confirmed the map
and visible totals.

One public map inspection found a legal three-node route: combat **(1,2)**,
unknown **(2,3)**, merchant **(3,4)**. The existing bounded travel callback used
the public reference policy for intervening combat/event/reward actions and
stopped at the next open inventory by **12:31:50 UTC**. Travel added **16/16/16**
actions over 180 reads, reaching cumulative **23/23/23** with no pending action.
It included four card plays, one end turn, gold/card rewards, one event option and
its rewards/leave, three map entries and opening the merchant. HP stayed 88/88;
gold was 826 and the deck had seventeen cards. Its stock had no remaining target
selector, so no additional relic purchase was attempted.

The zero-purchase case captured that exact inventory in one preflight read, then
performed only **Close → Leave**. Both actions reconciled over three controller
reads; one final read verified an actionable map, exact unchanged deck/relic/potion
nodes, gold **826** and HP **88/88**. The final deck had **17 cards**, **32 relics**
and five occupied potion slots. This added **2/2/2**, for a batch total of
**25/25/25**, no pending action and **214 public reads**, including the separately
counted preflight, map and verification reads. Both case controllers deliberately
stopped with `truncated/external_stop` at the map; no campaign victory is claimed.

Normal Save and Quit returned to Profile 3's main menu, followed by normal game
Quit. Stopped-process/closed-listener, exact quarantine/purge and unchanged-base
checks passed by **12:34:12 UTC**. Four generated files were removed, zero overlays
remained, and all 429 base files retained SHA-256
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
Quarantine state was
`96f3d1415fc51339fd4ee2ac864b3321e93929c63d1841803b3efd2fc98a16d1`.
The recorded live-preparation-through-cleanup interval was **535 seconds**;
separate setup/controller and user-wait times were not measured. No profile/save/
history/Cloud filesystem content or retained live trajectory corpus was accessed.

This establishes Gnarled Hammer's three-card pickup and a separate zero-purchase
shop visit. Zero/fewer-card Hammer confirmation, selector reversal, Royal Stamp,
Cauldron/Orrery rewards, reload persistence and the complete shared v2 ending
retain separate evidence limits.

## Royal Stamp preview toggle passed, 2026-09-26

The same accepted manifest
`289fabed66cddcd01003747383962f0c18f9a17395d2eb6c4a1b340bb4c5b302`, source
`7829456da1bb28471f4aa4c910d3b5ca6d693032` and DLL
`91182c7940b4ce420841eece40292213479838f9240a20add75523f250639405` were reused.
The installation was checked by **12:34:58 UTC**, state
`588996d8fe8edd47a99ad7bd8077db8b1cf1866aa2037065e7e736bb6ea1c543`.
No production, test, toolchain or package input changed; release checks and review
were reused with fresh installed metadata, runtime, health and compatibility checks.

Live work resumed at **12:38:27 UTC** after the user's manual Profile 3 launch.
Continue restored the merchant checkpoint at floor 41 with Gnarled Hammer,
**826 gold**, HP **88/88**, **17 cards**, **32 relics** and five occupied potion
slots. Two native `room shop` preparations preceded attachment; the second offered
Royal Stamp for **212**. No act reset or gold/card/relic/potion/HP grant was needed.
One public preflight read verified the exact supported affordable offer and
**0/0/0** counts with no pending action.

The controller completed by **12:40:42 UTC** at **7/7/7** with 19 controller reads,
zero stale rejections and no pending action. Its actions were buy, select,
deselect, reselect the same original, confirm, close inventory and leave.
Before confirmation the deck stayed unchanged. Confirmation applied exactly
**Royally Approved** to the original upgrade-1 **Defend**, and its public keywords
included both **Innate** and **Retain**. The enchantment has no displayed amount;
the public counter was null. Card identity and upgrade were preserved, and the
other sixteen card nodes stayed exact. Gold changed **826 → 614** and exactly one
Royal Stamp was appended (**32 → 33 relics**); HP **88/88**, deck size **17** and
all five potion slots were unchanged.

One final public read verified those effects, settled **7/7/7** counts and an
actionable map: **21 public reads** in total. The UI separately showed the map,
614 gold, 88/88 HP, seventeen cards and Royal Stamp. The bounded controller's
`truncated/external_stop` was intentional at map return, not a campaign victory.
No manual mutation intervened between attachment and that settled map.

Normal Save and Quit returned to Profile 3's main menu, followed by normal game
Quit. Stopped-process/closed-listener and exact owned quarantine/purge passed by
**12:42:36 UTC**, removing four generated files and leaving zero overlays. All
429 base files retained SHA-256
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
Quarantine state was
`da3d36d7fac7008ac74b33384f9ac37b369bb44feff455ce5e5f1a37c395e86b`.
The recorded live-through-cleanup interval was **249 seconds**; separate setup,
controller and user-wait durations were not measured. No profile/save/history/
Cloud filesystem content or live trajectory corpus was accessed.

All five supported shop card-selector families now have one successful native
case. This test does not establish every selector variant, Royal Stamp persistence
across reload, Cauldron/Orrery rewards or the complete shared v2 ending.

## Orrery five-card rewards and merchant travel passed, 2026-09-26

This batch reused manifest
`289fabed66cddcd01003747383962f0c18f9a17395d2eb6c4a1b340bb4c5b302`, source
`7829456da1bb28471f4aa4c910d3b5ca6d693032` and DLL
`91182c7940b4ce420841eece40292213479838f9240a20add75523f250639405`.
Installation was verified by **12:46:53 UTC**, state
`9a4d3f300710a5140ab79a876f89c768a6ea232497b3e07aa48379f9498b0343`.
Unchanged production/test/toolchain/package inputs retained the accepted gate and
review. Fresh runtime, metadata, authenticated health and compatibility passed.

After manual Profile 3 launch, Continue restored floor 41's merchant checkpoint
with **826 gold**, HP **88/88**, **17 cards**, **32 relics** and five occupied
potion slots. Royal Stamp from the previous console-prepared room was not present;
its prior result remains a within-session test, not reload-persistence evidence.
Six native `room shop` preparations preceded attachment. The sixth offered
**Orrery for 177**, at floor 47. No act reset or inventory/HP/gold grant was needed.
A public inspection verified the affordable supported offer at **0/0/0**; a separate
one-read controller preflight captured exact inventory before purchase.

The controller bought Orrery and opened/chose each of five reward menus. Every
original card stayed exact; the additions were **Cinder, Headbutt, Setup Strike,
Stomp and Armaments+**. Gold changed **826 → 649**, the deck **17 → 22** and relics
**32 → 33**, with exactly Orrery appended. HP **88/88** and all five potions stayed
exact. After the fifth card, the native reward screen closed automatically and
returned to inventory. The disposable helper expected an explicit `leave_rewards`
and stopped with `shop_rewards_unexpected_context` by **12:56:25 UTC**, after
**11/11/11**, twelve controller reads, no stale rejection and no pending action.
Its callback had already checked the complete five-card inventory effects before
rejecting that context. This was a test expectation failure, not an uncertain
mutation or a bridge failure; the purchase and card choices were not repeated.

A separate bounded Close/Leave controller captured the settled inventory in one
read, completed **2/2/2** over three reads and used one final read to verify an
exact unchanged inventory and actionable map. The Orrery case therefore finished
at **13/13/13**, with **19 total public reads**, including both preflights, the
initial offer inspection and final verification. Its final stop was intentionally
`truncated/external_stop`. UI inspection also showed 649 gold, 22 cards, five
potions, Orrery and the returned map. The helper was corrected to allow a settled
automatic shop return; no production source or release input changed.

One map read identified the legal route **unknown (4,4) → merchant (5,5)**.
The unknown room was combat. Travel completed seven card plays, an end turn and
gold collection, reaching **23/23/23**. A subsequent `open_reward` dispatch was
explicitly rejected as `stale_decision` with `mutation_state=none`; the first
travel helper stopped after 139 reads. A fresh one-read inspection verified the
settled reward decision and unchanged counts. Continuing from that fresh decision
completed open/choose/leave rewards, map entry and Open Shop in five actions and
sixteen reads, reaching **28/28/28** by **12:58:56 UTC**. No uncertain action was
retried. The helper's known-stale handling was aligned with the existing host.
The merchant had no Cauldron. Final visible totals were **665 gold**, HP **88/88**,
**23 cards**, **33 relics** and five potions at floor 49. The entire batch used
**176 public reads**, with one known non-mutating rejection and no pending action.

Normal Save and Quit returned to Profile 3's main menu, followed by normal game
Quit. Stopped-process/closed-listener checks and exact owned quarantine/purge
passed by **13:00:51 UTC**, removing four generated files and leaving zero overlays.
All 429 base files retained SHA-256
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
Quarantine state was
`5d7acdcd3093c74582bd6e3270bc1b7aa50a292846eb88b8611684bcf60267d8`.
Recorded clock checkpoints from **12:52:02 to 13:00:51 UTC** span **529 seconds**;
the earlier runtime preflight and separate setup/controller/user-wait durations
were not measured. No profile/save/history/Cloud filesystem content or retained
live trajectory corpus was accessed. Cauldron, alternate Orrery choices/Skip,
reload persistence and the full shared v2 ending remain separate evidence limits.

## Cauldron helper stop and expired purchase, 2026-09-26

The unchanged accepted manifest `289fabed66cddcd01003747383962f0c18f9a17395d2eb6c4a1b340bb4c5b302`
ran from installation state
`247628e31adb63cbaf48851a59a37bb84b3ed2815a2dff9250c9a2c7c84235fe`, verified by
**13:01:17 UTC**. Manual Profile 3 Continue restored the floor-49 merchant with
665 gold, HP 88/88, 23 cards, 33 relics including Orrery, and five occupied potion
slots. Runtime, metadata, authenticated health and compatibility passed. The
second of two native `room shop` preparations offered **Cauldron for 211** at
floor 51; no inventory/HP/gold grant or act reset was needed. Public inspection
attached the full producer at **0/0/0**, with no pending action.

The helper incorrectly expected to clear all five potion slots before purchase.
The shop's legal discard actions require a full belt, so after discarding Swift
Potion only the purchase was chosen. Cauldron was bought and its first reward,
**Blessing of the Forge**, was collected in that slot. The helper then lacked the
branch to discard another original while the reward screen was full and stopped
with `shop_rewards_expected_action_unavailable`: **3 attempted / 3 accepted /
2 reconciled**, four controller reads and one pending purchase. Gold was **454**;
HP 88/88 and all 23 original cards stayed exact; Cauldron was appended as relic 34.
A separate public read still exposed the four protected-original discard choices.
The newly collected Blessing was distinct from the original same-key potion.

Preparation of a continuation exceeded the purchase's existing **60-second**
owner deadline in `PinnedShopEffectDispatch.Invoke/Owner`. Its next preflight read
failed `read_native_failed` by **13:09:12 UTC**, before any continuation mutation.
The exact failing predicate was not separately exposed, but the source deadline
had expired. No reward action was retried after that failure. The UI still showed
four unclaimed potions. Seven public reads succeeded across inspection, preflight,
controller and the settled-child inspection; the eighth read failed. The
**3/3/2** result remains unresolved and is not live acceptance for Cauldron.

Normal game Quit was used without Save and Quit or further reward input.
Stopped-process/closed-listener, exact quarantine/purge and unchanged-base checks
passed by **13:10:43 UTC**: four generated files removed, zero overlays, all 429
base files retaining SHA-256
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
Quarantine state was
`16db5c1ecc46cfba8e4111dc483e2f9e76318ac4b19b9816e58bd8a21b6919c1`.
Clock checkpoints **13:04:27–13:10:43 UTC** span **376 seconds**; exclusive
controller/preparation and user-wait durations were not measured. Cleanup does
not reconcile the purchase. No profile/save/history/Cloud files or live corpus
were accessed. The disposable helper now interleaves original-potion discards
and reward claims, preserves newly obtained potions and uses a 45-second bound.
Production sources, deadlines and the accepted release remain unchanged.

## Cauldron five-potion replacement passed, 2026-09-26

The corrected experiment reused the same accepted manifest
`289fabed66cddcd01003747383962f0c18f9a17395d2eb6c4a1b340bb4c5b302`, source
`7829456da1bb28471f4aa4c910d3b5ca6d693032` and DLL
`91182c7940b4ce420841eece40292213479838f9240a20add75523f250639405`.
Installation state
`5ff6a20b72bab4188074b5948b9d911ada2e7c597c10d1a9ae466630a7e55657` was checked
by **13:12:07 UTC**. Only the disposable test helper changed; production sources,
interfaces, deadlines, tests, toolchain and package inputs were unchanged. The
accepted release gate and review were reused with fresh runtime, metadata,
authenticated health and compatibility checks.

Manual Profile 3 Continue restored the pre-purchase floor-49 merchant: **665
gold**, HP **88/88**, **23 cards**, **33 relics** and five occupied potion slots.
Two native `room shop` preparations preceded attachment; the second offered
Cauldron for **211** at floor 51. No act reset or inventory/HP/gold grant was
needed. The controller's one-read preflight captured the exact inventory and
fresh **0/0/0** counts. All later gameplay was through the shared producer.

By **13:16:17 UTC**, the controller completed **13 attempted / 13 accepted /
13 reconciled** actions, fourteen reads, zero stale rejections and no pending
action. It discarded Swift Potion, bought Cauldron, then alternated claiming a
reward with discarding one remaining original when the belt filled. All five
originals were discarded exactly once: Swift Potion, Flex Potion, Blessing of
the Forge, Blood Potion and Skill Potion. All five offered rewards were collected:
**Blessing of the Forge, Regen Potion, Clarity Extract, Attack Potion and
Gambler's Brew**. Newly obtained potions were never selected for discard,
including the new Blessing while the distinct original same-key potion was removed.

The last claim automatically returned to shop inventory. Close/Leave completed
the map handoff; a final independent read verified **13/13/13**, no pending
action and an actionable map. There were **16 public reads** including preflight
and final verification. Gold changed **665 → 454**, exactly one Cauldron was
appended (**33 → 34 relics**), every original card remained exact (**23 cards**),
HP stayed **88/88** and potion capacity stayed **5**. The five final potion
identities matched the visible reward offers. The UI independently showed the
map, 454 gold, 23 cards, Cauldron and the five new potions. The controller stopped
intentionally with `truncated/external_stop`; this was not a campaign victory.

Normal Save and Quit returned to Profile 3's main menu, then normal game Quit
closed the process. Stopped-process/closed-listener checks and exact quarantine/
purge passed by **13:18:15 UTC**: four generated files removed, zero overlays,
and all 429 base files unchanged at SHA-256
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
Quarantine state was
`0a487fea310ec2dab8624ce119b6151da88c015633432d5292718c69c40b065f`.
Clock checkpoints **13:14:15–13:18:15 UTC** span **240 seconds**; separate
controller/setup and user-wait durations were not measured. No profile/save/
history/Cloud files or retained live trajectory corpus were accessed.

Cauldron and Orrery now each have representative shared-producer purchase,
reward and shop/map acceptance. This successful fresh attempt does not reconcile
the preceding **3/3/2** attempt. Other belt sizes, alternate choices/Skip, reload
persistence and the full shared v2 ending retain their separate evidence limits.


## Silver Crucible empty chest passed, 2026-09-26

The unchanged accepted manifest
`289fabed66cddcd01003747383962f0c18f9a17395d2eb6c4a1b340bb4c5b302`, source
`7829456da1bb28471f4aa4c910d3b5ca6d693032` and DLL
`91182c7940b4ce420841eece40292213479838f9240a20add75523f250639405` were reused.
Installation state
`b8e6c5b2b911e13ab3fbbef3b4b5641c91f2a4925feda4855c3acc5f0f48350a` was checked
by **13:20:38 UTC**. Fresh process, source, metadata, authenticated health and
compatibility checks passed after the user's manual Profile 3 launch. No
production source, test, toolchain or package input changed.

The pinned `SilverCrucible.ShouldGenerateTreasure` suppresses the owner's first
treasure-room reward. Continue restored the floor-49 merchant with **665 gold**,
HP **88/88**, **23 cards**, **33 relics** and five occupied potion slots. Native
setup added **Silver Crucible** once and entered `room treasure`, leaving the
floor-50 chest unopened. No act reset or HP/gold/card/potion grant was used.
All setup preceded attachment; the first shared read captured the exact inventory
with 34 relics, Crucible counter 3, no offered relic and fresh **0/0/0** counts.

By **13:29:23 UTC**, the public-only helper completed **Open → Proceed** at
**2 attempted / 2 accepted / 2 reconciled**, eighteen controller reads, zero stale
rejections and no pending action. It observed no offered relic. A final independent
read verified an actionable map and exact unchanged gold, HP, deck, relics and
potion inventory. There were **20 public reads** including preflight and final
verification. The UI independently showed the map, unchanged inventory totals
and Crucible counter 3. The controller intentionally stopped with
`truncated/external_stop`; this was not a campaign victory.

Normal Save and Quit returned to the main menu, then normal game Quit stopped
the process. Exact cleanup passed by **13:31:05 UTC**: four generated files removed,
zero overlays and all 429 base files unchanged at SHA-256
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
Quarantine state was
`6fafb44f9b8c1c292df83cc2ba420f0817b1e5bb640897456eb95b3dff0613cb`.
An initial cleanup invocation rejected a malformed expected identity before any
change; the verified full identity was then used successfully. Clock checkpoints
**13:27:18–13:31:05 UTC** span **227 seconds**; separate setup/controller and
user-wait durations were not measured. No profile/save/history/Cloud files or
retained live corpus were accessed.

This is representative acceptance of empty-chest completion under the shared
producer. Crucible's card-reward upgrades, other empty-chest causes, reload
persistence and the full shared v2 ending retain their separate evidence limits.


## Trial direct-shop setup rejected, 2026-09-26

The unchanged accepted manifest `289fabed…`, source `7829456` and DLL `91182c79…`
used installation state
`34e0a95a89114778b57a0112fc3833216d2dfa8205a67065c6f96801bec7e24c`, checked by
**13:37:45 UTC**. Fresh runtime, source, metadata, health and compatibility checks
passed after manual Profile 3 launch. Continue restored the floor-49 merchant:
**665 gold**, HP **88/88**, **23 cards**, **33 relics**, five occupied potion slots.
Native `event TRIAL` and Accept exposed Nondescript/Innocent's Doubt-plus-two-
transforms option at floor 50. No inventory assistance or act reset was used.

The disposable helper's single-read preflight encountered native admission still
waiting and returned `trial_requires_fresh_prepared_verdict`, before any input.
A bounded public inspection then reached **`read_native_event_parent_travel`** at
**0 attempted / 0 accepted / 0 reconciled**, with no pending action or public
decision. There were **34 reads**: one initial preflight and 33 diagnostic reads,
including the final failed response. Neither the verdict nor its selector ran.

The diagnostic identifies the enabled map-travel guard. Pinned source shows the
merchant enables map travel, whereas console event creation does not reset it;
normal map entry disables it. The next setup therefore enters a connected
non-shop room normally before preparing Trial. The helper now waits boundedly
for initial admission instead of treating an ordinary waiting reply as a prepared-
verdict mismatch. No production ownership guard or package changed.

No gameplay input followed the failed read. Normal game Quit, stopped-process/
closed-listener checks and exact cleanup passed by **13:41:37 UTC**, removing four
generated files and leaving zero overlays and all 429 base files unchanged at
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
Quarantine state was
`2dbf51922ae61b020bcdb14d627c14fd36c2698c7950f6e28d0925f6f38f15aa`.
Clock checkpoints **13:38:48–13:41:37 UTC** span **169 seconds**; separate setup,
controller and user-wait times were not measured. No profile/save/history/Cloud
files or retained live corpus were accessed. Trial selector acceptance remains open.


## Trial curse and two transforms passed, 2026-09-26

The unchanged accepted manifest
`289fabed66cddcd01003747383962f0c18f9a17395d2eb6c4a1b340bb4c5b302`, source
`7829456da1bb28471f4aa4c910d3b5ca6d693032` and DLL
`91182c7940b4ce420841eece40292213479838f9240a20add75523f250639405` were reused.
Installation state
`9e5515310e7078abc5bc50a2eb44bc88d73bcf0d8da9a934a0846bd5a207dfa5` was checked
by **13:43:10 UTC**. After manual Profile 3 launch, fresh process, source,
metadata, authenticated health and compatibility checks passed. No production
source, tests, toolchain or package input changed.

Continue restored the floor-49 merchant: **665 gold**, HP **88/88**, **23 cards**,
**33 relics**, five occupied potion slots. Normal native Proceed and connected
rest-site entry reached floor 50, without selecting any rest option. Native
`event TRIAL` and Accept then exposed **Nondescript/Innocent** at floor 51. All
setup preceded attachment; no act reset or inventory/HP/gold assistance was used.
A native save notification appeared on normal rest entry; reload persistence of
later debug-event changes was not tested.

The preflight reached the exact untouched verdict after **34 reads**, with fresh
**0/0/0** counts and no pending action. By **14:51:20 UTC**, the shared producer
completed Innocent, two original-card selections, Confirm and Proceed at
**5 attempted / 5 accepted / 5 reconciled**, fifteen controller reads, zero stale
rejections and no pending action. **Doubt** was observed as the sole appended card
before selection. The two selected **Bludgeon+** originals were removed and replaced
by **Headbutt** and **True Grit+**. All **21 other original cards**, the appended
Doubt, gold, HP, all 33 relics and all five potions remained exact. The deck grew
**23 → 24** solely from the observed curse addition.

One independent final read verified the exact effects, **5/5/5**, no pending action
and an actionable map. There were **50 public reads** in total. The UI also showed
the map, 665 gold, HP88/88 and 24 cards. The intentional result was
`truncated/external_stop`, not a campaign victory. This accepts the fixed-two
transform child after the observed curse; it does not broaden automatic-grant
provenance beyond the existing generic-event contract.

Normal Save and Quit returned to the main menu, then normal game Quit stopped
the process. Exact cleanup passed by **14:53:12 UTC**: four generated files removed,
zero overlays and all 429 base files unchanged at SHA-256
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
Quarantine state was
`dda0d5d4874bc12d73cc340b7e5cab970d4fcfa8c3d005caf8e5d6aade1dec8a`.
Clock checkpoints **14:49:27–14:53:12 UTC** span **225 seconds**; separate setup,
controller and user-wait durations were not measured. No profile/save/history/
Cloud files or retained live corpus were accessed. Merchant/Innocent's two
upgrades, other callers and the full shared v2 ending remain separate cases.


## Trial seed limit and Sphere setup stop, 2026-09-26

The unchanged manifest `289fabed…`, source `7829456` and DLL `91182c79…` used
installation state
`957dc03911d95691663db12be03214c4348999d04f705eed6e889f1c4c537f73`, checked by
**14:53:56 UTC**. After manual Profile 3 launch, fresh runtime, source, metadata,
health and compatibility checks passed by **15:01:11 UTC**. Continue restored
the floor-50 rest site with **665 gold**, HP **88/88**, **23 cards**, **33 relics**
and five occupied potion slots. The preceding debug Trial transformations were
not present on reload; their accepted result did not claim reload persistence.

Two native `event TRIAL` preparations followed by Accept each exposed Nondescript,
at floors 51 and 52. No verdict was chosen. Pinned `EventModel.BeginEvent` source
seeds the event RNG from the campaign seed, player slot and event ID; Trial Accept
uses its first `NextInt(3)`. Recreating this event cannot expose Merchant for the
same single-player campaign. The displayed entrant number uses the separate
chaotic RNG and is not a branch-selection signal. Merchant/Innocent therefore
remains untested, pending a different matching campaign.

Preparation switched to the already planned Sphere tool coverage. One native
Swift Potion Discard click was issued, but the next screenshot still showed the
occupied slot. Flex's menu was opened for inspection; no second discard was
issued. The discard's completion/cause was not established, so no mutation was
retried and setup stopped. No Sphere event was created. There were **zero public
gameplay reads and zero bridge actions**: health/manifest checks did not attach
the shared producer. Neither the Trial upgrade case nor Sphere was exercised.
This is a setup stop, not evidence of a production bridge defect or live success.

Normal game Quit was used without Save and Quit. The stopped process and closed
listener were checked before exact owned cleanup. By **15:11:52 UTC**, four
generated files were removed, overlays were zero, and all 429 base files matched
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
Quarantine state was
`50cf9087ff1c92e96e7c775e51a8f96ac691755c0a001dc32a60391934c23113`.
The recorded **15:01:11–15:11:52 UTC** interval spans **641 seconds**; separate
setup/controller/user-wait durations were not measured. No profile/save/history/
Cloud filesystem access or retained live corpus was used.

A disposable shared-adapter Sphere helper is now prepared for Payment Plan,
big→small→big switching, one small reveal, five big reveals, currently visible
rewards and settled map return. It checks exact public fog/count/tool changes,
uses only visible fragments when choosing cells, and requires three free potion
slots before the first event action. The slot premise must be established in the
fresh saved room before console event setup. Four offline helper cases passed:
ordinary completion, one known non-mutating stale rejection, a gold-reward
continuation, and rejection of an incorrect tool/fog effect before another action.
An initial test-harness syntax error and an invalid synthetic node definition
were corrected before that passing run. These checks are not native evidence.
No production source, package or runtime safeguard changed, and the accepted
release gate was not rerun for documentation and disposable-helper changes.


## Sphere small and big tools passed, 2026-09-26

The unchanged accepted manifest
`289fabed66cddcd01003747383962f0c18f9a17395d2eb6c4a1b340bb4c5b302`, source
`7829456da1bb28471f4aa4c910d3b5ca6d693032` and DLL
`91182c7940b4ce420841eece40292213479838f9240a20add75523f250639405` were reused.
Installation state
`d69654a11c1a0897fbca12814aa6b975685b97090ebd58f575a147bc323024b6` was checked
by **15:20:01 UTC**; fresh manual Profile 3 launch, runtime, source, metadata,
health and compatibility checks passed by **15:53:52 UTC**.

Continue restored the untouched floor-50 rest site. Automated potion-menu input
did not visibly discard Swift; its popup could reopen, ruling out a pending
discard under the pinned holder guard. The user then manually discarded Swift,
Flex and Blessing. A fresh screenshot confirmed three empty slots, retained
Blood/Skill potions, **665 gold**, HP **88/88**, **23 cards** and **33 relics**.
Native `event CRYSTAL_SPHERE` prepared the untouched initial options at floor 51.
All setup preceded the first shared read; no rest option, act reset or inventory
grant was used. This successful setup does not change the preceding process's
separately recorded uncertain setup result.

The bounded public-only helper completed **17 attempted / 17 accepted /
17 reconciled** actions with **64 public reads**, zero stale rejections and no
pending action. Payment Plan first appended the observed **Debt**. It switched
big → small, revealed cell 60, switched back to big, then revealed cells
15, 48, 40, 53 and 73. Both tool changes preserved the remaining divinations;
each reveal consumed exactly one. All eight tool/reveal transitions were checked
against the next public board, including exact fog changes: the small reveal
cleared one cell and the five big reveals cleared **9, 8, 9, 7 and 8** previously
hidden cells. Cell selection used only current public fog and visible fragments.

The helper collected three gold entries, two potions and one card reward, then
left the event. Gold changed **665 → 715**; the new potions were **Explosive
Ampoule** and **Bottled Potential**. The final 26-card deck contained the 23 exact
originals plus **Debt**, **Doubt** and **Fight Me**, all upgrade 0. Debt was
observed before the board; this result does not separately certify the provenance
of every automatic card grant. Original Blood/Skill potion identities remained
exact, capacity stayed five, and HP/relic totals stayed **88/88** and **33**.
The final public decision and UI both showed the actionable map. This helper
stopped after the settled case; it did not report campaign victory or run a
separate terminal-outcome transition.

Normal Save and Quit returned to Profile 3's main menu, then normal Quit stopped
the game. Exact cleanup passed by **16:11:01 UTC**: four generated files removed,
zero overlays and all 429 base files unchanged at SHA-256
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
Quarantine state was
`a3c06a990b8164a5b29016ae05aaf64e2bb78f0eec3d691670d3016bae199c69`.
Recorded checkpoints **16:08:22–16:11:01 UTC** span **159 seconds**; separate
controller/setup and user-wait times were not measured. No profile/save/history/
Cloud files or retained live corpus were accessed. No production source or
package changed. Earned relics, other board/reward outcomes, full-belt handling,
reload persistence and the full shared v2 ending retain their separate limits.

## Shared v2 route stopped at Small Capsule, 2026-09-26

The unchanged manifest
`289fabed66cddcd01003747383962f0c18f9a17395d2eb6c4a1b340bb4c5b302`, source
`7829456da1bb28471f4aa4c910d3b5ca6d693032`, was installed under state
`a24e9673f20aa29dde0ce657d4d0aaadf9da5701c8498e137ae38e1e1adacb19` and
checked by **16:19:14 UTC**. The user manually launched Profile 3. The running
process check passed at **16:32:22 UTC**, and authenticated health/manifest
preflight passed by **16:33:35 UTC**. A disposable preflight initially checked
the wrong health-field name; using the existing core summary validator corrected
that read-only helper assertion before any gameplay read or action.

Continue restored the untouched floor-50 rest site at HP **88/88**, gold **665**,
23 cards, 33 relics and five occupied potion slots. Native `act 1` reset the saved
campaign's map and entered Neow at total floor 51. Under the user's upfront
assistance authorization, 64 Looming Fruit add/remove pairs raised HP/max HP to
**2072/2072** while leaving the temporary relic absent. Four Break and two Flash
of Steel cards were added. All six were visible in the deck screen; the public
preflight independently confirmed **29 cards**, including exactly those counts.
The top HUD still displayed the old count of 23. All assistance and UI inspection
preceded attachment. No native gameplay intervention followed it.

The unchanged shared public-only chooser selected Small Capsule, then attempted
its relic reward. By **16:40:46 UTC**, the controller had stopped with
**`uncertain_dispatch`**, **2 attempted / 1 accepted / 0 reconciled**, controller
decision count 1, two controller reads, 34 separate preflight reads and no stale
rejections. It reported pending work and no outcome; route acceptance was false.
Only Act 1's Neow event and reward contexts were observed. A read-only screenshot
showed Small Capsule in the relic bar and **Stone Cracker** still offered on the
reward screen. This is not effect reconciliation or permission to retry. No
further bridge request or gameplay input followed the stop.

Normal game Quit, stopped-process/closed-listener verification and exact owned
quarantine/purge completed. Unchanged-base verification passed before the recorded
**16:44:26 UTC** checkpoint: four generated files removed, zero overlays and all
429 base files unchanged at
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
Quarantine state was
`02f15144dd1034a285971e9384d708d5567f346dfac8df55f643538ce5ca901b`.
No profile/save/history/Cloud files or live corpus were accessed. Isolated setup,
controller, cleanup and user-wait durations were not measured.

Source inspection found that the ordinary reward-effect observer retained
`AfterObtained` as reflected through the concrete derived relic type. Stone
Cracker inherits that method. The shop and compound-pickup observers already
normalize inherited callbacks to their declaring method for Harmony. A new
derived-passive reward fixture reproduced `collect:0` returning `uncertain`
before correction, at `/private/tmp/sts-inherited-reward-jt1ogch7/log-002.txt`
(build/reproduction **3.446 seconds**). This is a concrete reproduced defect
consistent with the live stop; the live receipt did not retain its exact native
exception. The correction resolves the same selected callback on its declaring
type and uses that single identity for foreign-hook checks, patching, validation
and cleanup, preserving real overrides.

A preceding disposable experiment used the base relic class and passed 2,925
reward checks in 48.729 seconds, so it did not exercise inherited reflection.
Its first version omitted a required model ID and stopped at admission; neither
experiment is native acceptance. The existing route helper now retains only
closed failure labels/counters from failed POST replies and the first four
public action summaries; nine offline checks verify pass-through, no retry and
suppression of arbitrary response/exception text. It still retains no live corpus.
The corrected package and live retest remain separate from this unresolved attempt.

The same targeted audit found the identical inherited-method defect in the
non-compound Sacrifice observer. Its new derived-passive fixture failed during
reconciliation at `/private/tmp/sts-inherited-sacrifice-9altk8wn/log-002.txt`
(**3.367 seconds**). That observer now normalizes before ownership checks and
retaining the cleanup target. A foreign hook may be detected after the native
Sacrifice click/counter update but before relic acquisition; this stays uncertain
and cannot be replayed. It is not a mutation-free rejection.

The ordinary correction passed **16,879 native checks** in a three-group focused
check (**180.486 seconds**, `/private/tmp/sts-bridge-s88kd1s7`). The subsequent
Sacrifice/terminal correction passed **216 reward-alternative checks** in
**4.829 seconds**, `/private/tmp/sts-inherited-rewards-fixed-4abt2q4r`. An earlier
corrected run stopped because the foreign-hook fixture expected a returned
rejection instead of the inner applier's thrown exception; the fixture now
handles either failure representation with the same strict effect/count/cleanup
assertions. No runtime guard was relaxed.

Independent source review found no blocker: **16:51:06–16:52:06 UTC** for the
ordinary reward path and **16:54:33–16:55:16 UTC** for the same-mechanism Sacrifice
extension (**103 seconds total**). The reviewer did not run tests or the game.
These focused results precede the final combined release gate and do not certify
native recovery or a complete shared-v2 campaign.

The final combined gate passed **85 groups in 371.271 seconds**, including
**16,903 native event checks**, reproducible builds, clients/socket integration,
metadata, package and disposable-cleanup checks. Evidence is retained at
`/private/tmp/sts-bridge-cj8jmqx7`. Source/feature commit is
`57b61efb8deee847b5db1f6db6147085cdf0d85a`; corrected manifest is
`e8cfb4c7fb75fd87d72aa38d9b40e6a4580b07b3d8730238d0278f2e2c5b52fc`.
All 102 bound Python files match the preceding manifest. No new broad Python
run is claimed. The prior release record and package inputs are preserved under
`previous-release-record` and `previous-install-inputs` in that evidence root,
with their original identities; Git `57b61ef` also retains the prior record.

The corrected DLL is **1,793,536 bytes**, SHA-256
`a8fda9fc80fcb5275547393913ad40003ac9b9752c956bcf1e3d0fe9cc8ab1a5`.
Publish, stopped-game install, overlay/base verification and installed metadata
validation passed by **17:09:11 UTC** on 2026-09-26 under state
`0a07959bbbf2334cb961d72db6e10d86654d6ca55ac0ae4258114f8a19e45dec`.
There are two exact overlay files and all 429 base files remain unchanged.
Credential content was not read during this installation verification. The
package was then awaiting a manual Profile 3 launch; the next entry records
its actual live result. Exclusive release-preparation and user-wait durations were not measured.

## Shared v2 Neow recovery and large-deck Cook stop, 2026-09-26

Manifest `e8cfb4c7fb75fd87d72aa38d9b40e6a4580b07b3d8730238d0278f2e2c5b52fc`,
source `57b61efb8deee847b5db1f6db6147085cdf0d85a`, ran under installed state
`0a07959bbbf2334cb961d72db6e10d86654d6ca55ac0ae4258114f8a19e45dec`.
The user manually launched Profile 3. Running-process verification passed at
**17:30:33 UTC** and authenticated release/health preflight by **17:31:07 UTC**.
Continue restored the already-reset Neow room at floor 51, HP **88/88**, gold
**665**, 23 cards and five occupied potion slots. There was no act reset this
session. The previous console assistance had not persisted: before attachment,
64 native Looming Fruit add/remove pairs restored **2072/2072 HP**, with the
fruit absent, then four Break and two Flash of Steel cards were added. The
public preflight confirmed **29 cards** and these exact damage-card counts;
the stale top HUD still showed 23. Console setup was closed before attachment.

The unchanged `game.agent.full_policy.choose_action` chose Small Capsule,
claimed its relic reward, left Neow and reached the map. It then completed four
fights at floors 52, 53, 54 and 56, with Slippery Bridge at floor 55. Neow recovery
is demonstrated within this route; no separate per-case counter total is claimed.
At floor 57 it entered Cook's two-card removal screen with **33 cards**, no
selected cards, HP **2072/2072** and gold **726**. The controller remained waiting.
A graceful interrupt of the exact owned controller produced **`interrupted_pending`**
by **17:37:42 UTC**: **51 attempted / 51 accepted / 50 reconciled**, 51 decisions,
3,861 controller reads, 34 separate preflight reads, zero stale rejections and
pending work. Only Act 1 was observed; no Architect or terminal outcome was seen,
and route acceptance was false. No manual gameplay input or mutation retry
followed attachment. A read-only screenshot established the Cook screen, not
an exact native holder count or predicate. The earlier uncertain reward attempt
remains separate and unreconciled.

Normal Quit, stopped-process/closed-listener checks and exact quarantine/purge
completed. Unchanged-base verification passed by **17:39:16 UTC**: four generated
files removed, zero overlays and all 429 base files unchanged at
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
Quarantine state was
`7cac22c5b3446df232acdbe95c2771a988978f274c5c0c92fda3be717d5aa788`.
Cleanup does not reconcile Cook. No profile/save/history/Cloud filesystem access
or retained live corpus occurred. Exclusive setup, controller, cleanup and user
wait durations were not measured.

The shared `PinnedDeckCardChoice` required its allocated native holders to equal
the full candidate count. Pinned `NCardGrid` instead recycles a bounded window for
larger decks. A partial-grid fixture reproduced failure to become ready at
`/private/tmp/sts-bridge-w56ogio5/log-003.txt`. The correction keeps the complete
public domain, validates the native display order and navigates only toward an
explicitly selected original. It retains the same holder/card-node/hitbox pool,
ignores hidden padding's stale models, checks the native selected set across
pages and stops scrolling before exact native selection. Domain, ownership,
foreign selection and unowned binding changes fail without replay.

Independent review found a second concrete edge in the first correction:
`UpdateScrollPosition` allocates at the old position before moving. A slow frame
can snap to the bottom while the last row remains unallocated. The corrected
fixture reproduced that zero-distance failure at
`/private/tmp/sts-bridge-k3odcdec/log-003.txt`. Pending navigation now finishes the
exact native presentation allocation under its retained owner and revalidates
on the next read before selection. Navigation is bounded to 64 pages per semantic
request, 128 reads per page and the existing 256 native-input budget. This changes
no policy choice, selector domain, wire schema, deck or RNG directly.

The 33-card/25-holder fixture covers gradual and snapping frames, delayed
highlights, exact cross-page selection/deselection/reselection/confirmation and
hidden final-row padding. Adversarial cases cover changes during allocation and
no allocation progress. **946 shop pickup checks** passed in **4.260 seconds**
(`/private/tmp/sts-bridge-44lnv2f7`, three groups), including the final tightening
of the distinct-holder invariant. An earlier production build passed in 2.259 seconds
and affected direct-input/event consumers in 36.990 seconds; both preceded the
allocation-order correction and are not final-release evidence.

Independent source review ran **17:40:56–17:43:44 UTC** (design),
**17:49:08–17:52:51 UTC** (implementation, found the slow-frame edge), and
**17:58:28–17:59:06 UTC** (correction clear), **429 seconds total**.
The reviewer ran no tests or game. Final validation and native Cook recovery
remain separate; the intended retest continues the saved campaign.

The stable correction was committed as `327e7da` and its final combined gate
passed **85 groups in 369.018 seconds**, including **16,972 native event checks**,
reproducible production builds, clients/socket integration, metadata, packaging
and disposable cleanup. Evidence root: `/private/tmp/sts-bridge-0ceoerz0`.
Corrected manifest:
`fed09e937f44d54c52064b0a9c0adc09a03bcfd7ca21bbd3a805277b4151da37`.
DLL: **1,800,704 bytes**, SHA-256
`e90607c18b127d3299f67b5ab1ba7b0039f35ab237d33338a56c7762cc7a3bbd`.
All 102 bound Python files match the preceding release. Its exact release record
and fixed package inputs were verified and preserved under `previous-release-record`
and `previous-install-inputs` in this evidence root; Git `327e7da` retains that
record too. No old live evidence was repinned to the new binary.

Publish, stopped-game installation, base/overlay verification and installed
metadata checks passed by **18:11:04 UTC**, under state
`279151f568527c80cdd9f860dee982da7fa90000761f9858c34ce06c576602ca`.
Two exact overlay files are installed and all 429 base files remain unchanged.
A first stopped-process read lacked sandbox process access; the authorized
read-only check passed outside the sandbox. An initial two-argument verifier
invocation was rejected before inspection; the supported three-argument check
passed. Neither error mutated the game. Credentials were not read for installation
verification. The package now awaits manual Profile 3 launch for the saved Cook
retest; no native recovery is yet claimed.

Disposable helper modes retain the existing adapter/controller. The focused
Cook mode checks the 33-card premise, all eligible choices, the first/last eligible
originals, deselection/reselection, exact two-card removal, +9 HP/max HP, unchanged
other inventory and map return. Six offline cases passed. The continuation mode
accepts only settled initial counters and uses the unchanged common chooser;
five offline cases verify count deltas, missing-act/defeat rejection and explicit
resumed-run scope. Those eleven cases are helper evidence, not native acceptance.
Implementation and checks overlapped; exclusive implementation, release preparation
and user-wait durations were not measured.

## Large-deck Cook retest passed, 2026-09-27

The user manually reopened Profile 3 on manifest
`fed09e937f44d54c52064b0a9c0adc09a03bcfd7ca21bbd3a805277b4151da37`, source
`327e7dad258f30dc2a60bf65549cf38d157bfc07`, installed state
`279151f568527c80cdd9f860dee982da7fa90000761f9858c34ce06c576602ca`.
Running-process verification passed by **09:40:01 UTC**; authenticated health,
compatibility and installed/source identity checks passed before native Continue.
The saved campaign restored the floor-57 rest site with HP **2072/2072**, gold
**726**, four Break, two Flash of Steel and **32 cards**, confirmed independently
by the HUD and one public read at **0/0/0**, with nothing pending. The previous
session's Cook screenshot had shown 33; no persistence explanation is claimed.
No setup mutation, act reset or new campaign was needed.

Before any action, the disposable helper's exact deck-count premise was adjusted
to the observed 32, and its six Cook/five continuation offline cases passed.
The helper retained the existing closed POST-failure diagnostics and controllers.
It then selected public deck positions **0 and 31**, deselected/reselected position 0,
confirmed and left the rest site. By **09:43:26 UTC** it reported **7 attempted /
7 accepted / 7 reconciled**, 48 controller reads, one preflight read, zero stale
rejections and no pending action. The exact removed originals were **Blood Wall+**
and **Stomp**. All other cards and inventory were preserved: HP/max HP became
**2081/2081**, deck size **30**, gold **726**, 35 relics and five occupied potion
slots. One independent public read verified the same counts/effects and actionable
map. This is a controlled selector result, not a full campaign victory. No exact
live allocation count or scroll-frame sequence was sampled.

The unchanged common policy was then resumed from that settled map in the same
process. Its route result and owned cleanup are recorded separately below; the
Cook success does not reconcile either earlier failed attempt. No profile/save/
history/Cloud filesystem access or retained live corpus occurred. The accepted
85-group release gate was reused because the production inputs were unchanged.

## Shared-v2 Act 2 rest handoff stop, 2026-09-27

The same process and unchanged `game.agent.full_policy.choose_action` continued
from the settled floor-57 map under manifest `fed09e937f44d54c52064b0a9c0adc09a03bcfd7ca21bbd3a805277b4151da37`,
source `327e7dad258f30dc2a60bf65549cf38d157bfc07`. No setup mutation or manual
gameplay intervention followed policy attachment. This continued an assisted
saved campaign; it was not a fresh uninterrupted campaign.

The policy cleared further fights, rewards, treasure and rests, crossed Act 1
into Act 2, and passed natural Pael entry, Room Full of Cheese and Ranwid through
event/map return. The Pael observation does not establish every Ancient branch.
At Act 2 floor 79, `read_native_failed` stopped the controller by **09:47:15 UTC**:
**236 attempted / 234 accepted / 233 reconciled**, including the seven earlier
Cook actions, with one pending action and two known no-mutation stale rejections.
The route delta was **229/227/226**, with 227 decisions, 2,685 controller reads
and one preflight public read. No Architect or victory was observed.

The final public view was rest, HP **2126/2126**, gold **1142**. A read-only game
screenshot showed an **86-card** deck, no remaining rest options and Proceed.
The helper did not retain the final semantic action, so Clone is a
source-consistent explanation, not an observed final action. No uncertain action
was retried or adopted. Normal quit and exact cleanup finished by **09:49:02 UTC**:
process/listener stopped, four generated files purged, zero overlays and all
429 base files unchanged (`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`).
Quarantine state: `3444072dac814175cbeac7e6712ddf5153cb31bf5f2dad7c4accde9b44dd99a5`.
Cleanup does not reconcile the pending action. No profile/save/history/Cloud
filesystem access or retained live corpus occurred.

Source inspection found two concrete defects consistent with this stop. Rest
entry rejected decks over 64 even when only Proceed remained, whereas Clone
effect verification and the full public run view allowed 128. The coordinator
also read the next surface before returning an already verified room receipt;
a failure there prevented the outer session from receiving completion credit.
The native rest fixture reproduced Clone reaching 86 followed by rejection of
the regenerated empty rest at `/private/tmp/sts-bridge-dovczm21/log-003.txt`.
This diagnosis does not retrospectively alter the observed live counts.

The correction explicitly enables 128-card rest capture and selector domains for
the existing full profile; legacy defaults remain 64. Clone's predicted result
must fit the 128-card public inventory before publication and fresh dispatch.
Closed capacity diagnostics stop without hiding a native legal option. Completed
rest/shop receipts now return before any successor read; native completion and
cleanup remain prerequisites. A coordinator fixture executes the production
backend and outer agent session, confirming that a failed next read retains
verified completion while an unverified option remains pending.

The 128-card grid regression exposed allocation cycling at a settled page:
the pinned native top/bottom predicates can alternate adjacent holder windows.
The driver now detects a repeated fully validated window under that pan, stops
that page's motion and continues toward the same requested original. It retains
all identity/highlight checks and input/read/page bounds. A fixture's initial
bottom limit also made its last row unreachable; the positive case now derives
the bottom from native container sizing, while the old unreachable boundary
remains an explicit zero-card-input rejection case. No production zero-distance
guard was relaxed.

Focused results: **694 rest checks**, **1,642 router checks**, **168 client tests**
and coordinator receipt/failure cases passed in `/private/tmp/sts-bridge-wruy3fyb`;
that combined focused attempt then failed the initial large-grid case. After the
cycle/fixture correction, **956 pickup checks** passed in **4.239 seconds** at
`/private/tmp/sts-bridge-o0d4qbd1`. Production build passed in **1.885 seconds** at
`/private/tmp/sts-bridge-tvetwvlz`. These are inert fixture/build results, not live
86/128-card acceptance. The production shared chooser was unchanged.

Independent source review ran **09:50:33–09:56:27 UTC** (diagnosis/design),
**10:02:29–10:03:41 UTC** (implementation) and **10:05:00–10:06:27 UTC**
(allocation cycle), **513 seconds total**. The reviewer identified the fixture
bottom issue; its correction was author-verified by the passing focused check.
Implementation, review and checks overlapped; exclusive implementation, live
controller, release preparation and user-wait durations were not measured.

The stable correction was committed as `1f74e08`. Its final combined release
gate passed **85 groups in 356.419 seconds**, including 16,982 native event
checks, 694 rest checks, 1,642 router checks and 168 client tests. Evidence root:
`/private/tmp/sts-bridge-gi4ihmno`. Corrected manifest:
`da706c27c151f0e8e1d286a1f16dc48a0770ec17f04e69598b677979f944b3dd`.
DLL: **1,802,240 bytes**, SHA-256
`3d1a78ac7a3e166372bc1f45d109d7c00ce73edecfeb720f1327e73846c165dd`.
Only the bound Python failure-code consumer changed; it passed client/integration
coverage. No new broad headless-suite run is claimed.

The preceding three package inputs were checked against their original manifest
and preserved under this root's `previous-install-inputs`; Git `1f74e08` retains
the preceding release record and complete live/cleanup summary. Publish and
stopped-game installation passed. Exact overlay/base and installed native metadata
checks passed by **10:16:59 UTC**, under state
`13420352011a5c163e0559333bb4a02a01da87d6d9648f934e879ed9f5f31aa8`.
Two exact overlay files are installed and all 429 base files are unchanged.
An unnecessary post-install base-only invocation rejected the expected overlay;
the correct overlay mode verified it and every base file. That check made no
mutation. The game remains stopped for manual Profile 3 launch.

The disposable recovery helper will accept only a fresh settled large rest with
native Proceed, leave once and verify exact inventory/map return at 1/1/1.
Continuation can start in Act 2 or 3 and keeps that scope separate from full
three-act acceptance; it retains one bounded final-action summary for failures.
Six Cook, eight continuation and seven large-rest-exit offline cases passed.
These helper results do not establish live recovery on the corrected artifact.

## Large-rest recovery and floor-81 stop, 2026-09-27

The user manually launched Profile 3 on manifest
`da706c27c151f0e8e1d286a1f16dc48a0770ec17f04e69598b677979f944b3dd`, source
`1f74e084ee9a182a8062c6f13e7ff2f3eab7c0a1`, installed state
`13420352011a5c163e0559333bb4a02a01da87d6d9648f934e879ed9f5f31aa8`.
Running-process, exact installed/source identity, overlay/base, authenticated
health and compatibility checks passed before native Continue. The HUD and a
public read independently showed Act 2 floor 79, **63 cards**, HP **2117/2117**,
gold **1142**, 24 Clone-enchanted cards and all rest options, at **0/0/0** with
nothing pending. This was an earlier rest state than the previous session's
86-card Proceed screen; no persistence explanation is claimed. There was no
setup mutation, new campaign or adoption of the old unresolved action.

Before input, the existing disposable helper was adapted to this premise. Ten
new offline cases checked restored-state admission, Clone growth and preserved
originals/inventory, premature exit rejection and exact final inventory/counts;
the preceding 21 helper cases also passed. Using the unchanged
`game.agent.full_policy.choose_action`, the bounded rest controller completed
Smith, Heal and its card reward, Dig, Cook, Kindle, Clone and Leave. By
**10:29:06 UTC**, it passed **14 attempted / 14 accepted / 14 reconciled**,
134 controller reads, one preflight read, one independent verification read,
zero stale rejections and nothing pending. Clone added 24 cards to the 62-card
post-Cook deck, yielding **86**. Original cards and non-deck inventory at the
Clone boundary were preserved; native effect ownership certified its additions.
HP/max HP ended at **2126/2126**, gold remained **1142**, and Leave preserved the
exact final rest inventory through an actionable map. This demonstrates the
large rest handoff; it does not establish every 128-card selector or campaign
ending. A separate initial diagnostic public read established the restored setup.

The same unchanged policy then continued without manual gameplay intervention.
It entered the floor-80 shop and returned to the map with gold **377**, then
selected another map node. `read_native_failed` stopped it at **27/27/26**, one
pending action, zero stale rejections, 13 decisions, 35 controller reads and one
preflight read. Its continuation delta was **13/13/12**. The final semantic action
was `choose_map_node`; no combat action or combat decision was published. A
read-only screenshot showed an ordinary three-enemy fight on floor **81**,
**93 deck cards**, HP **2126/2126** and gold **377**. Only Act 2 was observed in this
continuation; no Architect or victory was observed. No full per-stage record,
observation corpus or profile/save/history/Cloud filesystem data was retained.

No uncertain action was retried or adopted. Normal quit and exact owned cleanup
passed by **10:31:01 UTC**: process/listener stopped, four generated files purged,
zero overlays and all 429 base files unchanged
(`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`).
Quarantine state: `0afbf36e7ab3837f6f392f3c612b1339aa3d4da3919a152aafd005ca8af645d9`.
Cleanup does not change the failed attempt's unreconciled count.

Source inspection identified an exact matching failure path: full navigation
still required `TotalFloor <= 80`, so the floor-81 read could fail before reading
combat at all. Native `TotalFloor` counts retained map history; it is not an
execution counter and does not index or allocate bridge state. The coordinator
also settled the map action internally before reading navigation, but lost that
receipt when the later read threw. This explains the observed shape independently
of deck size, without claiming the live predicate itself was captured.

The correction keeps nonnegative native integer floors for full navigation and
retains 0–80 for legacy `campaign_v2`, whose client requires that range. Existing
run/player/network/act checks, map-action and navigation-room budgets, shared
read/action limits and feature-session limits remain in force. Failed full
captures now deliver certified receipts with the same terminal failure; the
outer session accounts for them before stopping. Combat outcomes and successor
ready IDs are validated before credit, and unresolved ancestors remain pending.
The backend also latches failure. Existing rest/shop success barriers are retained.

Independent diagnosis/design review ran **10:31:24–10:33:16 UTC** and
implementation review **10:34:09–10:37:35 UTC**, **318 seconds total**. The reviewer
identified combat outcome validation occurring after settlement; it was moved
before settlement and covered by malformed/missing-outcome regressions. No
remaining blocking finding was reported. Review was source-only.

Focused campaign checks passed **284 assertions** at
`/private/tmp/sts-bridge-zec86m5e`; that combined attempt later hit a sandbox
loopback-listener permission error. A follow-up at
`/private/tmp/sts-bridge-g6qy_uq9` exposed an inert fixture still withholding its
successor after simulated combat completion. Correcting that fixture did not
change production behavior. The final selected coordinator/router/client run
passed **six check groups in 17.659 seconds** at
`/private/tmp/sts-bridge-op1tul79`. It covers map successor/projection failures,
unverified travel, malformed combat completion, missing next decisions, potion
completion and verified children whose combat/potion parent then fails. Repeated
reads do not retry or double-credit; uncertain cleanup remains unresolved.
Implementation, review and testing overlapped; exclusive implementation, live
controller, release-preparation and user-wait durations were not measured.

The stable source correction was committed as `2fbb99a`. The final release gate
passed **85 groups in 360.645 seconds** at `/private/tmp/sts-bridge-2347lgir`,
including **284 campaign checks**, **1,642 router checks**, **168 client tests**
and **16,982 native event checks**. Accepted manifest:
`418330cff79f95d517596c27929ac84a3440693d0aed716da0de563cdda97149`.
DLL: **1,802,752 bytes**, SHA-256
`0f9cc8c8286a45abb3516cca46192a1c64e8a88777e975b2cc7c03c9871aeb91`.
All 102 bound Python files match the preceding accepted release; no new broad
headless run is claimed. The preceding three package inputs were checked against
their original manifest and preserved at this root's `previous-install-inputs`;
Git `2fbb99a` retains their full release/live/cleanup record.

Publish, fresh stopped-process/listener verification, installation, exact overlay/
base checks and installed native metadata checks passed by **10:48:07 UTC**.
Installed state:
`b6ddfd36b730046504ec7f893fe9d9ae95feac721065347ec262541e7f275011`.
Two exact overlay files are installed and all 429 base files are unchanged.
The game remains stopped for manual Profile 3 launch. The existing continuation
helper now permits a settled combat entry, retaining its unchanged common policy,
explicit resumed-act acceptance and execution bounds. Its ninth continuation case
passed, bringing disposable helper coverage to **32 offline cases**. The next
case checks the actual restored saved state before continuing combat/rewards/map
and the remaining campaign. Corrected live continuation is not yet demonstrated.

## Floor-81 recovery and settled Clone-capacity stop, 2026-09-27

The user manually reopened Profile 3 on the same accepted manifest
`418330cff79f95d517596c27929ac84a3440693d0aed716da0de563cdda97149`, source
`2fbb99af3b0760ae79ca0c0e8fabe2352a9a7d3f`, installed state
`b6ddfd36b730046504ec7f893fe9d9ae95feac721065347ec262541e7f275011`.
Running-process and exact overlay/base checks passed by **10:51:59 UTC**.
Authenticated health, installed/source identity and compatibility passed before
native Continue. The initial metadata helper looked for the wrong compatibility
field and raised a local KeyError; the documented `build_compatibility` check
then passed. Both requests were read-only, with no gameplay mutation or credential
output. The UI confirmed Profile 3, pinned v0.107.1 and one loaded mod.

Continue restored Act 2 floor **81**, **93 deck cards**, HP **2126/2126**, gold
**377**, four Break and two Flash of Steel. The shared controller's preflight
confirmed a fresh **0/0/0** session and no pending work. No setup mutation, new
campaign or manual gameplay intervention followed attachment. The unchanged
`game.agent.full_policy.choose_action` admitted combat, cleared the three-enemy
fight, processed rewards and returned to the map. It then selected the next node.

The controller stopped with the explicit `read_native_rest_clone_capacity` code:
**10 attempted / 10 accepted / 10 reconciled**, 10 decisions, 86 controller reads,
one preflight read, zero stale rejections and **nothing pending**. The final
semantic action was `choose_map_node`; no rest option was dispatched. Its final
public map view had HP **2125/2126**, gold **389**. A read-only screenshot showed
the next rest on floor **82**, **94 cards**, the same HP/gold and available Clone.
The failed rest read retained the already verified map completion. This is live
acceptance of floor-81 admission and certified receipt preservation, plus a
representative pre-input Clone-capacity stop. The exact number of clonable cards
was not sampled in this session; no predicted size beyond “over 128” is claimed.
Only Act 2 was observed; no Architect, victory or complete campaign is claimed.

Normal quit, stopped process/listener, exact quarantine/purge and base verification
finished by **10:56:07 UTC**. Four generated files were removed, zero overlays
remained and all 429 base files matched
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
Quarantine state: `b3cba01e6bcd619759086503b0ce93ba850abd9635fb75b98e03c4a884cc6157`.
The stopped host was not resumed or bypassed. No profile/save/history/Cloud
filesystem access or retained live corpus occurred.

No production correction is needed for this explicit bound. To keep the
remaining ending test within it, the next controlled setup will remove the exact
`PAELS_GROWTH` relic through the native console before policy attachment and
refresh the rest options with `room RestSite`. Source inspection confirms the
exact relic-ID preference/removal operation and that Pael's Growth adds Clone
when rest options are constructed. Removing a relic alone is not assumed to
rewrite the already-open rest. The UI and fresh public view must confirm the
new setup before policy attachment. These setup actions have **not yet occurred**.
The existing continuation helper now accepts a settled rest entry and resolves
its one final-action subject from the full public graph; ten continuation cases
and the previous 23 helper cases passed (**33 total**), without running the game.

The accepted package and gate were reused unchanged. Reinstallation, exact
overlay/base verification and installed metadata checks passed by **10:57:23 UTC**,
under installed state
`79001d017b36208ef30280a0a1f1908a378f66961f0b75294cf0ee02d986fe0e`.
Two exact overlays are installed; all 429 base files remain unchanged. The game
is stopped for manual Profile 3 launch. Live controller/setup/cleanup durations
were not separately measured; the above wall-clock milestones are retained.

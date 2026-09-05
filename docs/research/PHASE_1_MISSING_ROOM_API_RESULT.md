# Missing-room API static results

- Date: 2026-09-05; selected 23cf integration baseline `951620a`.
- Evidence: pinned target metadata and bounded selected IL, independently reviewed. No live campaign, target-assembly execution, save/profile read or gameplay result.
- Scope: [approved repository/static gate](../PHASE_1_MISSING_ROOM_API_SCOPE.md).
- Exact selection: [sanitized signatures and output hashes](PHASE_1_MISSING_ROOM_API_SELECTION.json): **47 types, 102 actual method bodies**, within 80/200. The final selector and actual ledger are hash-bound there. Generated async bodies are linked to selected methods by metadata attributes and counted separately. No further target inspection is part of this increment.
- Both immutable DLL images matched the pinned 23811903/v0.107.1 identities before metadata parsing. The inspector used PEReader, an offline net9.0 build and the existing isolated 9.0.303 SDK. Raw outputs remain disposable; only member/behavior facts, exact selections and hashes are retained here.

## Item reward collection

`NRewardButton.OnRelease()` launches asynchronous `GetReward()` through the game's task helper. The latter disables the button and awaits the existing reward synchronizer. The selected generic `Reward.SelectUnsynchronized()` body separately shows OnSelect followed by AfterRewardTaken, then SuccessfullySelected=true. The synchronizer implementation linking these operations remains an unselected dependency. Dispatch return, disabled state, a claimed signal and screen disappearance are not effect receipts.

PotionReward exposes the offered Potion, ClaimedPotion and IsPopulated. RelicReward exposes Relic, ClaimedRelic and IsPopulated. These and SuccessfullySelected are pure field/null-check getters. Their Description uses the same offered model's Title for the visible reward label. Stable model IDs remain mappings from that visibly bound model, using the already accepted model-ID compile surface; no native address or platform identity is public output.

Player.PotionSlots and MaxPotionCount expose the ordered backing list and its length. NPotionContainer places the acquired model in the holder matching its index in that list, supporting the public belt ordering. Immediately copy lists for baselines; IReadOnlyList is not proof of immutability. Do not use HasOpenPotionSlots, whose selected body calls an unselected predicate, when the copied null-slot list suffices.

**Full-inventory hazard:** Player.AddPotionInternal resolves the default slot to IndexOf(null). No empty slot returns failure reason 1. PotionReward treats that reason as taken, assigns ClaimedPotion and returns true even without inventory acquisition. Therefore claimed/selected flags alone would falsely accept a full-belt collection. A supported potion dispatch requires an immediately revalidated empty slot. Its resolution requires exactly one prior null becoming the exact offered model/key, identical capacity/order, every other reference/key/null unchanged, and exact ClaimedPotion plus SuccessfullySelected. Replacement, decline, skip and full inventory remain unsupported. An unexpected change after dispatch stops with the reservation retained.

RelicReward awaits RelicCmd.Obtain and assigns the returned ClaimedRelic before returning true. RelicCmd awaits the relic's AfterObtained hook; the generic reward path later awaits AfterRewardTaken before marking selected. The first slice requires exact offered ClaimedRelic plus selected state, and claims only reward-local acquisition. Relic stack/insertion internals and arbitrary callback effects are not proven; a relic-count +1 rule would be unjustified.

NRewardsScreen.RewardCollectedFrom removes and queues the reward button for freeing, then updates the screen. An empty nonterminal reward screen removes itself from the overlay; an empty terminal screen marks IsComplete and emits Completed. Reconcile retained reward/player/model facts **before** foreground classification and without dereferencing a freed button. Screen closure itself never proves acquisition or parent completion. Exact signal subscription wiring was not selected.

Independent item review covered 53 output files; its sorted `sha256  basename\n` manifest digest is `be99b5b4abed23e7273e28e3fab9788c6a5bdb9aa9e855ca9afe3e171e724cf5`. Final per-file hashes are in the selection record. Its approved design direction is captured in the [isolated item contract](../PHASE_1_ITEM_V1_CONTRACT.md).

## Event visibility and progression

NEventOptionButton._Ready supplies Event.DynamicVars to public Option.Title/Description, formats those LocStrings and writes the result to its `%Text` MegaRichTextLabel. Its private label field need not be accessed reflectively: inherited public GetNode can address that existing label. A final metadata-only extension establishes a public declared MegaRichTextLabel.get_Text(): string. The getter body was not inspected, so its passivity and exact returned formatting remain future gates; public declaration alone does not justify enabling a new reader.

EventModel.IsFinished means the final page, not actual exit. SetEventFinished changes event state to no ordinary choices and marks finished. NEventRoom then constructs a synthetic Proceed choice. Actual Proceed enables map travel and opens the map. IsProceed chooses a special dispatch route; it is not a generic success witness. The constructor's exact Boolean mapping was not inspected and remains an inference from the selected control flow.

EventOption.WasChosen is set before awaiting pre-choice and choice callbacks. It survives exceptions and only prevents repeat invocation when private DisableOnChosen is true. It cannot be an accepted/completed receipt. CurrentOptions is a mutable list behind IReadOnlyList; clearing/rebuilding the layout can create new buttons with previously seen public content. No generic monotonic, lineage-bound progression witness was found. Preserve rejected/reserved ABA behavior. IsFinished false-to-true witnesses only the bounded final-page transition. Overlay presence/closure does not identify the parent action that caused it.

Independent event review accepted these distinctions; it did not accept a generic event ordinal, a synchronous action receipt, an overlay-to-parent causal link, or a change to 0.8.0 D47.

## Shops

Public declarations support visible stock projection via NMerchantRoom.Inventory, NMerchantInventory.Inventory/IsOpen/GetAllSlots and NMerchantSlot.Entry/Hitbox. Card entries expose CreationResult and stocked state; potion/relic entries expose Model. GetAllSlots is the game's native enumeration order, not proven geometric screen order, and still requires visibility and control checks.

MerchantEntry.Cost is the value written to the visible cost label and may apply Hook.ModifyMerchantPrice while in a merchant room. Revalidate public Cost; never substitute its private backing field. EnoughGold includes equality. Ordinary card purchase awaits CardPileCmd.Add before PlayerCmd.LoseGold; potion purchase similarly awaits procurement before debit. Acquisition-only can be an intermediate state, while debit-only contradicts the selected ordinary-card ordering. Purchase return remains asynchronous with respect to UI dispatch.

After successful acquisition/debit, the wrapper either clears the entry or conditionally restocks it, then awaits AfterItemPurchased before raising PurchaseCompleted. A replacement may occupy the same slot, possibly with the same public key/price. Reserved lineage and exact player deltas remain necessary; stock disappearance alone is not a universal witness.

Inventory closure and room leave are distinct. Opening stock disables the room Proceed. Inventory Close sets IsOpen=false and emits InventoryClosed, without opening the map. Room Proceed is wired to HideScreen; its non-FTUE branch opens the map. The proposal must count a separate close_inventory action before leave can become eligible.

**Unresolved dispatch gates:** the saved bodies do not prove the public Hitbox-to-private OnSelected connection, the exact BackButton lambda that invokes Close, the InventoryClosed lambda that re-enables room controls, or the private FTUE interception predicate. No reflective fallback is accepted. Shop action implementation stays unfrozen pending a new narrow static selection; the proposal is corrected to these facts. Relic purchase ordering and card removal remain outside this body selection.

Independent shop review covered 48 output files; sorted manifest digest `a9e59da8a3cd51c23ce70799c759a317a70aebbaee7219dfb050fa8822cb9e51`. See the [corrected shop proposal](PHASE_1_SHOP_CAPABILITY_PROPOSAL.md).

## Stops and next implementation gate

Save, history, NetId/platform, Cloud, grab-bag and other excluded callees were encountered only as static references and were not followed. Their values are neither actor fields nor completion witnesses. Item synchronization internals, signal hookup, relic insertion/stack and hook bodies, potion failure subscribers, event lifecycle callbacks, and the shop gaps above remain explicit residuals.

Only the independently reviewed item first slice advances to isolated implementation and synthetic execution. Separate pure core tests may run with injected in-memory surfaces; native adapter compilation is allowed against exact references, without executing the adapter or either game DLL. Live capability selection, transport, packaging, installation and campaign remain later gates. Existing 0.8.0 production source, wire/output contracts and artifact identity remain frozen.

Tooling note: the first disposable inspector build used a fresh CLI home before the certificate-suppression variable was supplied. The SDK emitted a development-certificate installation message and a CSSM error. No trust command, credential/keychain inspection or follow-up certificate action was performed, so this report does not assert that no certificate-side effect occurred. Subsequent builds explicitly suppress certificate generation and use isolated CLI/package directories with offline restore.

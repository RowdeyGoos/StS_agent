# Shop/event bounded static result

Date: 2026-09-05. Evidence: metadata and selected IL only. The independently
reviewed follow-up selected 21 types and 38 actual method bodies within the
60/160 ceiling. Each extension was selected before inspection. Exact original,
final-selector, actual-signature and disposable-output hashes are preserved in
[the selection record](PHASE_1_SHOP_EVENT_API_SELECTION.json). No raw target IL
or content corpus is retained in the repository.

The inspector reused Program.cs
89dac8133d430c5a2065707a5a721e889f25e7e4b061ee2a7bf21b04b95a401c,
MetadataNames.cs
f7b481088f436e9ada05fc269101cd98b05326122798ff6043eeab8286517d23
and IlDecoder.cs
58a15d83f6b97916ab5f63b2b765f29cd8d46e380d5a270bf8c91dd333d25933.
It was rebuilt offline with SDK 9.0.303 in fresh disposable scratch, with
certificate generation suppressed. PEReader consumed only verified byte images
of the pinned arm64 sts2.dll and GodotSharp.dll; target assemblies were never
loaded or executed.

## Selected behavior facts

- Merchant card Hitbox ForceClick emits Released, while the card purchase
  wiring listens to MouseReleased. That proposed route would not purchase.
  The retained NMerchantCard's inherited public _GuiInput accepts an
  InputEventAction with Action=MegaInput.select and Pressed=true, routing once
  to OnSelected. MegaInput.select is public static readonly StringName.
  Input allocation and invocation follow the action reservation; disposal is
  guaranteed. No global input, debug input, hover synthesis or private dispatch
  is selected.
- The rendered %CostLabel is a MegaLabel whose inherited Label.Text ultimately
  uses the normal native getter. MerchantEntry.Cost may invoke a price hook and
  is excluded from observation. Exact rendered canonical decimal is used.
- CardCreationResult.Card is a public zero-argument getter. PurchaseCompleted
  success on the retained entry follows acquisition/debit/stock and awaited
  AfterItemPurchased handling. Signal alone is insufficient; controller
  reconciliation also requires exact card/deck/gold/stock facts.
- Inventory Back uses its separately proven Released-to-Close route.
  InventoryClosed restores Merchant and Proceed controls. Closing inventory
  and leaving the room therefore remain separate actions.
- Merchant Proceed may encounter a tutorial. MerchantFtueCheck's excluded
  SaveManager callees were not followed. The bridge performs no profile/FTUE
  query; only an action-bound open/travel-enabled/nontraveling same-map
  poststate resolves. Intercepted or unsupported transitions stop without
  retry or dismissal.
- MegaRichTextLabel.Text uses RichTextLabel.Text and its normal native getter.
  The projection is exact current label source, potentially BBCode and LF,
  not parsed effects or plain glyphs.
- The selected EventOption constructor confirms the final singleton PROCEED
  flag. Its chosen callback is scheduled; normal ForceClick return alone
  proves only dispatch. NEventRoom.Proceed enables travel and opens the global
  map. Hooks can veto travel, so later map getters are still required.
- NEventRoom.Instance and NMapScreen.Instance resolve through the current NRun.
  Native adapters retain and revalidate those exact references. Item child
  completion does not itself complete the parent event.

No profile/save content, Steam Cloud state, operator files, endpoints, game
launch or live controls were accessed in this static follow-up. Encountered
excluded callees remained stopped dependencies. Native compilation is a
separate gate; these facts make no live-success claim.

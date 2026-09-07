# Generic event v2 removal preview mapping — result

2026-09-07. One new metadata-only invocation passed after independent scope/tool
review, using a clean environment. No target methods executed and no live or
profile operation occurred. The frozen prepared scope remains
[the scope document](PHASE_1_GENERIC_EVENT_V2_PREVIEW_SCOPE.md).

Root invoked the frozen capture.py with `env -i`, `PATH=/usr/bin:/bin`,
`TMPDIR=/private/tmp`, `DOTNET_CLI_TELEMETRY_OPTOUT=1`,
`DOTNET_MULTILEVEL_LOOKUP=0`, the main repository `.venv` Python with `-B -I -S`,
the pinned disposable dotnet, frozen three-file bundle, `--target`, and fresh
output root `/private/tmp/generic-removal-preview-v2-target-a`.

The retained `stdout.bin` is23108 bytes, SHA256
`f9404d721c4ba8824938ee0684ccf7fe21a885eda974bc986b825b986a82cf56`.
It contains exactly6 bodies,127 instructions,23 PreviewHolder method declarations,
and0 explicit MethodImpl rows; stderr is empty. The result hash was independently
recomputed before analysis. Target hash matches the scope.

The selected bodies close the public original-reference mapping:

- NCard.Create passes its original argument to set_Model at IL17; set_Model
  assigns that argument to `_model` at IL26; get_Model reads `_model` at IL1.
- PreviewHolder.Initialize passes its NCard argument to virtual NCardHolder.SetCard
  at IL67. Its complete23-method declaration set has no SetCard, CardNode or
  CardModel override/shadow; there are no explicit MethodImpl mappings.
- SetCard passes the same NCard to set_CardNode at IL21, whose IL2 stores it
  directly in the backing field read by the previously retained public getter.
- The previously retained public CardModel getter returns CardNode.Model.

Together with the retained removal PreviewSelection body, this supports reading
exact original identities from actual NPreviewCardHolder.CardNode.Model and
cross-checking CardModel. Runtime admission/control must still require exact
holder/card types, complete unique membership, unchanged candidate key/level,
reconciled selection receipts, and stable preview holder/card bindings before
Confirm. Static creation flow does not replace those runtime identity checks.

Some selected setter instructions refer symbolically to unrelated helpers
(including visual/model subscriptions and a SaveManager call). Their bodies and
content were neither followed nor executed. No recursive inspection was needed.
This result establishes the required API mapping for generic removal preview
implementation; it does not demonstrate a live event or broaden supported
families, event catalogs, cancellation, or scrolling.

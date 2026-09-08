# Off-screen card selection: retained-code verification

2026-09-08; baseline `c6da627`. Read-only analysis of retained pinned-game IL
and frozen G7 source. No game launch, target assembly capture, installed overlay,
profile access or live input. No frozen implementation was changed.

## Finding

Screen clipping alone is not a selection gate in the inspected managed input
path. An existing, clickable holder that remains bound to the intended card can
reach the selection callback through direct `_GuiInput(select)` without any
viewport test in these methods. This is conditional static evidence, not a
successful live off-screen selection or proof of every downstream native callee.

The grid uses a limited set of rows and can reassign their holders. Consequently,
not every card in the source deck necessarily has a holder at the same time.
An off-screen but allocated card and an unallocated card are different cases.
The latter needs scrolling/rebinding or a separately verified supported path.

## Evidence

All 15 retained JSONL files listed below were rehashed and matched
`PHASE_1_CARD_SELECTION_API_SELECTION.json` (`raw_output_hashes`). That catalog
preserves exact file hashes and pinned target identities. Files remain under
`/private/tmp/card-selection-static-qfocay2o/outputs/`; names have prefix
`sts2.il.MegaCrit.Sts2.Core.Nodes.` and suffix `.jsonl`.

- `Cards.Holders.NCardHolder._GuiInput`
- `Cards.Holders.NCardHolder.EmitPressed`
- `Cards.Holders.NCardHolder.get_CardModel`
- `Cards.Holders.NGridCardHolder.get_CardModel`
- `Cards.NCardGrid.OnHolderPressed`
- `Screens.CardSelection.NCardGridSelectionScreen.ConnectSignalsAndInitGrid`
- `Screens.CardSelection.NCardGridSelectionScreen.<ConnectSignalsAndInitGrid>b__7_0`
- `Screens.CardSelection.NDeckTransformSelectScreen._Ready`
- `Screens.CardSelection.NDeckTransformSelectScreen.OnCardClicked`
- `Cards.NCardGrid.InitGrid`
- `Cards.NCardGrid.CalculateRowsNeeded`
- `Cards.NCardGrid.AssignCardsToRow`
- `Cards.NCardGrid.get_CurrentlyDisplayedCardHolders`
- `Cards.NCardGrid_<>c.<get_CurrentlyDisplayedCardHolders>b__47_0`
- `Cards.NCardGrid.UpdateGridPositions`

`NCardHolder._GuiInput` calls the Godot base method, checks `_isClickable` and
CardNode, then tests the select action. The select branch plays a sound and calls
`CallDeferred(EmitPressed)` at IL65. It contains no coordinate, clipping or
viewport predicate. `EmitPressed` emits the holder itself. `InitGrid` connects
that signal to `OnHolderPressed`, which emits the grid HolderPressed signal.
`ConnectSignalsAndInitGrid` connects that signal to its callback, which reads
`holder.CardModel` and invokes `OnCardClicked`. The transform implementation
adds/removes the model from its selected set, changes its highlight, opens the
preview at the maximum, and refreshes confirmation. These inspected methods do
not insert a viewport gate into the selection path.

The press is deferred: the callback reads the holder's model at delivery time.
Reassignment between dispatch and callback can change that model. Exact holder,
card and screen identity checks must therefore survive any future geometry change.

`CalculateRowsNeeded` returns
`min(ceil((gridHeight + padding) / (cardHeight + padding)) + 2, totalRows)`.
The synchronous `InitGrid` body in the retained file allocates only the computed
rows and connects their holders; it does not allocate the entire deck regardless
of row count. `AssignCardsToRow` rebinds existing holders to row-start plus column,
marks occupied holders Visible=true and excess slots false.
`CurrentlyDisplayedCardHolders` simply flattens `_cardRows`; its lambda returns
each row unchanged. It is neither a geometric visibility filter nor a guarantee
that the entire source deck is represented.

## Current bridge and next step

Frozen `GenericEventV7TransformAdapter.DispatchCard` calls `_GuiInput` directly.
Its `CompleteVisibleLayout` nevertheless requires the complete card layout to fit
inside the grid. This is a bridge admission restriction, not a viewport condition
found in the inspected click path. The adapter also requires exact complete
expected-card coverage by unique holders. Removing the fit check alone cannot
make an unallocated card selectable. Its `IsVisibleInTree` checks must not be
conflated with the separate full-layout fit predicate.

The suggested ten-card setup was a way to stay within frozen admission, not a
native ten-card limit. The next development candidate is admission of a complete,
stable holder set even when some holders are clipped, with identity, legality,
deferred-callback and completion checks retained. Handling an incomplete holder
set is a separate scrolling/rebinding feature. Production changes require a new
successor; all 29 successors remain frozen.

The previous 15-card Aroma test stopped at `prepare_geometry` before child input.
Its screenshot does not establish exact dimensions, complete holder inventory,
or which geometry predicate failed. This audit does not retrospectively turn
that stop into a successful off-screen test.

Independent read-only review agreed with this distinction. Validation was hash
verification and inspection of retained method bodies and signal wiring; no
mocked test was presented as execution of the actual Godot runtime. Godot base
input, native event matching, signal/deferred delivery and the full selection
outcome remain a live verification gap. No game setup is needed now.

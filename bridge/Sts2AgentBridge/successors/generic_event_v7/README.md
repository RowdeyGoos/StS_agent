# Generic event v7 — variable-count transformation

Extends the generic event controller with positive variable-count transformations:
select between1 and8 cards according to the native minimum/maximum, optionally
finish selection early through the native preview control, then confirm the exact
previewed originals. Variable requests require native manual confirmation. Fixed
transformation, upgrades, removal, card rewards and singleton items are preserved.

The root selection-confirm button and final preview-confirm button are distinct.
Expected originals are reserved before early preview or the final automatic-max
selection, so a partially populated preview cannot authorize transformation.
The existing authoritative replacement journal verifies the selected-only effect.
Event names are ownership/test data, never a semantic registration catalog.

The outer protocol is generic_event_v7 with generic-event-v7 routes; transform
children use card_transform_v2. Ordinary card_selection_v1 and item_v1 engines
remain frozen. Limits, no uncertain retry, lineage and cumulative completion are
preserved. Optional selection, variable upgrades, scrolling, multiple-item rewards,
custom interactions and event combat remain outside this increment.

See the [contract](../../../../docs/PHASE_1_GENERIC_EVENT_V7_CONTRACT.md) and
[acceptance ledger](../../../../docs/research/PHASE_1_GENERIC_EVENT_V7_ACCEPTANCE.md).
This functional component is not an installable release and has no live v7 claim.
All27 predecessors and original bridge remain frozen; no game setup is needed.

## Offline validation

```sh
python -B bridge/Sts2AgentBridge/successors/generic_event_v7/check.py \
  --dotnet /absolute/path/to/dotnet \
  --game-data-dir /absolute/path/to/pinned/game/data \
  --scratch /private/tmp/a-new-generic-v7-gate
```

Use Python3.10+ and SDK9.0.303. Validation runs inert fixtures and actual native
adapters against those fixtures; production is compiled twice and never executed.
All build artifacts stay in disposable snapshots. No network restore or live
installation occurs.

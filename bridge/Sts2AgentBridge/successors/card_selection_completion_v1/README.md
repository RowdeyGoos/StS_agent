# Card selection completion v1

This corrective release changes only two projection branches in the frozen
card-selection native adapter. A completed selection with its overlay still
present is transient; a closed selector has no active preview metadata. The
unchanged core continues to require exact selected originals, deck effect and
parent completion before resolving the child and allowing parent Proceed.

All eleven predecessors remain frozen. The production assembly links 29 exact
predecessor sources and substitutes only the derived child adapter. Runtime,
wire, host, routes, budgets, config selection and game capabilities are unchanged:
Cheese adds two cards and ordinary rest Smith upgrades one. Other native event
operations remain unsupported.

The [accepted contract](../../../../docs/PHASE_1_CARD_SELECTION_COMPLETION_V1_CONTRACT.md)
and [acceptance ledger](../../../../docs/research/PHASE_1_CARD_SELECTION_COMPLETION_V1_ACCEPTANCE.md)
record the exact derivation, static evidence, original failing controls,
actual-adapter/core fixtures, candidate policy and release gates. Fixture success
is not live evidence, and this repair does not identify a discarded live reply.

The package keeps the accepted DLL/manifest names and uses the distinct artifact
root `/private/tmp/sts-card-selection-completion-v1-release`. Installation uses
`CARD-SELECTION-COMPLETION-V1-SMOKE-V1` and rejects every existing predecessor
state or operator/overlay. No source or artifact is overwritten or adopted.

Run the complete offline gate only with SDK9.0.303, the exact two pinned
compile-only references and a new temporary root:

```sh
python3 -B -I -S bridge/Sts2AgentBridge/successors/card_selection_completion_v1/check.py \
  --dotnet /absolute/path/to/pinned/dotnet \
  --game-data-dir /absolute/path/to/pinned/game/data \
  --scratch /private/tmp/a-new-card-completion-gate
```

No target or candidate assembly is executed by that gate. Live testing requires
after acceptance a new untouched rest site, not the previous uncertain action.
The fixed client runs once; normal quit, code-first quarantine, exact purge and
clean-base checks remain mandatory. Repeated unmodded relaunch is waived.

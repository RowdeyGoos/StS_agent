# Holder public-model projection result

2026-09-07. One reviewed [single-method invocation](PHASE_1_GENERIC_HOLDER_MODEL_SCOPE.md) passed; no retry or execution of target code.

- Output `/private/tmp/generic-holder-model-target-a/stdout.bin`,4390bytes.
- SHA256 `10b1c72bda7716253288bdf7c81fc231f86d1f85883c39d2a2a391b057ad2c7a`.
- Exactly1 private instance method,31 instructions; stderr empty.
- Root and independent reviewer verified the hash, scope and interpretation.

At IL0–14, `UpdateCardModel` reads `CardNode.Model` and stores the exact reference
in `_baseCard`. If upgradable, a separate `MutableClone` is stored in
`_upgradedCard` at IL39. The examined refresh therefore preserves the original
public-model reference and keeps its upgrade preview separate. No evidence here
establishes a live candidate-admission defect or justifies changing its guards.

The preceding [seven-body inspection](PHASE_1_GENERIC_CANDIDATE_HOLDER_RESULT.md)
and this single-body inspection resolve the examined reassignment/projection
chain. Scene runtime subtypes and the individual live candidate predicate remain
unverified. Select a reviewed diagnostic-only successor with finite individual
candidate failure codes; preserve identity, ownership and existing evaluation
order. No more target inspection is authorized by these closed invocations.
Game closed, all generic campaigns closed, no overlay or credential remains.

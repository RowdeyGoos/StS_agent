# Generic candidate holder static result

2026-09-07. One invocation of the independently reviewed [scope](PHASE_1_GENERIC_CANDIDATE_HOLDER_SCOPE.md) passed. No retry or target execution occurred.

- Retained output: `/private/tmp/generic-candidate-holder-target-a/stdout.bin`,25986bytes.
- SHA256: `c6619157d1f17aa11bac7b4ac553b8963541713784a70b8e3924f64be2e0b39b`.
- Exactly7 selected method bodies,181 instructions; stderr empty.
- Root and independent reviewer rehashed and interpreted the result.

`NCardHolder.ReassignToCard` assigns the supplied original to `CardNode.Model`,
then invokes virtual `OnCardReassigned`. The grid-holder override calls
`UpdateCardModel` and `UpdateName`. `NGridCardHolder.Create` also calls
`UpdateCardModel`. None of these selected bodies directly establishes the
`_baseCard` projection returned by the public `CardModel` getter.

`ConnectSignals` obtains the hitbox through `GetNode` and stores it in the
`NClickableControl` field. This does not prove its exact concrete runtime type.
The seven-body result establishes no specific cause of live `prepare_candidates`;
exact-type and original-reference guards remain unchanged.

The remaining relevant model projection is `UpdateCardModel`. Search retained
evidence before proposing a separate single-method inspection. No automatic
callee traversal, asset inspection, generated callback inspection, launch or
profile/save/Cloud access is included. Game closed; all generic campaigns closed.

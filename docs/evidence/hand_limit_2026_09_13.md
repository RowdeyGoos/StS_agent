# Ordinary draw and hand-limit source check, 2026-09-13

The game engine now limits ordinary draws to ten cards in hand. Excess requested
draws leave cards in their current piles. A full or overfull hand does not trigger
a draw-pile refill or consume shuffle RNG. Capacity is checked again for each card.

## Source identity and inspection

- Target: v0.107.1, Steam build 23811903; [binary identity](../../manifests/game-builds/sts2-steam-main-build-23811903-macos-universal.json).
- Assembly SHA-256: `e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
- Reference: `/private/tmp/sts-current-release-final/references/sts2.dll`.
- Implementation base: `206132a` on `codex/headless-integration`.

Reused the bounded static scanner described in the
[starter-card source check](strike_upgrade_2026_09_13.md), with exact selectors
`MegaCrit.Sts2.Core.Commands.CardPileCmd` and
`MegaCrit.Sts2.Core.Entities.Cards.CardPile` and their nested types.
The scanner retained its hash, symlink, file-size, type-count and method-size guards. The existing
.NET 9.0.303 runtime executed the metadata reader, not native game code. It decoded
33 types / 121 method bodies. Raw output is in
`/private/tmp/sts-headless-hand-limit-native/il.json` while scratch storage exists;
the anchors below remain reproducible without that file.

## Inspected anchors

Tokens and IL offsets are decimal for the exact assembly above.

| Method | Token | Relevant findings |
| --- | --- | --- |
| `CardPile.get_MaxCardsInHand` | 100696501 | Offset 0 returns constant 10. |
| `CardPileCmd.<Draw>d__16.MoveNext` | 100712233 | 342–370 computes `max(0, limit - hand.Count)`; 372–393 returns when no capacity remains, before a shuffle. |
| Same draw body | 100712233 | Checks draw availability at 431 before `ShuffleIfNecessary` at 453; checks again at 552, takes the next card at 574 and checks hand capacity at 611–616 before moving it at 653. |
| Same draw body | 100712233 | 936–964 recomputes capacity after the draw/after-draw work; 990–1006 continues only while requested draws and capacity remain. |
| `CheckIfDrawIsPossibleAndShowThoughtBubbleIfNot` | 100697344 | 0–35 checks draw/discard availability; 74–96 compares hand count to the limit; 98–134 reports full hand and returns false. |
| `CardPileCmd.<ShuffleIfNecessary>d__19.MoveNext` | 100712247 | 44–70 skips shuffling unless draw is empty and discard nonempty; 177 invokes `Shuffle`. |

## Implementation and limits

[Deck.draw](../../game/headless/core/deck.py) checks the game-owned capacity before
moving a card or calling the existing refill. The existing refill still consumes
one Python shuffle of the discard pile when it is actually needed. No state field,
public projection, encoder vocabulary or per-feature profile was added.

[Direct cases](../../tests/headless/test_draw_rules.py) cover below/exact/overflow
requests, full and already-overfull hands, a last-slot draw that must not reshuffle,
a multi-draw crossing the pile boundary, zero/empty/invalid requests, card identity
and exhaust conservation, card-play draws and JSON continuation. RNG comparisons
verify the existing Python stream's consumption, not native seeded parity.

This verifies ordinary draw capacity and when refilling is allowed. It does not
certify native shuffle permutations, fractional draw requests, draw-prevention
powers, after-draw triggers, generation directly into a full hand, retained cards
or all card-resolution ordering. Native draw hooks appear before/after the inspected
operations and remain separate implementation work. The Python API continues to
accept nonnegative integer draw counts and reject negative ones; native decimal
normalization is outside this slice. Existing overfull authored states are left
intact and further draws stop; this is not a new route to create oversized hands.

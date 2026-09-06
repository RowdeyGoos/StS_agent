# Phase 1 event card preview result

- Date: 2026-09-06
- Status: capture failed validation; complete private diagnostic bytes reviewed
- Reviewed scope SHA-256:
  `3546c522bcbce17dfdcb18daca8dd1531514f6c5b1f87a28d38368f5e3a88bb7`
- Reviewed capture wrapper SHA-256:
  `8f823279dc59938b87d6e30d8753b40259343878613beb583db211d1be1cbb49`

## Invocation result

The one authorized metadata-only invocation inspected the exact pinned game
image without loading or executing it. The capture wrapper exited 1 and emitted
no summary. No retry or further target read occurred.

The create-only private output directory is
`/private/tmp/event-card-preview-capture-235342f6df5b4c1ba424a6aa`:

- `stdout.bin`: 14,163 bytes, mode `0600`, SHA-256
  `587b2ee8484f2e372fb317416c94f048e47833d2e35f984e6a75dc62850e0857`;
- `stderr.bin`: 0 bytes, mode `0600`, SHA-256
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

The scanner completed and wrote one complete JSON object followed by a newline.
It identifies the pinned image SHA-256
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`
and contains 3 implementers, 0 `MethodImpl` rows, 8 bodies and 82 decoded
instructions. All exact keys, nested shapes, counts and bounds pass the accepted
wrapper's schema checks before its final canonical-byte comparison.

The wrapper rejected only its final canonical-byte comparison. The .NET JSON
serializer encoded the `+` in the member identity
`Godot.PackedScene+GenEditState` as `\u002B`; the Python canonical encoder used
by the wrapper expects a literal `+`. This is one escape occurrence and a
five-byte representation difference. The persisted bytes were not rewritten or
normalized. The invocation remains a failed capture rather than a successful
scoped result.

## Bounded diagnostic disposition

The complete persisted evidence is reviewable as failure diagnostic data. It
enumerates the exact concrete `ICardScope` candidates `RunState`, `CombatState`
and `NullRunState`. `RunState.CloneCard` and `CombatState.CloneCard` call
`AbstractModel.ClonePreservingMutability`, cast the result, add it to their
scope and return it. Neither body calls `CardModel.CreateClone` nor assigns the
returned model's `_cloneOf` field. `NullRunState.CloneCard` throws.

The separate `CardModel.CreateClone` body calls `ICardScope.CloneCard` and then
assigns `_cloneOf` to the source card. `CardModel.get_CloneOf` only returns that
field, and `get_IsClone` tests it for null. The retained multi-upgrade preview
path calls `ICardScope.CloneCard` directly, so these rows do not prove that a
preview model's public `CloneOf` identifies the exact selected original.

Accordingly, this evidence does not authorize a multi-upgrade native mapping or
production caller row. The accepted single-upgrade Aroma of Chaos and Sapphire
Seed rows use their separately proved single-preview original and are
unaffected. No listener, package, installation, live campaign, profile/save,
Cloud, network or gameplay action was included.

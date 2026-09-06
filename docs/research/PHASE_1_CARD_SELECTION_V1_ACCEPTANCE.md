# Card selection v1 acceptance ledger

Date: 2026-09-06. Baseline `c56d579f063818c330530090a54dc6e9334b0841`,
23cf checkout, `codex/phase1-actor-ready-integration`. This ledger records the
new isolated `card_selection_v1` component. It does not reopen any closed live
campaign or alter predecessor acceptance.

## Scope and evidence levels

The user selected event add/remove/upgrade/transform support, including multiple
cards, and ordinary rest upgrades of exactly one card. The pure core models all
four operations with explicit minimum/maximum cardinality and native commit
modes. Initially selected native policies are Cheese/Gorge add-two-of-eight and
ordinary SmithCount=1 upgrade-one. Other native event callers, removal/transform,
multi-card upgrade and scrolling remain unselected. Generic fixture support is
not a claim that those native callers are implemented.

The [contract](../PHASE_1_CARD_SELECTION_V1_CONTRACT.md) specifies immutable
parent/card bindings, complete candidate/deck witnesses, selection task and typed
effect completion, no uncertain retry, and the separate Proceed/map handoff.
The [static result](PHASE_1_CARD_SELECTION_STATIC_RESULT.md) and
[exact selection record](PHASE_1_CARD_SELECTION_API_SELECTION.json) contain only
sanitized metadata facts and hashes. No game/Godot code was executed by static
inspection or pure fixtures.

## Development and review record

Core, native adapter, parent flow and C#/Python wire/controller are implemented
in separate owned directories. Review found and corrected:

- missing explicit full-deck projection evidence;
- base-grid geometry assumptions without exact-type admission;
- ambiguity between parent initialization waiting and an admitted child;
- premature child creation before the public selector projection is ready;
- public single-player binding for the rest parent without private owner access.

The final offline aggregate passed from one verified source snapshot:

| Suite | Result |
| --- | --- |
| Pure card core | 16 authored scenario groups |
| Native admission rules | 28 predicate assertions |
| Parent flow | 12 authored scenario groups |
| Parent native rules | 5 authored scenario groups |
| Actual parent adapter linked against inert stubs | 8 authored scenario groups |
| C# wire/service | 11 authored scenario groups |
| Python host | 13 unit tests |
| Actual C#/Python child-to-parent composition | 2 complete scenarios |
| Project/build boundary mutations | 15 cases |

Both native assemblies compiled twice in separate clean physical snapshots with
identical outputs. The child adapter is 24,064 bytes, SHA256
`b7b6cff562a93d4b72de0bd39d418404425d356c231093e53505d36e7196c0ca`;
the parent adapter is 30,208 bytes, SHA256
`a069b1b640f904dc2c9e8a1f937587d2635ff2a27d668eaab396d595587b7403`.
The pinned game and Godot assemblies were compile-only references and were never
executed. These component DLLs are not an installable release.

The canonical result is
`/private/tmp/sts-card-selection-v1-final-gate-a1/result.json`. All nine frozen
predecessor source inventories and the original 48-file bridge inventory passed
the preservation gate. The new source manifest covers exactly 40 files plus the
manifest itself:

- Contract SHA256: `af8125ba2dd7bd8d7df85144f5a275d20a347ca7d4fe5bd5e666e53b3f57186c`.
- Manifest SHA256: `ca4e18dbb66520481881ea86a91925162593f8496c7abccc061a31f1c319a0ac`.
- Inventory SHA256: `51135dfb6749d58b897bb4670ffa709ca5b756873464c9e045f2ba80f87bfc64`.

Final repository regression passed **1,192 tests in 107.55 seconds**. An earlier
collection attempt stopped because a new `host_tests` package marker collided
with a frozen predecessor's package name. Removing only that new marker fixed
collection; the completed regression includes all 13 new host tests.

The [independent review](PHASE_1_CARD_SELECTION_V1_REVIEW.md) records the exact
source and boundary disposition. The final create-only source generator and
aggregate checker also passed independent review. Preserve every byte of this
new component along with all nine predecessors.

## Outstanding gates and operational state

The functional component has passed its offline gate. The separately isolated
[release contract](../PHASE_1_CARD_SELECTION_RELEASE_V1_CONTRACT.md) defines the
next production and operational composition; its own identities and readiness
remain pending that implementation and review.

This component has no game listener, secure operator lifecycle, launch/install
manager or live CLI. Production frame/transport composition, exact artifact
verification, package/campaign tooling and their fixtures are required before
live testing. No release readiness or live card-selector success is claimed.

No campaign was started for this development. The prior event campaign's cleanup
completed at 2026-09-06 11:06:16 UTC and remains closed. No profile/save filesystem,
Steam Cloud, retained live corpus, remote Git, discarded response reconstruction,
or retry of any historical uncertain action occurred. No game setup is currently
needed. Future live setup must name the exact untouched parent screen, beginning
with an ordinary rest site showing Smith or Cheese's initial Gorge choice.

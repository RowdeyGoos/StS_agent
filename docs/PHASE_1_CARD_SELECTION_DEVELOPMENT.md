# Card-selection static discovery and development scope

Date: 2026-09-06. Baseline c56d579f063818c330530090a54dc6e9334b0841 in the
23cf integration checkout. The user requested event card addition, transformation,
upgrade and removal, rest-site upgrade, and explicitly required multiple-card
event selection while rest upgrades select exactly one card. This authorizes
necessary static/repository development; prior capability exclusions remain
frozen for prior releases and do not prohibit this new isolated successor.

Use only the manifest-pinned arm64 sts2.dll and GodotSharp.dll, hashes
respectively e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18
and 0e4897ecdfb31456a97c7d8028dfb8d7dbdc632e2f73fc9b438d7b266a139289.
The accepted metadata inspector's bounded-image, physical-path and pre-PEReader
hash checks remain unchanged. Rebuild offline in fresh disposable scratch,
without loading or executing target assemblies or initializing Godot.

A fixed name-only catalog first selects non-generated types in Core whose names
identify card selection screens/commands/preferences, card holders, card-pile
commands, or rest-site room/options. Regex and inspector hash are recorded before
invocation. One global catalog cap of 80 results, with overflow fail-closed and no truncation. Exact type/method
selectors must be frozen before every member/body invocation. All actual selected
types and overloaded/generated bodies count against this increment's aggregate
80-type/200-body ceilings. Each body is limited to 2500 IL instructions. Generated
methods must belong to a selected method/type and direct followups must establish
public UI projection, selection/cardinality/control/confirmation, parent binding,
or exact deck effect/completion. Encountered profile/save/Cloud/seed/history/
platform/network dependencies are not followed. No content-wide event enumeration.

Only sanitized member signatures, behavior facts, selector/inspector/output
hashes are committed; raw IL remains disposable. CLR accessibility alone does
not establish actor visibility. Selection and effect reconciliation are separate:
required number, selection state, explicit confirmation versus native auto-commit,
and exact operation-bound completion must be proven. No generic early confirmation
or one-card assumption. Rest upgrade requires exactly one card; event cardinality
comes from proven native semantics, including any minimum/maximum distinction.
Do not infer success from overlay disappearance or a deck-count delta alone.

The coordinator owns this scope, inspector, shared contract and integration docs.
Read-only parallel repository/native-fact audits precede a reviewed contract.
Implementation ownership will be assigned only after that contract is accepted.
New sources live in a sibling successor tree with independent source identity;
all nine accepted successor trees, old 0.8.0 sources and frozen contracts remain
byte-exact. Synthetic tests inject surfaces and never execute game/Godot code.

No live launch, control, endpoint/credential read, install/config write, profile/
save filesystem access, Cloud changes, retained live corpus, remote Git, uncertain
action retry or discarded response reconstruction belongs to this discovery.
Any later live campaign needs completed review/build/verifier/fixture gates and
an exact game-state setup. No campaign is currently active; prior cleanup stands.

## Frozen initial catalog and independent review

Inspector Program.cs SHA-256:
`3d5f811b9cc25b684d0e4cdfd99f200d2fb322bc5686fd7f6a6274968ded3b08`.
The exact name-only predicate is:

```text
^MegaCrit\.Sts2\.Core\.(?!.*(?:Profile|Save|Cloud|Seed|History|Steam|Platform|Network))[^+]*(?:Card[^+]*Select|Select[^+]*Card|CardHolder|CardPileCmd|RestSite)[^+]*$
```

Independent read-only review accepted discovery after this exact predicate and
global catalog cap were recorded. Direct seed/RNG observation remains excluded;
a proven retained native transform control may cause the game to use its own
RNG downstream. Do not follow that excluded dependency or predict replacements.
Event/rest actions must use revalidated retained public controls, never direct
card-pile commands or private methods. Command bodies are static effect-ordering
evidence only. Exact operation-bound effect witnesses, finite cardinality,
parent/control/card identity and no later-overlay adoption remain contract gates.

### Parent policy discovery refinement

Independent review selects statically witnessed parent-bound policies, not a
private-field read or a count guess from button visibility. The first named
parent is the already observed Room Full of Cheese / Gorge addition of two
cards; ordinary smith is the rest upgrade-one entry. Other operations remain
unselected in production until their exact parent callsites are established.
The shared pure selector may model all requested operations behind that gate.
To resolve the displayed event's exact type name, a second name-only catalog
predicate is frozen before invocation:
`^MegaCrit\.Sts2\.Core\.Models\.Events\.[^+]*Cheese[^+]*$`.
It adds to the same aggregate 80-name/type and 200-body ceilings. No event-wide
content enumeration is selected. Inspector v2 changes only that predicate;
its hash is recorded with the selection artifact before execution.

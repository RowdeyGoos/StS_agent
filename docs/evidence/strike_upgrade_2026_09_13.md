# Strike upgrade source check, 2026-09-13

The first HF-13 slice implements ordinary Ironclad Strike at 6 damage and Strike+
at 9 damage, both costing 1 energy and targeting one enemy. The permanent upgrade
is limited to one level for this card. These numbers were checked against the
pinned game assembly using static metadata/IL inspection. Combat, persistence and
replay tests exercise the Python implementation; no native game execution or
live differential comparison was performed.

## Source identity and method

- Game: v0.107.1, Steam build 23811903, macOS arm64; see the
  [pinned manifest](../../manifests/game-builds/sts2-steam-main-build-23811903-macos-universal.json).
- Assembly: `sts2.dll`, SHA-256
  `e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
- Repository base: `73348735724e80d5898a28aa0786f4f0d39f6cf6`.
- Retained reference read: `/private/tmp/sts-current-release-final/references/sts2.dll`.
- Toolchain: existing .NET SDK 9.0.303, `PEReader`, and the repository's
  [metadata names](../../bridge/Sts2AgentBridge/tools/Sts2AgentBridge.Verifier/MetadataNames.cs)
  and [IL decoder](../../bridge/Sts2AgentBridge/tools/Sts2AgentBridge.Verifier/IlDecoder.cs).

A scratch copy of the existing [static scanner](event_interactions_2026_09_09/scan.cs)
was restricted to exact selected type names and their nested types, instead of its
ordinary event-namespace selection. It retained the assembly hash, symlink and
size guards. It did not load or execute game types. Selected roots were
`MegaCrit.Sts2.Core.Models.Cards.StrikeIronclad`, `DefendIronclad`, `Bash`, followed
by `MegaCrit.Sts2.Core.Localization.DynamicVars.DynamicVar` and
`MegaCrit.Sts2.Core.Models.CardModel`. Only Strike and its immediate shared helpers
support the implementation claim here; the other cards remain unsupported upgrades.
The scanner build passed with no warnings or errors. Raw selected IL remains in
`/private/tmp/sts-headless-hf13-native/il.json` and `helpers.json` while scratch
storage exists. It is not a runtime fixture or a committed game-source dump.

The method tokens below are decimal metadata tokens for this exact assembly;
offsets are decimal IL offsets. They provide reproducible inspection anchors with
any metadata reader without depending on those temporary files.

## Inspected anchors

| Method | Token | Relevant offsets and finding |
| --- | --- | --- |
| `StrikeIronclad..ctor` | 100693405 | Offset 1 supplies energy cost 1 to `CardModel..ctor(Int32,CardType,CardRarity,TargetType,Boolean)` at 6. |
| `StrikeIronclad.get_CanonicalVars` | 100693407 | Offset 0 supplies 6, converted to Decimal at 1 and passed to `DamageVar..ctor` at 7. |
| `StrikeIronclad.OnUpgrade` | 100693409 | Gets Damage at 6; supplies 3 at 11 and calls `DynamicVar.UpgradeValueBy(Decimal)` at 17. No cost mutation appears in this override. |
| `DynamicVar.get_BaseValue` | 100694850 | Loads `_baseValue` at 1. |
| `DynamicVar.UpgradeValueBy` | 100694863 | Reads BaseValue at 2, adds the argument with Decimal addition at 8 and writes BaseValue at 13. Thus the ordinary damage becomes 6 + 3 = 9. |
| `CardModel.get_MaxUpgradeLevel` | 100682151 | Returns 1 at offsets 0–1; Strike has no override. |
| `CardModel.UpgradeInternal` | 100682239 | Increments CurrentUpgradeLevel at 7–17, dispatches OnUpgrade at 23, then recalculates dynamic variables at 34. |
| `StrikeIronclad.OnPlay` | 100693408 | Dispatches the async play body below. |
| `StrikeIronclad+<OnPlay>d__5.MoveNext` | 100710839 | Requires `CardPlay.Target` at 26; reads damage BaseValue at 52; calls `DamageCmd.Attack` at 57, `FromCard` at 63 and `Targeting(Creature)` at 79. |

## Implemented boundary and limits

[Card rules](../../game/engine/card_upgrades.py) preview and upgrade exactly one
persistent Strike at an idle, living combat boundary, preserving its ID and deck
position without RNG or ID allocation. This programmatic operation is not a
rest-site action or proof that an arbitrary game upgrade source is legal.

[CombatV0Backend](../../game/backends/headless/combat_v0_backend.py) opts in with
`card_profile="strike_upgrade_v1"`. Its content, rules, backend and projection
identities differ from the unchanged default profile. The public contract already
supports `upgraded`; the existing public actor encoder already encodes that flag.
The optional legacy combat encoder adds a `Strike+` vocabulary entry only within
this profile. Existing legacy checkpoint dimensions are not compatible with that
expanded encoder. Accepted datasets and snapshots still require matching pins.

The [regression cases](../../tests/backends/headless/test_strike_upgrade.py) cover
same-ID mutation among duplicate cards, preview immutability, base/upgraded damage
and energy, public flags and legal masks, target selection, private identity
exclusion, discard/reshuffle, search cloning, stale action rejection, atomic
unsupported upgrades, profile separation, exact snapshot continuation and two
completed combats with the same permanent deck.

Enemy rules, RNG, damage/status ordering, relic/enchantment hooks and the remaining
card pool still use the reduced simulator's evidence level. This isolated source
check does not establish their native parity, a full run, upgrade-card selection
UI, reward upgrades or training readiness for this profile.

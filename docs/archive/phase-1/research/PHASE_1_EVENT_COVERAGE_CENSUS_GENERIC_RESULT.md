# Phase 1 event coverage census generic result

- Date: 2026-09-06
- Invocation time: 2026-09-06T16:21:23Z
- Status: passed; finite pinned-build event denominator established
- Scope: `PHASE_1_EVENT_COVERAGE_CENSUS_GENERIC_SCOPE.md` SHA-256
  `0f83322a84851242e5bce9d391932182e78419f0777db6044e060404834f4c4e`
- Independently accepted disposable source manifest SHA-256:
  `25e2e3c64b82b100764b01ec9b1f98b813ed5f25c92455d1089641dbc9e7be8f`

## Invocation boundary

After independent review accepted the corrected generic-ancestry scope, the
tool was rebuilt with .NET SDK 9.0.303 and invoked exactly once in pinned
mode. Its file-shape, link, size and SHA-256 gates passed before `PEReader`
constructed a metadata view. The target assembly was read as a bounded byte
image and zeroed by the reviewed tool; it was never loaded or executed.

The process exited zero. Stdout is 11,197 bytes including its trailing LF,
SHA-256 `ef86bb9489f983d0bf40c8103226f55d26d39c82245739e08313574d8f78c01f`.
Stderr is empty, SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
No second target invocation or target read was made.

## Exact sanitized result

The following is the complete canonical stdout line. The recorded hash above
also covers the trailing LF after this JSON object.

```json
{"schema_version":1,"evidence":"metadata_only","sha256":"e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18","counts":{"events":68,"event_concrete":68,"custom":1,"custom_concrete":1,"layouts":2,"layout_concrete":2,"overall":71},"rows":[{"kind":"custom","name":"MegaCrit.Sts2.Core.Nodes.Events.Custom.NFakeMerchant","base":"Godot.Control","interfaces":["MegaCrit.Sts2.Core.Nodes.Events.ICustomEventNode","MegaCrit.Sts2.Core.Nodes.Screens.ScreenContext.IScreenContext"],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.AbyssalBaths","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.Amalgamator","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.AromaOfChaos","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.BattlewornDummy","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.BrainLeech","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.Bugslayer","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.ByrdonisNest","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.ColorfulPhilosophers","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.ColossalFlower","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.CrystalSphere","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.Darv","base":"MegaCrit.Sts2.Core.Models.AncientEventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.DenseVegetation","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.DeprecatedAncientEvent","base":"MegaCrit.Sts2.Core.Models.AncientEventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.DeprecatedEvent","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.DollRoom","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.DoorsOfLightAndDark","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.DrowningBeacon","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.EndlessConveyor","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.FakeMerchant","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.FieldOfManSizedHoles","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.GraveOfTheForgotten","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.HungryForMushrooms","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.InfestedAutomaton","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.JungleMazeAdventure","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.LostWisp","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.LuminousChoir","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.MorphicGrove","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.Neow","base":"MegaCrit.Sts2.Core.Models.AncientEventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.Nonupeipe","base":"MegaCrit.Sts2.Core.Models.AncientEventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.Orobas","base":"MegaCrit.Sts2.Core.Models.AncientEventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.Pael","base":"MegaCrit.Sts2.Core.Models.AncientEventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.PotionCourier","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.PunchOff","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.RanwidTheElder","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.Reflections","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.RelicTrader","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.RoomFullOfCheese","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.RoundTeaParty","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.SapphireSeed","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.SelfHelpBook","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.SlipperyBridge","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.SpiralingWhirlpool","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.SpiritGrafter","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.StoneOfAllTime","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.SunkenStatue","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.SunkenTreasury","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.Symbiote","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.TabletOfTruth","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.Tanx","base":"MegaCrit.Sts2.Core.Models.AncientEventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.TeaMaster","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.Tezcatara","base":"MegaCrit.Sts2.Core.Models.AncientEventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.TheArchitect","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.TheFutureOfPotions","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.TheLanternKey","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.TheLegendsWereTrue","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.ThisOrThat","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.TinkerTime","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.TrashHeap","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.Trial","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.UnrestSite","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.Vakuu","base":"MegaCrit.Sts2.Core.Models.AncientEventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.WarHistorianRepy","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.WaterloggedScriptorium","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.WelcomeToWongos","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.Wellspring","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.WhisperingHollow","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.WoodCarvings","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"event","name":"MegaCrit.Sts2.Core.Models.Events.ZenWeaver","base":"MegaCrit.Sts2.Core.Models.EventModel","interfaces":[],"abstract":false},{"kind":"layout","name":"MegaCrit.Sts2.Core.Nodes.Events.NAncientEventLayout","base":"MegaCrit.Sts2.Core.Nodes.Events.NEventLayout","interfaces":[],"abstract":false},{"kind":"layout","name":"MegaCrit.Sts2.Core.Nodes.Events.NCombatEventLayout","base":"MegaCrit.Sts2.Core.Nodes.Events.NEventLayout","interfaces":[],"abstract":false}]}
```

## Coverage inventory

| Category | Total | Concrete |
| --- | ---: | ---: |
| Event models | 68 | 68 |
| Custom event nodes | 1 | 1 |
| Event layouts | 2 | 2 |
| Aggregate category rows | 71 | 71 |

All 68 event rows are concrete. Their exact sorted identities and immediate
bases are:

| Event type | Immediate base |
| --- | --- |
| `MegaCrit.Sts2.Core.Models.Events.AbyssalBaths` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.Amalgamator` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.AromaOfChaos` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.BattlewornDummy` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.BrainLeech` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.Bugslayer` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.ByrdonisNest` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.ColorfulPhilosophers` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.ColossalFlower` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.CrystalSphere` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.Darv` | `MegaCrit.Sts2.Core.Models.AncientEventModel` |
| `MegaCrit.Sts2.Core.Models.Events.DenseVegetation` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.DeprecatedAncientEvent` | `MegaCrit.Sts2.Core.Models.AncientEventModel` |
| `MegaCrit.Sts2.Core.Models.Events.DeprecatedEvent` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.DollRoom` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.DoorsOfLightAndDark` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.DrowningBeacon` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.EndlessConveyor` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.FakeMerchant` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.FieldOfManSizedHoles` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.GraveOfTheForgotten` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.HungryForMushrooms` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.InfestedAutomaton` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.JungleMazeAdventure` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.LostWisp` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.LuminousChoir` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.MorphicGrove` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.Neow` | `MegaCrit.Sts2.Core.Models.AncientEventModel` |
| `MegaCrit.Sts2.Core.Models.Events.Nonupeipe` | `MegaCrit.Sts2.Core.Models.AncientEventModel` |
| `MegaCrit.Sts2.Core.Models.Events.Orobas` | `MegaCrit.Sts2.Core.Models.AncientEventModel` |
| `MegaCrit.Sts2.Core.Models.Events.Pael` | `MegaCrit.Sts2.Core.Models.AncientEventModel` |
| `MegaCrit.Sts2.Core.Models.Events.PotionCourier` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.PunchOff` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.RanwidTheElder` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.Reflections` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.RelicTrader` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.RoomFullOfCheese` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.RoundTeaParty` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.SapphireSeed` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.SelfHelpBook` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.SlipperyBridge` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.SpiralingWhirlpool` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.SpiritGrafter` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.StoneOfAllTime` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.SunkenStatue` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.SunkenTreasury` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.Symbiote` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.TabletOfTruth` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.Tanx` | `MegaCrit.Sts2.Core.Models.AncientEventModel` |
| `MegaCrit.Sts2.Core.Models.Events.TeaMaster` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.Tezcatara` | `MegaCrit.Sts2.Core.Models.AncientEventModel` |
| `MegaCrit.Sts2.Core.Models.Events.TheArchitect` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.TheFutureOfPotions` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.TheLanternKey` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.TheLegendsWereTrue` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.ThisOrThat` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.TinkerTime` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.TrashHeap` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.Trial` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.UnrestSite` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.Vakuu` | `MegaCrit.Sts2.Core.Models.AncientEventModel` |
| `MegaCrit.Sts2.Core.Models.Events.WarHistorianRepy` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.WaterloggedScriptorium` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.WelcomeToWongos` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.Wellspring` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.WhisperingHollow` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.WoodCarvings` | `MegaCrit.Sts2.Core.Models.EventModel` |
| `MegaCrit.Sts2.Core.Models.Events.ZenWeaver` | `MegaCrit.Sts2.Core.Models.EventModel` |

The non-event category rows are:

| Category | Type | Immediate base | Declared interfaces |
| --- | --- | --- | --- |
| custom | `MegaCrit.Sts2.Core.Nodes.Events.Custom.NFakeMerchant` | `Godot.Control` | `MegaCrit.Sts2.Core.Nodes.Events.ICustomEventNode`, `MegaCrit.Sts2.Core.Nodes.Screens.ScreenContext.IScreenContext` |
| layout | `MegaCrit.Sts2.Core.Nodes.Events.NAncientEventLayout` | `MegaCrit.Sts2.Core.Nodes.Events.NEventLayout` | none |
| layout | `MegaCrit.Sts2.Core.Nodes.Events.NCombatEventLayout` | `MegaCrit.Sts2.Core.Nodes.Events.NEventLayout` | none |

## Disposition

The pinned build contains 68 concrete event-model types in the exact event
namespace. This is the mechanical denominator, not a supported-event count.
The one custom node and two layout rows are independent categories and do not
establish an executable interaction policy.

This result adds no member/body evidence and no runtime capability. Ordinary
event options, the bounded item child and the exact RoomFullOfCheese/Gorge
add-two child remain the only accepted event paths. Any member or IL follow-up
requires its own frozen finite selector and review. No profile/save, Cloud,
gameplay, native execution, network or remote operation occurred.

using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json.Nodes;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Map;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.MonsterMoves.Intents;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Runs;
using static Sts2AgentBridge.Unified.FullPublicGraph;

namespace Sts2AgentBridge.Unified;

// Shared run/combat facts for all native decision families. Entity references
// are allocated from public order, with private bindings retained separately.
internal sealed class FullNativeState : IDisposable
{
    private readonly Dictionary<string, Dictionary<object, string>> _refs = new();
    private readonly Dictionary<string, int> _counts = new();
    private readonly Dictionary<object, Dictionary<(string, int), object>> _indexed = new(ReferenceEqualityComparer.Instance);
    private readonly List<object> _bindings = new();
    private readonly AgentCombatHistory _history = new(card => FullNativeDisplay.Card(card));
    private readonly List<Creature> _enemySlots = new();
    private readonly Dictionary<Creature, JsonObject> _lastEnemies = new(ReferenceEqualityComparer.Instance);
    private CardModel[][] _drawGroups = Array.Empty<CardModel[]>();
    private RunState? _run;
    private Player? _player;
    private CombatState? _combat;
    private readonly int _thread = Environment.CurrentManagedThreadId;
    private bool _disposed;
    internal Player Player => _player ?? throw new AgentUnsupported();
    internal RunState Run => _run ?? throw new AgentUnsupported();
    internal object[] Bindings => _bindings.ToArray();
    internal readonly Dictionary<string, MapPoint> MapCoordinates = new(StringComparer.Ordinal);

    internal void Begin()
    {
        Require(!_disposed && Environment.CurrentManagedThreadId == _thread);
        var run = RunManager.Instance.DebugOnlyGetState();
        Require(run is not null && run.Players.Count == 1 && NRun.Instance is not null);
        _run ??= run; _player ??= run!.Players[0];
        Require(ReferenceEquals(run, _run) && ReferenceEquals(run!.Players[0], _player) &&
            run.AscensionLevel is >= 0 and <= 10 && (int)RunManager.Instance.NetService.Type == 1 &&
            Player.Creature.HpDisplay is HpDisplay.Normal or HpDisplay.InfiniteWithNumbers);
        _bindings.Clear(); Bind(run!); Bind(Player); Bind(NRun.Instance!);
    }
    internal static void Require(bool condition) { if (!condition) throw new AgentUnsupported(); }
    internal void Bind(object value) => _bindings.Add(value);
    internal object Indexed(object owner, string kind, int index)
    {
        Require(index is >= 0 and < 2048);
        if (!_indexed.TryGetValue(owner, out var entries)) { Require(_indexed.Count < 16384); _indexed.Add(owner, entries = new()); }
        if (!entries.TryGetValue((kind, index), out var identity)) entries.Add((kind, index), identity = new());
        return identity;
    }
    internal string Ref(string kind, object value)
    {
        if (!_refs.TryGetValue(kind, out var map)) _refs.Add(kind, map = new(ReferenceEqualityComparer.Instance));
        if (!map.TryGetValue(value, out var reference))
        {
            int count = _counts.GetValueOrDefault(kind); Require(count < 16384);
            _counts[kind] = count + 1; map.Add(value, reference = kind + ":" + count);
        }
        return reference;
    }
    internal void Adopt(string kind, object offer, object model)
    {
        string reference = Ref(kind, offer); var map = _refs[kind];
        Require(!map.TryGetValue(model, out var existing) || existing == reference);
        map[model] = reference;
    }
    internal JsonObject Card(CardModel card)
    { Bind(card); return FullNativeDisplay.Card(card, Ref("card", card)); }
    internal JsonObject Relic(RelicModel relic)
    { Bind(relic); return FullNativeDisplay.Relic(relic, Ref("relic", relic)); }
    internal JsonObject Potion(PotionModel potion)
    { Bind(potion); return FullNativeDisplay.Potion(potion, Ref("potion", potion)); }
    private static int Number(string reference) => int.Parse(reference[(reference.IndexOf(':') + 1)..]);
    private static string Signature(JsonObject card)
    { var view = (JsonObject)card.DeepClone(); view["ref"] = null; return view.ToJsonString(); }

    internal JsonObject PublicRun(IEnumerable<JsonObject> history)
    {
        Require(Player.Deck.Cards.Count <= 128 && Player.Relics.Count <= 128 && Player.PotionSlots.Count <= 8);
        var deck = FullReadFailure.At(FullReadStage.Deck, () => Player.Deck.Cards.Select(card => (Card: card, View: FullNativeDisplay.Card(card)))
            .OrderBy(row => Signature(row.View), StringComparer.Ordinal).ToArray());
        foreach (var row in deck) { Bind(row.Card); row.View["ref"] = Ref("card", row.Card); }
        var relics = FullReadFailure.At(FullReadStage.Relics, () => Player.Relics.Select(Relic).ToArray());
        var potions = FullReadFailure.At(FullReadStage.Potions, () => Player.PotionSlots.Select((potion, index) => Node("potion_slot",
            fields: new (string, object?)[] { ("index", index) },
            children: potion is null ? Array.Empty<JsonObject>() : new[] { Potion(potion) })).ToArray());
        return Node("run", fields: new (string, object?)[] {
            ("character", Player.Character.Id.Entry.ToLowerInvariant()), ("ascension", Run.AscensionLevel),
            ("act", Run.CurrentActIndex + 1), ("floor", Run.TotalFloor), ("hp", Player.Creature.CurrentHp),
            ("max_hp", Player.Creature.MaxHp), ("gold", Player.Gold) }, children: new[] {
                Node("deck", children: deck.Select(row => row.View)), Node("relics", children: relics),
                Node("potions", fields: new (string, object?)[] { ("capacity", Player.PotionSlots.Count) }, children: potions),
                FullReadFailure.At(FullReadStage.Map, PublicMap), Node("history", fields: new (string, object?)[] { ("coverage", "attachment") },
                    children: history.Select(n => (JsonObject)n.DeepClone())) });
    }

    private JsonObject PublicMap()
    {
        var mapPoints = Run.Map.GetAllMapPoints().Append(Run.Map.StartingMapPoint).Append(Run.Map.BossMapPoint);
        if (Run.Map.SecondBossMapPoint is {} secondBoss) mapPoints = mapPoints.Append(secondBoss);
        var points = mapPoints
            .Distinct().OrderBy(point => point.coord.row).ThenBy(point => point.coord.col).ToArray();
        Require(points.Length is > 0 and <= 384 && points.Select(point => point.coord).Distinct().Count() == points.Length);
        foreach (var point in points) Ref("node", point);
        MapCoordinates.Clear();
        var children = points.Select(point => {
            Bind(point); MapCoordinates.Add(point.coord.row + ":" + point.coord.col, point);
            Require(point.Children.All(points.Contains));
            string kind = point.PointType.ToString() switch {
                "Monster" => "combat", "Elite" => "elite", "Boss" => "boss", "Unknown" => "unknown",
                "RestSite" => "rest", "Shop" => "shop", "Treasure" => "treasure", "Ancient" => "ancient",
                _ => throw new AgentUnsupported() };
            return Node("node", kind, Ref("node", point), new (string, object?)[] {
                ("row", point.coord.row), ("column", point.coord.col), ("visited", Run.VisitedMapCoords.Contains(point.coord)),
                ("fur_coat_marked", point.Quests.Any(q => q is MegaCrit.Sts2.Core.Models.Relics.FurCoat)),
                ("spoils_map_marked", point.Quests.Any(q => q is MegaCrit.Sts2.Core.Models.Cards.SpoilsMap)) },
                links: new[] { ("next_nodes", point.Children.OrderBy(p => p.coord.row).ThenBy(p => p.coord.col).Select(p => Ref("node", p))) });
        }).ToArray();
        return Node("map", fields: new (string, object?)[] { ("available", true) }, children: children,
            links: new[] { ("current", (IEnumerable<string>)(Run.CurrentMapPoint is {} current ? new[] { Ref("node", current) } : Array.Empty<string>())) });
    }

    private JsonObject[] Powers(Creature creature)
    {
        Require(creature.Powers.Count <= 128);
        return creature.Powers.Where(power => power.IsVisible).Select(power => {
            Bind(power); string key = power.Id.Entry.ToLowerInvariant();
            if (key.EndsWith("_power", StringComparison.Ordinal)) key = key[..^6];
            var tips = power.HoverTips.ToArray();
            Require(tips.Length is > 0 and <= 64 && tips[0] is HoverTip);
            var tip = (HoverTip)tips[0];
            return Node("power", key, Ref("power", power), new (string, object?)[] {
                ("amount", power.DisplayAmount), ("title", tip.Title), ("description", tip.Description) },
                tips.Skip(1).Select(FullNativeDisplay.Hover));
        }).ToArray();
    }

    internal JsonObject PublicCombat()
    {
        var combat = CombatManager.Instance.DebugOnlyGetState();
        Require(combat is not null && combat.Players.Count == 1 && ReferenceEquals(combat.Players[0], Player));
        if (!ReferenceEquals(_combat, combat))
        { _combat = combat; _drawGroups = Array.Empty<CardModel[]>(); _enemySlots.Clear(); _lastEnemies.Clear(); }
        Bind(combat!);
        var player = Player.PlayerCombatState; Require(player is not null); Bind(player!);
        var powers = _history.Powers(combat!).Where(row => !player!.AllCards.Contains(row.Card)).ToArray();
        var piles = new[] { ("hand", player!.Hand.Cards.ToArray()), ("draw", player.DrawPile.Cards.ToArray()),
            ("discard", player.DiscardPile.Cards.ToArray()), ("exhaust", player.ExhaustPile.Cards.ToArray()),
            ("in_play", player.PlayPile.Cards.ToArray()) };
        Require(piles.Sum(row => row.Item2.Length) <= 256);
        var views = piles.SelectMany(row => row.Item2).Distinct().ToDictionary(card => card, card => FullNativeDisplay.Card(card));
        var draw = piles[1].Item2.OrderBy(card => Signature(views[card]), StringComparer.Ordinal).ToArray();
        var visible = piles.Where(row => row.Item1 != "draw").SelectMany(row => row.Item2).ToArray();
        foreach (var group in _drawGroups)
        {
            string[] refs = group.Select(card => Ref("card", card)).OrderBy(Number).ToArray();
            var destinations = visible.Concat(draw).Where(group.Contains).ToArray();
            for (int i = 0; i < destinations.Length; i++) _refs["card"][destinations[i]] = refs[i];
            foreach (var gone in group.Except(destinations)) _refs["card"].Remove(gone);
        }
        foreach (var card in visible.Concat(draw)) Ref("card", card);
        _drawGroups = draw.GroupBy(card => Signature(views[card])).Where(group => group.Count() > 1).Select(group => group.ToArray()).ToArray();
        var children = piles.Select(pile => {
            var originals = pile.Item1 == "draw" ? draw.OrderBy(card => Signature(views[card]), StringComparer.Ordinal)
                .ThenBy(card => Number(Ref("card", card))).ToArray() : pile.Item2;
            var cards = originals.Select(card => { Bind(card); var view = (JsonObject)views[card].DeepClone(); view["ref"] = Ref("card", card); return view; });
            return Node("pile", pile.Item1, fields: new (string, object?)[] {
                ("count", originals.Length), ("order", pile.Item1 == "draw" ? "canonical" : "visible") }, children: cards);
        }).ToList();
        children.Add(Node("pile", "powers", fields: new (string, object?)[] { ("count", powers.Length), ("coverage", "observed_plays") },
            children: powers.Select(power => { var view = (JsonObject)power.View.DeepClone(); view["ref"] = Ref("card", power.Card); return view; })));
        foreach (var enemy in combat!.Enemies) if (!_enemySlots.Contains(enemy)) _enemySlots.Add(enemy);
        Require(_enemySlots.Count <= 128);
        var enemies = new List<JsonObject>();
        for (int slot = 0; slot < _enemySlots.Count; slot++)
        {
            var enemy = _enemySlots[slot];
            if (!combat.Enemies.Contains(enemy))
            {
                // A removed enemy's later private state is not inspectable.
                enemies.Add(Node("enemy", _lastEnemies[enemy]["definition_id"]!.GetValue<string>(), Ref("enemy", enemy),
                    new (string, object?)[] { ("slot", slot), ("present", false) }));
                continue;
            }
            Bind(enemy); Require(enemy.Monster is not null && enemy.HpDisplay is HpDisplay.Normal or HpDisplay.InfiniteWithNumbers or HpDisplay.InfiniteWithoutNumbers);
            bool infinite = enemy.HpDisplay == HpDisplay.InfiniteWithoutNumbers;
            var details = new List<JsonObject>(Powers(enemy));
            if (enemy.Monster!.NextMove is MoveState move)
            {
                foreach (var intent in move.Intents)
                {
                    string kind = intent.IntentType.ToString() switch {
                        "DebuffStrong" => "debuff_strong", "StatusCard" => "status_card", "CardDebuff" => "card_debuff",
                        "DeathBlow" => "death_blow", var other => other.ToLowerInvariant() };
                    details.Add(Node("intent", kind, fields: new (string, object?)[] {
                        ("damage", intent is AttackIntent attack ? attack.GetSingleDamage(new[] { Player.Creature }, enemy) : null),
                        ("hits", intent is AttackIntent hit ? hit.Repeats : null),
                        ("card_count", intent is StatusIntent status ? status.CardCount : null) }));
                }
            }
            var view = Node("enemy", enemy.Monster!.Id.Entry.ToLowerInvariant(), Ref("enemy", enemy), new (string, object?)[] {
                ("slot", slot), ("present", true), ("alive", enemy.IsAlive), ("hp", infinite ? null : enemy.CurrentHp),
                ("max_hp", infinite ? null : enemy.MaxHp), ("infinite_hp", infinite), ("block", enemy.Block) }, details);
            _lastEnemies[enemy] = (JsonObject)view.DeepClone(); enemies.Add(view);
        }
        children.Add(Node("enemies", children: enemies));
        children.Add(Node("powers", children: Powers(Player.Creature)));
        var resources = player.OrbQueue.Orbs.Select(orb => {
            Bind(orb); string key = orb.Id.Entry.ToLowerInvariant(); if (key.EndsWith("_orb", StringComparison.Ordinal)) key = key[..^4];
            return Node("orb", key, Ref("orb", orb), new (string, object?)[] { ("passive", (int)orb.PassiveVal), ("evoke", (int)orb.EvokeVal) });
        }).ToList();
        if (Player.Osty is {} osty) resources.Add(Node("osty", fields: new (string, object?)[] {
            ("hp", osty.CurrentHp), ("max_hp", osty.MaxHp), ("block", osty.Block) }, children: Powers(osty)));
        children.Add(Node("resources", fields: new (string, object?)[] { ("stars", player.Stars), ("orb_slots", player.OrbQueue.Capacity) }, children: resources));
        return Node("combat", fields: new (string, object?)[] { ("round", combat.RoundNumber), ("hp", Player.Creature.CurrentHp),
            ("max_hp", Player.Creature.MaxHp), ("block", Player.Creature.Block), ("energy", player.Energy) }, children: children);
    }
    public void Dispose() { _history.Dispose(); _disposed = true; }
}

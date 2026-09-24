using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Nodes;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Map;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.MonsterMoves;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.MonsterMoves.Intents;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Rewards;
using MegaCrit.Sts2.Core.Runs;
using Sts2AgentBridge.Adapters.Public;
using Sts2AgentBridge.Cards.Combat;

namespace Sts2AgentBridge.Unified;

// Explicit public fields only. Native object references remain in Bindings and
// never enter the observation. All methods run in the router's owner frame.
internal sealed class AgentPublicReader : IAgentPublicReader
{
    private readonly PinnedPublicRewardDecisionReader _rewards;
    private readonly CombatCardChoiceService _choice;
    private readonly AgentCombatHistory _history;
    private readonly Dictionary<string, Dictionary<object, string>> _refs = new();
    private readonly Dictionary<string, int> _counts = new();
    private readonly List<object> _bindings = new();
    private readonly List<AgentCommand> _commands = new();
    private CardModel[][] _drawGroups = Array.Empty<CardModel[]>();
    private RunState? _run;
    private Player? _player;
    private CombatState? _combat;
    private readonly Dictionary<string, object> _nodes = new();
    internal AgentPublicReader(PinnedPublicRewardDecisionReader rewards, CombatCardChoiceService choice)
    { _rewards = rewards; _choice = choice; _history = new(card => Card(card, true)); }
    private static JsonNode J(object value) => JsonSerializer.SerializeToNode(value)!;
    private static JsonNode Known(object value) => J(new { status = "known", value });
    private static JsonNode NA() => J(new { status = "not_applicable", value = (object?)null });
    private static JsonNode Unknown() => J(new { status = "unknown", value = (object?)null });
    private static void Require(bool condition) { if (!condition) throw new AgentUnsupported(); }
    private static string Key(string value) => value.ToLowerInvariant();
    private static string CardKey(CardModel card) => card.Id.Entry switch {
        "STRIKE_IRONCLAD" => "strike", "DEFEND_IRONCLAD" => "defend", _ => Key(card.Id.Entry) };
    private string Ref(string kind, object model)
    {
        if (!_refs.TryGetValue(kind, out var refs)) _refs.Add(kind, refs = new(ReferenceEqualityComparer.Instance));
        if (!refs.TryGetValue(model, out var value))
        {
            int count = _counts.GetValueOrDefault(kind);
            Require(count < 4096); _counts[kind] = count + 1;
            refs.Add(model, value = kind + ":" + count);
        }
        return value;
    }
    private static int Number(string value) => int.Parse(value.Split(':')[1]);
    private void Bind(object value) => _bindings.Add(value);
    private void Action(string native, string kind, string? subject = null, string? target = null)
    {
        var candidate = (JsonObject)J(new { @ref = "action:" + _commands.Count, kind, subject, target });
        _commands.Add(new(native, candidate));
    }
    public string InitialFamily()
    {
        if (NRun.Instance?.GlobalUi?.MapScreen?.IsOpen == true) return "map";
        if (CombatManager.Instance.IsInProgress) return "combat";
        return "reward";
    }
    public AgentCapture Capture(string family, JsonElement legacy, JsonArray history, string? source)
    {
        _bindings.Clear(); _commands.Clear();
        RunState? run = RunManager.Instance.DebugOnlyGetState();
        Require(run is not null && run.Players.Count == 1);
        if (_run is null) { _run = run; _player = run!.Players[0]; }
        Require(ReferenceEquals(run, _run) && ReferenceEquals(run!.Players[0], _player));
        Player player = _player!;
        Bind(run!); Bind(player); Bind(NRun.Instance!);
        // Potion use/discard are legal game choices outside this profile.
        Require(!player.Potions.Any());
        Require(run!.AscensionLevel is >= 0 and <= 10 && player.Deck.Cards.Count <= 128);
        string character = Key(player.Character.Id.Entry);
        Require(new[] { "ironclad", "silent", "regent", "necrobinder", "defect" }.Contains(character));
        JsonNode map = Map(run);
        var deck = player.Deck.Cards.Select(c => (Card: c, View: Card(c, false))).OrderBy(x => Signature(x.View), StringComparer.Ordinal).ToArray();
        foreach (var row in deck) { row.View["ref"] = Ref("card", row.Card); Bind(row.Card); }
        var publicRun = J(new { character, ascension = run.AscensionLevel, act = run.CurrentActIndex + 1,
            floor = run.TotalFloor, hp = player.Creature.CurrentHp, max_hp = player.Creature.MaxHp, gold = player.Gold,
            deck = Known(deck.Select(x => x.View).ToArray()), relics = Known(player.Relics.Select(Relic).ToArray()),
            potions = Known(player.PotionSlots.Select((p, i) => new { index = i, potion = (object?)null }).ToArray()),
            map = Known(map), history = Known(new { coverage = "attachment", events = history }) });
        JsonNode context = family switch {
            "combat" => Combat(player, legacy, true),
            "choice" => Selection(player, legacy, source),
            "reward" => Rewards(legacy),
            "map" => MapChoice(legacy),
            _ => throw new AgentUnsupported() };
        var observation = (JsonObject)J(new { schema = "sts_public_decision_v1", profile = "combat_reward_map_v1",
            run = publicRun, context, candidates = _commands.Select(c => c.Candidate).ToArray() });
        Require(JsonSerializer.SerializeToUtf8Bytes(observation).Length <= 60000);
        return new(observation, _commands.ToArray(), _bindings.ToArray());
    }

    private static string Signature(JsonObject card)
    {
        var copy = (JsonObject)card.DeepClone(); copy.Remove("ref"); copy.Remove("origin");
        return copy.ToJsonString();
    }
    private JsonObject Card(CardModel card, bool combat)
    {
        Require(card.Enchantment is null && card.Affliction is null && card.CurrentUpgradeLevel is >= 0 and <= 99);
        string id = CardKey(card);
        // A named, bounded preview profile. DynamicVars alone cannot establish
        // completeness: e.g. Zap channels one orb without a dynamic variable.
        Require(new[] { "strike", "defend", "bash", "neows_fury", "anger", "cleave", "headbutt",
            "iron_wave", "pommel_strike", "shrug_it_off", "twin_strike", "thunderclap", "inflame",
            "strike_silent", "defend_silent", "strike_regent", "defend_regent", "strike_necrobinder", "defend_necrobinder",
            "strike_defect", "defend_defect", "zap", "dualcast", "defy" }.Contains(id));
        var variables = card.DynamicVars.Clone(card);
        // Preview a detached variable set, never update the game's own cache.
        card.UpdateDynamicVarPreview(CardPreviewMode.Normal, null, variables);
        var values = new SortedDictionary<string, int>(StringComparer.Ordinal);
        foreach (var v in variables.Values)
        {
            string key = v.Name switch {
                "Damage" => "damage", "Block" => "block", "Repeat" => "hits",
                "Cards" => id == "neows_fury" ? "select_maximum" : "draw",
                "Vulnerable" or "VulnerablePower" => "vulnerable", "Weak" or "WeakPower" => "weak", "Strength" or "StrengthPower" => "strength",
                "Dexterity" => "dexterity", "Focus" => "focus", "Vigor" => "vigor",
                "Stars" => "stars", "Forge" => "forge", "Summon" => "summon",
                "MaxHp" => "max_hp", "HpLoss" => "hp_loss", "Energy" => "energy",
                _ => throw new AgentUnsupported() };
            // The displayed label truncates the decimal preview (Weak/Frail can
            // produce fractions); do not reject a normal public integer label.
            Require(Math.Abs(v.PreviewValue) <= 1000000);
            values.Add(key, (int)v.PreviewValue);
        }
        if (values.ContainsKey("damage") && !values.ContainsKey("hits")) values.Add("hits", id == "twin_strike" ? 2 : 1);
        if (id == "headbutt") values.Add("select", 1);
        if (id == "zap") values.Add("channel_lightning", 1);
        if (id == "dualcast") values.Add("evoke", 2);
        var modifiers = new SortedDictionary<string, int>(StringComparer.Ordinal);
        foreach (var keyword in card.Keywords)
        {
            string key = keyword.ToString() switch {
                "Exhaust" => "exhausts", "Ethereal" => "ethereal", "Innate" => "innate", "Retain" => "retain",
                "Eternal" => "eternal", "Sly" => "sly", "Unplayable" => "unplayable", _ => throw new AgentUnsupported() };
            modifiers.Add(key, 1);
        }
        int energy = card.EnergyCost.GetWithModifiers(CostModifiers.All);
        int stars = card.GetStarCostWithModifiers();
        return (JsonObject)J(new { @ref = "card:0", definition_id = id, upgrade_level = card.CurrentUpgradeLevel,
            cost = new { energy = energy < 0 ? NA() : Known(energy), energy_x = card.EnergyCost.CostsX,
                stars = stars < 0 ? NA() : Known(stars), stars_x = card.HasStarCostX },
            values = Known(values.Select(v => new { key = v.Key, amount = v.Value }).ToArray()),
            modifiers = Known(modifiers.Select(v => new { key = v.Key, amount = v.Value }).ToArray()),
            origin = combat ? Unknown() : NA() });
    }
    private JsonNode Relic(RelicModel relic)
    {
        string id = Key(relic.Id.Entry);
        Require(new[] { "burning_blood", "ring_of_the_snake", "divine_right", "bound_phylactery", "cracked_core",
            "strawberry", "pear", "mango", "golden_pearl", "nutritious_oyster" }.Contains(id));
        Bind(relic);
        return J(new { @ref = Ref("relic", relic), definition_id = id, counters = Known(Array.Empty<object>()) });
    }
    private JsonNode Powers(Creature creature)
    {
        Require(creature.Powers.Count <= 64);
        return Known(creature.Powers.OrderBy(p => p.Id.Entry, StringComparer.Ordinal).Select(power => {
            string id = Key(power.Id.Entry);
            if (id.EndsWith("_power", StringComparison.Ordinal)) id = id[..^6];
            Require(new[] { "strength", "dexterity", "focus", "vigor", "vulnerable", "weak", "frail", "artifact",
                "poison", "doom", "ritual", "plating", "thorns" }.Contains(id));
            Bind(power);
            return J(new { @ref = Ref("power", power), definition_id = id, amount = power.DisplayAmount,
                counters = Known(Array.Empty<object>()) });
        }).ToArray());
    }
    private JsonNode Map(RunState run)
    {
        var points = run.Map.GetAllMapPoints().Append(run.Map.StartingMapPoint).Append(run.Map.BossMapPoint)
            .Distinct().OrderBy(p => p.coord.row).ThenBy(p => p.coord.col).ToArray();
        Require(points.Length is > 0 and <= 256 && points.Select(p => p.coord).Distinct().Count() == points.Length);
        foreach (var point in points) Ref("node", point);
        _nodes.Clear();
        var nodes = points.Select(point => {
            Bind(point); string id = Ref("node", point); _nodes.Add(point.coord.row + ":" + point.coord.col, point);
            string kind = point.PointType.ToString() switch {
                "Monster" => "combat", "Elite" => "elite", "Boss" => "boss", "Unknown" => "unknown",
                "RestSite" => "rest", "Shop" => "shop", "Treasure" => "treasure", "Ancient" => "ancient",
                _ => throw new AgentUnsupported() };
            Require(point.Children.All(points.Contains));
            return J(new { @ref = id, row = point.coord.row, column = point.coord.col, kind,
                next_nodes = point.Children.OrderBy(p => p.coord.row).ThenBy(p => p.coord.col).Select(p => Ref("node", p)).ToArray() });
        }).ToArray();
        return J(new { current = run.CurrentMapPoint is {} current ? Known(Ref("node", current)) : NA(), nodes });
    }
    private JsonNode MapChoice(JsonElement legacy)
    {
        var reachable = new List<string>();
        foreach (var action in legacy.GetProperty("legal_actions").EnumerateArray())
        {
            var node = legacy.GetProperty("candidates")[action.GetProperty("candidate_index").GetInt32()];
            string key = node.GetProperty("row").GetInt32() + ":" + node.GetProperty("col").GetInt32();
            Require(_nodes.TryGetValue(key, out var native));
            string id = Ref("node", native!); reachable.Add(id);
            Action(action.GetProperty("action_id").GetString()!, "choose_map_node", id);
        }
        return J(new { kind = "map", reachable });
    }

    private JsonNode Combat(Player player, JsonElement legacy, bool actions)
    {
        var combat = CombatManager.Instance.DebugOnlyGetState();
        Require(combat is not null && combat.Players.Count == 1 && ReferenceEquals(combat.Players[0], player));
        _combat ??= combat;
        Require(ReferenceEquals(combat, _combat));
        Bind(combat!);
        var pcs = player.PlayerCombatState!; Require(pcs is not null); Bind(pcs!);
        var playedPowers = _history.Powers(combat!).Where(p => !pcs!.AllCards.Contains(p.Card)).ToArray();
        var powersPile = playedPowers.Select(p => p.Card).ToArray();
        var piles = new[] { ("hand", pcs!.Hand.Cards.ToArray()), ("draw", pcs.DrawPile.Cards.ToArray()),
            ("discard", pcs.DiscardPile.Cards.ToArray()), ("exhaust", pcs.ExhaustPile.Cards.ToArray()),
            ("in_play", pcs.PlayPile.Cards.ToArray()), ("powers", powersPile) };
        Require(piles.Sum(p => p.Item2.Length) <= 128);
        var views = piles.Where(p => p.Item1 != "powers").SelectMany(p => p.Item2).Distinct().ToDictionary(c => c, c => Card(c, true));
        foreach (var power in playedPowers) views.Add(power.Card, (JsonObject)power.View.DeepClone());
        var draw = piles[1].Item2.OrderBy(c => Signature(views[c]), StringComparer.Ordinal).ToArray();
        var visible = piles.Where(p => p.Item1 != "draw").SelectMany(p => p.Item2).ToArray();
        // Equal copies in an unordered pile are interchangeable until a visible
        // destination distinguishes them. Do not leak which hidden copy was drawn.
        foreach (var group in _drawGroups)
        {
            string[] names = group.Select(c => Ref("card", c)).OrderBy(Number).ToArray();
            var destinations = visible.Concat(draw).Where(group.Contains).ToArray();
            for (int i = 0; i < destinations.Length; i++) _refs["card"][destinations[i]] = names[i];
            foreach (var gone in group.Except(destinations)) _refs["card"].Remove(gone);
        }
        foreach (var card in visible.Concat(draw)) Ref("card", card);
        _drawGroups = draw.GroupBy(c => Signature(views[c])).Where(g => g.Count() > 1).Select(g => g.ToArray()).ToArray();
        var publicPiles = piles.Select(pile => {
            IEnumerable<CardModel> cards = pile.Item1 == "draw" ? draw.OrderBy(c => Signature(views[c]), StringComparer.Ordinal).ThenBy(c => Number(Ref("card", c))) : pile.Item2;
            var rows = cards.Select(card => { Bind(card); var view = (JsonObject)views[card].DeepClone(); view["ref"] = Ref("card", card); return view; }).ToArray();
            return J(new { kind = pile.Item1, count = rows.Length, cards = Known(rows), order = pile.Item1 == "draw" ? "canonical" : "visible" });
        }).ToArray();
        var enemies = combat!.Enemies.Where(e => e.IsAlive).ToArray();
        Require(enemies.Length <= 6);
        // The shared v1 schema has numeric health only.
        Require(player.Creature.HpDisplay is HpDisplay.Normal or HpDisplay.InfiniteWithNumbers &&
            enemies.All(e => e.HpDisplay is HpDisplay.Normal or HpDisplay.InfiniteWithNumbers));
        foreach (var enemy in enemies) Ref("enemy", enemy);
        var publicEnemies = enemies.Select(enemy => {
            Bind(enemy); Require(enemy.Monster?.NextMove is MoveState);
            var move = (MoveState)enemy.Monster!.NextMove!;
            var intents = move.Intents.Select(intent => {
                string kind = intent.IntentType.ToString() switch { "DebuffStrong" => "debuff_strong", "StatusCard" => "status_card",
                    "CardDebuff" => "card_debuff", "DeathBlow" => "death_blow", var other => other.ToLowerInvariant() };
                return J(new { kind, damage = intent is AttackIntent attack ? Known(attack.GetSingleDamage(new[] { player.Creature }, enemy)) : NA(),
                    hits = intent is AttackIntent hit ? Known(Math.Max(1, hit.Repeats)) : NA() });
            }).ToArray();
            return J(new { @ref = Ref("enemy", enemy), definition_id = Key(enemy.Monster.Id.Entry), hp = enemy.CurrentHp,
                max_hp = enemy.MaxHp, block = enemy.Block, powers = Powers(enemy), intents = Known(intents) });
        }).ToArray();
        string character = Key(player.Character.Id.Entry);
        bool regent = character == "regent" || pcs.Stars != 0 || views.Values.Any(c => c["cost"]!["stars"]!["status"]!.GetValue<string>() == "known" || c["definition_id"]!.GetValue<string>() == "sovereign_blade");
        bool necro = character == "necrobinder" || player.Osty is not null;
        bool defect = character == "defect" || pcs.OrbQueue.Capacity != 0 || pcs.OrbQueue.Orbs.Count != 0 ||
            views.Values.Any(c => c["definition_id"]!.GetValue<string>() is "zap" or "dualcast");
        var osty = player.Osty;
        JsonNode resources = J(new {
            stars = regent ? Known(pcs.Stars) : NA(),
            sovereign_blades = regent ? Known(visible.Concat(draw).Where(c => views[c]["definition_id"]!.GetValue<string>() == "sovereign_blade").Select(c => Ref("card", c)).ToArray()) : NA(),
            osty = necro ? Known(new { creature = osty is null ? null : J(new { hp = osty.CurrentHp, max_hp = osty.MaxHp, block = osty.Block, powers = Powers(osty) }) }) : NA(),
            orb_slots = defect ? Known(pcs.OrbQueue.Capacity) : NA(),
            orbs = defect ? Known(pcs.OrbQueue.Orbs.Select(orb => { Bind(orb); string key = Key(orb.Id.Entry);
                if (key.EndsWith("_orb", StringComparison.Ordinal)) key = key[..^4];
                return J(new { @ref = Ref("orb", orb), kind = key, passive = (int)orb.PassiveVal, evoke = (int)orb.EvokeVal }); }).ToArray()) : NA() });
        if (actions)
            foreach (var a in legacy.GetProperty("legal_actions").EnumerateArray())
            {
                string action = a.GetProperty("action_id").GetString()!;
                if (a.GetProperty("kind").GetString() == "end_turn") Action(action, "end_turn");
                else
                {
                    int hand = a.GetProperty("hand_index").GetInt32();
                    var target = a.GetProperty("target_index");
                    Action(action, "play_card", Ref("card", pcs.Hand.Cards[hand]), target.ValueKind == JsonValueKind.Null ? null : Ref("enemy", enemies[target.GetInt32()]));
                }
            }
        return J(new { kind = "combat", round = combat.RoundNumber, block = player.Creature.Block, energy = pcs.Energy,
            powers = Powers(player.Creature), resources, enemies = publicEnemies, piles = publicPiles });
    }
    private JsonNode Selection(Player player, JsonElement legacy, string? source)
    {
        JsonNode combat = Combat(player, legacy, false);
        var surface = _choice.PublicSurface(legacy.GetProperty("decision_id").GetString()!);
        Require(!surface.Cancelable && surface.Cards.All(c => c.Enabled));
        Bind(surface.Identity);
        foreach (var card in surface.Cards) { Bind(card.Model); Bind(card.Holder); }
        foreach (var action in legacy.GetProperty("legal_actions").EnumerateArray())
        {
            string id = action.GetString()!;
            if (id == "confirm") Action(id, "confirm_selection");
            else { string[] parts = id.Split(':'); Action(id, parts[0] == "select" ? "select_card" : "deselect_card", Ref("card", surface.Cards[int.Parse(parts[1])].Model)); }
        }
        return J(new { kind = "card_selection", combat, source = source is null ? Unknown() : Known(source), pile = surface.Pile,
            options = surface.Cards.Select(c => Ref("card", c.Model)).ToArray(),
            selected = (surface.SelectedOrder ?? throw new AgentUnsupported()).Select(c => Ref("card", c)).ToArray(),
            minimum = surface.MinSelect, maximum = surface.MaxSelect, manual_confirmation = surface.ManualConfirmation, cancelable = false });
    }
    private JsonNode Rewards(JsonElement legacy)
    {
        var session = _rewards.InteractionSession;
        Require(ReferenceEquals(session.Player, _player));
        string decision = legacy.GetProperty("decision_id").GetString()!;
        bool child = legacy.GetProperty("screen_kind").GetString() == "card_reward";
        var entries = new List<JsonNode>();
        var subjects = new Dictionary<int, string>();
        var offers = new Dictionary<int, string>();
        if (child)
        {
            var parent = session.ActiveCardReward ?? throw new AgentUnsupported();
            Bind(parent.Reward); string id = Ref("reward", parent.Reward);
            var cards = new List<JsonNode>();
            for (int i = 0; session.TryGetCardTarget(decision, i, out var screen, out var target); i++)
            {
                Require(i < 5); Bind(screen!); Bind(target!.Holder); Bind(target.Model);
                var card = Card(target.Model, false); string cardRef = Ref("card", target.Model);
                card["ref"] = cardRef; cards.Add(card); offers.Add(i, cardRef);
            }
            Require(cards.Count > 0);
            entries.Add(J(new { @ref = id, kind = "card", presentation = "choice", amount = NA(), cards = Known(cards), potion = NA(), relic = NA(), resolved = false }));
            subjects.Add(0, id);
        }
        else
        {
            for (int i = 0; session.TryGetParentTarget(decision, i, out var screen, out var target); i++)
            {
                Require(i < 8); Bind(screen!); Bind(target!.Button); Bind(target.Reward);
                string id = Ref("reward", target.Reward); subjects.Add(i, id);
                bool resolved = target.Reward.SuccessfullySelected || session.WasSkipped(target.Reward);
                string kind = target.Reward switch { GoldReward => "gold", CardReward => "card", PotionReward => "potion", RelicReward => "relic", _ => throw new AgentUnsupported() };
                JsonNode potion = NA(), relic = NA();
                if (!resolved && kind is "potion" or "relic")
                {
                    object model = PinnedPublicItemRewardClaim.Model(target.Reward)!; Bind(model);
                    if (model is PotionModel p) potion = Known(new { @ref = Ref("potion", p), definition_id = Key(p.Id.Entry) });
                    else if (model is RelicModel r) relic = Known(Relic(r));
                    else throw new AgentUnsupported();
                }
                entries.Add(J(new { @ref = id, kind, presentation = "summary", amount = !resolved && target.Reward is GoldReward gold ? Known(gold.Amount) : NA(),
                    // Closed card rewards must not reveal their precomputed offers.
                    cards = NA(), potion, relic, resolved }));
            }
        }
        foreach (var a in legacy.GetProperty("legal_actions").EnumerateArray())
        {
            string native = a.GetProperty("action_id").GetString()!;
            string[] parts = native.Split(':');
            switch (parts[0])
            {
                case "claim": case "collect": Action(native, "claim_reward", subjects[int.Parse(parts[1])]); break;
                case "open": Action(native, "open_card_reward", subjects[int.Parse(parts[1])]); break;
                case "choose": Action(native, "choose_reward_card", subjects[0], offers[int.Parse(parts[1])]); break;
                case "skip_card": Action(native, "skip_reward", subjects[0]); break;
                case "proceed": Action(native, "leave_rewards"); break;
                default: throw new AgentUnsupported();
            }
        }
        return J(new { kind = "rewards", entries });
    }
    public void Dispose() => _history.Dispose();
}

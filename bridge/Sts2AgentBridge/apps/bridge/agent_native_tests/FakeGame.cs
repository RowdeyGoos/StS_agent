// Inert authored objects only. Production is separately compiled against the
// pinned assemblies; these fixtures prove projection, not real game behavior.
using System;
using System.Collections.Generic;
using System.Linq;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Map;
using MegaCrit.Sts2.Core.Rewards;

namespace MegaCrit.Sts2.Core.Entities.Cards
{
    public enum CardType { Attack, Skill, Power }
    public enum CardKeyword { Exhaust, Ethereal, Innate, Retain, Eternal, Sly, Unplayable }
    public enum CardPreviewMode { Normal }
    public enum CostModifiers { All }
    public sealed class CardEnergyCost { public int Value = 1; public bool CostsX; public int GetWithModifiers(CostModifiers _) => Value; }
    public sealed class CardPile
    {
        public List<CardModel> Cards = new(); public event Action<CardModel>? CardAdded;
        public void Add(CardModel c) { Cards.Add(c); c.Pile = this; CardAdded?.Invoke(c); }
    }
}
namespace MegaCrit.Sts2.Core.Models
{
    public sealed record ModelId(string Entry);
    public sealed class Variable { public string Name; public decimal PreviewValue; public Variable(string name, decimal value) { Name = name; PreviewValue = value; } }
    public sealed class Vars
    {
        public List<Variable> Values = new();
        public Vars Clone(CardModel _) => new() { Values = Values.Select(v => new Variable(v.Name, v.PreviewValue)).ToList() };
    }
    public sealed class CardModel
    {
        public ModelId Id = new("STRIKE_IRONCLAD"); public object? Enchantment, Affliction;
        public int CurrentUpgradeLevel, BaseStarCost = -1; public bool HasStarCostX;
        public CardType Type; public HashSet<CardKeyword> Keywords = new(); public Vars DynamicVars = new();
        public CardEnergyCost EnergyCost = new(); public CardPile? Pile;
        public int GetStarCostWithModifiers() => BaseStarCost;
        public void UpdateDynamicVarPreview(CardPreviewMode _, object? target, Vars vars) { }
        public event Action? Played; public void Play() => Played?.Invoke();
    }
    public sealed class RelicModel { public ModelId Id = new("BURNING_BLOOD"); }
    public sealed class PotionModel { public ModelId Id = new("FIRE_POTION"); }
    public sealed class CharacterModel { public ModelId Id = new("IRONCLAD"); }
    public sealed class PowerModel { public ModelId Id = new("STRENGTH_POWER"); public int DisplayAmount; }
    public sealed class OrbModel { public ModelId Id = new("LIGHTNING_ORB"); public decimal PassiveVal = 3, EvokeVal = 8; }
    public sealed class MonsterModel { public ModelId Id = new("NIBBIT"); public object NextMove = new MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine.MoveState(); }
}
namespace MegaCrit.Sts2.Core.Entities.Creatures
{
    public enum HpDisplay {Normal,InfiniteWithNumbers,InfiniteWithoutNumbers}
    public sealed class Creature
    {
        public HpDisplay HpDisplay; public int CurrentHp = 80, MaxHp = 80, Block; public bool IsAlive => CurrentHp > 0;
        public List<PowerModel> Powers = new(); public MonsterModel? Monster;
    }
}
namespace MegaCrit.Sts2.Core.Entities.Players
{
    public sealed class OrbQueue { public int Capacity; public List<OrbModel> Orbs = new(); }
    public sealed class PlayerCombatState
    {
        public CardPile Hand = new(), DrawPile = new(), DiscardPile = new(), ExhaustPile = new(), PlayPile = new();
        public CardPile[] AllPiles => new[] { Hand, DrawPile, DiscardPile, ExhaustPile, PlayPile };
        public IEnumerable<CardModel> AllCards => AllPiles.SelectMany(p => p.Cards);
        public int Energy = 3, Stars; public OrbQueue OrbQueue = new();
    }
    public sealed class Player
    {
        public CardPile Deck = new(); public Creature Creature = new(); public CharacterModel Character = new();
        public PlayerCombatState PlayerCombatState = new(); public Creature? Osty;
        public int Gold = 99; public List<RelicModel> Relics = new();
        public PotionModel?[] PotionSlots = new PotionModel?[3]; public IEnumerable<PotionModel> Potions => PotionSlots.OfType<PotionModel>();
    }
}
namespace MegaCrit.Sts2.Core.Map
{
    public readonly record struct MapCoord(int col, int row);
    public enum MapPointType { Monster, Elite, Boss, Unknown, RestSite, Shop, Treasure, Ancient }
    public sealed class MapPoint { public MapCoord coord; public MapPointType PointType; public HashSet<MapPoint> Children = new(); }
    public sealed class ActMap
    {
        public MapPoint StartingMapPoint = new(), BossMapPoint = new(); public List<MapPoint> Points = new();
        public IEnumerable<MapPoint> GetAllMapPoints() => Points;
    }
}
namespace MegaCrit.Sts2.Core.Runs
{
    public sealed class RunState { public List<Player> Players = new(); public int AscensionLevel, CurrentActIndex, TotalFloor = 1; public ActMap Map = new(); public MapPoint? CurrentMapPoint; }
    public sealed class RunManager { public static RunManager Instance = new(); public RunState? State; public RunState? DebugOnlyGetState() => State; }
}
namespace MegaCrit.Sts2.Core.Combat
{
    public sealed class CombatState { public List<Player> Players = new(); public List<Creature> Enemies = new(); public int RoundNumber = 1; }
    public sealed class CombatManager
    {
        public static CombatManager Instance = new(); public CombatState? State; public bool IsInProgress = true;
        public CombatState? DebugOnlyGetState() => State;
        public event Action<CombatState>? CombatSetUp;
        public void Setup(CombatState state) { State = state; CombatSetUp?.Invoke(state); }
    }
}
namespace MegaCrit.Sts2.Core.MonsterMoves { public sealed class NamespaceMarker { } }
namespace MegaCrit.Sts2.Core.MonsterMoves.Intents
{
    public enum IntentType { Attack, Defend, Hidden, DebuffStrong, StatusCard, CardDebuff, DeathBlow }
    public class Intent { public IntentType IntentType; }
    public sealed class AttackIntent : Intent
    {
        public int Damage = 7, Repeats = 1;
        public int GetSingleDamage(Creature[] targets, Creature owner) => Damage;
    }
}
namespace MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine
{
    public sealed class MoveState { public List<MegaCrit.Sts2.Core.MonsterMoves.Intents.Intent> Intents = new(); }
}
namespace MegaCrit.Sts2.Core.Nodes
{
    public sealed class NRun { public static NRun Instance = new(); public Global GlobalUi = new(); }
    public sealed class Global { public MapScreen MapScreen = new(); }
    public sealed class MapScreen { public bool IsOpen; }
}
namespace MegaCrit.Sts2.Core.Rewards
{
    public class Reward { public bool SuccessfullySelected; }
    public sealed class GoldReward : Reward { public int Amount = 10; }
    public sealed class CardReward : Reward { public CardModel[] HiddenOffers = Array.Empty<CardModel>(); }
    public sealed class PotionReward : Reward { public PotionModel Model = new(); }
    public sealed class RelicReward : Reward { public RelicModel Model = new(); }
}
namespace Sts2AgentBridge.Cards.Combat
{
    internal sealed record ChoiceCard(object Model, object Holder, bool Enabled = true);
    internal sealed record ChoiceSurface(object Identity, string Pile, int MinSelect, int MaxSelect, bool ManualConfirmation, ChoiceCard[] Cards, object[]? SelectedOrder, bool Cancelable = false);
    internal sealed class CombatCardChoiceService { internal ChoiceSurface? Surface = null; internal ChoiceSurface PublicSurface(string _) => Surface!; }
}
namespace Sts2AgentBridge.Adapters.Public
{
    internal sealed class ParentTarget { internal Reward Reward = new(); internal object Button = new(); }
    internal sealed class CardTarget { internal CardModel Model = new(); internal object Holder = new(); }
    internal sealed class Session
    {
        internal Player? Player; internal ParentTarget? ActiveCardReward;
        internal List<ParentTarget> Parents = new(); internal List<CardTarget> Cards = new(); internal object Screen = new();
        internal bool WasSkipped(Reward _) => false;
        internal bool TryGetParentTarget(string _, int i, out object screen, out ParentTarget? target)
        { screen = Screen; target = i < Parents.Count ? Parents[i] : null; return target is not null; }
        internal bool TryGetCardTarget(string _, int i, out object screen, out CardTarget? target)
        { screen = Screen; target = i < Cards.Count ? Cards[i] : null; return target is not null; }
    }
    internal sealed class PinnedPublicRewardDecisionReader { internal Session InteractionSession = new(); }
    internal static class PinnedPublicItemRewardClaim
    {
        internal static object? Model(Reward r) => r switch { PotionReward p => p.Model, RelicReward relic => relic.Model, _ => null };
    }
}

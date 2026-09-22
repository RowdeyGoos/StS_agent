// Inert native surfaces. Harmony is real; no game or Godot assembly is loaded.
using System;
using System.Collections.Generic;
using System.Linq;
using System.Runtime.CompilerServices;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.RestSite;
using MegaCrit.Sts2.Core.Models.Relics;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.RestSite;
using MegaCrit.Sts2.Core.Nodes.Rooms;

namespace Godot
{
    public class GodotObject
    {
        public bool Valid = true;
        public static bool IsInstanceValid(GodotObject? value) => value?.Valid == true;
        public bool Visible = true;
        public bool IsVisibleInTree() => Visible;
    }
    public class Control : GodotObject { }
}
namespace MegaCrit.Sts2.Core.Entities.Players
{
    public class Player
    {
        public readonly List<RelicModel> Relics = new();
        public readonly List<PotionModel?> PotionSlots = new();
        public readonly Pile Deck = new();
        public object RunState = new();
        public readonly Creature Creature = new();
        public int Gold = 20;
        public Player() { foreach (var r in new RelicModel[] { new Girya(), new PumpkinCandle(), new Shovel(), new MeatCleaver(), new PaelsGrowth() }) { r.Owner = this; Relics.Add(r); } }
        public object Girya { get => GetRelic<Girya>()!; set { int i = Relics.FindIndex(r => r is Girya); Relics[i] = (RelicModel)value; Relics[i].Owner = this; } }
        public object Candle { get => GetRelic<PumpkinCandle>()!; set { int i = Relics.FindIndex(r => r is PumpkinCandle); Relics[i] = (RelicModel)value; Relics[i].Owner = this; } }
        public T? GetRelic<T>() where T : class => Relics.OfType<T>().SingleOrDefault();
    }
    public class Pile { public List<CardModel> Cards = new(); }
    public class Creature { public int CurrentHp = 30, MaxHp = 60; }
}
namespace MegaCrit.Sts2.Core.Models.Relics
{
    public class Girya : RelicModel { public int TimesLifted { get; set; } }
    public class PumpkinCandle : RelicModel { public int KindleCount { get; set; } }
    public class Shovel : RelicModel { }
    public class MeatCleaver : RelicModel { }
    public class PaelsGrowth : RelicModel { }
    public class Byrdpip : RelicModel
    {
        public override Task AfterObtained()
        {
            var deck = Owner!.Deck.Cards;
            for (int i = 0; i < deck.Count; i++)
                if (deck[i] is MegaCrit.Sts2.Core.Models.Cards.ByrdonisEgg)
                    deck[i] = new MegaCrit.Sts2.Core.Models.Cards.ByrdSwoop { Owner = Owner, RunState = Owner.RunState };
            return Task.CompletedTask;
        }
    }
}
namespace MegaCrit.Sts2.Core.Entities.RestSite
{
    public abstract class RestSiteOption
    {
        protected RestSiteOption(Player player) { Owner = player; }
        protected Player Owner { get; }
        public bool IsEnabled { get; set; } = true;
        public virtual void Select() { }
        public virtual Task<bool> OnSelect() { Select(); return Task.FromResult(true); }
    }
    public class LiftRestSiteOption(Player player) : RestSiteOption(player)
    { public override void Select() => Owner.GetRelic<Girya>()!.TimesLifted++; }
    public class KindleRestSiteOption(Player player) : RestSiteOption(player)
    { public override void Select() => Owner.GetRelic<PumpkinCandle>()!.KindleCount += 5; }
    public class DigRestSiteOption(Player player) : RestSiteOption(player)
    {
        public RelicModel Drawn = new();
        [MethodImpl(MethodImplOptions.NoInlining)]
        public override async Task<bool> OnSelect() { await MegaCrit.Sts2.Core.Commands.RelicCmd.Obtain(Drawn, Owner, -1); return true; }
    }
    public class HatchRestSiteOption(Player player) : RestSiteOption(player)
    {
        [MethodImpl(MethodImplOptions.NoInlining)]
        public override async Task<bool> OnSelect() { await MegaCrit.Sts2.Core.Commands.RelicCmd.Obtain(new Byrdpip(), Owner, -1); return true; }
    }
    public class CloneRestSiteOption(Player player) : RestSiteOption(player)
    {
        [MethodImpl(MethodImplOptions.NoInlining)]
        public override async Task<bool> OnSelect()
        {
            foreach (var c in Owner.Deck.Cards.Where(c => c.Enchantment is MegaCrit.Sts2.Core.Models.Enchantments.Clone).ToArray())
            {
                var copy = new CardModel { Owner = Owner, RunState = Owner.RunState, Id = c.Id, CurrentUpgradeLevel = c.CurrentUpgradeLevel };
                copy.Enchantment = new MegaCrit.Sts2.Core.Models.Enchantments.Clone { Card = copy, Amount = c.Enchantment!.Amount };
                await MegaCrit.Sts2.Core.Commands.CardPileCmd.Add(copy, MegaCrit.Sts2.Core.Entities.Cards.PileType.Deck, MegaCrit.Sts2.Core.Entities.Cards.CardPilePosition.Bottom, null, false);
            }
            return true;
        }
    }
    public class CookRestSiteOption(Player player) : RestSiteOption(player)
    {
        [MethodImpl(MethodImplOptions.NoInlining)]
        public override async Task<bool> OnSelect()
        {
            var cards = await MegaCrit.Sts2.Core.Commands.CardSelectCmd.Remove(Owner);
            if (!cards.Any()) return false;
            foreach (var c in cards) Owner.Deck.Cards.Remove(c);
            Owner.Creature.MaxHp += 9; Owner.Creature.CurrentHp += 9; return true;
        }
    }
}
namespace MegaCrit.Sts2.Core.Nodes
{
    public class NRun : Godot.GodotObject
    {
        public static NRun? Instance { get; set; }
        public NRestSiteRoom RestSiteRoom = new();
        public Ui GlobalUi = new();
    }
    public class Ui { public Map MapScreen = new(); public Screens.Overlays.NOverlayStack Overlays = new(); }
    public class Map : Godot.GodotObject { public bool IsOpen, IsTraveling; }
}
namespace MegaCrit.Sts2.Core.Nodes.RestSite
{
    public class NRestSiteCharacter : Godot.GodotObject { public Player Player = new(); }
    public class NRestSiteButton : Godot.GodotObject
    {
        public required RestSiteOption Option;
        public bool IsEnabled = true;
        public int Clicks;
        public Action? Click;
        public void ForceClick() { Clicks++; Click?.Invoke(); }
    }
}
namespace MegaCrit.Sts2.Core.Nodes.Rooms
{
    public class NRestSiteRoom : Godot.GodotObject
    {
        public static NRestSiteRoom? Instance;
        public List<NRestSiteCharacter> Characters = new() { new() };
        public List<RestSiteOption> Options = new();
        public Dictionary<RestSiteOption, NRestSiteButton> Buttons = new();
        public TaskCompletionSource Completion = new();
        public NRestSiteButton GetButtonForOption(RestSiteOption option) => Buttons[option];
        [MethodImpl(MethodImplOptions.NoInlining)]
        private Task AfterSelectingOptionAsync(RestSiteOption option) => Completion.Task;
        public void Continue(RestSiteOption option) { _ = AfterSelectingOptionAsync(option); }
    }
}

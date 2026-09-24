using System;
using System.Collections.Generic;
using System.Linq;
using System.Runtime.CompilerServices;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.CardSelection;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;

namespace MegaCrit.Sts2.Core.Models
{
    public class AbstractModel { }
    public sealed record ModelId(string Entry);
    public class RelicModel
    {
        public Player? Owner;
        public virtual Task AfterObtained() => Task.CompletedTask;
    }
    public class PotionModel { }
    public class CardModel
    {
        public Player? Owner;
        public object? RunState;
        public ModelId Id = new("STRIKE");
        public int CurrentUpgradeLevel;
        public bool IsRemovable = true;
        public bool IsUpgradable = true;
        public EnchantmentModel? Enchantment;
    }
    public class EnchantmentModel { public ModelId Id = new("CLONE"); public decimal Amount = 4; public CardModel? Card; }
}
namespace MegaCrit.Sts2.Core.Models.Cards
{
    public class ByrdonisEgg : CardModel { public ByrdonisEgg() { Id = new("BYRDONIS_EGG"); } }
    public class ByrdSwoop : CardModel { public ByrdSwoop() { Id = new("BYRD_SWOOP"); } }
}
namespace MegaCrit.Sts2.Core.Models.Enchantments { public class Clone : EnchantmentModel { } }
namespace MegaCrit.Sts2.Core.CardSelection
{
    public class CardSelectorPrefs { public int MinSelect, MaxSelect; public bool Cancelable, RequireManualConfirmation; }
}
namespace MegaCrit.Sts2.Core.Commands
{
    public static class RelicCmd
    {
        [MethodImpl(MethodImplOptions.NoInlining)]
        public static async Task<RelicModel> Obtain(RelicModel relic, Player player, int index)
        {
            relic.Owner = player; player.Relics.Add(relic); await relic.AfterObtained(); return relic;
        }
    }
    public static class CardSelectCmd
    {
        public static object? Selector { get; set; }
        public static Task<IEnumerable<CardModel>> Remove(Player player) => Select(player.Deck.Cards.Where(c => c.IsRemovable).ToArray(), 2);
        public static Task<IEnumerable<CardModel>> Select(IReadOnlyList<CardModel> cards, int count)
        {
            var screen = NDeckCardSelectScreen.Create(cards, new() { MinSelect = count, MaxSelect = count, Cancelable = true, RequireManualConfirmation = true });
            var overlays = NRun.Instance!.GlobalUi.Overlays; overlays.ScreenCount = 1; overlays.Top = screen;
            return screen.Selected.Task;
        }
    }
    public static class CardPileCmd
    {
        public static bool UpgradeAdded;
        [MethodImpl(MethodImplOptions.NoInlining)]
        public static Task<MegaCrit.Sts2.Core.Entities.Cards.CardPileAddResult> Add(CardModel card, MegaCrit.Sts2.Core.Entities.Cards.PileType pile,
            MegaCrit.Sts2.Core.Entities.Cards.CardPilePosition position, AbstractModel? source, bool skip)
        {
            if (UpgradeAdded) card.CurrentUpgradeLevel++;
            card.Owner!.Deck.Cards.Add(card);
            return Task.FromResult(new MegaCrit.Sts2.Core.Entities.Cards.CardPileAddResult { success = true, cardAdded = card });
        }
    }
}
namespace MegaCrit.Sts2.Core.Runs { public interface IRunState { } public sealed class RunState : IRunState { } }
namespace MegaCrit.Sts2.Core.Entities.Cards
{
    public enum PileType { Deck = 6 }
    public enum CardPilePosition { Bottom = 1 }
    public struct CardPileAddResult { public bool success; public CardModel cardAdded; }
}
namespace MegaCrit.Sts2.Core.Nodes.Screens.Overlays
{
    public class NOverlayStack : GodotObject { public int ScreenCount; public Control? Top; public Control? Peek() => Top; }
}
namespace MegaCrit.Sts2.Core.Nodes.Screens.CardSelection
{
    public class NDeckCardSelectScreen : Control
    {
        public readonly TaskCompletionSource<IEnumerable<CardModel>> Selected = new();
        public bool WrongSelection, Hold;
        [MethodImpl(MethodImplOptions.NoInlining)]
        public static NDeckCardSelectScreen Create(IReadOnlyList<CardModel> cards, CardSelectorPrefs prefs) => new();
    }
    public class NDeckUpgradeSelectScreen : NDeckCardSelectScreen
    {
        [MethodImpl(MethodImplOptions.NoInlining)]
        public static NDeckUpgradeSelectScreen ShowScreen(IReadOnlyList<CardModel> cards, CardSelectorPrefs prefs, MegaCrit.Sts2.Core.Runs.IRunState run)
        {
            var screen = new NDeckUpgradeSelectScreen(); var overlays = NRun.Instance!.GlobalUi.Overlays;
            overlays.ScreenCount = 1; overlays.Top = screen; return screen;
        }
    }
    public class NDeckEnchantSelectScreen : NDeckCardSelectScreen
    {
        [MethodImpl(MethodImplOptions.NoInlining)]
        public static NDeckEnchantSelectScreen ShowScreen(IReadOnlyList<CardModel> cards, EnchantmentModel enchantment, int amount, CardSelectorPrefs prefs) => new();
    }
}
namespace Sts2AgentBridge.Successors.RoomFlowsV1.Shop.Native
{
    // Inert stand-in for the shared input driver. Its real Godot control/preview
    // implementation is covered by the existing pickup native fixture suite.
    internal sealed record DeckChoiceView(CardModel[] Domain, CardModel[] Selected, int Minimum, int Maximum, bool Cancelable);
    internal sealed class PinnedDeckCardChoice
    {
        private readonly NDeckCardSelectScreen _screen;
        private readonly NOverlayStack _overlays;
        private CardModel[] _chosen = Array.Empty<CardModel>();
        private readonly CardModel[] _domain;
        private readonly Func<bool> _context;
        private readonly bool _interactive, _cancelable;
        private readonly int _minimum, _maximum;
        internal bool ConfirmationDispatched { get; private set; }
        internal bool CancellationDispatched { get; private set; }
        internal bool Cancelled => CancellationDispatched && Completed;
        internal CardModel[] Selected => _chosen.ToArray();
        internal bool Completed => (ConfirmationDispatched || CancellationDispatched) && _screen.Selected.Task.IsCompletedSuccessfully && _screen.Selected.Task.Result.SequenceEqual(CancellationDispatched ? Array.Empty<CardModel>() : _chosen);
        internal PinnedDeckCardChoice(Control screen, NOverlayStack overlays, IReadOnlyList<CardModel> domain, CardModel[] chosen, Func<bool> context, EnchantmentModel? enchantment, int amount, int maximum)
        { _screen = (NDeckCardSelectScreen)screen; _overlays = overlays; _chosen = chosen; _domain = domain.ToArray(); _context = context; _maximum = maximum; }
        internal PinnedDeckCardChoice(Control screen, NOverlayStack overlays, IReadOnlyList<CardModel> domain, Func<bool> context, EnchantmentModel? enchantment, int amount, int minimum, int maximum, bool cancelable, bool upgrade)
        { _screen = (NDeckCardSelectScreen)screen; _overlays = overlays; _domain = domain.ToArray(); _context = context; _minimum = minimum; _maximum = maximum; _cancelable = cancelable; _interactive = true; }
        internal void Advance()
        {
            if (!_context()) throw new InvalidOperationException("fixture context");
            if (_screen.Hold || _interactive) return;
            if (ConfirmationDispatched) { if (!Completed) throw new InvalidOperationException("fixture selection"); return; }
            Commit(false);
        }
        private void Commit(bool cancel)
        {
            ConfirmationDispatched = !cancel; CancellationDispatched = cancel;
            _overlays.ScreenCount = 0; _overlays.Top = null;
            _screen.Selected.SetResult(cancel || _screen.WrongSelection ? Array.Empty<CardModel>() : _chosen);
        }
        internal DeckChoiceView? Read()
        { if (!_context()) throw new InvalidOperationException("fixture context"); return Completed ? null : new(_domain, _chosen, _minimum, _maximum, _cancelable); }
        internal void Apply(string action, CardModel? card)
        {
            if (!_interactive || Read() is null) throw new InvalidOperationException("fixture interactive");
            if (action == "select" && card is not null && _domain.Contains(card)) _chosen = _chosen.Append(card).ToArray();
            else if (action == "deselect") _chosen = _chosen.Where(c => !ReferenceEquals(c, card)).ToArray();
            else if (action == "confirm" && _chosen.Length >= _minimum) Commit(false);
            else if (action == "cancel" && _cancelable) Commit(true);
            else throw new InvalidOperationException("fixture action");
        }
    }
}

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
    internal sealed class PinnedDeckCardChoice
    {
        private readonly NDeckCardSelectScreen _screen;
        private readonly NOverlayStack _overlays;
        private readonly CardModel[] _chosen;
        private readonly Func<bool> _context;
        internal bool ConfirmationDispatched { get; private set; }
        internal bool Completed => ConfirmationDispatched && _screen.Selected.Task.IsCompletedSuccessfully && _screen.Selected.Task.Result.SequenceEqual(_chosen);
        internal PinnedDeckCardChoice(Control screen, NOverlayStack overlays, IReadOnlyList<CardModel> domain, CardModel[] chosen, Func<bool> context, EnchantmentModel? enchantment, int amount, int maximum)
        { _screen = (NDeckCardSelectScreen)screen; _overlays = overlays; _chosen = chosen; _context = context; }
        internal void Advance()
        {
            if (!_context()) throw new InvalidOperationException("fixture context");
            if (_screen.Hold) return;
            if (ConfirmationDispatched) { if (!Completed) throw new InvalidOperationException("fixture selection"); return; }
            ConfirmationDispatched = true;
            _overlays.ScreenCount = 0; _overlays.Top = null;
            _screen.Selected.SetResult(_screen.WrongSelection ? Array.Empty<CardModel>() : _chosen);
        }
    }
}

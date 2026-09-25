using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.Rewards;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.Screens;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Nodes.Screens.ScreenContext;
using MegaCrit.Sts2.Core.Rewards;
using Sts2AgentBridge.Core.Public;
using Sts2AgentBridge.Rooms.Rest;

internal static partial class Program
{
    private sealed class RestRewardsFixture : IDisposable
    {
        internal sealed class Synchronizer
        {
            internal sealed class Entry { public RewardsSet set = null!; internal TaskCompletionSource? completionSource; }
            internal sealed class State { public List<Entry> rewardsStack = new(); }
            internal enum CompleteState { Completed,Skipped }
            internal readonly State Current = new();
            private State GetRewardStateForPlayer(MegaCrit.Sts2.Core.Entities.Players.Player player) => Current;
            internal void Complete(Entry entry,CompleteState state)=>CompleteRewardsSet(entry,state);
            [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
            private void CompleteRewardsSet(Entry entry,CompleteState state){Current.rewardsStack.Remove(entry);entry.completionSource!.SetResult();}
        }
        internal readonly Synchronizer Sync = new();
        internal readonly Fixture World = new("REST_REWARDS");
        internal readonly RewardsSet Set;
        internal readonly NRewardsScreen Screen = new();
        internal readonly NProceedButton Proceed = new() { IsEnabled = true };
        internal readonly TaskCompletionSource Offer = new();
        internal readonly RestRewardContinuation Child;
        internal readonly List<NRewardButton> Buttons = new();
        internal bool Context = true, AutoClose, Compact;
        internal int Dismissed;
        internal RestRewardsFixture(int count = 2, bool cards = false)
        {
            foreach (var card in World.Cards) card.Owner = World.Player;
            Set = new() { Player = World.Player };
            MegaCrit.Sts2.Core.Runs.RunManager.Instance = new() { State = (MegaCrit.Sts2.Core.Runs.RunState)World.Player.RunState, RewardsSetSynchronizer = Sync };
            Set.BindSynchronizer(Sync); Screen.BindRewards(Set, World.Player.RunState, terminal: false);
            Child = new(Set, World.Player, World.Overlays, () => Context);
            for (int i = 0; i < count; i++)
            {
                if (cards)
                {
                    var cardReward = new CardReward { Player = World.Player, RewardsSetIndex = 1 };
                    var offered = Enumerable.Range(0, 3).Select(j => { var c = new CardModel { Owner = World.Player }; c.Id.Entry = "OFFER_" + j; return c; }).ToArray();
                    cardReward.Setup(offered.Select(c => new MegaCrit.Sts2.Core.Entities.Cards.CardCreationResult(c)).ToList());
                    Set.Rewards.Add(cardReward);
                    var cardButton = new NRewardButton { Reward = cardReward }; Buttons.Add(cardButton); Screen.Children.Add(cardButton);
                    cardButton.Handler = () =>
                    {
                        var menu = new NCardRewardSelectionScreen(); var row = new Control();
                        cardReward.BindMenu(menu);
                        menu.Bind("UI/CardRow", row); menu.Children.Add(row);
                        foreach (var card in offered)
                        {
                            var holder = new NGridCardHolder { CardModel = card, CardNode = new NCard { Model = card } };
                            holder.RewardPressed = () => { World.Player.Deck.Cards.Add(card); cardReward.SuccessfullySelected = true; Close(); };
                            row.Children.Add(holder);
                        }
                        var skip = new NCardRewardAlternativeButton { Clicked = () => { World.Overlays.Screens.Remove(menu); ActiveScreenContext.Instance.Current = Screen; } }; menu.Children.Add(skip);
                        World.Overlays.Screens.Add(menu); ActiveScreenContext.Instance.Current = menu;
                        return Task.CompletedTask;
                    };
                    continue;
                }
                var potion = new PotionModel(); potion.Id.Entry = "POTION_" + i;
                var reward = new PotionReward { Player = World.Player, Potion = potion, RewardsSetIndex = 2 };
                Set.Rewards.Add(reward);
                var button = new NRewardButton { Reward = reward }; Buttons.Add(button); Screen.Children.Add(button);
                button.Handler = () =>
                {
                    reward.ClaimedPotion = potion; potion.Owner = World.Player;
                    World.Player.PotionSlots[World.Player.PotionSlots.FindIndex(p => p is null)] = potion;
                    reward.SuccessfullySelected = true;
                    if (Compact) Screen.Children.Remove(button);
                    if (AutoClose && Set.Rewards.All(r => r.SuccessfullySelected)) Close();
                    return Task.CompletedTask;
                };
            }
            Proceed.Clicked = () => { Dismissed++; Close(); }; Screen.BindProceed(Proceed);
            Child.Offering(Offer.Task);
            if (count > 0)
            {
                Sync.Current.rewardsStack.Add(new() { set = Set });
                Child.ScreenEntering(Set, false, World.Player.RunState);
                World.Overlays.Screens.Add(Screen);
                ActiveScreenContext.Instance = new() { Current = Screen };
                Child.ScreenEntered(Screen);
            }
        }
        internal void Close() { Sync.Current.rewardsStack.Clear(); World.Overlays.Screens.Clear(); ActiveScreenContext.Instance.Current = null; Offer.TrySetResult(); }
        public void Dispose() { try { Child.Dispose(); } catch (InvalidOperationException) { } World.Dispose(); }
    }
    private static void RestRewardCases()
    {
        foreach (bool autoClose in new[] { false, true })
        foreach (bool compact in new[] { false, true })
        {
            using var f = new RestRewardsFixture { AutoClose = autoClose, Compact = compact };
            for (int i = 0; i < 2; i++)
            {
                var view = f.Child.Read(); Check(view.Status == PublicDecisionStatus.Ready && !f.Child.Completed, "rest reward choice remains owned");
                if (compact && i == 1) Check(view.Rewards.Single().RewardIndex == 1 && view.LegalActions.Contains("collect:0"), "remaining original reward keeps its ordinal and new visible action position");
                f.Child.Apply(view.DecisionId, "collect:" + (compact ? 0 : i));
                var after = f.Child.Read();
                Check(f.Buttons[i].ForceClickCalls == 1 && after.Status == (autoClose && i == 1 ? PublicDecisionStatus.Complete : PublicDecisionStatus.Ready), "rest potion effect reconciles at overlay depth one");
            }
            if (!autoClose) { var view = f.Child.Read(); Check(f.Child.CanDismiss(view), "rest nonterminal proceed offered"); f.Child.Apply(view.DecisionId, "dismiss"); f.Child.Read(); }
            Check(f.Child.Completed && f.World.Player.PotionSlots.Count(p => p is not null) == 2, "both Tiny Mailbox fixture potions retained");
            f.Child.Dispose(); f.Child.Dispose();
        }
        foreach (string mode in new[] { "skip", "full", "foreground", "set", "context", "early_close", "lost", "failed_task", "dismiss_mutation", "pending_dispose", "manager", "synchronizer", "stack", "screen_set", "screen_run", "screen_terminal" })
        {
            using var f = new RestRewardsFixture();
            if (mode == "full") for (int i = 0; i < f.World.Player.PotionSlots.Count; i++) { var p = new PotionModel { Owner = f.World.Player }; p.Id.Entry = "EXISTING_" + i; f.World.Player.PotionSlots[i] = p; }
            var view = f.Child.Read(); Check(view.Status == PublicDecisionStatus.Ready, "rest reward fixture starts ready");
            if (mode == "foreground") ActiveScreenContext.Instance.Blocker = new();
            if (mode == "set") f.Set.Rewards.Reverse();
            if (mode == "context") f.Context = false;
            if (mode == "early_close") f.Close();
            if (mode == "failed_task") f.Offer.SetException(new InvalidOperationException());
            if (mode == "lost") f.Buttons[0].DispatchOverride = () => throw new InvalidOperationException();
            if (mode == "manager") MegaCrit.Sts2.Core.Runs.RunManager.Instance = new() { State = (MegaCrit.Sts2.Core.Runs.RunState)f.World.Player.RunState, RewardsSetSynchronizer = f.Sync };
            if (mode == "synchronizer") MegaCrit.Sts2.Core.Runs.RunManager.Instance!.RewardsSetSynchronizer = new RestRewardsFixture.Synchronizer();
            if (mode == "stack") f.Sync.Current.rewardsStack[0].set = new() { Player = f.World.Player };
            if (mode.StartsWith("screen_")) f.Screen.BindRewards(mode == "screen_set" ? new() { Player = f.World.Player } : f.Set,
                mode == "screen_run" ? new MegaCrit.Sts2.Core.Runs.RunState() : f.World.Player.RunState, terminal: mode == "screen_terminal");
            bool rejected = false;
            try
            {
                if (mode is "skip" or "full" or "dismiss_mutation")
                {
                    f.Child.Apply(view.DecisionId, "dismiss");
                    if (mode == "dismiss_mutation") f.World.Player.Gold++;
                    f.Child.Read();
                }
                else if (mode == "pending_dispose") f.Child.Dispose();
                else if (mode == "lost") f.Child.Apply(view.DecisionId, "collect:0");
                else if (mode is "manager" or "synchronizer" or "stack" || mode.StartsWith("screen_")) f.Child.Apply(view.DecisionId, "dismiss");
                else f.Child.Read();
            }
            catch (InvalidOperationException) { rejected = true; }
            Check(rejected == (mode is not ("skip" or "full")), "rest reward adversarial boundary: " + mode);
            if (mode is "skip" or "full") Check(f.Child.Completed && f.Dismissed == 1 && f.Buttons.All(b => b.ForceClickCalls == 0), "explicit reward skip returns without collection");
            else Check(!f.Child.Completed, "no completion for uncertain rest reward");
            if (mode is "manager" or "synchronizer" or "stack" || mode.StartsWith("screen_")) Check(f.Dismissed == 0 && f.Buttons.All(b => b.ForceClickCalls == 0), "changed reward owner sends zero native inputs");
        }
        using (var f = new RestRewardsFixture(0))
        {
            f.Child.Read(); Check(!f.Child.Completed, "empty offer awaits native task");
            f.Close(); f.Child.Read(); Check(f.Child.Completed, "ordinary Heal empty offer completes");
        }
        foreach (bool skip in new[] { false, true })
        {
            using var f = new RestRewardsFixture(1, cards: true);
            int before = f.World.Player.Deck.Cards.Count;
            var parent = f.Child.Read(); f.Child.Apply(parent.DecisionId, PublicRewardActionRequest.OpenCardActionIdFor(0));
            var child = f.Child.Read();
            Check(child.Status == PublicDecisionStatus.Ready && child.ScreenKind == "card_reward" && child.LegalActions.Count == 4, "owned Dream Catcher card menu opens");
            f.Child.Apply(child.DecisionId, skip ? PublicRewardActionRequest.SkipCardActionId : PublicRewardActionRequest.ChooseCardActionIdFor(1));
            if (skip)
            {
                var returned = f.Child.Read();
                Check(returned.Status == PublicDecisionStatus.Ready && returned.ScreenKind == "rewards" && !f.Child.Completed && !f.Offer.Task.IsCompleted, "native Skip returns to owned parent without completing Offer");
                f.Child.Apply(returned.DecisionId, "dismiss");
            }
            var complete = f.Child.Read();
            Check((skip || complete.Status == PublicDecisionStatus.Complete) && f.Child.Completed && f.World.Player.Deck.Cards.Count == before + (skip ? 0 : 1), "Dream Catcher choice auto-closes; skip needs native dismissal");
        }
        foreach (bool repoint in new[] { false, true })
        {
            using var f = new RestRewardsFixture(1, cards: true);
            var view = f.Child.Read(); f.Child.Apply(view.DecisionId, PublicRewardActionRequest.OpenCardActionIdFor(0));
            view = f.Child.Read(); var old = (NCardRewardSelectionScreen)f.World.Overlays.Peek()!;
            var foreign = new NCardRewardSelectionScreen(); foreach (var c in old.Children) foreign.Children.Add(c);
            foreign.Bind("UI/CardRow", old.GetNodeOrNull<Control>("UI/CardRow")!);
            f.World.Overlays.Screens.Remove(old); f.World.Overlays.Screens.Add(foreign); ActiveScreenContext.Instance.Current = foreign;
            if (repoint) ((CardReward)f.Set.Rewards[0]).BindMenu(foreign);
            int count = f.World.Player.Deck.Cards.Count; bool rejected = false;
            try { f.Child.Apply(view.DecisionId, PublicRewardActionRequest.ChooseCardActionIdFor(0)); } catch (InvalidOperationException) { rejected = true; }
            Check(rejected && f.World.Player.Deck.Cards.Count == count && !f.Offer.Task.IsCompleted, "same-offer foreign menu receives no input even if pointer changes");
        }
    }
}

namespace MegaCrit.Sts2.Core.Models.Cards { public sealed class ByrdonisEgg : CardModel { } }
namespace MegaCrit.Sts2.Core.Models.Enchantments { public sealed class Clone : EnchantmentModel { } }
namespace Sts2AgentBridge.Rooms.Rest { public sealed record RestV2Card(int Slot, string Key, int Upgrade, bool Removable); }

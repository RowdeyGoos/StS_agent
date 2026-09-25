using System;
using System.Linq;
using System.Text.Json;
using Godot;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using MegaCrit.Sts2.Core.Nodes.Screens.ScreenContext;
using Sts2AgentBridge.Cards.Combat;

internal sealed class CombatOfferFixture
{
    internal readonly NRun Run = new();
    internal readonly NChooseACardSelectionScreen Screen = new();
    internal readonly Control Row = new();
    internal readonly NPeekButton Peek = new();
    internal readonly Player Player = new();
    internal readonly CombatManager Manager = new();
    internal readonly CardModel[] Cards;
    internal readonly NGridCardHolder[] Holders;
    internal readonly CombatCardChoiceService Service;
    internal bool KeepOpen, WrongResult, Throw;
    internal CombatOfferFixture(int count = 2, bool skip = false)
    {
        NRun.Instance = Run; NOverlayStack.Instance = Run.GlobalUi.Overlays; Run.GlobalUi.Overlays.Top = Screen;
        CombatManager.Instance = Manager; Manager.State.Players.Add(Player);
        Manager.State.CurrentSide = CombatSide.Enemy; Manager.PlayerActionsDisabled = true;
        CardSelectCmd.Selector = null; Time.Ticks = 1000;
        ActiveScreenContext.Instance = new();
        Cards = Enumerable.Range(0, count).Select(i => new CardModel { Owner = Player,
            Id = new ModelId { Entry = i == 0 ? "DISINTEGRATION" : "MIND_ROT" } }).ToArray();
        Screen.Init(Cards, skip); Screen.Nodes["CardRow"] = Row; Screen.Nodes["%PeekButton"] = Peek;
        Screen.Nodes["SkipButton"] = new NChoiceSelectionSkipButton { Click=()=> { Screen.Result(Array.Empty<CardModel>()); if(!KeepOpen) Run.GlobalUi.Overlays.Top=null; } };
        Holders = Cards.Select(c => new NGridCardHolder { CardModel = c, CardNode = new NCard { Model = c }, DeferInput = true }).ToArray();
        Row.Children.AddRange(Holders);
        foreach (var holder in Holders)
            holder.Click = () => {
                void Select() {
                    Screen.Result(new[] { WrongResult ? new CardModel { Owner = Player } : holder.CardModel });
                    if (!KeepOpen) Run.GlobalUi.Overlays.Top = null;
                }
                Select();
                if (Throw) throw new InvalidOperationException("private native detail");
            };
        Service = new(PinnedCombatCardChoiceAdapter.TryCreate, new string('e', 32));
    }
    internal static JsonElement Parse(ChoiceReply reply) { using var json = JsonDocument.Parse(reply.Body); return json.RootElement.Clone(); }
    internal JsonElement Read(int version = 3) => Parse(Service.Read(version));
    internal ChoiceReply Select(int slot = 0, int version = 3) => Service.Apply(Read(version).GetProperty("decision_id").GetString()!, "select:" + slot, version);
}

internal static class CombatOfferFixtures
{
    internal static void Run(Action<bool,string> check)
    {
        for (int count = 1; count <= 3; count++)
        {
            var f = new CombatOfferFixture(count); var view = f.Read();
            check(view.GetProperty("pile").GetString() == "offer" && view.GetProperty("min_select").GetInt32() == 1 &&
                view.GetProperty("protocol").GetString() == "combat_card_choice_v3" &&
                view.GetProperty("legal_actions").GetArrayLength() == count, "mandatory enemy-turn offer advertised");
            check(CombatOfferFixture.Parse(f.Select(count-1)).GetProperty("status").GetString() == "accepted", "offer one native input");
            var done = f.Read();
            check(done.GetProperty("status").GetString() == "complete" && done.GetProperty("reconciled").GetInt32() == 1 &&
                done.GetProperty("selected_slots")[0].GetInt32() == count-1 && f.Holders.Sum(h => h.Calls) == 1 && !f.Service.IsActive,
                "exact offered task result and close reconcile");
        }
        foreach (int version in new[] { 1, 2 })
        {
            var f = new CombatOfferFixture(); var failure = f.Read(version);
            check(failure.GetProperty("code").GetString() == "unsupported_choice" && !failure.GetRawText().Contains("DISINTEGRATION") &&
                f.Holders.Sum(h => h.Calls) == 0, "older protocol cannot project or dispatch offered choice");
            f = new CombatOfferFixture(); string id = f.Read().GetProperty("decision_id").GetString()!;
            check(f.Service.Apply(id, "select:0", version).Terminal && f.Holders.Sum(h => h.Calls) == 0, "active offer rejects protocol change");
        }
        foreach (var mutate in new Action<CombatOfferFixture>[] {
            f => f.Row.Children.Reverse(), f => f.Cards[0] = new CardModel { Owner=f.Player },
            f => f.Holders[0].CardNode = new NCard { Model = f.Cards[0] },
            f => f.Holders[0].CardModel = f.Cards[1], f => f.Cards[0].Owner = new Player(),
            f => f.Cards[0].CurrentUpgradeLevel++, f => f.Screen.ReplaceTask(),
            f => f.Screen.Init(f.Cards, true), f => f.Screen.Init(f.Cards, opened: 1),
            f => f.Player.PlayerCombatState = new PlayerCombatState(),
            f => CombatManager.Instance = new CombatManager { State = f.Manager.State },
            f => f.Run.GlobalUi.Overlays.Top = new NChooseACardSelectionScreen(),
            f => f.Run.GlobalUi.MapScreen.IsOpen = true, f => CardSelectCmd.Selector = new object(),
            f => f.Row.Children.Add(new Control()) })
        {
            var f = new CombatOfferFixture(); string id = f.Read().GetProperty("decision_id").GetString()!; mutate(f);
            check(f.Service.Apply(id, "select:0", 3).Terminal && f.Holders.Sum(h=>h.Calls) == 0, "stale offer rejected before native input");
        }
        foreach (var f in new[] { new CombatOfferFixture(0), new CombatOfferFixture(4), new CombatOfferFixture(skip:true) })
        {
            // Each fixture must own the active singleton for its read.
            NRun.Instance = f.Run; NOverlayStack.Instance = f.Run.GlobalUi.Overlays; CombatManager.Instance = f.Manager;
            check(f.Service.Read(3).Terminal && f.Holders.Sum(h=>h.Calls) == 0, "unsupported offer shape stops without input");
        }
        foreach(bool take in new[]{false,true}) {
            var f=new CombatOfferFixture(skip:true);var v=f.Read(4);
            check(v.GetProperty("min_select").GetInt32()==0 && v.GetProperty("legal_actions").EnumerateArray().Any(a=>a.GetString()=="confirm"),"v4 optional offer skip advertised");
            check(!f.Service.Apply(v.GetProperty("decision_id").GetString()!,take?"select:1":"confirm",4).Terminal,"optional offer input");
            var result=f.Read(4);check(result.GetProperty("status").GetString()=="complete" && result.GetProperty("selected_slots").GetArrayLength()==(take?1:0),"optional offer exact selected or empty result");
        }
        var skipBlocked=new CombatOfferFixture(skip:true);var skipId=skipBlocked.Read(4).GetProperty("decision_id").GetString()!;
        ((NChoiceSelectionSkipButton)skipBlocked.Screen.Nodes["SkipButton"]).IsEnabled=false;
        check(skipBlocked.Service.Apply(skipId,"confirm",4).Terminal,"skip disabled before dispatch rejects");
        var delay = new CombatOfferFixture(); Time.Ticks=350;
        check(delay.Read().GetProperty("status").GetString() == "waiting", "native opening cooldown enforced");
        Time.Ticks=351; delay.Peek.IsPeeking=true;
        check(delay.Read().GetProperty("status").GetString() == "waiting", "peeking is not actionable");
        delay.Peek.IsPeeking=false; delay.Holders[0].Hitbox.IsEnabled=false;
        check(delay.Read().GetProperty("legal_actions").GetArrayLength() == 1, "disabled offer holder excluded");
        var blocked = new CombatOfferFixture(); string blockedId = blocked.Read().GetProperty("decision_id").GetString()!;
        ActiveScreenContext.Instance.Blocker = new object();
        check(blocked.Read().GetProperty("status").GetString() == "waiting", "native foreground blocker hides offered actions");
        check(blocked.Service.Apply(blockedId,"select:0",3).Terminal && blocked.Holders.Sum(h=>h.Calls) == 0,
            "modal or inspect screen appearing before POST prevents native signal");
        var immediate = new CombatOfferFixture { KeepOpen=true }; var receipt = CombatOfferFixture.Parse(immediate.Select());
        check(receipt.GetProperty("reconciled").GetInt32() == 0 && immediate.Holders[0].SignalCalls == 1 &&
            immediate.Holders.All(h => h.QueuedCalls == 0 && h.DeferredInput is null),
            "offer uses one synchronous native signal, no queued input or early reconciliation");
        immediate.Holders[0].CardModel = immediate.Cards[1]; immediate.Service.Dispose();
        check(immediate.Holders.All(h => h.DeferredInput is null) && immediate.Holders[0].Calls == 1,
            "holder replacement and disposal cannot leave a deferred offered input");
        var signalError = new CombatOfferFixture(); signalError.Holders[0].SignalError = Error.Failed;
        string signalDecision = signalError.Read().GetProperty("decision_id").GetString()!;
        check(signalError.Service.Apply(signalDecision,"select:0",3).Terminal &&
            signalError.Service.Apply(signalDecision,"select:0",3).Terminal && signalError.Holders[0].SignalCalls == 1,
            "uncertain native signal status stops without retry");
        var open = new CombatOfferFixture { KeepOpen=true }; open.Select();
        check(open.Read().GetProperty("status").GetString() == "waiting", "task result still waits for overlay close");
        open.Run.GlobalUi.Overlays.Top=null; check(open.Read().GetProperty("status").GetString() == "complete", "closed offer releases owner");
        var wrong = new CombatOfferFixture { WrongResult=true }; wrong.Select();
        check(wrong.Service.Read(3).Terminal, "wrong offered task model fails");
        var cancel = new CombatOfferFixture(); cancel.Read(); cancel.Screen.Cancel(); cancel.Run.GlobalUi.Overlays.Top=null;
        check(cancel.Service.Read(3).Terminal, "cancelled offer is not selection");
        var unsolicited = new CombatOfferFixture(); unsolicited.Read(); unsolicited.Screen.Result(new[] {unsolicited.Cards[0]});
        unsolicited.Run.GlobalUi.Overlays.Top=null; check(unsolicited.Service.Read(3).Terminal, "manual offer completion cannot be adopted");
        var lost = new CombatOfferFixture { Throw=true }; string decision=lost.Read().GetProperty("decision_id").GetString()!;
        check(lost.Service.Apply(decision,"select:0",3).Terminal && lost.Service.Apply(decision,"select:0",3).Terminal &&
            lost.Holders[0].Calls == 1, "uncertain offered input never retries");
    }
}

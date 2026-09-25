using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.CardSelection;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Relics;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using Sts2AgentBridge.Successors.RoomFlowsV1.Shop;
using Sts2AgentBridge.Successors.RoomFlowsV1.Shop.Native;
internal static partial class Program {
    private sealed class PickupPurchase(Player player,RelicModel relic):IShopV1NativeDispatch {
        internal Task? Task;internal Action? After;internal bool Disposed;internal TaskCompletionSource? Delay;
        public ShopV1Completion Completion=>Task?.IsCompletedSuccessfully==true?ShopV1Completion.Succeeded:Task?.IsFaulted==true?ShopV1Completion.Invalid:ShopV1Completion.Pending;
        public void Invoke()=>Task=Run();
        private async Task Run(){if(Delay is not null)await Delay.Task;player.Gold-=10;relic.Owner=player;player.Relics.Add(relic);await relic.AfterObtained();After?.Invoke();}
        public void Dispose()=>Disposed=true;
    }
    private static void ShopPickupCases() {
        InteractiveChoiceCases();
        foreach(string type in new[]{"mirror","hammer","kifuda","dagger","stamp"})foreach(int count in new[]{1,2,4})foreach(bool delayed in new[]{false,true})foreach(string mode in new[]{"success","wrong_result","wrong_effect","pending_dispose"}) foreach(bool interactive in new[]{false,true}) {
            var player=new Player{Gold=100};var cards=Enumerable.Range(0,count).Select(i=>{var c=new CardModel{Owner=player};c.Id.Entry="CARD_"+i;return c;}).ToArray();player.Deck.Cards.AddRange(cards);
            RelicModel relic=type switch{"mirror"=>new DollysMirror(),"hammer"=>new GnarledHammer(),"kifuda"=>new Kifuda(),"dagger"=>new PunchDagger(),_=>new RoyalStamp()};
            var overlays=new NOverlayStack();var purchase=new PickupPurchase(player,relic){Delay=delayed?new():null};var dispatch=new PinnedShopPickupDispatch(player,relic,overlays,purchase,()=>true,interactive:interactive);
            int clicks=0,confirms=0,previews=0;var chosen=new List<CardModel>();
            Control Build(IReadOnlyList<CardModel> domain,EnchantmentModel? effect,int amount,CardSelectorPrefs prefs) {
                NCardGridSelectionScreen screen=effect is null?new NDeckCardSelectScreen():new NDeckEnchantSelectScreen();
                var selected=new TaskCompletionSource<IEnumerable<CardModel>>();screen.SelectionTask=selected.Task;
                MegaCrit.Sts2.Core.Nodes.Screens.ScreenContext.ActiveScreenContext.Instance=new(){Current=screen};
                var grid=new NCardGrid();var container=new Control{Visible=false};var preview=new Control();var confirm=new NConfirmButton();var open=new NConfirmButton();
                screen.Bind("%CardGrid",grid);screen.Bind(effect is null?"%PreviewContainer":prefs.MaxSelect==1?"%EnchantSinglePreviewContainer":"%EnchantMultiPreviewContainer",container);screen.Bind(effect is null?"%Confirm":"Confirm",open);
                container.Bind(effect is null?"%PreviewConfirm":"Confirm",confirm);
                screen.Bind("%Close",new NBackButton());container.Bind(effect is null?"%PreviewCancel":"Cancel",new NBackButton());
                if(effect is not null&&prefs.MaxSelect==1){var single=new NEnchantPreview();single.Setup(new Control(),new Control());container.Bind("EnchantPreview",single);}else container.Bind(effect is null?"%Cards":"Cards",preview);
                void Show(){previews++;container.Visible=true;if(effect is not null&&prefs.MaxSelect==1){var single=container.GetNodeOrNull<NEnchantPreview>("EnchantPreview")!;var fields=single.ReadFixtureFields();var original=chosen.Single();var clone=new CardModel{Owner=player,IsEnchantmentPreview=true};clone.Id.Entry=original.Id.Entry;clone.Enchantment=new(){Card=clone,Amount=amount};clone.Enchantment.Id.Entry=effect.Id.Entry;((Control)fields[0]).Children.Add(new NPreviewCardHolder{CardNode=new NCard{Model=original}});((Control)fields[1]).Children.Add(new NPreviewCardHolder{CardNode=new NCard{Model=clone}});}else foreach(var card in chosen)preview.Children.Add(new NPreviewCardHolder{CardNode=new NCard{Model=card}});}
                foreach(var card in domain.Reverse()) {
                    var material=new ShaderMaterial();var holder=new NGridCardHolder{Hitbox=new NClickableControl{IsEnabled=true},CardModel=card,CardNode=new NCard{Model=card,CardHighlight=new NCardHighlight{Material=material}}};
                    holder.Selected=()=>{clicks++;chosen.Add(card);material.Width=BitConverter.Int32BitsToSingle(1033476506);if(chosen.Count==prefs.MaxSelect)Show();};grid.CurrentlyDisplayedCardHolders.Add(holder);
                }
                open.Clicked=Show;confirm.Clicked=()=>{confirms++;overlays.Screens.Clear();selected.SetResult(mode=="wrong_result"?new[]{new CardModel{Owner=player}}:chosen.ToArray());};return screen;
            }
            NDeckCardSelectScreen.Factory=(domain,prefs)=>(NDeckCardSelectScreen)Build(domain,null,0,prefs);
            NDeckEnchantSelectScreen.Factory=(domain,e,amount,prefs)=>(NDeckEnchantSelectScreen)Build(domain,e,amount,prefs);
            CardSelectCmd.GenericHandler=(p,prefs,filter)=>{var domain=p.Deck.Cards.Where(filter!).ToArray();if(domain.Length<=prefs.MinSelect&&!prefs.RequireManualConfirmation)return System.Threading.Tasks.Task.FromResult<IEnumerable<CardModel>>(domain);var screen=NDeckCardSelectScreen.Create(domain,prefs);overlays.Screens.Add(screen);return screen.CardsSelected();};
            CardSelectCmd.EnchantHandler=(domain,e,amount,prefs)=>{if(domain.Count<=prefs.MinSelect&&!prefs.RequireManualConfirmation)return System.Threading.Tasks.Task.FromResult<IEnumerable<CardModel>>(domain);var screen=NDeckEnchantSelectScreen.ShowScreen(domain,e,amount,prefs);overlays.Screens.Add(screen);return screen.CardsSelected();};
            void Advance() {
                dispatch.Advance();
                if(interactive && dispatch.Completion==ShopV1Completion.Pending && dispatch.ReadChoice() is {} choice) {
                    int desired=Math.Min(type is "hammer" or "kifuda"?3:1,count);
                    if(choice.Selected.Length<desired)dispatch.ApplyChoice("select",cards.First(c=>!choice.Selected.Contains(c)));
                    else dispatch.ApplyChoice("confirm",null);
                }
            }
            if(mode=="wrong_effect")purchase.After=()=>cards[0].CurrentUpgradeLevel++;
            try {
                if(mode!="success") {
                    bool failed=false;
                    try {
                        dispatch.Invoke();if(delayed)purchase.Delay!.SetResult();
                        if(mode!="pending_dispose")for(int i=0;i<24&&dispatch.Completion==ShopV1Completion.Pending;i++)Advance();
                    }catch(InvalidOperationException){failed=true;}
                    bool shortcut=clicks==0&&dispatch.Completion==ShopV1Completion.Succeeded;
                    if(shortcut&&mode is "wrong_result" or "pending_dispose"){dispatch.Dispose();continue;}
                    Check(failed||dispatch.Completion!=ShopV1Completion.Succeeded,"invalid pickup never succeeds: "+mode);
                    bool rejected=false;try{dispatch.Dispose();}catch(InvalidOperationException){rejected=true;}
                    Check(rejected&&purchase.Disposed,"unresolved pickup cleanup stops and detaches purchase");
                    rejected=false;try{dispatch.Dispose();}catch(InvalidOperationException){rejected=true;}
                    Check(rejected,"pickup cleanup failure remains sticky");continue;
                }
                dispatch.Invoke();if(delayed){Check(dispatch.Completion==ShopV1Completion.Pending,"debit delay retains pickup");purchase.Delay!.SetResult();}
                for(int i=0;i<24&&dispatch.Completion==ShopV1Completion.Pending;i++)Advance();
                Check(dispatch.Completion==ShopV1Completion.Succeeded,"native pickup complete "+type+count);
                int selectedCount=Math.Min(type is "hammer" or "kifuda"?3:1,count);
                Check(player.Gold==90&&player.Relics.Single()==relic,"pickup relic and payment exact");
                if(type=="mirror")Check(player.Deck.Cards.Count==count+1&&!cards.Contains(player.Deck.Cards[^1])&&player.Deck.Cards[^1].Id.Entry==cards[0].Id.Entry,"mirror exact native clone insertion");
                else Check(cards.Take(selectedCount).All(c=>c.Enchantment is not null)&&cards.Skip(selectedCount).All(c=>c.Enchantment is null),"only chosen originals enchanted");
                Check(confirms==(clicks==0?0:1)&&previews==confirms,"one native preview/confirm");dispatch.Dispose();Check(purchase.Disposed,"pickup detaches purchase");
            }finally{try{dispatch.Dispose();}catch{}typeof(PinnedShopPickupDispatch).GetField("Active",BindingFlags.Static|BindingFlags.NonPublic)!.SetValue(null,null);CardSelectCmd.GenericHandler=null;CardSelectCmd.EnchantHandler=null;NDeckCardSelectScreen.Factory=null;NDeckEnchantSelectScreen.Factory=null;}
        }
    }
    private sealed class InteractiveChoiceFixture
    {
        internal readonly Player Player = new();
        internal readonly CardModel[] Cards;
        internal readonly NCardGridSelectionScreen Screen;
        internal readonly NOverlayStack Overlays = new();
        internal readonly Control Container = new() { Visible = false };
        internal readonly Control Preview = new();
        internal readonly NCardGrid Grid = new();
        internal readonly NBackButton Back = new(), PreviewBack = new();
        internal readonly NConfirmButton Confirm = new();
        internal readonly TaskCompletionSource<IEnumerable<CardModel>> Task = new();
        internal readonly PinnedDeckCardChoice Choice;
        internal bool Context = true;
        internal bool DelayHighlights;
        private readonly Queue<Action> _highlightUpdates = new();
        internal int Inputs, Clears, Commits, Cancels;
        private readonly List<CardModel> _selected = new();
        internal InteractiveChoiceFixture(bool smith = false, bool transform = false, bool nested = false)
        {
            Cards = Enumerable.Range(0, 3).Select(i => { var c = new CardModel { Owner = Player }; c.Id.Entry = "CARD_" + i; return c; }).ToArray();
            Player.Deck.Cards.AddRange(Cards);
            bool single = smith || transform;
            Screen = transform ? new NDeckTransformSelectScreen() : smith ? new NDeckUpgradeSelectScreen() : new NDeckCardSelectScreen();
            Screen.SelectionTask = Task.Task;
            MegaCrit.Sts2.Core.Nodes.Screens.ScreenContext.ActiveScreenContext.Instance = new() { Current = Screen };
            Screen.Bind("%CardGrid", Grid); Screen.Bind("%Close", Back);
            Screen.Bind(smith ? "%UpgradeSinglePreviewContainer" : "%PreviewContainer", Container);
            if (transform) {
                var preview = new NTransformPreview(); preview.Bind("%Before", Preview); preview.Bind("%After", new Control());
                Container.Bind("TransformPreview", preview);
            } else Container.Bind(smith ? "UpgradePreview" : "%Cards", smith ? new NUpgradePreview() : Preview);
            Container.Bind(single ? "Confirm" : "%PreviewConfirm", Confirm);
            Container.Bind(single ? "Cancel" : "%PreviewCancel", PreviewBack);
            foreach (var card in Cards.Reverse())
            {
                var material = new ShaderMaterial();
                var holder = new NGridCardHolder { CardModel = card, CardNode = new NCard { Model = card, CardHighlight = new() { Material = material } }, Hitbox = new NClickableControl { IsEnabled = true } };
                holder.Selected = () => {
                    Inputs++;
                    if (_selected.Contains(card)) { _selected.Remove(card); Highlight(material, 0); }
                    else { _selected.Add(card); Highlight(material, BitConverter.Int32BitsToSingle(1033476506)); }
                    if (_selected.Count == (single ? 1 : 2))
                    {
                        Container.Visible = true; Back.IsEnabled = false;
                        if (smith) Container.GetNodeOrNull<NUpgradePreview>("UpgradePreview")!.Card = card;
                        else foreach (var c in _selected) Preview.Children.Add(new NPreviewCardHolder { CardNode = new NCard { Model = c } });
                        foreach (var h in Grid.CurrentlyDisplayedCardHolders) Highlight((ShaderMaterial)h.CardNode!.CardHighlight.Material!, 0);
                    }
                };
                Grid.CurrentlyDisplayedCardHolders.Add(holder);
            }
            PreviewBack.Clicked = () => { Clears++; Container.Visible = false; Back.IsEnabled = true; _selected.Clear(); Preview.Children.Clear();
                foreach (var h in Grid.CurrentlyDisplayedCardHolders) Highlight((ShaderMaterial)h.CardNode!.CardHighlight.Material!, 0); };
            Back.Clicked = () => { Cancels++; Overlays.Screens.Clear(); Task.SetResult(Array.Empty<CardModel>()); };
            Confirm.Clicked = () => { Commits++; Overlays.Screens.Clear(); Task.SetResult(_selected.ToArray()); };
            Control[] ancestors = nested ? new Control[] { new MegaCrit.Sts2.Core.Nodes.Screens.NRewardsScreen() } : Array.Empty<Control>();
            Overlays.Screens.AddRange(ancestors); Overlays.Screens.Add(Screen);
            Choice = new(Screen, Overlays, Cards, () => Context, null, 0, single ? 1 : 2, single ? 1 : 2, true, smith, ancestors, transform);
        }
        private void Highlight(ShaderMaterial material, float width)
        { if (DelayHighlights) _highlightUpdates.Enqueue(() => material.Width = width); else material.Width = width; }
        internal void Animate() { while (_highlightUpdates.TryDequeue(out var update)) update(); }
        internal DeckChoiceView Ready()
        {
            for (int i = 0; i < 12; i++) if (Choice.Read() is {} view) return view;
            throw new InvalidOperationException("choice did not become ready");
        }
        internal void Apply(string action, CardModel? card = null) { Ready(); Choice.Apply(action, card); }
        internal void Complete() { for (int i = 0; i < 12 && !Choice.Completed; i++) Choice.Read(); Check(Choice.Completed, "interactive completion"); }
    }
    private static void InteractiveChoiceCases()
    {
        NestedDeckChoiceCases();
        foreach (bool smith in new[] { false, true }) foreach (bool preview in new[] { false, true })
        {
            var f = new InteractiveChoiceFixture(smith);
            Check(f.Ready().Selected.Length == 0 && f.Inputs == 0, "reading never chooses a card");
            if (preview)
            {
                f.Apply("select", f.Cards[0]); f.Ready();
                if (!smith) { f.Apply("select", f.Cards[2]); f.Ready(); }
                Check(f.Container.Visible && f.Commits == 0, "policy confirmation remains separate");
            }
            f.Apply("cancel"); f.Complete();
            Check(f.Choice.Cancelled && f.Cancels == 1 && f.Commits == 0 && f.Clears == (preview ? 1 : 0), "native cancellation before/after preview");
            Check(f.Player.Deck.Cards.SequenceEqual(f.Cards), "cancellation does not mutate deck");
        }
        {
            var f = new InteractiveChoiceFixture { DelayHighlights = true };
            f.Apply("select", f.Cards[0]);
            for (int i = 0; i < 4; i++) Check(f.Choice.Read() is null && f.Inputs == 1, "owned highlight waits at old endpoint without duplicate select");
            f.Animate(); Check(f.Ready().Selected.Single() == f.Cards[0], "delayed selection settles");
            f.Apply("deselect", f.Cards[0]);
            for (int i = 0; i < 4; i++) Check(f.Choice.Read() is null && f.Inputs == 2, "owned highlight waits at old endpoint without duplicate deselect");
            f.Animate(); Check(f.Ready().Selected.Length == 0, "delayed deselection settles");
            f.Apply("select", f.Cards[0]); f.Choice.Read();
            var other = f.Grid.CurrentlyDisplayedCardHolders.Single(h => h.CardModel == f.Cards[2]);
            ((ShaderMaterial)other.CardNode!.CardHighlight.Material!).Width = BitConverter.Int32BitsToSingle(1033476506);
            bool rejected = false; try { f.Choice.Read(); } catch (InvalidOperationException) { rejected = true; }
            Check(rejected && f.Inputs == 3, "owned animation never excuses another card's changed selection");
        }
        {
            var f = new InteractiveChoiceFixture(); f.Apply("select", f.Cards[0]); f.Ready(); f.Apply("select", f.Cards[2]); f.Ready();
            f.Apply("deselect", f.Cards[0]); var view = f.Ready();
            Check(view.Selected.SequenceEqual(new[] { f.Cards[2] }) && f.Clears == 1 && f.Commits == 0, "preview deselect restores only retained selection");
            f.Apply("select", f.Cards[1]); f.Ready(); f.Apply("confirm"); f.Complete();
            Check(!f.Choice.Cancelled && f.Task.Task.Result.SequenceEqual(new[] { f.Cards[2], f.Cards[1] }) && f.Commits == 1, "exact user chosen pair confirmed");
        }
        foreach (string mode in new[] { "context", "screen", "holder", "task", "unknown_card", "premature_confirm", "foreground" })
        {
            var f = new InteractiveChoiceFixture(); f.Ready();
            if (mode == "context") f.Context = false;
            if (mode == "foreground") MegaCrit.Sts2.Core.Nodes.Screens.ScreenContext.ActiveScreenContext.Instance.Blocker = new();
            if (mode == "screen") f.Overlays.Screens.Clear();
            if (mode == "holder") f.Grid.CurrentlyDisplayedCardHolders.Reverse();
            if (mode == "task") f.Task.SetResult(Array.Empty<CardModel>());
            bool rejected = false;
            try {
                if (mode == "unknown_card") f.Choice.Apply("select", new CardModel());
                else if (mode == "premature_confirm") f.Choice.Apply("confirm");
                else f.Choice.Read();
            } catch (InvalidOperationException) { rejected = true; }
            Check(rejected && f.Inputs + f.Cancels + f.Commits == 0, "interactive boundary before input: " + mode);
        }
    }

    private static void NestedDeckChoiceCases()
    {
        foreach (string kind in new[]{"remove","upgrade","transform"}) foreach(string mode in new[]{"complete","ancestor_swap","preview_swap"})
        {
            var f=new InteractiveChoiceFixture(smith:kind=="upgrade",transform:kind=="transform",nested:true);
            f.Ready(); bool rejected=false;
            if(mode=="ancestor_swap") {
                f.Overlays.Screens[0]=new MegaCrit.Sts2.Core.Nodes.Screens.NRewardsScreen();
                try{f.Apply("select",f.Cards[0]);}catch(InvalidOperationException){rejected=true;}
                Check(rejected&&f.Inputs==0,"nested selector requires the exact ancestor before input: "+kind);continue;
            }
            f.Apply("select",f.Cards[0]);f.Ready();
            if(kind=="remove"){f.Apply("select",f.Cards[1]);f.Ready();}
            if(mode=="preview_swap") {
                if(kind=="upgrade")f.Container.GetNodeOrNull<NUpgradePreview>("UpgradePreview")!.Card=f.Cards[2];
                else ((NPreviewCardHolder)f.Preview.Children[0]).CardNode!.Model=f.Cards[2];
                try{f.Apply("confirm");}catch(InvalidOperationException){rejected=true;}
                Check(rejected&&f.Commits==0,"nested selector checks original preview identity: "+kind);continue;
            }
            f.Apply("confirm");f.Complete();
            Check(f.Commits==1&&f.Task.Task.Result.SequenceEqual(f.Cards.Take(kind=="remove"?2:1)),"nested selector completes its exact native task: "+kind);
        }
    }

}

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
        SingleEnchantPreviewCases();
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
        internal readonly Control BeforeEnchant = new NPreviewCardHolder(), AfterEnchant = new NPreviewCardHolder();
        internal readonly EnchantmentModel Enchantment = new() { Amount = 5 };
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
        private int _windowStart;
        internal InteractiveChoiceFixture(bool smith = false, bool transform = false, bool nested = false, bool enchant = false, int count = 3, int window = 0, int maximumDomain = 64, Player? owner = null, CardModel[]? domain = null, NOverlayStack? overlays = null, EnchantmentModel? enchantment = null)
        {
            if (owner is not null) Player = owner;
            if (overlays is not null) Overlays = overlays;
            if (enchantment is not null) Enchantment = enchantment;
            Cards = domain ?? Enumerable.Range(0, count).Select(i => { var c = new CardModel { Owner = Player }; c.Id.Entry = "CARD_" + i; return c; }).ToArray();
            if (domain is null) Player.Deck.Cards.AddRange(Cards);
            count = Cards.Length;
            bool single = smith || transform || enchant;
            Screen = enchant ? new NDeckEnchantSelectScreen() : transform ? new NDeckTransformSelectScreen() : smith ? new NDeckUpgradeSelectScreen() : new NDeckCardSelectScreen();
            Screen.SelectionTask = Task.Task;
            MegaCrit.Sts2.Core.Nodes.Screens.ScreenContext.ActiveScreenContext.Instance = new() { Current = Screen };
            Screen.Bind("%CardGrid", Grid); Screen.Bind("%Close", Back);
            Screen.Bind(enchant ? "%EnchantSinglePreviewContainer" : smith ? "%UpgradeSinglePreviewContainer" : "%PreviewContainer", Container);
            if (enchant) {
                if (enchantment is null) Enchantment.Id.Entry = "MOMENTUM";
                var preview = new NEnchantPreview(); preview.Setup(BeforeEnchant, AfterEnchant);
                Container.Bind("EnchantPreview", preview);
                // The pinned scene uses preview-holder instances as its containers.
                // Init queues their initial hitboxes (and later old holders) for
                // deletion, then adds the new previews within the same frame.
                BeforeEnchant.Children.Add(new Control()); AfterEnchant.Children.Add(new Control());
                if (domain is null) Cards[0].CurrentUpgradeLevel = 1;
            } else if (transform) {
                var preview = new NTransformPreview(); preview.Bind("%Before", Preview); preview.Bind("%After", new Control());
                Container.Bind("TransformPreview", preview);
            } else Container.Bind(smith ? "UpgradePreview" : "%Cards", smith ? new NUpgradePreview() : Preview);
            Container.Bind(single ? "Confirm" : "%PreviewConfirm", Confirm);
            Container.Bind(single ? "Cancel" : "%PreviewCancel", PreviewBack);
            Grid.FixtureCards.AddRange(Cards.Reverse());
            Grid.Size = new(1800, 920);
            // Native container height: total rows * pitch - padding + 80 +
            // 320 + YOffset. Scroll bottom is grid height minus that height.
            Grid.FixtureScrollBottom = Math.Min(0, 920 - (((count + 4) / 5) * 320 - 40 + 80 + 320));
            Grid.FixtureAllocate = Allocate;
            foreach (var initialCard in Grid.FixtureCards.Take(window > 0 ? window : count))
            {
                var material = new ShaderMaterial();
                var holder = new NGridCardHolder { CardModel = initialCard, CardNode = new NCard { Model = initialCard, CardHighlight = new() { Material = material } }, Hitbox = new NClickableControl { IsEnabled = true } };
                holder.Selected = () => {
                    var card = holder.CardModel!;
                    Inputs++;
                    if (_selected.Contains(card)) { _selected.Remove(card); Highlight(material, 0); }
                    else { _selected.Add(card); Highlight(material, BitConverter.Int32BitsToSingle(1033476506)); }
                    Grid.FixtureHighlights.Clear(); Grid.FixtureHighlights.AddRange(_selected);
                    if (_selected.Count == (single ? 1 : 2))
                    {
                        Container.Visible = true; Back.IsEnabled = false; Grid.FixtureHighlights.Clear();
                        if (enchant) {
                            foreach (var node in BeforeEnchant.Children.Concat(AfterEnchant.Children)) node.QueueFree();
                            var clone = new CardModel { Owner = Player, CurrentUpgradeLevel = card.CurrentUpgradeLevel, IsEnchantmentPreview = true };
                            clone.Id.Entry = card.Id.Entry;
                            clone.Enchantment = new() { Card = clone, Amount = Enchantment.Amount }; clone.Enchantment.Id.Entry = Enchantment.Id.Entry;
                            BeforeEnchant.Children.Add(new NPreviewCardHolder { CardNode = new NCard { Model = card } });
                            AfterEnchant.Children.Add(new NPreviewCardHolder { CardNode = new NCard { Model = clone } });
                        } else if (smith) Container.GetNodeOrNull<NUpgradePreview>("UpgradePreview")!.Card = card;
                        else foreach (var c in _selected) Preview.Children.Add(new NPreviewCardHolder { CardNode = new NCard { Model = c } });
                        foreach (var h in Grid.CurrentlyDisplayedCardHolders) Highlight((ShaderMaterial)h.CardNode!.CardHighlight.Material!, 0);
                    }
                };
                Grid.CurrentlyDisplayedCardHolders.Add(holder);
            }
            PreviewBack.Clicked = () => { Clears++; Container.Visible = false; Back.IsEnabled = true; _selected.Clear(); Grid.FixtureHighlights.Clear(); Preview.Children.Clear();
                foreach (var h in Grid.CurrentlyDisplayedCardHolders) Highlight((ShaderMaterial)h.CardNode!.CardHighlight.Material!, 0); };
            Back.Clicked = () => { Cancels++; Overlays.Screens.Clear(); Task.SetResult(Array.Empty<CardModel>()); };
            Confirm.Clicked = () => { Commits++; Overlays.Screens.Clear(); Task.SetResult(_selected.ToArray()); };
            Control[] ancestors = nested ? new Control[] { new MegaCrit.Sts2.Core.Nodes.Screens.NRewardsScreen() } : Array.Empty<Control>();
            Overlays.Screens.AddRange(ancestors); Overlays.Screens.Add(Screen);
            Choice = new(Screen, Overlays, Cards, () => Context, enchant ? Enchantment : null, enchant ? Enchantment.Amount : 0, single ? 1 : 2, single ? 1 : 2, true, smith, ancestors, transform, maximumDomain);
        }
        private void Allocate()
        {
            // Pinned AllocateCardHolders predicates: five columns, row pitch
            // 320, first center 300, viewport 1000. Height 920 allocates five
            // rows: ceil((920 + 40) / 320) + 2. Recycle at most one row.
            var holders = Grid.CurrentlyDisplayedCardHolders;
            float first = 300 + _windowStart / 5 * 320 + Grid.FixtureScroll.Position.Y;
            float last = first + (holders.Count / 5 - 1) * 320;
            int start = _windowStart;
            if (first > 0) start = Math.Max(0, start - 5);
            else if (last < 1000 && start + holders.Count < Cards.Length) start += 5;
            if (start == _windowStart) return;
            var row = start > _windowStart ? holders.Take(5).ToArray() : holders.TakeLast(5).ToArray();
            foreach (var h in row) holders.Remove(h);
            if (start > _windowStart) holders.AddRange(row); else holders.InsertRange(0, row);
            _windowStart = start;
            for (int i = 0; i < holders.Count; i++)
            {
                var h = holders[i];
                if (start + i >= Cards.Length) { h.Visible = false; continue; }
                h.Visible = true; h.CardModel = Grid.FixtureCards[start + i]; h.CardNode!.Model = h.CardModel;
                Highlight((ShaderMaterial)h.CardNode.CardHighlight.Material!, _selected.Contains(h.CardModel!) ? BitConverter.Int32BitsToSingle(1033476506) : 0);
            }
        }
        internal void ScrollFrame() => Grid.FixtureScrollFrame();
        internal DeckChoiceView PagedReady()
        {
            for (int i = 0; i < 120; i++)
            {
                if (Choice.Read() is {} view) return view;
                ScrollFrame(); Animate();
            }
            throw new InvalidOperationException($"paged choice did not become ready: cards={Cards.Length}, inputs={Inputs}, pans={Grid.FixturePanInputs}, start={_windowStart}, y={Grid.FixtureScroll.Position.Y}, target={Grid.FixtureScrollTarget}");
        }
        internal void FlushFreedPreviews()
        { BeforeEnchant.Children.RemoveAll(n => n.IsQueuedForDeletion()); AfterEnchant.Children.RemoveAll(n => n.IsQueuedForDeletion()); }
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

    private static void SingleEnchantPreviewCases()
    {
        {
            var f = new InteractiveChoiceFixture(enchant: true);
            f.Apply("select", f.Cards[0]);
            for (int i = 0; i < 8; i++) Check(f.Choice.Read() is null && f.Inputs == 1 && f.Commits == 0,
                "single enchant waits for native queued hitboxes without repeating input");
            f.FlushFreedPreviews();
            Check(f.Ready().Selected.Single() == f.Cards[0] && f.Cards[0].CurrentUpgradeLevel == 1 && f.Cards[0].Enchantment is null,
                "settled preview binds the upgraded original without applying its effect");
            f.Apply("deselect", f.Cards[0]);
            Check(f.Ready().Selected.Length == 0 && f.Clears == 1, "single enchant can return to selection");
            f.Apply("select", f.Cards[1]);
            for (int i = 0; i < 8; i++) Check(f.Choice.Read() is null && f.Inputs == 2 && f.Commits == 0,
                "reselection waits for queued old previews without confirming");
            f.FlushFreedPreviews(); Check(f.Ready().Selected.Single() == f.Cards[1], "reselected original settles");
            f.Apply("confirm"); f.Complete();
            Check(f.Commits == 1 && f.Task.Task.Result.Single() == f.Cards[1], "only the explicitly confirmed selection completes");
        }
        foreach (string mode in new[] { "extra_child", "wrong_original", "wrong_effect", "wrong_upgrade", "hidden_preview", "context_during_wait", "bound_holder_queued" })
        {
            var f = new InteractiveChoiceFixture(enchant: true); f.Apply("select", f.Cards[0]); f.Choice.Read();
            if (mode == "context_during_wait") f.Context = false;
            else
            {
                f.FlushFreedPreviews();
                var before = (NPreviewCardHolder)f.BeforeEnchant.Children.Single();
                var after = (NPreviewCardHolder)f.AfterEnchant.Children.Single();
                if (mode == "extra_child") f.BeforeEnchant.Children.Add(new Control());
                if (mode == "wrong_original") before.CardNode!.Model = f.Cards[1];
                if (mode == "wrong_effect") after.CardModel!.Enchantment!.Amount++;
                if (mode == "wrong_upgrade") after.CardModel!.CurrentUpgradeLevel++;
                if (mode == "hidden_preview") after.Visible = false;
                if (mode == "bound_holder_queued") { f.Ready(); after.QueueFree(); }
            }
            bool rejected = false; try { f.Choice.Read(); } catch (InvalidOperationException) { rejected = true; }
            Check(rejected && f.Inputs == 1 && f.Commits == 0, "single enchant rejects before confirmation: " + mode);
        }
    }
    private static void InteractiveChoiceCases()
    {
        {
            var f = new InteractiveChoiceFixture();
            f.Grid.CurrentlyDisplayedCardHolders.RemoveAt(2);
            Check(f.Ready().Domain.SequenceEqual(f.Cards) && f.Inputs == 0,
                "partial native allocation preserves the full selector domain without input");
        }
        VirtualizedChoiceCases();
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

    private static void VirtualizedChoiceCases()
    {
        foreach (bool smith in new[] { false, true })
        {
            var f = new InteractiveChoiceFixture(smith: smith, count: 128, window: 25, maximumDomain: 128);
            f.Grid.FixtureSnapScroll = true;
            Check(f.Ready().Domain.Length == 128 && f.Inputs == 0, "full rest exposes all 128 originals");
            f.Choice.Apply("select", f.Cards[0]); f.PagedReady();
            if (!smith) { f.Choice.Apply("select", f.Cards[127]); f.PagedReady(); }
            f.Choice.Apply("confirm"); f.Complete();
            Check(f.Commits == 1 && f.Task.Task.Result.SequenceEqual(smith ? new[] { f.Cards[0] } : new[] { f.Cards[0], f.Cards[127] }),
                "full rest confirms exact endpoint originals across 128-card grid");
        }
        foreach (var (count, limit) in new[] { (65, 64), (129, 128), (3, 129) })
        {
            bool rejected = false;
            try { _ = new InteractiveChoiceFixture(count: count, maximumDomain: limit); }
            catch (InvalidOperationException) { rejected = true; }
            Check(rejected, "selector retains explicit legacy/full bounds");
        }
        {
            var f = new InteractiveChoiceFixture(count: 128, window: 25, maximumDomain: 128);
            f.Grid.FixtureScrollBottom = -6720; f.Grid.FixtureSnapScroll = true;
            f.Ready(); f.Choice.Apply("select", f.Cards[0]);
            bool rejected = false; try { f.PagedReady(); } catch (InvalidOperationException) { rejected = true; }
            Check(rejected && f.Inputs == 0 && f.Commits == 0, "unreachable allocation boundary fails without selecting another card");
        }
        foreach (bool snap in new[] { true, false }) foreach (bool delayed in new[] { false, true })
        {
            var f = new InteractiveChoiceFixture(count: 33, window: 25) { DelayHighlights = delayed };
            f.Grid.FixtureSnapScroll = snap;
            Check(f.Ready().Domain.SequenceEqual(f.Cards) && f.Inputs == 0 && f.Grid.FixturePanInputs == 0,
                "large Cook domain is complete without observation-time scrolling");
            f.Choice.Apply("select", f.Cards[32]); f.PagedReady();
            f.Choice.Apply("select", f.Cards[0]);
            for (int i = 0; i < 8; i++) Check(f.Choice.Read() is null && f.Grid.FixturePanInputs == 1 && f.Inputs == 1,
                "same-frame reads await native allocation without duplicate pan or selection");
            var view = f.PagedReady();
            Check(view.Selected.SequenceEqual(new[] { f.Cards[32], f.Cards[0] }) && f.Inputs == 2 &&
                f.Grid.CurrentlyDisplayedCardHolders.Any(h => !h.Visible) && f.Grid.FixtureScroll.Position.Y == f.Grid.FixtureScrollTarget,
                "two exact originals across pages reach preview with motion stopped and padding ignored");
            f.Choice.Apply("deselect", f.Cards[32]);
            Check(f.PagedReady().Selected.Single() == f.Cards[0] && f.Clears == 1,
                "preview return restores only the retained original");
            f.Choice.Apply("select", f.Cards[32]); f.PagedReady();
            Check(f.Inputs == 4 && f.Grid.FixturePanInputs > 1 && f.Commits == 0,
                "backward navigation reselects the exact original without premature confirmation");
            f.Choice.Apply("confirm"); f.Complete();
            Check(f.Commits == 1 && f.Task.Task.Result.SequenceEqual(new[] { f.Cards[0], f.Cards[32] }),
                "large Cook commits exactly the explicit final pair");
        }
        foreach (string mode in new[] { "domain", "order", "holder_rebind", "foreign_highlight", "context_during_pan", "pool_during_pan", "target_during_pan", "allocation_timeout" })
        {
            var f = new InteractiveChoiceFixture(count: 33, window: 25); f.Ready();
            bool pan = mode.EndsWith("during_pan", StringComparison.Ordinal) || mode == "allocation_timeout";
            if (pan) { f.Choice.Apply("select", f.Cards[0]); f.Choice.Read(); }
            if (mode == "domain") f.Grid.FixtureCards[0] = new CardModel();
            if (mode == "order") f.Grid.FixtureCards.Reverse();
            if (mode == "holder_rebind") { var h = f.Grid.CurrentlyDisplayedCardHolders[0]; h.CardModel = f.Cards[0]; h.CardNode!.Model = f.Cards[0]; }
            if (mode == "foreign_highlight") f.Grid.FixtureHighlights.Add(f.Cards[0]);
            if (mode == "context_during_pan") f.Context = false;
            if (mode == "pool_during_pan") { var h = f.Grid.CurrentlyDisplayedCardHolders[0]; f.Grid.CurrentlyDisplayedCardHolders[0] = new() { CardModel = h.CardModel, CardNode = h.CardNode, Hitbox = h.Hitbox }; }
            if (mode == "target_during_pan") f.Grid.SetScrollPosition(-99);
            bool rejected = false;
            try { for (int i = 0; i < (mode == "allocation_timeout" ? 130 : 1); i++) f.Choice.Read(); }
            catch (InvalidOperationException) { rejected = true; }
            Check(rejected && f.Inputs == 0 && f.Commits == 0 && f.Grid.FixturePanInputs == (pan ? 1 : 0),
                "virtualized selector rejects without choosing or replaying: " + mode);
        }
        foreach (string mode in new[] { "context", "pool", "highlight", "stalled" })
        {
            var f = new InteractiveChoiceFixture(count: 33, window: 25); f.Ready();
            f.Grid.FixtureSnapScroll = true;
            f.Choice.Apply("select", f.Cards[0]); f.Choice.Read(); f.ScrollFrame();
            f.Grid.FixtureAllocate = () => {
                if (mode == "context") f.Context = false;
                if (mode == "pool") { var h = f.Grid.CurrentlyDisplayedCardHolders[0]; f.Grid.CurrentlyDisplayedCardHolders[0] = new() { CardModel = h.CardModel, CardNode = h.CardNode, Hitbox = h.Hitbox }; }
                if (mode == "highlight") f.Grid.FixtureHighlights.Add(f.Cards[0]);
            };
            bool rejected = false;
            try { f.PagedReady(); } catch (InvalidOperationException) { rejected = true; }
            Check(rejected && f.Inputs == 0 && f.Commits == 0 && f.Grid.FixturePanInputs == (mode == "stalled" ? 2 : 1),
                "settled-page allocation revalidates before any card input: " + mode);
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

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
        foreach(string type in new[]{"mirror","hammer","kifuda","dagger","stamp"})foreach(int count in new[]{1,2,4})foreach(bool delayed in new[]{false,true})foreach(string mode in new[]{"success","wrong_result","wrong_effect","pending_dispose"}) {
            var player=new Player{Gold=100};var cards=Enumerable.Range(0,count).Select(i=>{var c=new CardModel{Owner=player};c.Id.Entry="CARD_"+i;return c;}).ToArray();player.Deck.Cards.AddRange(cards);
            RelicModel relic=type switch{"mirror"=>new DollysMirror(),"hammer"=>new GnarledHammer(),"kifuda"=>new Kifuda(),"dagger"=>new PunchDagger(),_=>new RoyalStamp()};
            var overlays=new NOverlayStack();var purchase=new PickupPurchase(player,relic){Delay=delayed?new():null};var dispatch=new PinnedShopPickupDispatch(player,relic,overlays,purchase,()=>true);
            int clicks=0,confirms=0,previews=0;var chosen=new List<CardModel>();
            Control Build(IReadOnlyList<CardModel> domain,EnchantmentModel? effect,int amount,CardSelectorPrefs prefs) {
                NCardGridSelectionScreen screen=effect is null?new NDeckCardSelectScreen():new NDeckEnchantSelectScreen();
                var selected=new TaskCompletionSource<IEnumerable<CardModel>>();screen.SelectionTask=selected.Task;
                var grid=new NCardGrid();var container=new Control{Visible=false};var preview=new Control();var confirm=new NConfirmButton();var open=new NConfirmButton();
                screen.Bind("%CardGrid",grid);screen.Bind(effect is null?"%PreviewContainer":prefs.MaxSelect==1?"%EnchantSinglePreviewContainer":"%EnchantMultiPreviewContainer",container);screen.Bind("%Confirm",open);
                container.Bind(effect is null?"%PreviewConfirm":"Confirm",confirm);
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
            if(mode=="wrong_effect")purchase.After=()=>cards[0].CurrentUpgradeLevel++;
            try {
                if(mode!="success") {
                    bool failed=false;
                    try {
                        dispatch.Invoke();if(delayed)purchase.Delay!.SetResult();
                        if(mode!="pending_dispose")for(int i=0;i<12&&dispatch.Completion==ShopV1Completion.Pending;i++)dispatch.Advance();
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
                for(int i=0;i<12&&dispatch.Completion==ShopV1Completion.Pending;i++)dispatch.Advance();
                Check(dispatch.Completion==ShopV1Completion.Succeeded,"native pickup complete "+type+count);
                int selectedCount=Math.Min(type is "hammer" or "kifuda"?3:1,count);
                Check(player.Gold==90&&player.Relics.Single()==relic,"pickup relic and payment exact");
                if(type=="mirror")Check(player.Deck.Cards.Count==count+1&&!cards.Contains(player.Deck.Cards[^1])&&player.Deck.Cards[^1].Id.Entry==cards[0].Id.Entry,"mirror exact native clone insertion");
                else Check(cards.Take(selectedCount).All(c=>c.Enchantment is not null)&&cards.Skip(selectedCount).All(c=>c.Enchantment is null),"only chosen originals enchanted");
                Check(confirms==(clicks==0?0:1)&&previews==confirms,"one native preview/confirm");dispatch.Dispose();Check(purchase.Disposed,"pickup detaches purchase");
            }finally{try{dispatch.Dispose();}catch{}typeof(PinnedShopPickupDispatch).GetField("Active",BindingFlags.Static|BindingFlags.NonPublic)!.SetValue(null,null);CardSelectCmd.GenericHandler=null;CardSelectCmd.EnchantHandler=null;NDeckCardSelectScreen.Factory=null;NDeckEnchantSelectScreen.Factory=null;}
        }
    }
}

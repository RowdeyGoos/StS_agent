using System.Reflection;
using System.Runtime.CompilerServices;
using System.Text.Json;

// Real native run/reward objects under TestMode and explicit in-memory saves.
internal static class EventInventoryOracle
{
    public static async Task<string> Run(Assembly asm,string digest)
    {
        const BindingFlags flags=BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance|BindingFlags.Static;
        Type T(string n)=>asm.GetType("MegaCrit.Sts2.Core."+n,true)!;
        object P(object o,string n)=>o.GetType().GetProperty(n,flags)!.GetValue(o)!;
        object C(object o,string n,params object?[] a){var t=o as Type??o.GetType();return t.GetMethods(flags).Single(m=>m.Name==n&&!m.IsGenericMethodDefinition&&m.GetParameters().Length==a.Length&&m.GetParameters().Select((p,i)=>a[i] is null||p.ParameterType.IsInstanceOfType(a[i])).All(x=>x)).Invoke(o is Type?null:o,a)!;}
        void F(object o,string n,object? v)=>o.GetType().GetField(n,flags)!.SetValue(o,v);
        object[] Items(object o)=>((System.Collections.IEnumerable)o).Cast<object>().ToArray();
        Array Typed(IEnumerable<object> source,Type t){var v=source.ToArray();var result=Array.CreateInstance(t,v.Length);Array.Copy(v,result,v.Length);return result;}
        void Require(bool value,string message){if(!value)throw new InvalidOperationException(message);}
        async Task Await(object task)=>await ((Task)task).WaitAsync(TimeSpan.FromSeconds(3));
        object Get(string method,string suffix)=>T("Models.ModelDb").GetMethods().Single(m=>m.Name==method&&m.IsGenericMethodDefinition).MakeGenericMethod(T("Models."+suffix)).Invoke(null,null)!;
        T("TestSupport.TestMode").GetProperty("IsOn")!.SetValue(null,true);
        // Native TestMode initialization exits before inspecting mod directories.
        await Await(C(T("Modding.ModManager"),"Initialize",null,null,null));
        foreach(var t in asm.GetTypes().Where(t=>!t.IsAbstract&&t.IsSubclassOf(T("Models.AbstractModel"))&&t.Namespace!.StartsWith("MegaCrit.Sts2.Core.Models.")))C(T("Models.ModelDb"),"Inject",t);
        var loc=RuntimeHelpers.GetUninitializedObject(T("Localization.LocManager"));
        var tables=(System.Collections.IDictionary)Activator.CreateInstance(typeof(Dictionary<,>).MakeGenericType(typeof(string),T("Localization.LocTable")))!;
        void Table(string name,Dictionary<string,string> entries)=>tables.Add(name,Activator.CreateInstance(T("Localization.LocTable"),new object?[]{name,entries,null})!);
        var eventText=new Dictionary<string,string>();
        foreach(var pair in new[]{("SELF_HELP_BOOK",new[]{"READ_THE_BACK","READ_PASSAGE","READ_ENTIRE_BOOK","READ_THE_BACK_LOCKED","READ_PASSAGE_LOCKED","READ_ENTIRE_BOOK_LOCKED","NO_OPTIONS"}),("WOOD_CARVINGS",new[]{"BIRD","SNAKE","SNAKE_LOCKED","TORUS"}),("TEA_MASTER",new[]{"BONE_TEA","EMBER_TEA","TEA_OF_DISCOURTESY","BONE_TEA_LOCKED","EMBER_TEA_LOCKED"}),("THE_FUTURE_OF_POTIONS",new[]{"POTION"})})
        {
            foreach(var branch in pair.Item2){foreach(var suffix in new[]{"title","description"})eventText[pair.Item1+".pages.INITIAL.options."+branch+"."+suffix]="Event";eventText[pair.Item1+".pages."+branch+".description"]="Event";}
            eventText[pair.Item1+".pages.DONE.description"]="Done";
        }
        foreach(var key in new[]{"PROCEED.title","PROCEED.description"})eventText[key]="Continue";
        Table("events",eventText);
        Table("characters",new[]{"title","titleObject","possessiveAdjective","pronounObject","pronounPossessive","pronounSubject"}.ToDictionary(k=>"IRONCLAD."+k,k=>"Ironclad"));
        foreach(var pair in new[]{("cards","CardModel"),("relics","RelicModel"),("powers","PowerModel"),("potions","PotionModel"),("enchantments","EnchantmentModel")})
        {
            var texts=new Dictionary<string,string>();
            foreach(var t in asm.GetTypes().Where(t=>!t.IsAbstract&&t.IsSubclassOf(T("Models."+pair.Item2))))
            foreach(var suffix in new[]{"name","title","description","upgradeDescription","selectionScreenPrompt"})texts[C(T("Helpers.StringHelper"),"Slugify",t.Name)+"."+suffix]=t.Name;
            Table(pair.Item1,texts);
        }
        var ui=new Dictionary<string,string>();
        foreach(var prefix in new[]{"CARD_TYPE","CARD_RARITY","POTION_RARITY"})foreach(var value in new[]{"ATTACK","SKILL","POWER","COMMON","UNCOMMON","RARE","EVENT","TOKEN"})ui[prefix+"."+value]="Kind";
        Table("gameplay_ui",ui);
        F(loc,"_tables",tables);C(loc,"LoadLocFormatters");loc.GetType().GetProperty("CultureInfo",flags)!.SetValue(loc,System.Globalization.CultureInfo.InvariantCulture);loc.GetType().GetProperty("Instance",flags)!.SetValue(null,loc);
        foreach(var pair in new[]{("card_keywords","Entities.Cards.CardKeyword"),("static_hover_tips","HoverTips.StaticHoverTip")})
            Table(pair.Item1,Enum.GetNames(T(pair.Item2)).SelectMany(n=>new[]{"title","description"}.Select(k=>C(T("Helpers.StringHelper"),"Slugify",n)+"."+k)).ToDictionary(k=>k,k=>k));
        var cache=T("Assets.PreloadManager").GetProperty("Cache")!.GetValue(null)!;
        var assets=cache.GetType().GetField("_cache",flags)!.GetValue(cache)!;
        C(assets,"TryAdd","res://images/enchantments/missing_enchantment.png",new Godot.CompressedTexture2D());
        C(assets,"TryAdd","res://images/atlases/ui_atlas.sprites/card/energy_ironclad.tres",new Godot.AtlasTexture());
        // Hover tips load presentation resources even without a scene tree.
        var mockIcons=new List<Godot.Texture2D>();
        foreach(var powerType in asm.GetTypes().Where(t=>!t.IsAbstract&&t.IsSubclassOf(T("Models.PowerModel"))))
        {
            var icon=new Godot.GradientTexture2D();
            icon.TakeOverPath("res://images/atlases/power_atlas.sprites/"+C(T("Helpers.StringHelper"),"Slugify",powerType.Name).ToString()!.ToLowerInvariant()+".tres");
            mockIcons.Add(icon);
        }
        var rows=new List<object>();
        foreach(string seed in new[]{"0","2","42"})
        foreach(int ascension in new[]{0,10})
        foreach(bool enhanced in new[]{false,true})
        foreach(string eventName in new[]{"SelfHelpBook","WoodCarvings","TeaMaster","TheFutureOfPotions"})
        foreach(int optionIndex in new[]{0,1,2})
        {
            var store=Activator.CreateInstance(T("Saves.Test.MockGodotFileIo"),new object[]{"user://isolated-fixture"})!;
            var saves=Activator.CreateInstance(T("Saves.SaveManager"),new object[]{store,true})!;F(saves,"_currentProfileId",0);C(T("Saves.SaveManager"),"MockInstanceForTesting",saves);
            C(saves,"InitPrefsDataForTest");P(saves,"PrefsSave").GetType().GetProperty("UploadData")!.SetValue(P(saves,"PrefsSave"),false);
            T("Context.LocalContext").GetProperty("NetId")!.SetValue(null,0UL);
            var player=C(T("Entities.Players.Player"),"CreateForNewRun",Get("Character","Characters.Ironclad"),T("Unlocks.UnlockState").GetField("all")!.GetValue(null),0UL);
            var state=C(T("Runs.RunState"),"CreateForTest",Typed(new[]{player},player.GetType()),null,null,Enum.Parse(T("Runs.GameMode"),"Standard"),ascension,seed);
            var manager=T("Runs.RunManager").GetProperty("Instance")!.GetValue(null)!;
            C(manager,"SetUpTest",state,Activator.CreateInstance(T("Multiplayer.NetReplayGameService"),new object[]{0UL})!,true,false);
            try
            {
                Require(!(bool)P(manager,"ShouldSave") && !(bool)P(P(saves,"PrefsSave"),"UploadData"),"Persistence and metrics must be disabled.");
                var selector=Activator.CreateInstance(T("TestSupport.TestCardSelector"))!;
                using var selected=(IDisposable)C(T("Commands.CardSelectCmd"),"UseSelector",selector);
                // Authored starting inventory; the actual option commands perform all effects.
                C(P(player,"Creature"),"SetCurrentHpInternal",31m);
                player.GetType().GetProperty("Gold")!.SetValue(player,250);
                var power=C(state,"CreateCard",Get("Card","Cards.Inflame"),player);
                C(P(player,"Deck"),"AddInternal",power,-1,true);
                var deck=Items(P(P(player,"Deck"),"Cards"));
                foreach(int i in new[]{0,5}){C(deck[i],"UpgradeInternal");C(deck[i],"FinalizeUpgradeInternal");}
                var setupRelics=new List<string>();
                if(enhanced)setupRelics.AddRange(new[]{"MoltenEgg","ToxicEgg","FrozenEgg","WingCharm"});
                if(eventName=="TheFutureOfPotions" && ascension>=4)setupRelics.Add("PotionBelt");
                if(eventName=="TeaMaster" && enhanced)setupRelics.Add(new[]{"BoneTea","EmberTea","TeaOfDiscourtesy"}[optionIndex]);
                foreach(string name in setupRelics)await Await(C(T("Commands.RelicCmd"),"Obtain",C(Get("Relic","Relics."+name),"ToMutable"),player,-1));
                if(enhanced)C(T("Commands.CardCmd"),"Enchant",C(Get("Enchantment","Enchantments.Slither"),"ToMutable"),deck[0],1m);
                if(eventName=="TheFutureOfPotions")foreach(string name in new[]{"FirePotion","Ashwater","SoldiersStew"})await Await(C(T("Commands.PotionCmd"),"TryToProcure",C(Get("Potion","Potions."+name),"ToMutable"),player,-1));
                object Card(object c)=>new{id=P(P(c,"Id"),"Entry").ToString(),upgrade=P(c,"CurrentUpgradeLevel"),enchantment=P(c,"Enchantment") is object e?(object)new{id=P(P(e,"Id"),"Entry").ToString(),amount=P(e,"Amount")}:null};
                object Boundary()=>new{hp=P(P(player,"Creature"),"CurrentHp"),maxHp=P(P(player,"Creature"),"MaxHp"),gold=P(player,"Gold"),deck=Items(P(P(player,"Deck"),"Cards")).Select(Card).ToArray(),relics=Items(P(player,"Relics")).Select(r=>P(P(r,"Id"),"Entry").ToString()).ToArray(),potions=Items(P(player,"PotionSlots")).Select(p=>p is null?null:P(P(p,"Id"),"Entry").ToString()).ToArray()};
                var before=Boundary();
                var canonical=Get("Event","Events."+eventName);
                var parent=Activator.CreateInstance(T("Rooms.EventRoom"),new[]{canonical})!;C(state,"PushRoom",parent);
                // Reward claims append to the current in-memory map history entry.
                var history=Activator.CreateInstance(T("Runs.History.MapPointHistoryEntry"),new[]{Enum.Parse(T("Map.MapPointType"),"Unknown"),state})!;
                var historyList=(System.Collections.IList)state.GetType().GetField("_mapPointHistory",flags)!.GetValue(state)!;
                var actHistory=(System.Collections.IList)Activator.CreateInstance(historyList.GetType().GetGenericArguments()[0])!;
                actHistory.Add(history);historyList.Add(actHistory);
                C(P(manager,"EventSynchronizer"),"BeginEvent",canonical,false,null);
                var evt=C(P(manager,"EventSynchronizer"),"GetLocalEvent");
                var options=Items(P(evt,"CurrentOptions"));Require(options.Length==3,"Expected three event options: "+eventName);
                var option=options[optionIndex];Require(!(bool)P(option,"IsLocked"),"Chosen option must be legal.");
                var selection=Array.Empty<int>();
                if(eventName is "SelfHelpBook" or "WoodCarvings")
                {
                    string? enchant=eventName=="SelfHelpBook"?new[]{"Sharp","Nimble","Swift"}[optionIndex]:optionIndex==1?"Slither":null;
                    var model=enchant is null?null:Get("Enchantment","Enchantments."+enchant);
                    selection=Enumerable.Range(0,deck.Length).Where(i=>model is null?(bool)P(deck[i],"IsTransformable")&&P(deck[i],"Rarity").ToString()=="Basic":(bool)C(model,"CanEnchant",deck[i]) && (eventName!="SelfHelpBook" || P(deck[i],"Type").ToString()==new[]{"Attack","Skill","Power"}[optionIndex])).Take(1).ToArray();
                    Require(selection.Length==1,"Expected an eligible physical deck card.");
                    // Singleton native grids auto-select before consulting the selector.
                    int count=deck.Count(c=>model is null?(bool)P(c,"IsTransformable")&&P(c,"Rarity").ToString()=="Basic":(bool)C(model,"CanEnchant",c)&&(eventName!="SelfHelpBook"||P(c,"Type").ToString()==new[]{"Attack","Skill","Power"}[optionIndex]));
                    if(count>1)C(selector,"PrepareToSelect",Typed(selection.Select(i=>deck[i]),T("Models.CardModel")));
                }
                var rewardOffers=new List<object>();
                var method=selector.GetType().GetMethod("PrepareToSelectCardReward")!;
                var delegateType=method.GetParameters()[0].ParameterType;
                var invoke=delegateType.GetMethod("Invoke")!;
                Func<object,object,object> chooseReward=(offered,alternatives)=>{
                    var cards=Items(offered).Select(o=>P(o,"Card")).ToArray();
                    rewardOffers.Add(cards.Select(Card).ToArray());
                    var answer=Activator.CreateInstance(invoke.ReturnType)!;invoke.ReturnType.GetField("card")!.SetValue(answer,cards[0]);return answer;
                };
                var parameters=invoke.GetParameters().Select(p=>System.Linq.Expressions.Expression.Parameter(p.ParameterType)).ToArray();
                var body=System.Linq.Expressions.Expression.Convert(System.Linq.Expressions.Expression.Invoke(System.Linq.Expressions.Expression.Constant(chooseReward),parameters.Select(p=>System.Linq.Expressions.Expression.Convert(p,typeof(object)))),invoke.ReturnType);
                method.Invoke(selector,new[]{System.Linq.Expressions.Expression.Lambda(delegateType,body,parameters).Compile()});
                var choices=options.Where(o=>!(bool)P(o,"IsLocked")).Select(o=>P(o,"TextKey").ToString()!.Split('.').Last()).ToArray();
                await Await(C(option,"Chosen"));
                Require((bool)P(evt,"IsFinished"),"Event did not finish: "+eventName);
                Require(Items(selector.GetType().GetField("_cardsToSelectTaskQueue",flags)!.GetValue(selector)!).Length==0,"Physical selection was not consumed.");
                var result=Boundary();
                object Rng(object rng)=>new{counter=P(rng,"Counter"),suffix=C(rng,"NextDouble")};
                rows.Add(new{seed,ascension,enhanced,eventName,optionIndex,selection,choices,before,rewardOffers,state=result,canRemovePotions=P(player,"CanRemovePotions"),rng=new{eventRng=Rng(P(evt,"Rng")),rewards=Rng(P(P(player,"PlayerRng"),"Rewards")),niche=Rng(P(P(state,"Rng"),"Niche")),transformations=Rng(P(P(player,"PlayerRng"),"Transformations"))}});
            }
            finally {C(manager,"CleanUp",true);}
        }
        GC.KeepAlive(mockIcons);
        return JsonSerializer.Serialize(new{source="Native event option commands with authored inventory, declared physical selections and first reward choice; TestMode/mock persistence, no UI or combat",assemblySha256=digest,rows},new JsonSerializerOptions{WriteIndented=true});
    }
}

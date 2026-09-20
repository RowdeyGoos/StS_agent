using System.Reflection;
using System.Runtime.CompilerServices;
using System.Text.Json;

public class EventChoiceSelector : DispatchProxy
{
    public Func<MethodInfo,object?[],object?> Handler = null!;
    protected override object? Invoke(MethodInfo? method,object?[]? args)=>Handler(method!,args!);
}

internal static class EventRosterOracle
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
        // Only localization identifiers are extracted; display strings are authored stubs.
        var eventText=new Dictionary<string,string>();
        var atoms=new Dictionary<string,HashSet<string>>();
        foreach(var type in asm.GetTypes().Where(t=>t.FullName!.StartsWith("MegaCrit.Sts2.Core.Models.Events.")))
        foreach(var method in type.GetMethods(flags|BindingFlags.DeclaredOnly).Cast<MethodBase>().Concat(type.GetConstructors(flags)))
        {
            var il=method.GetMethodBody()?.GetILAsByteArray();if(il is null)continue;
            for(int i=0;i<il.Length-4;i++)if(il[i]==0x72)
            {
                string? literal=null;try{literal=method.Module.ResolveString(BitConverter.ToInt32(il,i+1));}catch(ArgumentException){}
                if(literal is null)continue;
                var rootType=type;while(rootType.IsNested)rootType=rootType.DeclaringType!;
                var modelId=C(T("Helpers.StringHelper"),"Slugify",rootType.Name).ToString()!;
                if(!atoms.ContainsKey(modelId))atoms[modelId]=new HashSet<string>{"INITIAL","ALL","DONE"};
                foreach(System.Text.RegularExpressions.Match match in System.Text.RegularExpressions.Regex.Matches(literal,@"[A-Z][A-Z_0-9]+"))atoms[modelId].Add(match.Value);
                if(!literal.Contains('.'))continue;
                eventText[literal]="Event";
                foreach(var suffix in new[]{"title","description","selectionScreenPrompt"})eventText[literal+"."+suffix]="Event";
            }
        }
        foreach(var key in new[]{"PROCEED.title","PROCEED.description","GENERIC.youAreDead.description"})eventText[key]="Continue";
        foreach(var pair in atoms)
        {
            var words=pair.Value.SelectMany(w=>new[]{w}.Concat(w.EndsWith("_")?Enumerable.Range(0,10).Select(i=>w+i).Append(w+"LOOP"):Array.Empty<string>())).ToArray();
            foreach(var page in words)foreach(var option in words)
            foreach(var suffix in new[]{"title","description"})eventText[pair.Key+".pages."+page+".options."+option+"."+suffix]="Event";
            foreach(var word in words)eventText[pair.Key+".DISHES."+word+".title"]="Dish";
        }
        foreach(var color in new[]{"IRONCLAD","SILENT","REGENT","NECROBINDER","DEFECT"})
        foreach(var suffix in new[]{"title","description"})eventText["COLORFUL_PHILOSOPHERS.pages.INITIAL.options."+color+"."+suffix]="Event";
        foreach(var key in eventText.Keys.Where(k=>k.StartsWith("FAKE_MERCHANT.talk.")).ToArray())eventText.Remove(key);
        Table("events",eventText);
        Table("ancients",eventText);
        Table("characters",new[]{"IRONCLAD","SILENT","REGENT","NECROBINDER","DEFECT"}.SelectMany(c=>new[]{"title","titleObject","possessiveAdjective","pronounObject","pronounPossessive","pronounSubject","aromaPrinciple","goldMonologue"}.Select(k=>c+"."+k)).ToDictionary(k=>k,k=>"Character"));
        foreach(var pair in new[]{("cards","CardModel"),("relics","RelicModel"),("powers","PowerModel"),("potions","PotionModel"),("enchantments","EnchantmentModel"),("monsters","MonsterModel"),("afflictions","AfflictionModel")})
        {
            var texts=new Dictionary<string,string>();
            foreach(var t in asm.GetTypes().Where(t=>!t.IsAbstract&&t.IsSubclassOf(T("Models."+pair.Item2))))
            foreach(var suffix in new[]{"name","title","description","eventDescription","upgradeDescription","selectionScreenPrompt"})texts[C(T("Helpers.StringHelper"),"Slugify",t.Name)+"."+suffix]=t.Name;
            if(pair.Item1=="relics")foreach(var character in new[]{"IRONCLAD","SILENT","REGENT","NECROBINDER","DEFECT"})texts["SEA_GLASS."+character+".title"]="Sea Glass";
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

        var stunIcon=new Godot.GradientTexture2D();
        stunIcon.TakeOverPath("res://images/atlases/intent_atlas.sprites/intent_stun.tres");mockIcons.Add(stunIcon);
        Table("intents",new Dictionary<string,string>{{"STUN.title","Stun"},{"STUN.description","Stun"}});

        var tree=(Godot.SceneTree)Godot.Engine.GetMainLoop();
        await tree.ToSignal(tree,Godot.SceneTree.SignalName.ProcessFrame);
        var names=new[]{"AromaOfChaos","MorphicGrove","TabletOfTruth","WhisperingHollow","Wellspring","SlipperyBridge","SunkenStatue","SapphireSeed","ByrdonisNest","LuminousChoir","UnrestSite","BrainLeech","RoomFullOfCheese","TheLegendsWereTrue","ThisOrThat","Amalgamator","Bugslayer","DoorsOfLightAndDark","DrowningBeacon","FieldOfManSizedHoles","GraveOfTheForgotten","HungryForMushrooms","InfestedAutomaton","LostWisp","PotionCourier","Reflections","SpiralingWhirlpool","SpiritGrafter","SunkenTreasury","Symbiote","WaterloggedScriptorium","ZenWeaver","StoneOfAllTime","AbyssalBaths","ColossalFlower","DollRoom","RoundTeaParty","Trial","ColorfulPhilosophers","RanwidTheElder","RelicTrader","WelcomeToWongos","TinkerTime","TrashHeap","EndlessConveyor","SelfHelpBook","WoodCarvings","TeaMaster","TheFutureOfPotions","JungleMazeAdventure","Darv","Nonupeipe","Orobas","Pael","Tanx","Tezcatara","Vakuu","Neow","WarHistorianRepy","DenseVegetation","BattlewornDummy","PunchOff","TheLanternKey","CrystalSphere","FakeMerchant"};
        string? filter=Godot.OS.GetCmdlineUserArgs().Skip(1).FirstOrDefault();
        if(filter is not null)Require(names.Contains(filter),"Undeclared event case.");
        var rows=new List<object>();
        var ancientNames=new[]{"Darv","Nonupeipe","Orobas","Pael","Tanx","Tezcatara","Vakuu","Neow"};
        var coveredAncients=new Dictionary<string,HashSet<string>>();
        foreach(string name in names.Where(n=>filter is null||n==filter))
        foreach(string seed in ancientNames.Contains(name)?Enumerable.Range(0,128).Select(n=>n.ToString()):name=="TinkerTime"?Enumerable.Range(0,32).Select(n=>n.ToString()):name=="Trial"?new[]{"0","2","6","42"}:new[]{"0","2","42"})
        foreach(int ascension in new[]{"0","2","42"}.Contains(seed)?new[]{0,10}:new[]{0})
        foreach(bool enhanced in new[]{"0","2","42"}.Contains(seed)?new[]{false,true}:new[]{false})
        foreach(int variant in name=="CrystalSphere"?Enumerable.Range(0,32):name=="WarHistorianRepy"?new[]{0,1,2}:name is "Darv" or "BattlewornDummy"?new[]{0,1}:new[]{0})
        foreach(int selectionVariant in seed=="0"&&ascension==0&&enhanced&&name is not ("CrystalSphere" or "FakeMerchant" or "BattlewornDummy")?new[]{0,1,2}:new[]{0})
        {
            var frontier=new Queue<int[]>();
            if(name!="CrystalSphere"||variant==0)frontier.Enqueue(Array.Empty<int>());
            else{frontier.Enqueue(new[]{0});frontier.Enqueue(new[]{1});}
            var seen=new HashSet<string>();int visited=0;
            while(frontier.TryDequeue(out var path))
            {
                Require(++visited<(name=="FakeMerchant"?512:256),"Event branch exploration bound exceeded.");
                Godot.GD.Print($"CASE {name} {seed} A{ascension} enhanced={enhanced} path={string.Join(',',path)}");
                var store=Activator.CreateInstance(T("Saves.Test.MockGodotFileIo"),new object[]{"user://isolated-fixture"})!;
                var saves=Activator.CreateInstance(T("Saves.SaveManager"),new object[]{store,true})!;F(saves,"_currentProfileId",0);C(T("Saves.SaveManager"),"MockInstanceForTesting",saves);
                C(saves,"InitPrefsDataForTest");P(saves,"PrefsSave").GetType().GetProperty("UploadData")!.SetValue(P(saves,"PrefsSave"),false);
                T("Context.LocalContext").GetProperty("NetId")!.SetValue(null,0UL);
                var player=C(T("Entities.Players.Player"),"CreateForNewRun",Get("Character","Characters.Ironclad"),T("Unlocks.UnlockState").GetField("all")!.GetValue(null),0UL);
                var state=C(T("Runs.RunState"),"CreateForTest",Typed(new[]{player},player.GetType()),null,null,Enum.Parse(T("Runs.GameMode"),"Standard"),ascension,seed);
                var manager=T("Runs.RunManager").GetProperty("Instance")!.GetValue(null)!;
                int actIndex=ancientNames.Contains(name)&&name!="Neow"?1+(name=="Darv"?variant:0):0;
                state.GetType().GetProperty("CurrentActIndex")!.SetValue(state,actIndex);
                C(manager,"SetUpTest",state,Activator.CreateInstance(T("Multiplayer.NetReplayGameService"),new object[]{0UL})!,true,false);
                try
                {
                    Require(!(bool)P(manager,"ShouldSave")&&!(bool)P(P(saves,"PrefsSave"),"UploadData"),"Persistence and uploads must be disabled.");
                    C(P(player,"Creature"),"SetCurrentHpInternal",61m);player.GetType().GetProperty("Gold")!.SetValue(player,500);
                    foreach(string card in (name=="WarHistorianRepy"?new[]{"Inflame","Offering"}.Concat(Enumerable.Repeat("LanternKey",2-variant)).ToArray():new[]{"Inflame","Offering"}))C(P(player,"Deck"),"AddInternal",C(state,"CreateCard",Get("Card","Cards."+card),player),-1,true);
                    var setupRelics=new List<string>{"Anchor","BagOfPreparation","BronzeScales","TheBoot","HandDrill"};
                    if(enhanced)setupRelics.AddRange(new[]{"MoltenEgg","ToxicEgg","FrozenEgg","WingCharm","BingBong"});
                    foreach(string relic in setupRelics)await Await(C(T("Commands.RelicCmd"),"Obtain",C(Get("Relic","Relics."+relic),"ToMutable"),player,-1));
                    foreach(string potion in new[]{"FoulPotion","FirePotion"})await Await(C(T("Commands.PotionCmd"),"TryToProcure",C(Get("Potion","Potions."+potion),"ToMutable"),player,-1));
                    var selections=new List<object>();
                    object Card(object c)=>new{id=P(P(c,"Id"),"Entry").ToString(),upgrade=P(c,"CurrentUpgradeLevel"),enchantment=P(c,"Enchantment") is object e?(object)new{id=P(P(e,"Id"),"Entry").ToString(),amount=P(e,"Amount")}:null,
                        eventData=c.GetType().Name=="MadScience"?(object)new{kind=P(c,"TinkerTimeType").ToString()!.ToLowerInvariant(),rider=P(c,"TinkerTimeRider").ToString()!.ToLowerInvariant()}:null};
                    object Boundary()=>new{hp=P(P(player,"Creature"),"CurrentHp"),maxHp=P(P(player,"Creature"),"MaxHp"),gold=P(player,"Gold"),deck=Items(P(P(player,"Deck"),"Cards")).Select(Card).ToArray(),relics=Items(P(player,"Relics")).Select(r=>P(P(r,"Id"),"Entry").ToString()).ToArray(),potions=Items(P(player,"PotionSlots")).Select(p=>p is null?null:P(P(p,"Id"),"Entry").ToString()).ToArray()};
                    var selector=(EventChoiceSelector)DispatchProxy.Create(T("TestSupport.ICardSelector"),typeof(EventChoiceSelector));
                    selector.Handler=(method,args)=>{
                        if(method.Name=="GetSelectedCards")
                        {
                            var offered=Items(args[0]!);int min=(int)args[1]!,max=(int)args[2]!;
                            int count=Math.Min(max,selectionVariant==1?min:selectionVariant==2?offered.Length:Math.Max(min,1));
                            var selected=(selectionVariant==2?offered.Reverse():offered).Take(count).ToArray();
                            var deck=Items(P(P(player,"Deck"),"Cards"));
                            selections.Add(new{kind="grid",min,max,offers=offered.Select(Card).ToArray(),deckIndices=offered.Select(c=>Array.IndexOf(deck,c)).ToArray(),selected=selected.Select(c=>Array.IndexOf(offered,c)).ToArray()});
                            var result=Typed(selected,T("Models.CardModel"));
                            return typeof(Task).GetMethod("FromResult")!.MakeGenericMethod(method.ReturnType.GetGenericArguments()[0]).Invoke(null,new object[]{result});
                        }
                        Require(method.Name=="GetSelectedCardReward","Unknown selection boundary.");
                        var offeredCards=Items(args[0]!).Select(c=>P(c,"Card")).ToArray();
                        int? rewardIndex=selectionVariant==1?null:selectionVariant==2?offeredCards.Length-1:0;
                        selections.Add(new{kind="reward",offers=offeredCards.Select(Card).ToArray(),selected=rewardIndex});
                        var answer=Activator.CreateInstance(method.ReturnType)!;method.ReturnType.GetField("card")!.SetValue(answer,rewardIndex is int index?offeredCards[index]:null);return answer;
                    };
                    using var selectedScope=(IDisposable)C(T("Commands.CardSelectCmd"),"UseSelector",selector);
                    Func<object,Task> chooseRewards=async set=>{
                        var sync=P(manager,"RewardsSetSynchronizer");
                        var originalRewards=Items(P(set,"Rewards"));
                        // CallingBell has an explicit TestMode-only fixed reward list. Execute
                        // its real production factory separately, without enabling UI or I/O.
                        if(originalRewards.Length==3 && originalRewards.All(r=>r.GetType().Name=="RelicReward") &&
                           originalRewards.Select(r=>P(P(P(r,"Relic"),"Id"),"Entry").ToString()).SequenceEqual(new[]{"ANCHOR","GREMLIN_HORN","MUMMIFIED_HAND"}) &&
                           Items(P(player,"Relics")).Any(r=>r.GetType().Name=="CallingBell"))
                        {
                            var bell=Items(P(player,"Relics")).Single(r=>r.GetType().Name=="CallingBell");
                            object production;
                            T("TestSupport.TestMode").GetProperty("IsOn")!.SetValue(null,false);
                            try{production=C(bell,"GenerateRewards");}
                            finally{T("TestSupport.TestMode").GetProperty("IsOn")!.SetValue(null,true);}
                            var rewards=(System.Collections.IList)P(set,"Rewards");rewards.Clear();
                            foreach(var reward in Items(production)){C(reward,"Populate");rewards.Add(reward);}
                            selections.Add(new{kind="source_boundary",description="CallingBell production GenerateRewards replaces its TestMode-only fixed list; native Populate and selection follow"});
                        }
                        foreach(var reward in Items(P(set,"Rewards")))
                        {
                            Dictionary<string,object?>? claim=null;
                            if(reward.GetType().Name!="CardReward")
                            {
                                claim=new(){{"kind","claim"},{"reward",reward.GetType().Name},{"claimed",false}};
                                if(reward.GetType().Name=="PotionReward")claim["content"]=P(P(P(reward,"Potion"),"Id"),"Entry").ToString();
                                if(reward.GetType().Name=="RelicReward")claim["content"]=P(P(P(reward,"Relic"),"Id"),"Entry").ToString();
                                if(reward.GetType().Name=="GoldReward")claim["content"]=P(reward,"Amount");
                                if(reward.GetType().Name=="SpecialCardReward")claim["content"]=P(P(reward.GetType().GetField("_card",flags)!.GetValue(reward)!,"Id"),"Entry").ToString();
                                selections.Add(claim);
                            }
                            if(selectionVariant!=1 || reward.GetType().Name=="CardReward")await Await(C(sync,"SelectLocalReward",reward));
                            if(claim is not null)claim["claimed"]=P(reward,"SuccessfullySelected");
                        }
                        if(!(bool)C(sync,"IsRewardsSetCompleted",set))C(sync,"SkipLocalRewardsSet");
                    };
                    var rewardField=T("Rewards.RewardsSet").GetField("testSelector")!;
                    var rewardParameter=System.Linq.Expressions.Expression.Parameter(T("Rewards.RewardsSet"));
                    rewardField.SetValue(null,System.Linq.Expressions.Expression.Lambda(rewardField.FieldType,System.Linq.Expressions.Expression.Invoke(System.Linq.Expressions.Expression.Constant(chooseRewards),System.Linq.Expressions.Expression.Convert(rewardParameter,typeof(object))),rewardParameter).Compile());
                    var before=Boundary();
                    var canonical=Get("Event","Events."+name);
                    C(state,"PushRoom",Activator.CreateInstance(T("Rooms.EventRoom"),new[]{canonical})!);
                    var history=Activator.CreateInstance(T("Runs.History.MapPointHistoryEntry"),new[]{Enum.Parse(T("Map.MapPointType"),"Unknown"),state})!;
                    var historyList=(System.Collections.IList)state.GetType().GetField("_mapPointHistory",flags)!.GetValue(state)!;
                    var actHistory=(System.Collections.IList)Activator.CreateInstance(historyList.GetType().GetGenericArguments()[0])!;actHistory.Add(history);historyList.Add(actHistory);
                    C(P(manager,"EventSynchronizer"),"BeginEvent",canonical,false,null);
                    var evt=C(P(manager,"EventSynchronizer"),"GetLocalEvent");
                    if(P(evt,"LayoutType").ToString()=="Combat")C(evt,"GenerateInternalCombatState",state);
                    await Await(C(evt,"AfterEventStarted"));
                    bool customFinished=false;
                    object[] Choices()
                    {
                        if(name!="FakeMerchant")return Items(P(evt,"CurrentOptions"));
                        if(customFinished||P(state,"CurrentRoom").GetType().Name=="CombatRoom")return Array.Empty<object>();
                        var inventory=P(evt,"Inventory");var result=new List<object>();
                        foreach(var entry in Items(P(inventory,"RelicEntries")).Where(e=>(bool)P(e,"IsStocked")))
                        {
                            var captured=entry;
                            result.Add(new EventCallbackOption(P(P(P(entry,"Model"),"Id"),"Entry").ToString()!,!(bool)P(entry,"EnoughGold"),async()=>{
                                var purchased=(Task)C(captured,"OnTryPurchaseWrapper",inventory,false);await Await(purchased);
                                Require((bool)P(purchased,"Result"),"Native merchant rejected a legal purchase.");
                            }));
                        }
                        if(Items(P(player,"Potions")).Any(p=>p.GetType().Name=="FoulPotion"))
                        result.Add(new EventCallbackOption("THROW_FOUL_POTION",false,async()=>{
                            var node=(Godot.Node)Activator.CreateInstance(T("Nodes.Events.Custom.NFakeMerchant"))!;
                            var button=(Godot.Node)Activator.CreateInstance(T("Nodes.Rooms.NMerchantButton"))!;
                            var view=(Godot.Node)Activator.CreateInstance(T("Nodes.Screens.Shops.NMerchantInventory"))!;
                            try
                            {
                                C(node,"Initialize",evt);
                                node.GetType().GetProperty("MerchantButton",flags)!.SetValue(node,button);
                                node.GetType().GetProperty("Inventory",flags)!.SetValue(node,view);
                                T("Models.EventModel").GetProperty("Node",flags)!.SetValue(evt,node);
                                var potion=Items(P(player,"Potions")).Single(p=>p.GetType().Name=="FoulPotion");
                                Require((bool)P(potion,"PassesCustomUsabilityCheck"),"Native foul potion target is not usable.");
                                await Await(C(potion,"OnUseWrapper",Activator.CreateInstance(T("GameActions.Multiplayer.ThrowingPlayerChoiceContext"))!,null));
                            }
                            finally{T("Models.EventModel").GetProperty("Node",flags)!.SetValue(evt,null);view.Free();button.Free();node.Free();}
                        }));
                        result.Add(new EventCallbackOption("LEAVE",false,async()=>{
                            await Await(C(manager,"EnterRoom",Activator.CreateInstance(T("Rooms.MapRoom"))!));customFinished=true;
                        }));
                        return result.ToArray();
                    }
                    string Key(object option)=>P(option,"Relic") is object relic?P(P(relic,"Id"),"Entry").ToString()!:P(option,"TextKey").ToString()!;
                    var trace=new List<object>();bool confirmation=false;
                    foreach(int index in path)
                    {
                        if(confirmation)
                        {
                            selections.Clear();
                            using(var presentation=new EventPresentation(asm,true,abandon:true))
                            {
                                var popup=(Godot.Node)Activator.CreateInstance(T("Nodes.CommonUi.NAbandonRunConfirmPopup"))!;
                                var net=P(manager,"NetService");
                                try
                                {
                                    manager.GetType().GetProperty("NetService",flags)!.SetValue(manager,Activator.CreateInstance(T("Multiplayer.NetSingleplayerGameService")));
                                    C(popup,index==0?"OnYesButtonPressed":"OnNoButtonPressed",new object?[]{null});
                                    await Task.Yield();
                                    Require(index!=0||(bool)P(manager,"IsAbandoned")&&(int)P(P(player,"Creature"),"CurrentHp")==0,"Native abandon callback did not terminate.");
                                }
                                finally{manager.GetType().GetProperty("NetService",flags)!.SetValue(manager,net);if(Godot.GodotObject.IsInstanceValid(popup))popup.Free();}
                            }
                            confirmation=false;
                            trace.Add(new{choice=index==0?"CONFIRM":"CANCEL",index,selections=selections.ToArray(),state=Boundary(),boundary="native popup callback"});
                            continue;
                        }
                        var choices=Choices();
                        Require(index<choices.Length&&!(bool)P(choices[index],"IsLocked"),"Illegal declared option.");
                        selections.Clear();
                        var rngBefore=Activator.CreateInstance(T("Random.Rng"),new[]{P(P(evt,"Rng"),"Seed"),P(P(evt,"Rng"),"Counter")})!;
                        if(name=="Trial"&&Key(choices[index]).EndsWith(".DOUBLE_DOWN"))
                        {
                            // Native popup factory returns null in TestMode. Its UI-only opening
                            // is represented here; the next decision invokes the real popup callback.
                            confirmation=true;
                            trace.Add(new{choice=Key(choices[index]),index,selections=selections.ToArray(),state=Boundary(),boundary="popup opening (source contract; no native UI)"});
                            continue;
                        }
                        if(Key(choices[index])=="SCROLL_BOXES")
                        {
                            // TestMode hardcodes bundle zero. Reach the actual remote choice
                            // waiter with presentation disabled, then restore TestMode before
                            // completing the choice and executing card acquisition hooks.
                            Task chosen;
                            T("TestSupport.TestMode").GetProperty("IsOn")!.SetValue(null,false);
                            T("Context.LocalContext").GetProperty("NetId")!.SetValue(null,null);
                            try{chosen=(Task)C(choices[index],"Chosen");}
                            finally{T("TestSupport.TestMode").GetProperty("IsOn")!.SetValue(null,true);T("Context.LocalContext").GetProperty("NetId")!.SetValue(null,0UL);}
                            var synchronizer=P(manager,"PlayerChoiceSynchronizer");
                            var waiting=Items(synchronizer.GetType().GetField("_receivedChoices",flags)!.GetValue(synchronizer)!);
                            Require(waiting.Length==1,"Expected the native bundle choice waiter.");
                            uint choiceId=(uint)waiting[0].GetType().GetField("choiceId")!.GetValue(waiting[0])!;
                            int bundle=selectionVariant==2?1:0;
                            selections.Add(new{kind="bundle",selected=bundle});
                            C(synchronizer,"ReceiveReplayChoice",player,choiceId,C(C(T("GameActions.PlayerChoiceResult"),"FromIndex",(int?)bundle),"ToNetData"));
                            await Await(chosen);
                            trace.Add(new{choice=Key(choices[index]),index,selections=selections.ToArray(),state=Boundary()});
                            continue;
                        }
                        using(var presentation=new EventPresentation(asm,name is "Amalgamator" or "JungleMazeAdventure" or "PunchOff", name=="JungleMazeAdventure"))
                        {
                            // Trial.Accept's local-only guards touch portraits/VFX only.
                            // Restore local ownership before any synchronized card/reward choice.
                            bool portraitOnly=(name=="Trial"&&Key(choices[index]).EndsWith(".ACCEPT"))||(name=="DenseVegetation"&&!Key(choices[index]).EndsWith(".FIGHT"))||name=="CrystalSphere";
                            if(portraitOnly)T("Context.LocalContext").GetProperty("NetId")!.SetValue(null,null);
                            try{await Await(C(choices[index],"Chosen"));}
                            finally{if(portraitOnly)T("Context.LocalContext").GetProperty("NetId")!.SetValue(null,0UL);}
                        }
                        if(name=="CrystalSphere")await EventMinigame.Run(asm,player,P(evt,"Rng"),rngBefore,index==0?3:6,variant,selections.Add);
                        trace.Add(new{choice=Key(choices[index]),index,selections=selections.ToArray(),state=Boundary()});
                    }
                    if(P(state,"CurrentRoom").GetType().Name=="CombatRoom")
                    {
                        selections.Clear();
                        var child=P(state,"CurrentRoom");
                        bool timeout=name=="BattlewornDummy"&&variant==1;
                        if(name=="BattlewornDummy")P(child,"Encounter").GetType().GetProperty("RanOutOfTime")!.SetValue(P(child,"Encounter"),timeout);
                        C(child,"MarkPreFinished");
                        await Await(C(T("Hooks.Hook"),"AfterCombatEnd",state,null,child));
                        await Await(C(T("Hooks.Hook"),"AfterCombatVictory",state,null,child));
                        if(name!="BattlewornDummy")
                        {
                            var generated=(Task)C(T("Commands.RewardsCmd"),"GenerateForRoomEnd",player,child);await Await(generated);
                            await Await(C(P(generated,"Result"),"Offer"));
                        }
                        await Await(C(manager,"ProceedFromTerminalRewardsScreen"));
                        customFinished=true;
                        trace.Add(new{choice="NATIVE_COMBAT_RESUME",index=0,selections=selections.ToArray(),state=Boundary(),timedOut=timeout,boundary="authored finished combat; actual end/victory hooks, rewards and parent resume; no combat policy"});
                    }
                    var options=Choices();
                    bool combat=P(state,"CurrentRoom").GetType().Name=="CombatRoom";
                    bool finished=customFinished||combat||(name!="FakeMerchant"&&(bool)P(evt,"IsFinished"))||(int)P(P(player,"Creature"),"CurrentHp")<=0;
                    var optionKeys=confirmation?new[]{"CONFIRM","CANCEL"}:options.Select(Key).ToArray();
                    if(!finished)
                    {
                        var key=name+":"+actIndex;
                        if(!coveredAncients.ContainsKey(key))coveredAncients[key]=new HashSet<string>();
                        var fresh=path.Length==0&&ancientNames.Contains(name)?optionKeys.Select((k,i)=>(k,i)).Where(p=>coveredAncients[key].Add(p.k)).Select(p=>p.i).ToHashSet():null;
                        bool discovery=ancientNames.Contains(name)&&!new[]{"0","2","42"}.Contains(seed);
                        if(discovery&&path.Length==0&&fresh!.Count==0)continue;
                        var signature=string.Join('|',optionKeys)+"|"+string.Join(',',options.Select(o=>P(o,"IsLocked")));
                        if(name is "AbyssalBaths" or "EndlessConveyor")signature+="|"+P(player,"Gold")+"|"+P(P(player,"Creature"),"CurrentHp");
                        if(seen.Add(signature))foreach(int i in Enumerable.Range(0,optionKeys.Length).Where(i=>(confirmation||!(bool)P(options[i],"IsLocked"))&&(!discovery||path.Length>0||fresh!.Contains(i))))frontier.Enqueue(path.Append(i).ToArray());
                    }
                    object Rng(object rng)=>new{counter=P(rng,"Counter"),suffix=C(rng,"NextDouble")};
                    rows.Add(new{eventName=name,seed,ascension,enhanced,variant,actIndex,selectionVariant,path,before,trace,finished,combat,options=optionKeys,locked=confirmation?new[]{false,false}:options.Select(o=>(bool)P(o,"IsLocked")).ToArray(),state=Boundary(),rng=new{eventRng=Rng(P(evt,"Rng")),rewards=Rng(P(P(player,"PlayerRng"),"Rewards")),niche=Rng(P(P(state,"Rng"),"Niche")),transformations=Rng(P(P(player,"PlayerRng"),"Transformations")),shops=Rng(P(P(player,"PlayerRng"),"Shops"))}});
                }
                finally{T("Rewards.RewardsSet").GetField("testSelector")!.SetValue(null,null);C(manager,"CleanUp",true);}
            }
        }
        await tree.ToSignal(tree,Godot.SceneTree.SignalName.ProcessFrame);
        GC.Collect();GC.WaitForPendingFinalizers();
        await tree.ToSignal(tree,Godot.SceneTree.SignalName.ProcessFrame);
        GC.KeepAlive(mockIcons);
        return JsonSerializer.Serialize(new{source="Native event branch prefixes with authored inventory and declared first eligible selections; mock persistence, no combat policy",assemblySha256=digest,rows},new JsonSerializerOptions{WriteIndented=true});
    }
}

// Owned, off-tree presentation nodes; native gameplay and RNG are untouched.
internal sealed class EventPresentation : IDisposable
{
    const BindingFlags Flags=BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance|BindingFlags.Static;
    readonly List<Godot.Node> nodes=new();
    readonly PropertyInfo instance;
    public EventPresentation(Assembly asm,bool needed,bool audio=false,bool abandon=false)
    {
        Type T(string n)=>asm.GetType("MegaCrit.Sts2.Core."+n,true)!;
        instance=T("Nodes.NGame").GetProperty("Instance",Flags)!;
        if(!needed)return;
        if(instance.GetValue(null) is not null)throw new InvalidOperationException("Presentation already owned.");
        var game=(Godot.Node)Activator.CreateInstance(T("Nodes.NGame"))!;
        var scene=(Godot.Node)Activator.CreateInstance(T("Nodes.NSceneContainer"))!;nodes.Add(scene);
        game.GetType().GetProperty("RootSceneContainer",Flags)!.SetValue(game,scene);
        var shake=(Godot.Node)Activator.CreateInstance(T("Nodes.Vfx.Utilities.NScreenShake"))!;
        var target=new Godot.Control();nodes.AddRange(new[]{game,shake,target});
        shake.GetType().GetMethod("_Ready")!.Invoke(shake,null);
        shake.GetType().GetMethod("SetTarget")!.Invoke(shake,new[]{target});
        game.GetType().GetField("_screenShake",Flags)!.SetValue(game,shake);
        if(abandon)
        {
            var run=(Godot.Node)Activator.CreateInstance(T("Nodes.NRun"))!;
            var ui=(Godot.Node)Activator.CreateInstance(T("Nodes.CommonUi.NGlobalUi"))!;
            var capstone=(Godot.Node)Activator.CreateInstance(T("Nodes.Screens.Capstones.NCapstoneContainer"))!;
            var map=(Godot.Node)Activator.CreateInstance(T("Nodes.Screens.Map.NMapScreen"))!;
            var rooms=(Godot.Node)Activator.CreateInstance(T("Nodes.NSceneContainer"))!;
            nodes.AddRange(new[]{run,ui,capstone,map,rooms});
            run.GetType().GetField("_roomContainer",Flags)!.SetValue(run,rooms);
            scene.GetType().GetProperty("CurrentScene",Flags)!.SetValue(scene,run);
            run.GetType().GetProperty("GlobalUi",Flags)!.SetValue(run,ui);
            ui.GetType().GetProperty("CapstoneContainer",Flags)!.SetValue(ui,capstone);
            ui.GetType().GetProperty("MapScreen",Flags)!.SetValue(ui,map);
        }
        if(audio)
        {
            var debug=(Godot.Node)Activator.CreateInstance(T("Audio.Debug.NDebugAudioManager"))!;
            nodes.Add(debug);
            debug.AddChild(new Godot.AudioStreamPlayer());
            var cache=T("Assets.PreloadManager").GetProperty("Cache")!.GetValue(null)!;
            var assets=cache.GetType().GetField("_cache",Flags)!.GetValue(cache)!;
            var path=T("Audio.Debug.TmpSfx").GetMethod("GetPath")!.Invoke(null,new object[]{"hey.mp3"});
            var sound=new Godot.AudioStreamWav{Data=new byte[256],MixRate=44100};
            if(!(bool)assets.GetType().GetMethod("TryAdd")!.Invoke(assets,new object?[]{path,sound})!)sound.Dispose();
            ((Godot.SceneTree)Godot.Engine.GetMainLoop()).Root.AddChild(debug);
            game.GetType().GetProperty("DebugAudio",Flags)!.SetValue(game,debug);
        }
        instance.SetValue(null,game);
    }
    public void Dispose()
    {
        if(nodes.Count==0)return;
        foreach(var node in nodes.Where(n=>n.GetType().Name=="NDebugAudioManager"))node.GetType().GetMethod("StopAll")!.Invoke(node,null);
        instance.SetValue(null,null);
        foreach(var node in nodes.AsEnumerable().Reverse())node.Free();
        nodes.Clear();
    }
}

// Drives actual custom-event callbacks through the same branch explorer.
internal sealed class EventCallbackOption
{
    public string TextKey {get;}
    public object? Relic=>null;
    public bool IsLocked {get;}
    readonly Func<Task> callback;
    public EventCallbackOption(string key,bool locked,Func<Task> chosen){TextKey=key;IsLocked=locked;callback=chosen;}
    public Task Chosen()=>callback();
}

using System.Reflection;
using System.Runtime.CompilerServices;
using System.Text.Json;

// Real native run/reward objects under TestMode and explicit in-memory saves.
internal static class GeneratedStartOracle
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
        tables.Add("ancients",Activator.CreateInstance(T("Localization.LocTable"),new object?[]{"ancients",new Dictionary<string,string>{{"THE_ARCHITECT.talk.IRONCLAD.0-0.next","Continue"},{"PROCEED.title","Proceed"},{"PROCEED.description","Finished"}},null})!);
        tables.Add("characters",Activator.CreateInstance(T("Localization.LocTable"),new object?[]{"characters",new[]{"title","titleObject","possessiveAdjective","pronounObject","pronounPossessive","pronounSubject"}.ToDictionary(k=>"IRONCLAD."+k,k=>"Ironclad"),null})!);
        F(loc,"_tables",tables);C(loc,"LoadLocFormatters");loc.GetType().GetProperty("CultureInfo",flags)!.SetValue(loc,System.Globalization.CultureInfo.InvariantCulture);loc.GetType().GetProperty("Instance",flags)!.SetValue(null,loc);
        var cache=T("Assets.PreloadManager").GetProperty("Cache")!.GetValue(null)!;
        var assets=cache.GetType().GetField("_cache",flags)!.GetValue(cache)!;
        C(assets,"TryAdd","res://images/enchantments/missing_enchantment.png",new Godot.CompressedTexture2D());
        C(assets,"TryAdd","res://images/atlases/ui_atlas.sprites/card/energy_ironclad.tres",new Godot.AtlasTexture());
        var rows=new List<object>();
        foreach(string seed in new[]{"0"})
        {
            var store=Activator.CreateInstance(T("Saves.Test.MockGodotFileIo"),new object[]{"user://isolated-fixture"})!;
            var saves=Activator.CreateInstance(T("Saves.SaveManager"),new object[]{store,true})!;F(saves,"_currentProfileId",0);C(T("Saves.SaveManager"),"MockInstanceForTesting",saves);
            C(saves,"InitPrefsDataForTest");
            P(saves,"PrefsSave").GetType().GetProperty("UploadData")!.SetValue(P(saves,"PrefsSave"),false);
            Require(!(bool)P(P(saves,"PrefsSave"),"UploadData"),"Metrics uploads must be disabled.");
            T("Context.LocalContext").GetProperty("NetId")!.SetValue(null,0UL);
            var player=C(T("Entities.Players.Player"),"CreateForNewRun",Get("Character","Characters.Ironclad"),T("Unlocks.UnlockState").GetField("all")!.GetValue(null),0UL);
            var state=C(T("Runs.RunState"),"CreateForTest",Typed(new[]{player},player.GetType()),null,null,Enum.Parse(T("Runs.GameMode"),"Standard"),0,seed);
            var manager=T("Runs.RunManager").GetProperty("Instance")!.GetValue(null)!;
            var replay=Activator.CreateInstance(T("Multiplayer.NetReplayGameService"),new object[]{0UL})!;
            C(manager,"SetUpTest",state,replay,true,false);
            try
            {
                Require(!(bool)P(manager,"ShouldSave"),"Persistent saving must be disabled.");
                var relicText=new Dictionary<string,string>();
                foreach(var relic in Items(T("Models.ModelDb").GetProperty("AllRelics")!.GetValue(null)!))foreach(var suffix in new[]{"title","description","eventDescription","selectionScreenPrompt"})relicText[P(P(relic,"Id"),"Entry")+"."+suffix]=P(P(relic,"Id"),"Entry").ToString()!;
                if(!tables.Contains("relics"))tables.Add("relics",Activator.CreateInstance(T("Localization.LocTable"),new object?[]{"relics",relicText,null})!);
                if(!tables.Contains("events"))tables.Add("events",Activator.CreateInstance(T("Localization.LocTable"),new object?[]{"events",new Dictionary<string,string>(),null})!);
                foreach(var tableName in new[]{"card_keywords","cards","static_hover_tips","powers","enchantments","monsters"})
                {
                    var texts=new Dictionary<string,string>();
                    var names=tableName=="card_keywords"?Enum.GetNames(T("Entities.Cards.CardKeyword")).Select(n=>C(T("Helpers.StringHelper"),"Slugify",n).ToString()!):
                        tableName=="static_hover_tips"?Enum.GetNames(T("HoverTips.StaticHoverTip")).Select(n=>C(T("Helpers.StringHelper"),"Slugify",n).ToString()!):
                        tableName=="monsters"?asm.GetTypes().Where(t=>!t.IsAbstract&&t.IsSubclassOf(T("Models.MonsterModel"))).Select(t=>C(T("Helpers.StringHelper"),"Slugify",t.Name).ToString()!):
                        tableName=="enchantments"?asm.GetTypes().Where(t=>!t.IsAbstract&&t.IsSubclassOf(T("Models.EnchantmentModel"))).Select(t=>C(T("Helpers.StringHelper"),"Slugify",t.Name).ToString()!):
                        tableName=="cards"?Items(T("Models.ModelDb").GetProperty("AllCards")!.GetValue(null)!).Select(c=>P(P(c,"Id"),"Entry").ToString()!):
                        new[]{"BLOCK","POWER","STRENGTH","VULNERABLE","WEAK","DEXTERITY","DAMAGE","ENERGY","CARD_REWARD"};
                    foreach(var name in names)foreach(var suffix in new[]{"name","title","description","upgradeDescription","selectionScreenPrompt"})texts[name+"."+suffix]=name;
                    if(!tables.Contains(tableName))tables.Add(tableName,Activator.CreateInstance(T("Localization.LocTable"),new object?[]{tableName,texts,null})!);
                }
                var selector=Activator.CreateInstance(T("TestSupport.TestCardSelector"))!;
                using var selected=(IDisposable)C(T("Commands.CardSelectCmd"),"UseSelector",selector);
                C(manager,"GenerateRooms");
                await Await(C(manager,"EnterAct",0,false));
                var neow=C(P(manager,"EventSynchronizer"),"GetLocalEvent");
                var options=Items(P(neow,"CurrentOptions"));
                Require(options.Length==3,"Expected three Neow offers.");
                // Fixed policy: choose the second offered relic (native positive group).
                var option=options[1];
                var offers=options.Select(o=>P(P(P(o,"Relic"),"Id"),"Entry").ToString()).ToArray();
                var choice=P(P(P(option,"Relic"),"Id"),"Entry").ToString();
                await Await(C(option,"Chosen"));
                Require((bool)P(neow,"IsFinished"),"Neow did not finish.");
                var rewardsAfterNeow=P(P(P(player,"PlayerRng"),"Rewards"),"Counter");
                object point=P(P(state,"Map"),"StartingMapPoint");
                object Coord(object p)=>p.GetType().GetField("coord")!.GetValue(p)!;
                int Row(object p)=>(int)Coord(p).GetType().GetField("row")!.GetValue(Coord(p))!;
                int Col(object p)=>(int)Coord(p).GetType().GetField("col")!.GetValue(Coord(p))!;
                var next=Items(P(point,"Children")).OrderBy(Col).First();
                await Await(C(manager,"EnterMapCoord",Coord(next)));
                var combatManager=T("Combat.CombatManager").GetProperty("Instance")!.GetValue(null)!;
                var room=P(state,"CurrentRoom");
                Require(room.GetType().Name=="CombatRoom","First map room must be combat.");
                var combat=P(room,"CombatState");
                var clock=System.Diagnostics.Stopwatch.StartNew();
                while(P(P(manager,"ActionQueueSynchronizer"),"CombatState").ToString()!="PlayPhase"){Require(clock.ElapsedMilliseconds<3000,"Combat start timed out.");await Task.Yield();}
                var actions=new List<object>();
                object Card(object c)=>new{id=P(P(c,"Id"),"Entry").ToString(),upgrade=P(c,"CurrentUpgradeLevel")};
                object Boundary()=>new{hp=P(P(player,"Creature"),"CurrentHp"),block=P(P(player,"Creature"),"Block"),energy=P(P(player,"PlayerCombatState"),"Energy"),
                    hand=Items(P(P(P(player,"PlayerCombatState"),"Hand"),"Cards")).Select(Card).ToArray(),
                    enemies=Items(P(combat,"Enemies")).Select(c=>new{id=P(P(P(c,"Monster"),"Id"),"Entry").ToString(),hp=P(c,"CurrentHp"),block=P(c,"Block")}).ToArray()};
                var initial=Boundary();
                for(int n=0;n<300 && (bool)P(combatManager,"IsInProgress");n++)
                {
                    var pcs=P(player,"PlayerCombatState");
                    var target=Items(P(combat,"Enemies")).FirstOrDefault(e=>(bool)P(e,"IsAlive"));
                    var hand=Items(P(P(pcs,"Hand"),"Cards"));
                    var card=hand.FirstOrDefault(c=>(bool)C(c,"CanPlayTargeting",P(c,"TargetType").ToString()=="AnyEnemy"?target:null));
                    if(card is not null)
                    {
                        int index=Array.IndexOf(hand,card);
                        var play=Activator.CreateInstance(T("GameActions.PlayCardAction"),new object?[]{card,P(card,"TargetType").ToString()=="AnyEnemy"?target:null})!;
                        var queue=P(manager,"ActionQueueSet");var executor=P(manager,"ActionExecutor");
                        C(queue,"EnqueueWithoutSynchronizing",play);
                        await Await(C(executor,"FinishedExecutingActions"));
                        Require(P(play,"State").ToString()=="Finished","Card action paused unexpectedly.");
                        await Await(C(combatManager,"CheckWinCondition"));
                        actions.Add(new{kind="play",index,card=Card(card),state=(bool)P(combatManager,"IsInProgress")?Boundary():null});
                    }
                    else
                    {
                        await Await(C(combatManager,"EndPlayerTurnPhaseOneInternal"));
                        if((bool)P(combatManager,"IsInProgress"))await Await(C(combatManager,"EndPlayerTurnPhaseTwoInternal"));
                        if((bool)P(combatManager,"IsInProgress"))await Await(C(combatManager,"SwitchFromPlayerToEnemySide",(object?)null));
                        actions.Add(new{kind="end",state=(bool)P(combatManager,"IsInProgress")?Boundary():null});
                    }
                }
                Require(!(bool)P(combatManager,"IsInProgress"),"Combat action budget exhausted.");
                rows.Add(new{seed,offers,choice,rewardsAfterNeow,row=Row(next),col=Col(next),encounter=P(P(P(room,"Encounter"),"Id"),"Entry").ToString(),initial,actions,hp=P(P(player,"Creature"),"CurrentHp")});
            }
            finally{C(manager,"CleanUp",true);}
        }
        return JsonSerializer.Serialize(new{source="Native generated Neow and first combat only; real card action executor, manually invoked end-turn phases, UI-only mock localization/textures, mock saves and uploads disabled; no synthetic victories",assemblySha256=digest,rows},new JsonSerializerOptions{WriteIndented=true});
    }
}

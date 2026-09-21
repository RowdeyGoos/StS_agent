using System.Reflection;

// Authored active combat, real character definitions, starter callbacks and
// UsePotionAction. This is not a native run-start shuffle or complete campaign.
internal static class CharacterOracle
{
    public static async Task<object> Run(Assembly asm, object player, object pcs, object pc,
        object combat, object target, object runManager, object queue, object executor, string scenario)
    {
        if(scenario.EndsWith("_interaction"))return await Interactions(asm,player,pcs,pc,combat,target,runManager,queue,executor,scenario);
        const BindingFlags flags=BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance|BindingFlags.Static;
        Type T(string n)=>asm.GetType("MegaCrit.Sts2.Core."+n,true)!;
        object P(object o,string n)=>o.GetType().GetProperty(n,flags)!.GetValue(o)!;
        object C(object o,string n,params object?[] a){var t=o as Type??o.GetType();return t.GetMethods(flags).Single(m=>m.Name==n&&!m.IsGenericMethodDefinition&&m.GetParameters().Length==a.Length&&m.GetParameters().Select((p,i)=>a[i] is null||p.ParameterType.IsInstanceOfType(a[i])).All(x=>x)).Invoke(o is Type?null:o,a)!;}
        void F(object o,string n,object? v)=>o.GetType().GetField(n,flags)!.SetValue(o,v);
        object[] Items(object o)=>((System.Collections.IEnumerable)o).Cast<object>().ToArray();
        object Get(string method,string suffix)=>T("Models.ModelDb").GetMethods().Single(m=>m.Name==method&&m.IsGenericMethodDefinition).MakeGenericMethod(T("Models."+suffix)).Invoke(null,null)!;
        async Task Await(object task)=>await ((Task)task).WaitAsync(TimeSpan.FromSeconds(3));
        string Id(object o)=>P(P(o,"Id"),"Entry").ToString()!;
        var character=P(player,"Character");string name=character.GetType().Name;
        bool refined=scenario.EndsWith("_refined");
        var startRelic=Items(P(character,"StartingRelics"))[0];
        string relicName=refined?name switch{"Silent"=>"RingOfTheDrake","Regent"=>"DivineDestiny","Necrobinder"=>"PhylacteryUnbound",_=>"InfusedCore"}:startRelic.GetType().Name;
        var relic=C(Get("Relic","Relics."+relicName),"ToMutable");relic.GetType().GetProperty("Owner")!.SetValue(relic,player);
        var relics=(System.Collections.IList)P(player,"Relics");relics.Clear();relics.Add(relic);
        C(pc,"SetMaxHpInternal",Convert.ToDecimal(P(character,"StartingHp")));C(pc,"SetCurrentHpInternal",Convert.ToDecimal(P(character,"StartingHp")));
        C(P(target,"Monster"),"SetUpForCombat");C(target,"SetMaxHpInternal",1000m);C(target,"SetCurrentHpInternal",1000m);
        foreach(var pile in new[]{"Hand","DrawPile","DiscardPile"})foreach(var card in Items(P(P(pcs,pile),"Cards")))C(P(pcs,pile),"RemoveInternal",card,true);
        var side=Enum.Parse(T("Combat.CombatSide"),"Player");
        var context=Activator.CreateInstance(T("GameActions.Multiplayer.ThrowingPlayerChoiceContext"))!;
        var participants=P(combat,"PlayerCreatures");
        object Powers(object creature)=>Items(P(creature,"Powers")).ToDictionary(Id,p=>P(p,"Amount"));
        object State(){var osty=P(player,"Osty");return new{
            hp=P(pc,"CurrentHp"),draw=C(relic,"ModifyHandDraw",player,5m),stars=P(pcs,"Stars"),
            osty=osty is null?null:new{hp=P(osty,"CurrentHp"),maxHp=P(osty,"MaxHp")},
            slots=P(P(pcs,"OrbQueue"),"Capacity"),orbs=Items(P(P(pcs,"OrbQueue"),"Orbs")).Select(o=>o.GetType().Name).ToArray(),
            powers=Powers(pc),enemyPowers=Powers(target),
            cards= new[]{"Hand","DrawPile","DiscardPile"}.SelectMany(pile=>Items(P(P(pcs,pile),"Cards")).Select(card=>new{pile,id=Id(card),upgraded=P(card,"IsUpgraded")})).ToArray()};}
        await Await(C(relic,"BeforeCombatStart"));
        if(!refined&&name=="Regent"){
            var room=System.Runtime.CompilerServices.RuntimeHelpers.GetUninitializedObject(T("Rooms.CombatRoom"));
            await Await(C(relic,"AfterRoomEntered",room));
        }
        await Await(C(relic,"BeforeSideTurnStart",context,side,participants,combat));
        await Await(C(relic,"AfterSideTurnStart",side,participants,combat));
        var before=State();var steps=new List<object>();
        if(refined){C(pcs,"IncrementTurnNumber");await Await(C(relic,"AfterEnergyResetLate",player));await Await(C(relic,"AfterSideTurnStart",side,participants,combat));steps.Add(new{kind="next_start",state=State()});}
        else{
            var potions=name switch{"Silent"=>new[]{"PoisonPotion","GhostInAJar","CunningPotion"},"Regent"=>new[]{"StarPotion","CosmicConcoction","KingsCourage"},"Necrobinder"=>new[]{"PotionOfDoom","PotOfGhouls","BoneBrew"},_=>new[]{"FocusPotion","EssenceOfDarkness","PotionOfCapacity"}};
            var slots=(System.Collections.IList)player.GetType().GetField("_potionSlots",flags)!.GetValue(player)!;slots.Clear();for(int i=0;i<3;i++)slots.Add(null);
            F(executor,"_logger",queue.GetType().GetField("_logger",flags)!.GetValue(queue));
            var checksum=Activator.CreateInstance(T("Multiplayer.Game.ChecksumTracker"),new[]{P(runManager,"NetService"),P(player,"RunState")})!;
            checksum.GetType().GetProperty("IsEnabled")!.SetValue(checksum,false);runManager.GetType().GetProperty("ChecksumTracker",flags)!.SetValue(runManager,checksum);
            foreach(var potionName in potions){
                var potion=C(Get("Potion","Potions."+potionName),"ToMutable");C(player,"AddPotionInternal",potion,-1,false);
                var type=P(potion,"TargetType").ToString();var recipient=type=="AnyEnemy"?target:type=="AnyPlayer"?pc:null;
                var action=Activator.CreateInstance(T("GameActions.UsePotionAction"),new[]{potion,recipient,true})!;
                C(queue,"EnqueueWithoutSynchronizing",action);if(!ReferenceEquals(C(queue,"GetReadyAction"),action))throw new Exception("Character action not ready");
                F(executor,"<CurrentlyRunningAction>k__BackingField",action);await Await(C(action,"Execute"));F(executor,"<CurrentlyRunningAction>k__BackingField",null);
                if(P(action,"State").ToString()!="Finished"||!(bool)P(queue,"IsEmpty"))throw new Exception("Character action did not settle");
                steps.Add(new{kind=potionName,state=State()});
            }
        }
        runManager.GetType().GetProperty("State",flags)!.SetValue(runManager,null);
        return new{scenario,character=name,starter=Id(startRelic),hp=P(character,"StartingHp"),gold=P(character,"StartingGold"),deck=Items(P(character,"StartingDeck")).Select(Id).ToArray(),before,steps};
    }
    // Four bounded mechanism probes on authored active state. Card/potion actions
    // are real; named phase callbacks do not claim a complete turn lifecycle.
    private static async Task<object> Interactions(Assembly asm, object player, object pcs, object pc,
        object combat, object target, object runManager, object queue, object executor, string scenario)
    {
        const BindingFlags flags=BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance|BindingFlags.Static;
        Type T(string n)=>asm.GetType("MegaCrit.Sts2.Core."+n,true)!;
        object P(object o,string n)=>o.GetType().GetProperty(n,flags)!.GetValue(o)!;
        object C(object o,string n,params object?[] a){var t=o as Type??o.GetType();var ms=t.GetMethods(flags).Where(m=>m.Name==n&&!m.IsGenericMethodDefinition&&m.GetParameters().Length==a.Length&&m.GetParameters().Select((p,i)=>a[i] is null||p.ParameterType.IsInstanceOfType(a[i])).All(x=>x)).ToArray();if(ms.Length!=1)throw new Exception(t.Name+"."+n+" matches "+ms.Length);return ms[0].Invoke(o is Type?null:o,a)!;}
        void F(object o,string n,object? v)=>o.GetType().GetField(n,flags)!.SetValue(o,v);
        object[] Items(object o)=>((System.Collections.IEnumerable)o).Cast<object>().ToArray();
        Array Typed(IEnumerable<object> values,Type t){var v=values.ToArray();var a=Array.CreateInstance(t,v.Length);Array.Copy(v,a,v.Length);return a;}
        object Get(string method,string suffix)=>T("Models.ModelDb").GetMethods().Single(m=>m.Name==method&&m.IsGenericMethodDefinition).MakeGenericMethod(T("Models."+suffix)).Invoke(null,null)!;
        async Task Await(object task)=>await ((Task)task).WaitAsync(TimeSpan.FromSeconds(3));
        string Id(object o)=>P(P(o,"Id"),"Entry").ToString()!;
        string name=P(player,"Character").GetType().Name;
        var context=Activator.CreateInstance(T("GameActions.Multiplayer.ThrowingPlayerChoiceContext"))!;
        var side=Enum.Parse(T("Combat.CombatSide"),"Player");
        var relicNames=name switch{"Silent"=>new[]{"HelicalDart"},"Regent"=>new[]{"GalacticDust","MiniRegent"},"Necrobinder"=>new[]{"Bookmark","IvoryTile"},_=>new[]{"GoldPlatedCables","InfusedCore"}};
        var relics=(System.Collections.IList)P(player,"Relics");relics.Clear();
        foreach(var n in relicNames){var r=C(Get("Relic","Relics."+n),"ToMutable");r.GetType().GetProperty("Owner")!.SetValue(r,player);relics.Add(r);}
        foreach(var pile in new[]{"Hand","DrawPile","DiscardPile"})foreach(var card in Items(P(P(pcs,pile),"Cards")))C(P(pcs,pile),"RemoveInternal",card,true);
        C(pc,"SetMaxHpInternal",80m);C(pc,"SetCurrentHpInternal",80m);C(pcs,"GainEnergy",10m);
        C(P(target,"Monster"),"SetUpForCombat");C(target,"SetMaxHpInternal",1000m);C(target,"SetCurrentHpInternal",1000m);
        string[] names=name switch{"Silent"=>new[]{"Shiv","Shiv"},"Regent"=>new[]{"DefendRegent"},"Necrobinder"=>new[]{"CaptureSpirit"},_=>Array.Empty<string>()};
        var cards=names.Select(n=>C(combat,"CreateCard",Get("Card","Cards."+n),player)).ToArray();
        foreach(var card in cards)C(P(pcs,"Hand"),"AddInternal",card,-1,true);
        C(T("GameActions.Multiplayer.NetCombatCardDb").GetProperty("Instance")!.GetValue(null)!,"StartCombat",Typed(new[]{player},player.GetType()));
        F(executor,"_logger",queue.GetType().GetField("_logger",flags)!.GetValue(queue));
        var checksum=Activator.CreateInstance(T("Multiplayer.Game.ChecksumTracker"),new[]{P(runManager,"NetService"),P(player,"RunState")})!;
        checksum.GetType().GetProperty("IsEnabled")!.SetValue(checksum,false);runManager.GetType().GetProperty("ChecksumTracker",flags)!.SetValue(runManager,checksum);
        void Power(string power,int amount){var p=C(Get("Power","Powers."+power),"ToMutable",0);C(p,"ApplyInternal",pc,(decimal)amount,true);}
        var rng=P(P(player,"RunState"),"Rng");
        var streams=new[]{"CombatCardSelection","CombatTargets","CombatOrbGeneration"};
        object State()=>new{hp=P(pc,"CurrentHp"),block=P(pc,"Block"),energy=P(pcs,"Energy"),stars=P(pcs,"Stars"),enemyHp=P(target,"CurrentHp"),
            powers=Items(P(pc,"Powers")).ToDictionary(Id,p=>P(p,"Amount")),
            cards=cards.Select(c=>new{id=Id(c),cost=C(P(c,"EnergyCost"),"GetResolved"),pile=P(P(c,"Pile"),"Type").ToString()}).ToArray(),
            orbs=Items(P(P(pcs,"OrbQueue"),"Orbs")).Select(o=>new{kind=o.GetType().Name,passive=P(o,"PassiveVal"),evoke=P(o,"EvokeVal")}).ToArray(),
            counters=streams.ToDictionary(n=>n,n=>P(P(rng,n),"Counter")),dust=name=="Regent"?P(relics[0]!,"StarsSpent"):null};
        var before=State();var steps=new List<object>();
        void Record(string kind,int amount=0)=>steps.Add(new{kind,amount,state=State()});
        async Task Action(object action){C(queue,"EnqueueWithoutSynchronizing",action);if(!ReferenceEquals(C(queue,"GetReadyAction"),action))throw new Exception("Character action not ready");F(executor,"<CurrentlyRunningAction>k__BackingField",action);await Await(C(action,"Execute"));F(executor,"<CurrentlyRunningAction>k__BackingField",null);if(P(action,"State").ToString()!="Finished"||!(bool)P(queue,"IsEmpty"))throw new Exception("Character action did not settle");}
        async Task Play(int i){await Action(Activator.CreateInstance(T("GameActions.PlayCardAction"),new[]{cards[i],target})!);Record("play",i);}
        if(name=="Silent"){
            await Play(0);
            var potion=C(Get("Potion","Potions.SpeedPotion"),"ToMutable");((System.Collections.IList)player.GetType().GetField("_potionSlots",flags)!.GetValue(player)!).Add(null);C(player,"AddPotionInternal",potion,-1,false);
            await Action(Activator.CreateInstance(T("GameActions.UsePotionAction"),new object?[]{potion,null,true})!);Record("speed");
            Power("ArtifactPower",1);Record("artifact",1);
            await Play(1);
            foreach(var power in Items(P(pc,"Powers")))await Await(C(power,"AfterSideTurnEnd",context,side,P(combat,"PlayerCreatures")));
            Record("expire");
        }else if(name=="Regent"){
            C(pcs,"GainStars",40m);Record("gain_stars",40);
            foreach(int n in new[]{7,5,20}){await Await(T("Models.CardModel").GetMethod("SpendStars",flags)!.Invoke(cards[0],new object[]{n})!);Record("spend",n);}
            await Await(C(relics[1]!,"BeforeSideTurnStart",context,side,P(combat,"PlayerCreatures"),combat));Record("reset_mini");
            await Await(T("Models.CardModel").GetMethod("SpendStars",flags)!.Invoke(cards[0],new object[]{1})!);Record("spend",1);
            Power("ChildOfTheStarsPower",1);Power("JuggernautPower",6);C(target,"SetCurrentHpInternal",6m);relics[0]!.GetType().GetProperty("StarsSpent")!.SetValue(relics[0],9);
            await Await(C(relics[1]!,"BeforeSideTurnStart",context,side,P(combat,"PlayerCreatures"),combat));Record("terminal_setup");
            await Await(T("Models.CardModel").GetMethod("SpendStars",flags)!.Invoke(cards[0],new object[]{1})!);Record("spend",1);
        }else if(name=="Necrobinder"){
            async Task Discount(){await Await(C(relics[0]!,"AfterFlush",context,player,Typed(Array.Empty<object>(),T("Models.CardModel")),Typed(cards,T("Models.CardModel"))));Record("bookmark");}
            await Discount();C(P(cards[0],"EnergyCost"),"SetThisTurn",2,false);Record("turn_cost",2);
            await Discount();C(P(cards[0],"EnergyCost"),"EndOfTurnCleanup");Record("cost_cleanup");
            await Play(0);
        }else{
            foreach(var orb in new[]{"GlassOrb","LightningOrb"}){await Await(C(T("Commands.OrbCmd"),"Channel",context,C(Get("Orb","Orbs."+orb),"ToMutable",0),player));Record("channel_"+orb);}
            await Await(C(P(pcs,"OrbQueue"),"BeforeTurnEnd",context));Record("orb_end");
            Power("LoopPower",1);Record("loop_setup");
            var loop=Items(P(pc,"Powers")).Single(p=>p.GetType().Name=="LoopPower");
            await Await(C(loop,"AfterPlayerTurnStart",context,player));Record("loop");
            Power("FocusPower",-4);Record("focus",-4);
            await Await(C(T("Commands.OrbCmd"),"EvokeNext",context,player,true));Record("evoke");
            await Await(C(P(pcs,"OrbQueue"),"BeforeTurnEnd",context));Record("orb_end");
            await Await(C(loop,"AfterPlayerTurnStart",context,player));Record("loop");
            for(int i=0;i<4;i++){var random=C(T("Models.OrbModel"),"GetRandomOrb",P(rng,"CombatOrbGeneration"));await Await(C(T("Commands.OrbCmd"),"Channel",context,C(random,"ToMutable",0),player));Record("channel_random");}
        }
        if(!(bool)P(queue,"IsEmpty"))throw new Exception("Unsettled character queue");
        object Tail(string n)=>new{counter=P(P(rng,n),"Counter"),suffix=C(P(rng,n),"NextDouble")};
        var tails=streams.ToDictionary(n=>n,Tail);
        ((IDisposable)checksum).Dispose();runManager.GetType().GetProperty("State",flags)!.SetValue(runManager,null);
        return new{scenario,character=name,relicNames,cardNames=names,before,steps,tails};
    }
}

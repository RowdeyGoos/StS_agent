using System.Reflection;

// Authored active combat, real character definitions, starter callbacks and
// UsePotionAction. This is not a native run-start shuffle or complete campaign.
internal static class CharacterOracle
{
    public static async Task<object> Run(Assembly asm, object player, object pcs, object pc,
        object combat, object target, object runManager, object queue, object executor, string scenario)
    {
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
}

using System.Reflection;

internal static class ItemStatusOracle
{
    public static readonly string[] Scenarios = {"flex", "speed", "binding", "shackles", "ward", "replay", "healing", "duration", "fairy", "chaos", "flex_late", "speed_late"};

    public static async Task<object> Run(Assembly asm, object player, object pcs, object pc,
        object combat, object target, object manager, object runManager, object queue,
        object sync, object executor, object rng, string seed, string scenario, bool variant, int ascension)
    {
        const BindingFlags flags = BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance|BindingFlags.Static;
        Type T(string n)=>asm.GetType("MegaCrit.Sts2.Core."+n,true)!;
        object P(object o,string n)=>o.GetType().GetProperty(n,flags)!.GetValue(o)!;
        object C(object o,string n,params object?[] a){var t=o as Type??o.GetType();var methods=t.GetMethods(flags).Where(m=>m.Name==n&&!m.IsGenericMethodDefinition&&m.GetParameters().Length==a.Length&&m.GetParameters().Select((p,i)=>a[i] is null||p.ParameterType.IsInstanceOfType(a[i])).All(x=>x)).ToArray();Require(methods.Length==1,t.Name+"."+n+" args "+string.Join(",",a.Select(x=>x?.GetType().Name??"null")));return methods[0].Invoke(o is Type?null:o,a)!;}
        void F(object o,string n,object? v)=>o.GetType().GetField(n,flags)!.SetValue(o,v);
        object[] Items(object o)=>((System.Collections.IEnumerable)o).Cast<object>().ToArray();
        void Require(bool value,string message){if(!value)throw new InvalidOperationException(message);}
        async Task Await(object task)=>await ((Task)task).WaitAsync(TimeSpan.FromSeconds(3));
        object Get(string method,string suffix)=>T("Models.ModelDb").GetMethods().Single(m=>m.Name==method&&m.IsGenericMethodDefinition).MakeGenericMethod(T("Models."+suffix)).Invoke(null,null)!;
        void Power(object owner,string name,int amount){var p=C(Get("Power","Powers."+name),"ToMutable",0);C(p,"ApplyInternal",owner,(decimal)amount,true);}
        // The shared player context is an IRunState proxy. HasAscension reads
        // RunManager's concrete State instead; supply an owned marker for that
        // progress check and the real native AscensionManager for rule values.
        var runMarker=System.Runtime.CompilerServices.RuntimeHelpers.GetUninitializedObject(T("Runs.RunState"));
        runManager.GetType().GetProperty("State",flags)!.SetValue(runManager,runMarker);
        runManager.GetType().GetProperty("AscensionManager")!.SetValue(runManager,Activator.CreateInstance(T("Entities.Ascension.AscensionManager"),new object[]{ascension}));
        Require((bool)C(runManager,"HasAscension",Enum.Parse(T("Entities.Ascension.AscensionLevel"),"DeadlyEnemies"))==(ascension>=9),"Ascension fixture inactive");
        var relicNames=new List<string>{"BeltBuckle","ReptileTrinket"};
        if(scenario is "ward" or "fairy")relicNames.AddRange(new[]{"TungstenRod"});
        if(scenario=="replay")relicNames.AddRange(new[]{"Shuriken","Kunai","OrnamentalFan"});
        if(scenario=="fairy")relicNames.Add("LizardTail");
        if(variant)relicNames.Reverse();
        var relics=(System.Collections.IList)P(player,"Relics");relics.Clear();
        foreach(var name in relicNames){var r=C(Get("Relic","Relics."+name),"ToMutable");r.GetType().GetProperty("Owner")!.SetValue(r,player);relics.Add(r);}
        string[] potionNames=scenario switch {
            "flex_late"=>new[]{"StrengthPotion","FlexPotion","FlexPotion"},
            "speed_late"=>new[]{"StrengthPotion","SpeedPotion","DexterityPotion"},
            "flex"=>new[]{"FlexPotion","FlexPotion","StrengthPotion"},
            "speed"=>new[]{"SpeedPotion","DexterityPotion","Fortifier"},
            "binding"=>new[]{"PotionOfBinding","VulnerablePotion","BeetleJuice"},
            "shackles"=>new[]{"ShacklingPotion","WeakPotion","PowderedDemise"},
            "ward"=>new[]{"LuckyTonic","LiquidBronze","HeartOfIron"},
            "replay"=>new[]{"Duplicator","GigantificationPotion","SoldiersStew"},
            "healing"=>new[]{"BloodPotion","FruitJuice","RegenPotion"},
            "duration"=>new[]{"ShipInABottle","MazalethsGift","RadiantTincture"},
            "chaos"=>new[]{"StrengthPotion","EnergyPotion","DistilledChaos"},
            "fairy"=>new[]{"FairyInABottle","FoulPotion","FoulPotion"},
            _=>throw new InvalidOperationException(scenario)};
        var slots=(System.Collections.IList)player.GetType().GetField("_potionSlots",flags)!.GetValue(player)!;
        for(int i=0;i<3;i++)slots.Add(null);
        foreach(var name in potionNames)C(player,"AddPotionInternal",C(Get("Potion","Potions."+name),"ToMutable"),-1,false);
        C(pc,"SetCurrentHpInternal",scenario=="fairy"?1m:41m);
        F(player,"<MaxEnergy>k__BackingField",3);
        C(pcs,"GainEnergy",10m);
        C(P(target,"Monster"),"SetUpForCombat");C(target,"SetMaxHpInternal",1000m);C(target,"SetCurrentHpInternal",1000m);C(target,"PrepareForNextTurn",P(combat,"PlayerCreatures"),true);
        if(variant){Power(pc,"ArtifactPower",1);Power(target,"ArtifactPower",1);}
        if(scenario=="speed"){Power(pc,"FrailPower",2);C(pc,"GainBlockInternal",8m);}
        var physical=new List<object>();
        foreach(var name in new[]{"StrikeIronclad","StrikeIronclad","StrikeIronclad","DefendIronclad"}.Concat(Enumerable.Repeat("DefendIronclad",10)))
        {var card=C(combat,"CreateCard",Get("Card","Cards."+name),player);physical.Add(card);C(P(pcs,physical.Count<=4?"Hand":"DrawPile"),"AddInternal",card,-1,true);}
        Array Players(){var a=Array.CreateInstance(player.GetType(),1);a.SetValue(player,0);return a;}
        C(T("GameActions.Multiplayer.NetCombatCardDb").GetProperty("Instance")!.GetValue(null)!,"StartCombat",Players());
        F(executor,"_logger",queue.GetType().GetField("_logger",flags)!.GetValue(queue));
        var checksum=Activator.CreateInstance(T("Multiplayer.Game.ChecksumTracker"),new[]{P(runManager,"NetService"),P(player,"RunState")})!;
        checksum.GetType().GetProperty("IsEnabled")!.SetValue(checksum,false);runManager.GetType().GetProperty("ChecksumTracker",flags)!.SetValue(runManager,checksum);
        object[] Powers(object creature)=>Items(P(creature,"Powers")).Select(p=>(object)new{id=P(P(p,"Id"),"Entry"),amount=P(p,"Amount")}).ToArray();
        string Label(object card){if(!physical.Contains(card))physical.Add(card);return "card."+physical.IndexOf(card);}
        string[] Pile(string name)=>Items(P(P(pcs,name),"Cards")).Select(Label).ToArray();
        object State()=>new{hp=P(pc,"CurrentHp"),maxHp=P(pc,"MaxHp"),block=P(pc,"Block"),energy=P(pcs,"Energy"),turn=P(pcs,"TurnNumber"),
            powers=Powers(pc),enemy=new{hp=P(target,"CurrentHp"),block=P(target,"Block"),powers=Powers(target),move=P(P(P(target,"Monster"),"NextMove"),"Id")},
            potions=slots.Cast<object?>().Select(p=>p is null?null:P(P(p,"Id"),"Entry")).ToArray(),
            relics=relics.Cast<object>().Select(r=>new{id=P(P(r,"Id"),"Entry"),state=r.GetType().Name=="BeltBuckle"?P(r,"DexterityApplied"):r.GetType().Name=="LizardTail"?P(r,"WasUsed"):null}).ToArray(),
            hand=Pile("Hand"),draw=Pile("DrawPile"),discard=Pile("DiscardPile"),exhaust=Pile("ExhaustPile")};
        var before=State();var steps=new List<object>();
        async Task Execute(object action){C(queue,"EnqueueWithoutSynchronizing",action);Require(ReferenceEquals(C(queue,"GetReadyAction"),action),"Item action not ready");F(executor,"<CurrentlyRunningAction>k__BackingField",action);await Await(C(action,"Execute"));Require(P(action,"State").ToString()=="Finished"&&(bool)P(queue,"IsEmpty"),"Item action did not settle");F(executor,"<CurrentlyRunningAction>k__BackingField",null);}
        async Task Drink(int slot){var potion=slots[slot]!;var type=P(potion,"TargetType").ToString();var recipient=type=="AnyEnemy"?target:type=="AnyPlayer"?pc:null;await Execute(Activator.CreateInstance(T("GameActions.UsePotionAction"),new[]{potion,recipient,true})!);steps.Add(new{kind="potion",index=slot,state=State()});}
        foreach(int i in scenario=="fairy"?new[]{1,2}:new[]{0,1,2})await Drink(i);
        for(int i=0;i<(scenario=="fairy"?3:4);i++){await Execute(Activator.CreateInstance(T("GameActions.PlayCardAction"),new object?[]{physical[i],i==3?null:target})!);steps.Add(new{kind="play",index=i,state=State()});}
        for(int i=0;i<1;i++)
        {
            C(sync,"SetCombatState",Enum.Parse(T("Entities.Multiplayer.ActionSynchronizerCombatState"),"NotPlayPhase"));
            await Await(C(manager,"EndPlayerTurnPhaseOneInternal"));
            await Await(C(manager,"EndPlayerTurnPhaseTwoInternal"));
            await Await(C(manager,"SwitchFromPlayerToEnemySide",new object?[]{null}));
            Require((bool)P(queue,"IsEmpty")&&!Items(sync.GetType().GetField("_hookActions",flags)!.GetValue(sync)!).Any(),"Unresolved turn hook");
            Require(!(bool)P(manager,"IsEnding"),"Unexpected terminal state");
            steps.Add(new{kind="end_turn",index=i,state=State()});
        }
        object Stream(string name){var r=P(rng,name);return new{counter=P(r,"Counter"),suffix=C(r,"NextDouble")};}
        ((IDisposable)checksum).Dispose();
        runManager.GetType().GetProperty("State",flags)!.SetValue(runManager,null);
        return new{seed,scenario,variant,ascension,relicNames,potionNames,before,steps,
            shuffle=Stream("Shuffle"),targets=Stream("CombatTargets"),niche=Stream("Niche"),ai=Stream("MonsterAi")};
    }
}

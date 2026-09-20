using System.Reflection;

internal static class ItemStatusOracle
{
    public static readonly string[] Scenarios = {"flex", "speed", "binding", "shackles", "ward", "replay", "healing", "duration", "fairy", "chaos", "flex_late", "speed_late", "conditional_skull", "conditional_skull_helmet", "conditional_buckle", "conditional_skull_ending", "conditional_skull_helmet_ending", "conditional_buckle_ending", "focused_tender_first", "focused_ritual_first", "focused_disintegration", "focused_monster_FlailKnight", "focused_monster_HunterKiller", "focused_monster_SludgeSpinner", "focused_monster_Exoskeleton", "focused_monster_BowlbugRock", "focused_roster_ovicopter", "focused_roster_shield", "focused_possess_strength", "focused_possess_dexterity", "focused_possess_strength_ending", "focused_possess_dexterity_ending"};

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
        if(scenario.StartsWith("conditional_"))
        {
            // Actual relic callbacks/PowerCmd on an authored active combat. The
            // fixture controls HP and potion membership; it does not claim the
            // surrounding HP/inventory command dispatch or full combat cleanup.
            bool buckle=scenario.Contains("buckle"), helmet=scenario.Contains("helmet");
            var statNames=helmet?new[]{"RedSkull","RuinedHelmet"}:new[]{buckle?"BeltBuckle":"RedSkull"};
            var statRelics=(System.Collections.IList)P(player,"Relics");statRelics.Clear();
            foreach(var name in statNames){var r=C(Get("Relic","Relics."+name),"ToMutable");r.GetType().GetProperty("Owner")!.SetValue(r,player);statRelics.Add(r);}
            var conditionalRelic=statRelics[0]!;
            var statSlots=(System.Collections.IList)player.GetType().GetField("_potionSlots",flags)!.GetValue(player)!;
            for(int i=0;i<3;i++)statSlots.Add(null);
            var heldPotion=C(Get("Potion","Potions.FoulPotion"),"ToMutable");
            C(player,"AddPotionInternal",heldPotion,-1,false);
            C(pc,"SetCurrentHpInternal",41m);
            C(P(target,"Monster"),"SetUpForCombat");C(target,"SetMaxHpInternal",1000m);C(target,"SetCurrentHpInternal",1000m);
            if(variant)Power(pc,"ArtifactPower",1);
            object StatState()=>new{hp=P(pc,"CurrentHp"),maxHp=P(pc,"MaxHp"),ending=P(manager,"IsEnding"),
                powers=Items(P(pc,"Powers")).Select(p=>new{id=P(P(p,"Id"),"Entry"),amount=P(p,"Amount")}).ToArray(),
                active=P(conditionalRelic,buckle?"DexterityApplied":"StrengthApplied"),
                helmetUsed=helmet?P(statRelics[1]!,"UsedThisCombat"):null,
                potionCount=statSlots.Cast<object?>().Count(p=>p is not null)};
            var statBefore=StatState();var statSteps=new List<object>();
            async Task Toggle(bool active)
            {
                if(buckle)
                {
                    bool empty=!statSlots.Cast<object?>().Any(p=>p is not null);
                    if(active&&!empty)C(player,"DiscardPotionInternal",heldPotion,true);
                    if(!active&&empty)C(player,"AddPotionInternal",heldPotion,-1,false);
                    await Await(C(conditionalRelic,active?"AfterPotionDiscarded":"AfterPotionProcured",heldPotion));
                }
                else
                {
                    int oldHp=(int)P(pc,"CurrentHp");C(pc,"SetCurrentHpInternal",active?40m:41m);
                    await Await(C(conditionalRelic,"AfterCurrentHpChanged",pc,(decimal)((int)P(pc,"CurrentHp")-oldHp)));
                }
                Require((bool)P(queue,"IsEmpty")&&!Items(sync.GetType().GetField("_hookActions",flags)!.GetValue(sync)!).Any(),"Conditional stat hook did not settle");
                statSteps.Add(new{kind=active?"activate":"deactivate",state=StatState()});
            }
            if(scenario.EndsWith("_ending"))
            {
                C(target,"SetCurrentHpInternal",0m);Require((bool)P(manager,"IsEnding"),"Conditional fixture not ending");
                statSteps.Add(new{kind="ending",state=StatState()});
            }
            foreach(bool active in new[]{true,true,false,false,true,false,true})await Toggle(active);
            if(!scenario.EndsWith("_ending"))
            {
                C(target,"SetCurrentHpInternal",0m);Require((bool)P(manager,"IsEnding"),"Conditional fixture not ending");
                statSteps.Add(new{kind="ending",state=StatState()});
                await Toggle(false);await Toggle(true);
            }
            runManager.GetType().GetProperty("State",flags)!.SetValue(runManager,null);
            return new{seed,scenario,variant,ascension,relicNames=statNames,before=statBefore,steps=statSteps};
        }
        bool focused=scenario.StartsWith("focused_"), focusedMonster=scenario.StartsWith("focused_monster_"), focusedRoster=scenario.StartsWith("focused_roster_"), focusedPossess=scenario.StartsWith("focused_possess_");
        var relicNames=focused?new List<string>((focusedMonster||focusedRoster)?Array.Empty<string>():scenario=="focused_disintegration"?new[]{"TungstenRod"}:new[]{"RuinedHelmet"}):new List<string>{"BeltBuckle","ReptileTrinket"};
        if(scenario is "ward" or "fairy")relicNames.AddRange(new[]{"TungstenRod"});
        if(scenario=="replay")relicNames.AddRange(new[]{"Shuriken","Kunai","OrnamentalFan"});
        if(scenario=="fairy")relicNames.Add("LizardTail");
        if(variant)relicNames.Reverse();
        var relics=(System.Collections.IList)P(player,"Relics");relics.Clear();
        foreach(var name in relicNames){var r=C(Get("Relic","Relics."+name),"ToMutable");r.GetType().GetProperty("Owner")!.SetValue(r,player);relics.Add(r);}
        string[] potionNames=focused?Array.Empty<string>():scenario switch {
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
        if(focusedMonster||focusedRoster)C(pc,"SetMaxHpInternal",10000m);
        C(pc,"SetCurrentHpInternal",(focusedMonster||focusedRoster)?10000m:scenario=="focused_disintegration"?2m:scenario=="fairy"?1m:41m);
        F(player,"<MaxEnergy>k__BackingField",3);
        C(pcs,"GainEnergy",10m);
        if(scenario=="focused_monster_Exoskeleton")target.GetType().GetProperty("SlotName",flags)!.SetValue(target,"first");
        C(P(target,"Monster"),"SetUpForCombat");C(target,"SetMaxHpInternal",1000m);C(target,"SetCurrentHpInternal",1000m);C(target,"PrepareForNextTurn",P(combat,"PlayerCreatures"),true);
        if(focusedMonster||focusedPossess)await Await(C(P(target,"Monster"),"AfterAddedToRoom"));
        if(scenario is "focused_tender_first" or "focused_ritual_first")
        {
            foreach(var name in scenario=="focused_tender_first"?new[]{"TenderPower","RitualPower"}:new[]{"RitualPower","TenderPower"})Power(pc,name,1);
            Power(pc,"ArtifactPower",1);
        }
        if(scenario=="focused_disintegration"){Power(pc,"RegenPower",4);Power(pc,"DisintegrationPower",4);}
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
            relics=relics.Cast<object>().Select(r=>new{id=P(P(r,"Id"),"Entry"),state=r.GetType().Name=="BeltBuckle"?P(r,"DexterityApplied"):r.GetType().Name=="LizardTail"?P(r,"WasUsed"):focused&&r.GetType().Name=="RuinedHelmet"?P(r,"UsedThisCombat"):null}).ToArray(),
            hand=Pile("Hand"),draw=Pile("DrawPile"),discard=Pile("DiscardPile"),exhaust=Pile("ExhaustPile")};
        var roster = new List<object>{target};
        void ForceMove(object creature,string name)
        {
            var model=P(creature,"Monster");
            var states=(System.Collections.IDictionary)P(P(model,"MoveStateMachine"),"States");
            C(model,"SetMoveImmediate",states[name]!,true);
        }
        if(focusedRoster)
        {
            bool ovicopter=scenario.EndsWith("ovicopter");
            if(ovicopter)target.GetType().GetProperty("SlotName",flags)!.SetValue(target,"ovicopter");
            for(int i=0;i<(ovicopter?3:1);i++)
            {
                var model=C(Get("Monster","Monsters."+(ovicopter?"ToughEgg":"TurretOperator")),"ToMutable");
                var ally=C(combat,"CreateCreature",model,Enum.Parse(T("Combat.CombatSide"),"Enemy"),ovicopter?"egg"+(i+1):"ally."+i);
                C(combat,"AddCreature",ally);roster.Add(ally);
                C(model,"SetUpForCombat");C(ally,"SetMaxHpInternal",1000m);C(ally,"SetCurrentHpInternal",1000m);
                C(ally,"PrepareForNextTurn",P(combat,"PlayerCreatures"),true);
                if(ovicopter){ForceMove(ally,"NIBBLE_MOVE");Power(ally,"MinionPower",1);}
            }
            if(ovicopter)ForceMove(target,"TENDERIZER_MOVE");
            else await Await(C(P(target,"Monster"),"AfterAddedToRoom"));
            Power(roster[^1],"DoomPower",1000);
            C(combat,"SortEnemiesBySlotName");
        }
        object RosterState()=>new{player=State(),enemies=roster.Select(c=>new{type=P(c,"Monster").GetType().Name,hp=P(c,"CurrentHp"),block=P(c,"Block"),powers=Powers(c),move=P(P(P(c,"Monster"),"NextMove"),"Id")}).ToArray()};
        if(focusedPossess)
        {
            Power(pc,"ArtifactPower",1);
            if(!scenario.EndsWith("_ending"))
            {
                var model=C(Get("Monster","Monsters.Chomper"),"ToMutable");
                var survivor=C(combat,"CreateCreature",model,Enum.Parse(T("Combat.CombatSide"),"Enemy"),"survivor");
                C(combat,"AddCreature",survivor);C(model,"SetUpForCombat");
                C(survivor,"SetMaxHpInternal",1000m);C(survivor,"SetCurrentHpInternal",1000m);
            }
        }
        var before=focusedRoster?RosterState():State();var steps=new List<object>();
        async Task Execute(object action){C(queue,"EnqueueWithoutSynchronizing",action);Require(ReferenceEquals(C(queue,"GetReadyAction"),action),"Item action not ready");F(executor,"<CurrentlyRunningAction>k__BackingField",action);await Await(C(action,"Execute"));Require(P(action,"State").ToString()=="Finished"&&(bool)P(queue,"IsEmpty"),"Item action did not settle");F(executor,"<CurrentlyRunningAction>k__BackingField",null);}
        async Task Drink(int slot){var potion=slots[slot]!;var type=P(potion,"TargetType").ToString();var recipient=type=="AnyEnemy"?target:type=="AnyPlayer"?pc:null;await Execute(Activator.CreateInstance(T("GameActions.UsePotionAction"),new[]{potion,recipient,true})!);steps.Add(new{kind="potion",index=slot,state=State()});}
        if(focused)
        {
            if(focusedPossess)
            {
                var model=P(target,"Monster");string opening=(string)P(P(model,"NextMove"),"Id");
                for(int i=0;i<2;i++)
                {
                    ForceMove(target,opening);
                    await Await(C(model,"PerformMove"));
                    C(target,"PrepareForNextTurn",P(combat,"PlayerCreatures"),true);
                    steps.Add(new{kind="steal",index=i,state=State()});
                }
                // Real Possess callback and PowerCmd, with authored death/ending
                // premise; this case does not claim full combat-end cleanup.
                var possess=Items(P(target,"Powers")).Single(p=>p.GetType().Name.StartsWith("Possess"));
                C(target,"SetCurrentHpInternal",0m);
                Require((bool)P(manager,"IsEnding")==scenario.EndsWith("_ending"),"Wrong possession death premise");
                await Await(C(possess,"AfterDeath",Activator.CreateInstance(T("GameActions.Multiplayer.ThrowingPlayerChoiceContext"))!,target,false,0f));
                steps.Add(new{kind="possess_death",index=0,state=State()});
            }
            else if(focusedRoster)
            {
                C(sync,"SetCombatState",Enum.Parse(T("Entities.Multiplayer.ActionSynchronizerCombatState"),"NotPlayPhase"));
                await Await(C(manager,"EndPlayerTurnPhaseOneInternal"));
                await Await(C(manager,"EndPlayerTurnPhaseTwoInternal"));
                await Await(C(manager,"SwitchFromPlayerToEnemySide",new object?[]{null}));
                Require(!(bool)P(manager,"IsEnding") && P(combat,"CurrentSide").ToString()=="Player","Roster turn did not settle");
                Require((int)P(roster[^1],"CurrentHp")==0,"Later ally survived Doom");
                steps.Add(new{kind="end_turn",index=0,state=RosterState()});
                if(scenario.EndsWith("shield"))
                {
                    await Await(C(P(target,"Monster"),"PerformMove"));
                    C(target,"PrepareForNextTurn",P(combat,"PlayerCreatures"),true);
                    steps.Add(new{kind="monster_move",index=0,state=RosterState()});
                }
            }
            else if(focusedMonster)
            {
                for(int i=0;i<20;i++)
                {
                    if(scenario.EndsWith("BowlbugRock"))
                    {
                        pc.GetType().GetProperty("Block",flags)!.SetValue(pc,i%4==0?100:0);
                        steps.Add(new{kind="block",index=i%4==0?100:0,state=State()});
                    }
                    await Await(C(P(target,"Monster"),"PerformMove"));
                    C(target,"PrepareForNextTurn",P(combat,"PlayerCreatures"),true);
                    steps.Add(new{kind="monster_move",index=i,state=State()});
                }
            }
            else
            {
                if(scenario!="focused_disintegration")
                    foreach(int i in new[]{0,3}){await Execute(Activator.CreateInstance(T("GameActions.PlayCardAction"),new object?[]{physical[i],i==3?null:target})!);steps.Add(new{kind="play",index=i,state=State()});}
                C(sync,"SetCombatState",Enum.Parse(T("Entities.Multiplayer.ActionSynchronizerCombatState"),"NotPlayPhase"));
                await Await(C(manager,"EndPlayerTurnPhaseOneInternal"));
                await Await(C(manager,"EndPlayerTurnPhaseTwoInternal"));
                steps.Add(new{kind="end_player",index=0,state=State()});
            }
            Require((bool)P(queue,"IsEmpty")&&!Items(sync.GetType().GetField("_hookActions",flags)!.GetValue(sync)!).Any(),"Focused behavior did not settle");
            object FocusedStream(string name){var r=P(rng,name);return new{counter=P(r,"Counter"),suffix=C(r,"NextDouble")};}
            ((IDisposable)checksum).Dispose();runManager.GetType().GetProperty("State",flags)!.SetValue(runManager,null);
            return new{seed,scenario,variant,ascension,relicNames,potionNames,before,steps,
                shuffle=FocusedStream("Shuffle"),targets=FocusedStream("CombatTargets"),niche=FocusedStream("Niche"),ai=FocusedStream("MonsterAi")};
        }
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

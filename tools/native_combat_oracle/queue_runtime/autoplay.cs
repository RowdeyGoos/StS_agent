using System.Reflection;

internal static class AutoplayOracle
{
    public static async Task<object> Run(Assembly asm, object player, object pcs, object pc,
        object manager, object queue, object sync, object executor, object choices,
        object rng, List<object> physical, object mayhem, string seed, int fillers,
        int count, bool drawFirst, bool withStratagem, bool answerLast, bool flak, bool darkEmbrace)
    {
        const BindingFlags flags = BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance|BindingFlags.Static;
        Type T(string n)=>asm.GetType("MegaCrit.Sts2.Core."+n,true)!;
        object P(object o,string n)=>o.GetType().GetProperty(n,flags)!.GetValue(o)!;
        object C(object o,string n,params object?[] a)=>o.GetType().GetMethods(flags).Single(m=>m.Name==n&&!m.IsGenericMethodDefinition&&m.GetParameters().Length==a.Length&&m.GetParameters().Select((p,i)=>a[i] is null||p.ParameterType.IsInstanceOfType(a[i])).All(x=>x)).Invoke(o,a)!;
        void F(object o,string n,object? v)=>o.GetType().GetField(n,flags)!.SetValue(o,v);
        object[] Items(object o)=>((System.Collections.IEnumerable)o).Cast<object>().ToArray();
        void Require(bool b,string text){if(!b)throw new InvalidOperationException(text);}
        string Label(object card)=>"card."+physical.IndexOf(card);
        string[] Pile(string name)=>Items(P(P(pcs,name),"Cards")).Select(Label).ToArray();
        object State()=>new{hand=Pile("Hand"),draw=Pile("DrawPile"),discard=Pile("DiscardPile"),play=Pile("PlayPile"),exhaust=Pile("ExhaustPile"),energy=P(pcs,"Energy"),block=P(pc,"Block")};
        foreach(var card in physical.Take(flak ? 3 : drawFirst ? 1 : 0))
        {
            C(P(pcs,"DiscardPile"),"RemoveInternal",card,true);
            C(P(pcs,"DrawPile"),"AddInternal",card,-1,true);
        }
        var hook=Activator.CreateInstance(T("GameActions.Multiplayer.HookPlayerChoiceContext"),new[]{mayhem,(object)0UL,P(pc,"CombatState"),Enum.Parse(T("Entities.Multiplayer.GameActionType"),"CombatPlayPhaseOnly")})!;
        var before=State();
        var work=(Task)C(mayhem,"AfterAutoPrePlayPhaseEntered",hook,player);
        var completed=await ((Task<bool>)C(hook,"AssignTaskAndWaitForPauseOrCompletion",work)).WaitAsync(TimeSpan.FromSeconds(3));
        var checkpoint=State();
        var answers=new List<object>();
        if(!completed)
        {
            var action=P(hook,"GameAction");C(queue,"EnqueueWithoutSynchronizing",action);
            Require(ReferenceEquals(C(queue,"GetReadyAction"),action),"Mayhem hook not ready.");
            F(executor,"<CurrentlyRunningAction>k__BackingField",action);
            await ((Task)C(action,"Execute")).WaitAsync(TimeSpan.FromSeconds(3));
            uint choice=0;
            while(P(action,"State").ToString()=="GatheringPlayerChoice")
            {
                Require(choice<3,"Unexpected repeated shuffle.");
                var available=Items(P(P(pcs,"DrawPile"),"Cards"));
                Require(available.Length>1,"Unexpected explicit automatic choice.");
                var card=answerLast ? available[^1] : available[0];
                answers.Add(new{options=available.Select(Label).ToArray(),selected=Label(card),state=State()});
                var result=T("GameActions.PlayerChoiceResult").GetMethod("FromMutableCombatCard")!.Invoke(null,new[]{card})!;
                C(choices,"ReceiveReplayChoice",player,choice++,C(result,"ToNetData"));
                C(queue,"ResumeActionWithoutSynchronizing",P(action,"Id"));
                await ((Task)C(action,"Execute")).WaitAsync(TimeSpan.FromSeconds(3));
            }
            Require(P(action,"State").ToString()=="Finished","Mayhem did not finish.");
        }
        await work.WaitAsync(TimeSpan.FromSeconds(3));
        Require((bool)P(queue,"IsEmpty"),"Autoplay queue not empty.");
        Require(Pile("PlayPile").Length==0,"Collected cards remained in play.");
        var history=Items(P(P(manager,"History"),"Entries"));
        var plays=history.Where(e=>e.GetType().Name=="CardPlayFinishedEntry").Select(e=>Label(P(P(e,"CardPlay"),"Card"))).ToArray();
        Require(plays.Length<=fillers && plays.Distinct().Count()==plays.Length,"Mayhem recycled a card within one batch.");
        Require(new[]{"Hand","DrawPile","DiscardPile","ExhaustPile"}.SelectMany(Pile).OrderBy(x=>x).SequenceEqual(Enumerable.Range(0,fillers).Select(i=>"card."+i)),"Physical cards lost or duplicated.");
        object Stream(string name){var r=P(rng,name);return new{counter=P(r,"Counter"),suffix=C(r,"NextDouble")};}
        return new{seed,fillers,count,drawFirst,withStratagem,answerLast,flak,darkEmbrace,before,checkpoint,answers,after=State(),plays,enemyHp=Items(P(P(pc,"CombatState"),"Enemies")).Select(e=>P(e,"CurrentHp")).ToArray(),
            shuffle=Stream("Shuffle"),targets=Stream("CombatTargets"),selection=Stream("CombatCardSelection"),niche=Stream("Niche"),ai=Stream("MonsterAi")};
    }
}

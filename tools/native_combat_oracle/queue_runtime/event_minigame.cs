using System.Reflection;

// Native minigame callback boundary. The event's actual payment option is run
// separately with local presentation disabled. Reconstruct its board with a copy
// of the pre-option RNG, verify the consumed counter, then continue on its owned
// event stream. No native rule method is substituted and no UI scene is loaded.
internal static class EventMinigame
{
    public static async Task Run(Assembly asm,object player,object eventRng,object rngBefore,int divinations,int variant,Action<object> record)
    {
        const BindingFlags flags=BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance|BindingFlags.Static;
        Type T(string n)=>asm.GetType("MegaCrit.Sts2.Core."+n,true)!;
        object P(object o,string n)=>o.GetType().GetProperty(n,flags)!.GetValue(o)!;
        object C(object o,string n,params object?[] a)=>o.GetType().GetMethods(flags).Single(m=>m.Name==n&&m.GetParameters().Length==a.Length).Invoke(o,a)!;
        object[] Items(object o)=>((System.Collections.IEnumerable)o).Cast<object>().ToArray();
        var game=Activator.CreateInstance(T("Events.Custom.CrystalSphereEvent.CrystalSphereMinigame"),new[]{player,rngBefore,(object)divinations})!;
        if(!Equals(P(rngBefore,"Counter"),P(eventRng,"Counter")))throw new InvalidOperationException("Reconstructed native board RNG differs from event option.");
        game.GetType().GetProperty("Rng",flags)!.SetValue(game,eventRng);
        var cells=(Array)game.GetType().GetField("cells")!.GetValue(game)!;
        var items=Items(P(game,"Items"));
        object Cell(int x,int y)=>cells.GetValue(x,y)!;
        bool Hidden(int x,int y)=>(bool)P(Cell(x,y),"IsHidden");
        int[][] Covered(object item)=>Enumerable.Range(0,11).SelectMany(x=>Enumerable.Range(0,11).Where(y=>ReferenceEquals(P(Cell(x,y),"Item"),item)).Select(y=>new[]{x,y})).ToArray();
        string Kind(object item)
        {
            var saved=C(item,"ToSerializable");
            object Field(string n)=>saved.GetType().GetField(n)!.GetValue(saved)!;
            return Field("type").ToString() switch {
                "Potion"=>"potion_"+Field("potionRarity").ToString()!.ToLowerInvariant(),
                "CardReward"=>"card_"+Field("cardRarity").ToString()!.ToLowerInvariant(),
                "Gold"=>(bool)Field("isBigGold")?"gold_big":"gold_small",
                var kind=>kind!.ToLowerInvariant()};
        }
        object Board()=>new{
            clear=Enumerable.Range(0,11).SelectMany(x=>Enumerable.Range(0,11).Where(y=>!Hidden(x,y)).Select(y=>new[]{x,y})).ToArray(),
            items=items.Select(i=>new{kind=Kind(i),cells=Covered(i),subscriptions=((Delegate?)T("Events.Custom.CrystalSphereEvent.CrystalSphereItem").GetField("Revealed",flags)!.GetValue(i))?.GetInvocationList().Length??0}).ToArray(),
            revealed=Items(game.GetType().GetField("_revealed",flags)!.GetValue(game)!).Select(i=>Array.IndexOf(items,i)).ToArray()};
        record(new{kind="crystal_start",board=Board(),remaining=P(game,"DivinationCount")});
        bool small=variant%2==1;int target=variant/2;
        var desired=target<items.Length?Covered(items[target]):Array.Empty<int[]>();
        var offsets=small?new[]{(0,0)}:new[]{(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1),(0,0)};
        C(game,"SetTool",Enum.Parse(game.GetType().GetNestedType("CrystalSphereToolType")!,small?"Small":"Big"));
        while((int)P(game,"DivinationCount")>0)
        {
            var candidates=Enumerable.Range(0,11).SelectMany(x=>Enumerable.Range(0,11).Where(y=>Hidden(x,y)).Select(y=>(x,y)));
            int Score((int x,int y) c)=>offsets.Count(d=>desired.Any(p=>p[0]==c.x+d.Item1&&p[1]==c.y+d.Item2&&Hidden(p[0],p[1])));
            var chosen=candidates.OrderByDescending(Score).ThenBy(c=>c.x).ThenBy(c=>c.y).First();
            await ((Task)C(game,"CellClicked",Cell(chosen.x,chosen.y))).WaitAsync(TimeSpan.FromSeconds(3));
            record(new{kind="crystal_click",tool=small?"small":"big",x=chosen.x,y=chosen.y,board=Board(),remaining=P(game,"DivinationCount")});
        }
        await ((Task)C(game,"CompleteMinigame")).WaitAsync(TimeSpan.FromSeconds(3));
    }
}

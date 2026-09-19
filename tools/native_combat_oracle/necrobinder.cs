using System.Reflection;
using System.Text.Json;

internal static class NecrobinderOracle
{
    public static void Run(Assembly asm, string digest)
    {
        const BindingFlags flags = BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance|BindingFlags.Static;
        var db=asm.GetType("MegaCrit.Sts2.Core.Models.ModelDb",true)!;
        object Get(string method,string suffix)=>db.GetMethods().Single(m=>m.Name==method&&m.IsGenericMethodDefinition).MakeGenericMethod(asm.GetType("MegaCrit.Sts2.Core.Models."+suffix,true)!).Invoke(null,null)!;
        object Prop(object o,string n)=>o.GetType().GetProperty(n,flags)!.GetValue(o)!;
        object Call(object o,string n,params object?[] a)=>o.GetType().GetMethods(flags).Single(m=>m.Name==n&&!m.IsGenericMethodDefinition&&m.GetParameters().Length==a.Length&&m.GetParameters().Select((p,i)=>a[i] is null||p.ParameterType.IsInstanceOfType(a[i])).All(x=>x)).Invoke(o,a)!;
        object[] Items(object o)=>((System.Collections.IEnumerable)o).Cast<object>().ToArray();
        string Id(object o)=>Prop(Prop(o,"Id"),"Entry").ToString()!.ToLowerInvariant();

        Type T(string n)=>asm.GetType("MegaCrit.Sts2.Core."+n,true)!;

        var unlock=T("Unlocks.UnlockState").GetField("all")!.GetValue(null)!;
        var single=Enum.Parse(T("Entities.Cards.CardMultiplayerConstraint"),"SingleplayerOnly");
        var pool=Get("CardPool","CardPools.NecrobinderCardPool");
        var originals=Items(Call(pool,"GetUnlockedCards",unlock,single)).Concat(new[]{Get("Card","Cards.Soul"),Get("Card","Cards.SweepingGaze")}).ToArray();
        var rows=new List<object>();
        foreach(var original in originals) {
         var card=Call(original,"ToMutable");var levels=new List<object>();
         for(int level=0;level<=1;level++) {
          if(level==1){Call(card,"UpgradeInternal");Call(card,"FinalizeUpgradeInternal");}
          levels.Add(new { cost=Call(Prop(card,"EnergyCost"),"GetWithModifiers",Enum.ToObject(T("Entities.Cards.CostModifiers"),0)), x=Prop(Prop(card,"EnergyCost"),"CostsX"), star=Prop(card,"CurrentStarCost"), starX=Prop(card,"HasStarCostX"),keywords=Items(Prop(card,"Keywords")).Select(x=>x.ToString()),vars=Items(Prop(Prop(card,"DynamicVars"),"Values")).ToDictionary(v=>Prop(v,"Name").ToString()!,v=>Prop(v,"BaseValue"))});
         }
         rows.Add(new { id=Id(card),type=card.GetType().Name,kind=Prop(card,"Type").ToString(),rarity=Prop(card,"Rarity").ToString(),target=Prop(card,"TargetType").ToString(), generate=Prop(card,"CanBeGeneratedInCombat"),levels });
        }
        Console.Write(JsonSerializer.Serialize(new{assemblySha256=digest,rows},new JsonSerializerOptions{WriteIndented=true}));
    }
}

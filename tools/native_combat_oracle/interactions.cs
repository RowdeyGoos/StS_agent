using System.Reflection;
using System.Text.Json;

// Dedicated process only: native TestMode suppresses presentation, not rule hooks.
// Constructor-free player has no profile-backed state or active player hook inventory.
internal static class InteractionOracle {
public static async Task Run(Assembly asm, string digest) {
var flags=BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance|BindingFlags.Static;
var db=asm.GetType("MegaCrit.Sts2.Core.Models.ModelDb",true)!;
var abstractType=asm.GetType("MegaCrit.Sts2.Core.Models.AbstractModel",true)!;
foreach(var modelType in asm.GetTypes().Where(t=>!t.IsAbstract && t.IsSubclassOf(abstractType) && t.Namespace is "MegaCrit.Sts2.Core.Models.Acts" or "MegaCrit.Sts2.Core.Models.Encounters" or "MegaCrit.Sts2.Core.Models.Events" or "MegaCrit.Sts2.Core.Models.RelicPools" or "MegaCrit.Sts2.Core.Models.Relics" or "MegaCrit.Sts2.Core.Models.Characters" or "MegaCrit.Sts2.Core.Models.Cards" or "MegaCrit.Sts2.Core.Models.CardPools" or "MegaCrit.Sts2.Core.Models.Potions" or "MegaCrit.Sts2.Core.Models.PotionPools" or "MegaCrit.Sts2.Core.Models.Monsters" or "MegaCrit.Sts2.Core.Models.Powers"))
    db.GetMethod("Inject")!.Invoke(null,new object[]{modelType});
object Get(string method,string suffix)=>db.GetMethods().Single(m=>m.Name==method&&m.IsGenericMethodDefinition).MakeGenericMethod(asm.GetType("MegaCrit.Sts2.Core.Models."+suffix,true)!).Invoke(null,null)!;
object Prop(object o,string n)=>o.GetType().GetProperty(n,flags)!.GetValue(o)!;
object Call(object o,string n,params object?[] a)=>o.GetType().GetMethods(flags).Single(m=>m.Name==n&&!m.IsGenericMethodDefinition&&m.GetParameters().Length==a.Length&&m.GetParameters().Select((p,i)=>a[i] is null||p.ParameterType.IsInstanceOfType(a[i])).All(x=>x)).Invoke(o,a)!;
object[] Items(object o)=>((System.Collections.IEnumerable)o).Cast<object>().ToArray();
string Id(object o)=>Prop(Prop(o,"Id"),"Entry").ToString()!.ToLowerInvariant();

Type T(string n)=>asm.GetType("MegaCrit.Sts2.Core."+n,true)!;
Array Typed(object[] values,Type t){var a=Array.CreateInstance(t,values.Length);Array.Copy(values,a,values.Length);return a;}
void Field(object o,string n,object value)=>o.GetType().GetField(n,flags)!.SetValue(o,value);


T("TestSupport.TestMode").GetProperty("IsOn")!.SetValue(null,true);
T("Context.LocalContext").GetProperty("NetId")!.SetValue(null,(ulong)0);
var rows=new List<object>();
foreach(string seed in new[]{"0","1","2","42"}) foreach(string mode in new[]{"slippery","blocked","partial_block","zero","random_deaths","random_spawn","targeted_spawn","area_spawn"}) {
 var player=System.Runtime.CompilerServices.RuntimeHelpers.GetUninitializedObject(T("Entities.Players.Player"));
 Field(player,"<Character>k__BackingField",Get("Character","Characters.Ironclad"));
 Field(player,"<ExtraFields>k__BackingField",Activator.CreateInstance(T("Entities.Players.ExtraPlayerFields"))!);
 Field(player,"<PlayerCombatState>k__BackingField",System.Runtime.CompilerServices.RuntimeHelpers.GetUninitializedObject(T("Entities.Players.PlayerCombatState")));
 var context=DispatchProxy.Create(T("Runs.IRunState"),typeof(InteractionContext));var d=(InteractionContext)context;
 var rng=Activator.CreateInstance(T("Runs.RunRngSet"),new object[]{seed})!;
 d.Values["get_CurrentMapPointHistoryEntry"]=null;d.Values["get_Rng"]=rng;d.Values["get_TotalFloor"]=2;d.Values["get_CurrentActIndex"]=0;
 d.Values["get_CurrentMapCoord"]=Activator.CreateInstance(T("Map.MapCoord"),new object[]{3,2})!;
 d.Values["get_Players"]=Typed(new[]{player},T("Entities.Players.Player"));d.Values["get_AscensionLevel"]=0;
 Field(player,"_runState",context);
 var encounter=Call(Get("Encounter","Encounters.VantomBoss"),"MutableClone");
 var combat=Activator.CreateInstance(T("Combat.CombatState"),new object?[]{encounter,context,null,null,null})!;
 d.Listeners=()=>Call(combat,"IterateHookListeners");
 var pc=Activator.CreateInstance(T("Entities.Creatures.Creature"),new object[]{player,80,80})!;
 Field(player,"<Creature>k__BackingField",pc);Call(combat,"AddPlayer",player);
 var manager=T("Combat.CombatManager").GetProperty("Instance")!.GetValue(null)!;
 Field(manager,"_state",combat);Field(manager,"<IsInProgress>k__BackingField",true);Call(Prop(manager,"History"),"Clear");
 var initial=new List<object>();
 bool spawn=mode.EndsWith("spawn");
 int size=mode=="random_deaths"?3:mode=="area_spawn"?2:1;
 for(int i=0;i<size;i++) {
  string kind=spawn&&i==0?"PhrogParasite":"Vantom";
  var m=Call(Get("Monster","Monsters."+kind),"ToMutable");
  var c=Call(combat,"CreateCreature",m,Enum.Parse(T("Combat.CombatSide"),"Enemy"),"initial"+i);Call(combat,"AddCreature",c);initial.Add(c);
  Call(m,"SetUpForCombat");
  Call(c,"SetCurrentHpInternal",mode=="random_deaths"?(decimal)new[]{1,3,7}[i]:spawn?3m:173m);
  if(mode=="blocked"||mode=="partial_block")Field(c,"_block",mode=="blocked"?9:2);
  if(size==1&&!spawn){var power=Call(Get("Power","Powers.SlipperyPower"),"ToMutable",0);Call(power,"ApplyInternal",c,2m,true);}
  if(spawn&&i==0){var power=Call(Get("Power","Powers.InfestedPower"),"ToMutable",0);Call(power,"ApplyInternal",c,1m,true);}
 }
 object State(object c)=>new{type=Prop(c,"Monster").GetType().Name,slot=Prop(c,"SlotName"),hp=Prop(c,"CurrentHp"),maxHp=Prop(c,"MaxHp"),block=Prop(c,"Block"),powers=Items(Prop(c,"Powers")).Select(p=>new{id=Id(p),amount=Prop(p,"Amount")}).ToArray()};
 var before=initial.Select(State).ToArray();
 var card=Call(Get("Card","Cards.SwordBoomerang"),"ToMutable");T("Models.CardModel").GetProperty("Owner")!.SetValue(card,player);
 int hits=mode=="random_deaths"?5:spawn?4:3;decimal damage=mode=="zero"?0m:3m;
 var attack=Activator.CreateInstance(T("Commands.Builders.AttackCommand"),new object[]{damage})!;
 Call(attack,"FromCard",card);Call(attack,"WithHitCount",hits);
 if(mode=="targeted_spawn")Call(attack,"Targeting",initial[0]);
 else if(mode=="area_spawn")Call(attack,"TargetingAllOpponents",combat);
 else Call(attack,"TargetingRandomOpponents",combat,true);
 Call(attack,"WithNoAttackerAnim");
 try {await ((Task)Call(attack,"Execute",new object?[]{null})).WaitAsync(TimeSpan.FromSeconds(5));}
 catch(Exception e){Console.Error.WriteLine(seed+" "+mode);foreach(var f in new System.Diagnostics.StackTrace(e).GetFrames())Console.Error.WriteLine(f.GetMethod()+" IL="+f.GetILOffset());throw;}
 var targetRng=Prop(rng,"CombatTargets");var hpRng=Prop(rng,"Niche");var aiRng=Prop(rng,"MonsterAi");
 rows.Add(new{seed,mode,damage,hits,before,after=Items(Prop(combat,"Enemies")).Select(State).ToArray(),results=Items(Prop(attack,"Results")).Select(hit=>Items(hit).Select(r=>new{slot=Prop(Prop(r,"Receiver"),"SlotName"),damage=Prop(r,"UnblockedDamage"),blocked=Prop(r,"BlockedDamage"),overkill=Prop(r,"OverkillDamage")}).ToArray()).ToArray(),targetCounter=Prop(targetRng,"Counter"),targetSuffix=Call(targetRng,"NextDouble"),hpCounter=Prop(hpRng,"Counter"),hpSuffix=Call(hpRng,"NextDouble"),aiCounter=Prop(aiRng,"Counter"),aiSuffix=Call(aiRng,"NextDouble")});
}
Console.Write(JsonSerializer.Serialize(new{source="Actual pinned AttackCommand.Execute and CreatureCmd damage/death/Infested hooks in TestMode; explicit in-memory contexts, no card play wrapper or run",assemblySha256=digest,rows},new JsonSerializerOptions{WriteIndented=true}));

}
}
public class InteractionContext:DispatchProxy {
 public Dictionary<string,object?> Values=new();
 public Func<object>? Listeners;
 protected override object? Invoke(MethodInfo? method,object?[]? args)=>method!.Name=="IterateHookListeners"?Listeners!():Values.TryGetValue(method.Name,out var value)?value:throw new InvalidOperationException("Unexpected native context access: "+method.Name);
}

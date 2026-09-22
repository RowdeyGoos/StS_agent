using System.Reflection;
using System.Runtime.Loader;
using System.Text.Json;
// Read-only reflection: no game initialization or player-profile access.
if (args.Length != 2) throw new ArgumentException("Usage: oracle <pinned-sts2.dll> <dependency-directory>");
var assemblyPath = Path.GetFullPath(args[0]);
var dependencyDirectory = Path.GetFullPath(args[1]);
var digest = Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(File.ReadAllBytes(assemblyPath))).ToLowerInvariant();
if (digest != "e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18")
    throw new InvalidOperationException("Assembly differs from the pinned 0.107.1 build.");
AssemblyLoadContext.Default.Resolving += (context,name) => {
    var path = Path.Combine(dependencyDirectory, name.Name + ".dll");
    return File.Exists(path) ? context.LoadFromAssemblyPath(path) : null;
};
var asm=AssemblyLoadContext.Default.LoadFromAssemblyPath(assemblyPath);
var flags=BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance|BindingFlags.Static;
var db=asm.GetType("MegaCrit.Sts2.Core.Models.ModelDb",true)!;
var abstractType=asm.GetType("MegaCrit.Sts2.Core.Models.AbstractModel",true)!;
foreach(var modelType in asm.GetTypes().Where(t=>!t.IsAbstract && t.IsSubclassOf(abstractType) && t.Namespace is "MegaCrit.Sts2.Core.Models.Acts" or "MegaCrit.Sts2.Core.Models.Encounters" or "MegaCrit.Sts2.Core.Models.Events" or "MegaCrit.Sts2.Core.Models.RelicPools" or "MegaCrit.Sts2.Core.Models.Relics" or "MegaCrit.Sts2.Core.Models.Characters" or "MegaCrit.Sts2.Core.Models.Cards" or "MegaCrit.Sts2.Core.Models.CardPools" or "MegaCrit.Sts2.Core.Models.Potions" or "MegaCrit.Sts2.Core.Models.PotionPools"))
    db.GetMethod("Inject")!.Invoke(null,new object[]{modelType});
object Get(string method,string suffix)=>db.GetMethods().Single(m=>m.Name==method&&m.IsGenericMethodDefinition).MakeGenericMethod(asm.GetType("MegaCrit.Sts2.Core.Models."+suffix,true)!).Invoke(null,null)!;
object Prop(object o,string n)=>o.GetType().GetProperty(n,flags)!.GetValue(o)!;
object Call(object o,string n,params object?[] a)=>o.GetType().GetMethods(flags).Single(m=>m.Name==n&&!m.IsGenericMethodDefinition&&m.GetParameters().Length==a.Length&&m.GetParameters().Select((p,i)=>a[i] is null||p.ParameterType.IsInstanceOfType(a[i])).All(x=>x)).Invoke(o,a)!;
object[] Items(object o)=>((System.Collections.IEnumerable)o).Cast<object>().ToArray();
string Id(object o)=>Prop(Prop(o,"Id"),"Entry").ToString()!.ToLowerInvariant();

Type T(string n)=>asm.GetType("MegaCrit.Sts2.Core."+n,true)!;
Array Typed(object[] values,Type t){var a=Array.CreateInstance(t,values.Length);Array.Copy(values,a,values.Length);return a;}
void Field(object o,string n,object value)=>o.GetType().GetField(n,flags)!.SetValue(o,value);
var unlock=T("Unlocks.UnlockState").GetField("all")!.GetValue(null)!;
var player=System.Runtime.CompilerServices.RuntimeHelpers.GetUninitializedObject(T("Entities.Players.Player"));
Field(player,"<Character>k__BackingField",Get("Character","Characters.Ironclad"));
Field(player,"<UnlockState>k__BackingField",unlock);
var context=DispatchProxy.Create(T("Runs.IRunState"),typeof(Context));
var data=(Context)context;
data.Values["get_Players"]=Typed(new[]{player},T("Entities.Players.Player"));
data.Values["get_TotalFloor"]=0;
data.Values["get_CardMultiplayerConstraint"]=Enum.Parse(T("Entities.Cards.CardMultiplayerConstraint"),"SingleplayerOnly");
Field(player,"_runState",context);
var relics=Items(db.GetProperty("AllRelics")!.GetValue(null)!);
var scope=JsonDocument.Parse(File.ReadAllText("tests/fixtures/headless_relic_scope.json")).RootElement;
var names=scope.EnumerateObject().Where(p=>p.Value.ValueKind==JsonValueKind.Array && p.Name!="notes" && !p.Name.StartsWith("excluded_")).SelectMany(p=>p.Value.EnumerateArray()).Where(e=>e.ValueKind==JsonValueKind.String).Select(e=>e.GetString()).ToHashSet();
var scoped=relics.Where(r=>names.Contains(r.GetType().Name)).OrderBy(Id).ToArray();
var predicates=new List<object>();
foreach(int floor in new[]{0,40,41}) foreach(int runs in new[]{0,9999}) {
 data.Values["get_TotalFloor"]=floor;
 var u=Activator.CreateInstance(T("Unlocks.UnlockState"),new object[]{Array.Empty<string>(),Array.CreateInstance(T("Models.ModelId"),0),runs})!;
 Field(player,"<UnlockState>k__BackingField",u);
 predicates.Add(new{floor,runs,allowed=scoped.Where(r=>(bool)Call(r,"IsAllowed",context)).Select(Id).ToArray()});
}
Field(player,"<UnlockState>k__BackingField",unlock);data.Values["get_TotalFloor"]=0;
var metadata=scoped.Select(r=>new{id=Id(r),type=r.GetType().Name,rarity=Prop(r,"Rarity").ToString(),shop=Prop(r,"IsAllowedInShops"),predicate=r.GetType().GetMethod("IsAllowed")!.DeclaringType!.Name,neowPredicate=r.GetType().GetMethod("IsAllowedAtNeow")!.DeclaringType!.Name}).ToArray();
var pools=new List<object>();
foreach(var (method,type) in new[]{("CardPool","CardPools.IroncladCardPool"),("CardPool","CardPools.ColorlessCardPool"),("RelicPool","RelicPools.SharedRelicPool"),("RelicPool","RelicPools.IroncladRelicPool"),("PotionPool","PotionPools.IroncladPotionPool"),("PotionPool","PotionPools.SharedPotionPool")}) {
 var pool=Get(method,type);
 var values=method=="CardPool"?Call(pool,"GetUnlockedCards",unlock,data.Values["get_CardMultiplayerConstraint"]):Call(pool,method=="RelicPool"?"GetUnlockedRelics":"GetUnlockedPotions",unlock);
 var epochs=Items(T("Unlocks.UnlockState").GetField("_unlockedEpochIds",flags)!.GetValue(unlock)!).Select(e=>e.ToString()!).Order().ToArray();
 var epochRules=new List<object>();
 foreach(var epoch in epochs) {
  var partial=Activator.CreateInstance(T("Unlocks.UnlockState"),new object[]{epochs.Where(e=>e!=epoch).ToArray(),Array.CreateInstance(T("Models.ModelId"),0),9999})!;
  var available=Items(method=="CardPool"?Call(pool,"GetUnlockedCards",partial,data.Values["get_CardMultiplayerConstraint"]):Call(pool,method=="RelicPool"?"GetUnlockedRelics":"GetUnlockedPotions",partial)).Select(Id).ToHashSet();
  var excluded=Items(values).Select(Id).Where(id=>!available.Contains(id)).ToArray();
  if(excluded.Length>0)epochRules.Add(new{epoch,excluded});
 }
 pools.Add(new{pool=type,ids=Items(values).Select(Id),epochRules});
}

var bagType=T("Runs.RelicGrabBag");var relicType=T("Models.RelicModel");var rngType=T("Random.Rng");
var bagRows=new List<object>();
object Predicate(Type type,Func<object,bool> predicate){var arg=System.Linq.Expressions.Expression.Parameter(type);return System.Linq.Expressions.Expression.Lambda(typeof(Func<,>).MakeGenericType(type,typeof(bool)),System.Linq.Expressions.Expression.Invoke(System.Linq.Expressions.Expression.Constant(predicate),System.Linq.Expressions.Expression.Convert(arg,typeof(object))),arg).Compile();}
object DumpBag(object b)=>Items(Prop(Call(b,"ToSerializable"),"RelicIdLists")).ToDictionary(k=>Prop(k,"Key").ToString()!.ToLowerInvariant(),v=>Items(Prop(v,"Value")).Select(id=>Prop(id,"Entry").ToString()!.ToLowerInvariant()).ToArray());
foreach(int seed in new[]{0,1,2,42}) foreach(int floor in new[]{0,41}) {
 data.Values["get_TotalFloor"]=floor;
 var rng=Activator.CreateInstance(rngType,new object[]{(uint)seed,0})!;
 var shared=Items(Call(Get("RelicPool","RelicPools.SharedRelicPool"),"GetUnlockedRelics",unlock));
 var character=Items(Call(Get("RelicPool","RelicPools.IroncladRelicPool"),"GetUnlockedRelics",unlock));
 var sharedBag=Activator.CreateInstance(bagType)!;var bag=Activator.CreateInstance(bagType)!;
 Call(sharedBag,"Populate",Typed(shared,relicType),rng);
 Call(bag,"Populate",Typed(shared.Concat(character).Where(r=>new[]{"Common","Uncommon","Rare","Shop"}.Contains(Prop(r,"Rarity").ToString())).ToArray(),relicType),rng);
 var initial=DumpBag(bag);var steps=new List<object>();
 for(int i=0;i<9;i++) {
  string rarity=new[]{"common","uncommon","rare","shop"}[i%4];bool back=i%2==1;
  var requested=Enum.Parse(T("Entities.Relics.RelicRarity"),rarity,true);
  var allowed=Predicate(relicType,r=>(i!=4 || Id(r)=="molten_egg") && (!back || (bool)Prop(r,"IsAllowedInShops")));
  var found=Call(bag,back?"PullFromBack":"PullFromFront",requested,allowed,context);
  string name=found is null?"circlet":Id(found);
  if(found is not null)Call(sharedBag,"Remove",found);
  steps.Add(new{rarity,back,only=i==4?"molten_egg":null,selected=name,player=DumpBag(bag),shared=DumpBag(sharedBag),counter=Prop(rng,"Counter")});
 }
 bagRows.Add(new{seed,floor,initial,steps,suffix=Call(rng,"NextDouble")});
}
// Fresh shared bags alone refresh; authored deques isolate each boundary.
var bagEdges=new List<object>();
foreach(string mode in new[]{"empty_front","empty_back","player_empty","filtered_nonempty","fallback_empty","purged_then_refill","refill_purges","owned_repeat"}) {
 data.Values["get_TotalFloor"]=mode=="purged_then_refill"||mode=="refill_purges"?41:0;
 var rng=Activator.CreateInstance(rngType,new object[]{0U,0})!;
 var bag=Activator.CreateInstance(bagType,new object[]{mode!="player_empty"})!;
 var originals=Items(Call(Get("RelicPool","RelicPools.SharedRelicPool"),"GetUnlockedRelics",unlock));
 Call(bag,"Populate",Typed(originals,relicType),rng);
 var deques=(System.Collections.IDictionary)bagType.GetField("_deques",flags)!.GetValue(bag)!;
 foreach(var value in deques.Values)((System.Collections.IList)value).Clear();
 string rarity=mode=="refill_purges"?"Uncommon":"Common";
 var requested=Enum.Parse(T("Entities.Relics.RelicRarity"),rarity);
 var common=(System.Collections.IList)deques[Enum.Parse(T("Entities.Relics.RelicRarity"),"Common")]!;
 if(mode=="filtered_nonempty"||mode=="fallback_empty")common.Add(Get("Relic","Relics.Anchor"));
 if(mode=="purged_then_refill")common.Add(Get("Relic","Relics.MealTicket"));
 if(mode=="filtered_nonempty")((System.Collections.IList)deques[Enum.Parse(T("Entities.Relics.RelicRarity"),"Uncommon")]!).Add(Get("Relic","Relics.MoltenEgg"));
 var ownedList=Activator.CreateInstance(typeof(List<>).MakeGenericType(relicType))!;
 Field(player,"_relics",ownedList);
 if(mode=="owned_repeat")Call(player,"AddRelicInternal",Call(Get("Relic","Relics.AmethystAubergine"),"ToMutable"),-1,true);
 var initial=DumpBag(bag);
 var filter=Predicate(relicType,r=>mode is not ("filtered_nonempty" or "fallback_empty")||Id(r)=="molten_egg");
 var counter=Prop(rng,"Counter");
 var found=Call(bag,mode=="empty_back"?"PullFromBack":"PullFromFront",requested,filter,context);
 if(mode=="owned_repeat")Call(player,"AddRelicInternal",Call(found!,"ToMutable"),-1,true);
 bagEdges.Add(new{owned=Items(ownedList).Select(Id),mode,rarity=rarity.ToLowerInvariant(),floor=data.Values["get_TotalFloor"],initial,selected=found is null?"circlet":Id(found),final=DumpBag(bag),counterBefore=counter,counterAfter=Prop(rng,"Counter"),suffix=Call(rng,"NextDouble")});
}
data.Values["get_TotalFloor"]=0;
var rug=Call(Get("Relic","Relics.DingyRug"),"ToMutable");
rug.GetType().GetProperty("Owner",flags)!.SetValue(rug,player);
var cardRows=new List<object>();var optionsType=T("Runs.CardCreationOptions");var cardType=T("Models.CardModel");
foreach(var mode in new[]{"reward","direct","blocked","custom","colorless","rare_reward"}) {
 var pool=Get("CardPool",mode=="colorless"?"CardPools.ColorlessCardPool":"CardPools.IroncladCardPool");
 var input=Typed(new[]{pool},T("Models.CardPoolModel"));
 var source=Enum.Parse(T("Runs.CardCreationSource"),"Other");
 var odds=Enum.Parse(T("Runs.CardRarityOddsType"),"Uniform");
 var filter=mode=="rare_reward"?Predicate(cardType,c=>Prop(c,"Rarity").ToString()=="Rare"):null;
 var options=mode=="custom"?Activator.CreateInstance(optionsType,new object[]{Typed(Items(Call(pool,"GetUnlockedCards",unlock,data.Values["get_CardMultiplayerConstraint"])),cardType),source,odds})!:Activator.CreateInstance(optionsType,new object?[]{input,source,odds,filter})!;
 if(mode!="direct")Call(options,"WithFlags",Enum.ToObject(T("Runs.CardCreationFlags"),128|(mode=="blocked"?16:0)));
 var modified=Call(rug,"ModifyCardRewardCreationOptions",player,options);
 cardRows.Add(new{mode,ids=Items(Call(modified,"GetPossibleCards",player)).Select(Id)});
}
var potionRows=new List<object>();
var potionPool=Items(Call(Get("PotionPool","PotionPools.IroncladPotionPool"),"GetUnlockedPotions",unlock)).Concat(Items(Call(Get("PotionPool","PotionPools.SharedPotionPool"),"GetUnlockedPotions",unlock))).ToArray();
foreach(bool combat in new[]{false,true}) foreach(int seed in new[]{0,1,2,42}) {
 var rng=Activator.CreateInstance(rngType,new object[]{(uint)seed,0})!;
 var options=potionPool.Where(p=>Id(p)!="fire_potion"&&(!combat || (bool)Prop(p,"CanBeGeneratedInCombat"))).ToArray();
 var generated=T("Factories.PotionFactory").GetMethod("CreateRandomPotion",flags)!.Invoke(null,new object[]{Typed(options,T("Models.PotionModel")),3,rng})!;
 potionRows.Add(new{seed,combat,blacklist=new[]{"fire_potion"},available=options.Select(Id),selected=Items(generated).Select(Id),counter=Prop(rng,"Counter"),suffix=Call(rng,"NextDouble")});
}
Console.Write(JsonSerializer.Serialize(new{source="Pinned assembly execution over explicit in-memory solo contexts; no run launch or profile access",metadata,predicates,pools,bagRows,bagEdges,cardRows,potionRows},new JsonSerializerOptions{WriteIndented=true}));
public class Context:DispatchProxy {
 public Dictionary<string,object> Values=new();
 protected override object? Invoke(MethodInfo? method,object?[]? args)=>Values.TryGetValue(method!.Name,out var value)?value:throw new InvalidOperationException("Unexpected native context access: "+method.Name);
}

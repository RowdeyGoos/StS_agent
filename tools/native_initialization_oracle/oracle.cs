using System.Reflection;
using System.Runtime.Loader;
using System.Text.Json;
// Read-only reflection: no game initialization or player-profile access.
if (args.Length is < 2 or > 3) throw new ArgumentException("Usage: oracle <pinned-sts2.dll> <dependency-directory> [overgrowth|underdocks]");
var firstAct = args.Length == 3 ? args[2] : "overgrowth";
if (firstAct is not ("overgrowth" or "underdocks")) throw new ArgumentException("Unsupported first act.");
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
foreach(var modelType in asm.GetTypes().Where(t=>!t.IsAbstract && t.IsSubclassOf(abstractType) && t.Namespace is "MegaCrit.Sts2.Core.Models.Acts" or "MegaCrit.Sts2.Core.Models.Encounters" or "MegaCrit.Sts2.Core.Models.Events" or "MegaCrit.Sts2.Core.Models.RelicPools" or "MegaCrit.Sts2.Core.Models.Relics"))
    db.GetMethod("Inject")!.Invoke(null,new object[]{modelType});
object Get(string method,string suffix)=>db.GetMethods().Single(m=>m.Name==method&&m.IsGenericMethodDefinition).MakeGenericMethod(asm.GetType("MegaCrit.Sts2.Core.Models."+suffix,true)!).Invoke(null,null)!;
object Prop(object o,string n)=>o.GetType().GetProperty(n,flags)!.GetValue(o)!;
object Call(object o,string n,params object?[] a)=>o.GetType().GetMethods(flags).Single(m=>m.Name==n&&!m.IsGenericMethodDefinition&&m.GetParameters().Length==a.Length&&m.GetParameters().Select((p,i)=>a[i] is null||p.ParameterType.IsInstanceOfType(a[i])).All(x=>x)).Invoke(o,a)!;
object[] Items(object o)=>((System.Collections.IEnumerable)o).Cast<object>().ToArray();
string Id(object o)=>Prop(Prop(o,"Id"),"Entry").ToString()!.ToLowerInvariant();
var actType=asm.GetType("MegaCrit.Sts2.Core.Models.ActModel",true)!;
var unlock=asm.GetType("MegaCrit.Sts2.Core.Unlocks.UnlockState",true)!.GetField("all")!.GetValue(null)!;
var rngType=asm.GetType("MegaCrit.Sts2.Core.Random.Rng",true)!;
var hash=asm.GetType("MegaCrit.Sts2.Core.Helpers.StringHelper",true)!.GetMethod("GetDeterministicHashCode")!;
uint Hash(string text)=>unchecked((uint)(int)hash.Invoke(null,new object[]{text})!);
object Rng(string seed,string salt)=>Activator.CreateInstance(rngType,new object[]{unchecked(Hash(seed)+Hash(salt)),0})!;
object Mutable(object a)=>Call(a,"MutableClone");
object[] actModels={Get("Act",firstAct == "underdocks" ? "Acts.Underdocks" : "Acts.Overgrowth"),Get("Act","Acts.Hive"),Get("Act","Acts.Glory")};
var sharedEvents=Items(db.GetProperty("AllSharedEvents")!.GetValue(null)!);
var sharedAncients=Items(Prop(unlock,"SharedAncients"));
var catalog=actModels.Select(a=>new {act=Id(a),rooms=Call(a,"GetNumberOfRooms",false),weakCount=Prop(a,"NumberOfWeakEncounters"),
 events=Items(Prop(a,"AllEvents")).Select(Id),ancients=Items(Call(a,"GetUnlockedAncients",unlock)).Select(Id),
 encounters=Items(Prop(a,"AllEncounters")).Select(e=>new {name=e.GetType().Name,id=Id(e),kind=Prop(e,"RoomType").ToString(),weak=Prop(e,"IsWeak"),tags=Items(Prop(e,"Tags")).Select(Convert.ToInt32)})}).ToArray();
var sharedRelics=Items(Call(Get("RelicPool","RelicPools.SharedRelicPool"),"GetUnlockedRelics",unlock));
var ironcladRelics=Items(Call(Get("RelicPool","RelicPools.IroncladRelicPool"),"GetUnlockedRelics",unlock));
void Shuffle(object rng,object list,Type element)=>rngType.GetMethod("Shuffle")!.MakeGenericMethod(element).Invoke(rng,new[]{list});
Array Typed(object[] values,Type t){var a=Array.CreateInstance(t,values.Length);Array.Copy(values,a,values.Length);return a;}
var rows=new List<object>();
foreach(var seed in new[]{"0","1","2","3","4","5","6","7","8","9","42","ABC123","😀"}) {
 var rng=Rng(seed,"up_front");
 var bagType=asm.GetType("MegaCrit.Sts2.Core.Runs.RelicGrabBag",true)!;
 var relicType=asm.GetType("MegaCrit.Sts2.Core.Models.RelicModel",true)!;
 foreach(var pool in new[]{sharedRelics,sharedRelics.Concat(ironcladRelics).Where(r=>new[]{"Common","Uncommon","Rare","Shop"}.Contains(Prop(r,"Rarity").ToString())).ToArray()}) {
  var bag=Activator.CreateInstance(bagType,new object[]{true})!;Call(bag,"Populate",Typed(pool,relicType),rng);
 }
 int afterBags=(int)Prop(rng,"Counter");
 var acts=actModels.Select(Mutable).ToArray();
 var ancientType=asm.GetType("MegaCrit.Sts2.Core.Models.AncientEventModel",true)!;
 var remaining=sharedAncients.ToList();Shuffle(rng,remaining,typeof(object));
 var subsets=new List<string[]>();
 for(int i=1;i<3;i++) {int count=(int)Call(rng,"NextInt",remaining.Count+1);var chosen=remaining.Take(count).ToArray();remaining=remaining.Skip(count).ToList();actType.GetMethod("SetSharedAncientSubset")!.Invoke(acts[i],new object[]{Activator.CreateInstance(typeof(List<>).MakeGenericType(ancientType),new object[]{Typed(chosen,ancientType)})!});subsets.Add(chosen.Select(Id).ToArray());}
 int afterAllocation=(int)Prop(rng,"Counter");
 var generated=new List<object>();
 foreach(var act in acts) {
  Call(act,"GenerateRooms",rng,unlock,false);
  var rooms=actType.GetField("_rooms",flags)!.GetValue(act)!;
  generated.Add(new{act=Id(act),events=Items(rooms.GetType().GetField("events")!.GetValue(rooms)!).Select(Id),normal=Items(rooms.GetType().GetField("normalEncounters")!.GetValue(rooms)!).Select(e=>e.GetType().Name),elites=Items(rooms.GetType().GetField("eliteEncounters")!.GetValue(rooms)!).Select(e=>e.GetType().Name),boss=Prop(rooms,"Boss").GetType().Name,ancient=Id(Prop(rooms,"Ancient")),counter=Prop(rng,"Counter")});
 }
 var mapRng=Rng(seed,"act_1_map");
 var map=Activator.CreateInstance(asm.GetType("MegaCrit.Sts2.Core.Map.StandardActMap",true)!,new object?[]{mapRng,acts[0],false,false,false,null,true})!;
 int[] Coord(object point){var c=point.GetType().GetField("coord")!.GetValue(point)!;return new[]{(int)c.GetType().GetField("row")!.GetValue(c)!,(int)c.GetType().GetField("col")!.GetValue(c)!};}
 var nodes=Items(Call(map,"GetAllMapPoints")).Append(Prop(map,"BossMapPoint")).Select(p=>new{coord=Coord(p),kind=Prop(p,"PointType").ToString(),children=Items(Prop(p,"Children")).Select(Coord).OrderBy(c=>c[0]).ThenBy(c=>c[1])}).OrderBy(p=>p.coord[0]).ThenBy(p=>p.coord[1]);
 rows.Add(new{seed,afterBags,afterAllocation,subsets,acts=generated,upFrontCounter=Prop(rng,"Counter"),upFrontSuffix=Call(rng,"NextDouble"),map=new{nodes,starts=Items(map.GetType().GetField("startMapPoints")!.GetValue(map)!).Select(Coord).OrderBy(c=>c[0]).ThenBy(c=>c[1]),counter=Prop(mapRng,"Counter"),suffix=Call(mapRng,"NextDouble")}});
}
Console.Write(JsonSerializer.Serialize(new{source=$"Pinned assembly metadata, RelicGrabBag.Populate, ActModel.GenerateRooms and StandardActMap execution; explicit solo all-unlocked {firstAct}/Hive/Glory inputs, no profile access",dllSha256=digest,catalog,sharedEvents=sharedEvents.Select(Id),sharedAncients=sharedAncients.Select(Id),rows},new JsonSerializerOptions{WriteIndented=true}));

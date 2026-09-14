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
var type=asm.GetType("MegaCrit.Sts2.Core.Random.Rng",true)!;
var hash=asm.GetType("MegaCrit.Sts2.Core.Helpers.StringHelper",true)!.GetMethod("GetDeterministicHashCode")!;
var results=new List<object>();
foreach(uint seed in new uint[]{0,1,42,2147483647,2147483648,4294967295}) {
 var rng=Activator.CreateInstance(type,new object[]{seed,0})!;
 var rows=new List<object>();
 foreach(var count in new[]{1,2,17,2147483647}) rows.Add(new {op="int",max=count,value=type.GetMethod("NextInt",new[]{typeof(int)})!.Invoke(rng,new object[]{count})});
 for(int i=0;i<5;i++) rows.Add(new {op="float",value=type.GetMethod("NextFloat",new[]{typeof(float)})!.Invoke(rng,new object[]{1f})});
 for(int i=0;i<5;i++) rows.Add(new {op="double",value=type.GetMethod("NextDouble",Type.EmptyTypes)!.Invoke(rng,null)});
 var list=Enumerable.Range(0,12).ToList();type.GetMethod("Shuffle")!.MakeGenericMethod(typeof(int)).Invoke(rng,new object[]{list});
 results.Add(new {seed,rows,shuffle=list,counter=type.GetProperty("Counter")!.GetValue(rng)});
}
var gaussianRows=new List<object>();
foreach(uint seed in new uint[]{0,1,42,4294967295}) {
 var rng=Activator.CreateInstance(type,new object[]{seed,0})!;
 var values=Enumerable.Range(0,10).Select(_=>(int)type.GetMethod("NextGaussianInt")!.Invoke(rng,new object[]{5,2,3,7})!).ToArray();
 gaussianRows.Add(new{seed,values,counter=type.GetProperty("Counter")!.GetValue(rng),suffix=type.GetMethod("NextDouble",Type.EmptyTypes)!.Invoke(rng,null)});
}
var hashes=new[]{"","0","2","ABC123","shuffle","rewards","NEOW","😀"}.Select(s=>new {input=s,value=hash.Invoke(null,new object[]{s})}).ToArray();

var neowRows=new List<object>();
string[] curseOptions={"cursed_pearl", "hefty_tablet", "large_capsule", "leafy_poultice", "neows_bones", "precarious_shears", "silken_tress", "silver_crucible"};
string[] positiveOptions={"arcane_scroll", "booming_conch", "fishing_rod", "golden_pearl", "kaleidoscope", "lead_paperweight", "lost_coffer", "massive_scroll", "neows_torment", "new_leaf", "phial_holster", "precise_scissors", "scroll_boxes", "winged_boots"};
foreach(var seedText in new[]{"0","1","2","3","4","42","ABC123","😀"}) {
 uint root=unchecked((uint)(int)hash.Invoke(null,new object[]{seedText})!);
 uint salt=unchecked((uint)(int)hash.Invoke(null,new object[]{"NEOW"})!);
 var rng=Activator.CreateInstance(type,new object[]{unchecked(root+salt),0})!;
 int Next(int max)=>(int)type.GetMethod("NextInt",new[]{typeof(int)})!.Invoke(rng,new object[]{max})!;
 bool Coin()=>(bool)type.GetMethod("NextBool")!.Invoke(rng,null)!;
 string curse=curseOptions[Next(curseOptions.Length)];
 string? excluded=curse switch {"cursed_pearl"=>"golden_pearl","hefty_tablet"=>"arcane_scroll","leafy_poultice"=>"new_leaf","precarious_shears"=>"precise_scissors",_=>null};
 var positives=positiveOptions.Where(x=>x!=excluded).ToList();
 if(curse!="large_capsule") positives.Add(Coin()?"lava_rock":"small_capsule");
 positives.Add(Coin()?"nutritious_oyster":"stone_humidifier");
 positives.Add(Coin()?"neows_talisman":"pomander");
 positives.RemoveAll(x=>x=="kaleidoscope"||x=="massive_scroll");
 type.GetMethod("Shuffle")!.MakeGenericMethod(typeof(string)).Invoke(rng,new object[]{positives});
 neowRows.Add(new{seed=seedText,offers=positives.Take(2).Append(curse).ToArray(),counter=type.GetProperty("Counter")!.GetValue(rng)});
}
Console.Write(JsonSerializer.Serialize(new {source="pinned assembly Rng reflection; Neow source-derived composition with explicit Kaleidoscope and multiplayer exclusions",results,hashes,gaussian=gaussianRows,neow=neowRows}));

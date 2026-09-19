using System.Reflection;
using System.Runtime.Loader;
using System.Text.Json;
// Read-only reflection: no game initialization or player-profile access.
if (args.Length is not (2 or 3) || (args.Length == 3 && args[2] is not ("generation" or "interactions" or "transforms" or "silent" or "regent" or "necrobinder" or "defect"))) throw new ArgumentException("Usage: oracle <pinned-sts2.dll> <dependency-directory> [generation|interactions|transforms|silent|regent|necrobinder|defect]");
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
if(args.Length==3 && args[2]=="interactions") { await InteractionOracle.Run(asm,digest); return; }
var flags=BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance|BindingFlags.Static;
var db=asm.GetType("MegaCrit.Sts2.Core.Models.ModelDb",true)!;
var abstractType=asm.GetType("MegaCrit.Sts2.Core.Models.AbstractModel",true)!;
foreach(var modelType in asm.GetTypes().Where(t=>!t.IsAbstract && t.IsSubclassOf(abstractType) && t.Namespace is "MegaCrit.Sts2.Core.Models.Acts" or "MegaCrit.Sts2.Core.Models.Encounters" or "MegaCrit.Sts2.Core.Models.Events" or "MegaCrit.Sts2.Core.Models.RelicPools" or "MegaCrit.Sts2.Core.Models.Relics" or "MegaCrit.Sts2.Core.Models.Characters" or "MegaCrit.Sts2.Core.Models.Cards" or "MegaCrit.Sts2.Core.Models.CardPools" or "MegaCrit.Sts2.Core.Models.Potions" or "MegaCrit.Sts2.Core.Models.PotionPools" or "MegaCrit.Sts2.Core.Models.Monsters"))
    db.GetMethod("Inject")!.Invoke(null,new object[]{modelType});
if(args.Length==3 && args[2]=="defect") { DefectOracle.Run(asm,digest); return; }
if(args.Length==3 && args[2]=="necrobinder") { NecrobinderOracle.Run(asm,digest); return; }
if(args.Length==3 && args[2]=="regent") { RegentOracle.Run(asm,digest); return; }
if(args.Length==3 && args[2]=="silent") { SilentOracle.Run(asm,digest); return; }
object Get(string method,string suffix)=>db.GetMethods().Single(m=>m.Name==method&&m.IsGenericMethodDefinition).MakeGenericMethod(asm.GetType("MegaCrit.Sts2.Core.Models."+suffix,true)!).Invoke(null,null)!;
object Prop(object o,string n)=>o.GetType().GetProperty(n,flags)!.GetValue(o)!;
object Call(object o,string n,params object?[] a)=>o.GetType().GetMethods(flags).Single(m=>m.Name==n&&!m.IsGenericMethodDefinition&&m.GetParameters().Length==a.Length&&m.GetParameters().Select((p,i)=>a[i] is null||p.ParameterType.IsInstanceOfType(a[i])).All(x=>x)).Invoke(o,a)!;
object[] Items(object o)=>((System.Collections.IEnumerable)o).Cast<object>().ToArray();
string Id(object o)=>Prop(Prop(o,"Id"),"Entry").ToString()!.ToLowerInvariant();

Type T(string n)=>asm.GetType("MegaCrit.Sts2.Core."+n,true)!;
Array Typed(object[] values,Type t){var a=Array.CreateInstance(t,values.Length);Array.Copy(values,a,values.Length);return a;}
void Field(object o,string n,object value)=>o.GetType().GetField(n,flags)!.SetValue(o,value);

var player=System.Runtime.CompilerServices.RuntimeHelpers.GetUninitializedObject(T("Entities.Players.Player"));
var creatureType=T("Entities.Creatures.Creature");
Field(player,"<Character>k__BackingField",Get("Character","Characters.Ironclad"));
var all=Items(Prop(Get("Act","Acts.Overgrowth"),"AllEncounters")).Append(Get("Encounter","Encounters.DenseVegetationEventEncounter")).ToArray();
var rows=new List<object>();
foreach(string seed in new[]{"0","1","2","42"}) foreach(int floor in new[]{1,7}) foreach(var original in all) {
 var context=DispatchProxy.Create(T("Runs.IRunState"),typeof(Context));var d=(Context)context;
 var runRng=Activator.CreateInstance(T("Runs.RunRngSet"),new object[]{seed})!;
 d.Values["get_Rng"]=runRng;d.Values["get_TotalFloor"]=floor;d.Values["get_CurrentActIndex"]=0;
 d.Values["get_CurrentMapCoord"]=Activator.CreateInstance(T("Map.MapCoord"),new object[]{3,floor})!;
 d.Values["get_Players"]=Typed(new[]{player},T("Entities.Players.Player"));d.Values["get_AscensionLevel"]=0;
 Field(player,"_runState",context);
 var encounter=Call(original,"MutableClone");Call(encounter,"GenerateMonstersWithSlots",context);
 var combat=Activator.CreateInstance(T("Combat.CombatState"),new object?[]{encounter,context,null,null,null})!;
 var pc=Activator.CreateInstance(creatureType,new object[]{player,80,80})!;
 Field(player,"<Creature>k__BackingField",pc);Call(combat,"AddPlayer",player);
 var monsters=new List<object>();var creatures=new List<object>();
 foreach(var entry in Items(Prop(encounter,"MonstersWithSlots"))) {
  var m=entry.GetType().GetField("Item1")!.GetValue(entry)!;var slot=entry.GetType().GetField("Item2")!.GetValue(entry);
  var c=Call(combat,"CreateCreature",m,Enum.Parse(T("Combat.CombatSide"),"Enemy"),slot);Call(combat,"AddCreature",c);creatures.Add(c);
 }
 foreach(var c in creatures){var m=Prop(c,"Monster");Call(m,"SetUpForCombat");Call(m,"RollMove",Typed(new[]{pc},creatureType));monsters.Add(new{type=m.GetType().Name,id=Id(m),slot=Prop(c,"SlotName"),hp=Prop(c,"MaxHp"),move=Prop(Prop(m,"NextMove"),"Id"),localSeed=Prop(Prop(m,"Rng"),"Seed")});}
 var erng=T("Models.EncounterModel").GetField("_rng",flags)!.GetValue(encounter)!;
 var niche=Prop(runRng,"Niche");var ai=Prop(runRng,"MonsterAi");
 rows.Add(new{seed,floor,encounter=original.GetType().Name,id=Id(original),monsters,compositionCounter=Prop(erng,"Counter"),compositionSuffix=Call(erng,"NextDouble"),hpCounter=Prop(niche,"Counter"),hpSuffix=Call(niche,"NextDouble"),aiCounter=Prop(ai,"Counter"),aiSuffix=Call(ai,"NextDouble")});
}
var shuffles=new List<object>();
foreach(uint seed in new uint[]{0,1,42}) foreach(int size in new[]{0,1,3,10,16,17,31,64}) foreach(bool stable in new[]{false,true}) {
 var types=new[]{"StrikeIronclad","Bash","DefendIronclad","Anger","ShrugItOff"};
 var cardType=T("Models.CardModel");var inputs=new List<object>();var cards=new List<object>();
 for(int i=0;i<size;i++) {var type=types[(i*7+i/3)%types.Length];var card=Call(Get("Card","Cards."+type),"ToMutable");var upgraded=i%4==0;if(upgraded){Call(card,"UpgradeInternal");Call(card,"FinalizeUpgradeInternal");}cards.Add(card);inputs.Add(new{type,upgraded});}
 var array=(System.Collections.IList)Activator.CreateInstance(typeof(List<>).MakeGenericType(cardType))!;foreach(var card in cards)array.Add(card);var rng=Activator.CreateInstance(T("Random.Rng"),new object[]{seed,0})!;
 var method=T("Extensions.ListExtensions").GetMethods(flags).Single(m=>m.Name==(stable?"StableShuffle":"UnstableShuffle")&&m.IsGenericMethodDefinition);
 method.MakeGenericMethod(cardType).Invoke(null,new object[]{array,rng});
 shuffles.Add(new{seed,size,stable,inputs,order=Items(array).Select(c=>cards.FindIndex(x=>ReferenceEquals(x,c))).ToArray(),counter=Prop(rng,"Counter"),suffix=Call(rng,"NextDouble")});
}
if(args.Length==3) {
 Field(player,"<Deck>k__BackingField",Activator.CreateInstance(T("Entities.Cards.CardPile"),new object[]{Enum.Parse(T("Entities.Cards.PileType"),"Deck")})!);
 var unlock=T("Unlocks.UnlockState").GetField("all")!.GetValue(null)!;
 Field(player,"<UnlockState>k__BackingField",unlock);
 var context=(Context)Prop(player,"RunState");
 context.Values["get_CardMultiplayerConstraint"]=Enum.Parse(T("Entities.Cards.CardMultiplayerConstraint"),"SingleplayerOnly");
 if(args[2]=="transforms") { TransformOracle.Run(asm,digest,player); return; }
 var cardType=T("Models.CardModel");var factory=T("Factories.CardFactory");
 var pools=new Dictionary<string,object[]>();
 foreach(var (name,type) in new[]{("ironclad","CardPools.IroncladCardPool"),("colorless","CardPools.ColorlessCardPool")})
  pools[name]=Items(Call(Get("CardPool",type),"GetUnlockedCards",unlock,context.Values["get_CardMultiplayerConstraint"]));
 object[] Filter(IEnumerable<object> cards)=>Items(factory.GetMethod("FilterForCombat")!.Invoke(null,new object[]{Typed(cards.ToArray(),cardType)})!);
 object Metadata(object c)=>new{id=Id(c),kind=Prop(c,"Type").ToString(),rarity=Prop(c,"Rarity").ToString(),canGenerate=Prop(c,"CanBeGeneratedInCombat"),cost=Prop(Prop(c,"EnergyCost"),"Canonical"),costsX=Prop(Prop(c,"EnergyCost"),"CostsX")};
 var poolRows=pools.Select(p=>new{name=p.Key,cards=p.Value.Select(Metadata).ToArray(),eligible=Filter(p.Value).Select(Id).ToArray()}).ToArray();
 var generationRows=new List<object>();
 uint combatSeed=(uint)Prop(Prop(Activator.CreateInstance(T("Runs.RunRngSet"),new object[]{"2"})!,"CombatCardGeneration"),"Seed");
 foreach(uint seed in new uint[]{0,1,2,42,4294967295,combatSeed}) foreach(string mode in new[]{"infernal_blade","discovery","attack_potion","skill_potion","power_potion","colorless_potion","jack_of_all_trades","jackpot","stoke","calamity","orobic_acid"}) {
  var rng=Activator.CreateInstance(T("Random.Rng"),new object[]{seed,0})!;var calls=new List<object>();
  var kinds=mode=="orobic_acid"?new[]{"Attack","Skill","Power"}:new[]{mode switch {"infernal_blade" or "attack_potion" or "calamity"=>"Attack","skill_potion"=>"Skill","power_potion"=>"Power",_=>""}};
  foreach(var kind in kinds) {
   var family=mode is "colorless_potion" or "jack_of_all_trades"?"colorless":"ironclad";
   var options=pools[family].Where(c=>(kind==""||Prop(c,"Type").ToString()==kind)&&(mode!="jack_of_all_trades"||Id(c)!="jack_of_all_trades")&&(mode!="jackpot"||((int)Prop(Prop(c,"EnergyCost"),"Canonical")==0&&!(bool)Prop(Prop(c,"EnergyCost"),"CostsX")))).ToArray();
   bool distinct=mode is not ("jackpot" or "stoke" or "calamity");
   int count=mode switch {"infernal_blade" or "orobic_acid"=>1,"jack_of_all_trades"=>2,_=>3};
   var generated=Items(factory.GetMethod(distinct?"GetDistinctForCombat":"GetForCombat")!.Invoke(null,new object[]{player,Typed(options,cardType),count,rng})!);
   calls.Add(new{family,kind,distinct,count,eligible=Filter(options).Select(Id),selected=generated.Select(Id),upgrades=generated.Select(c=>Prop(c,"CurrentUpgradeLevel")),counter=Prop(rng,"Counter")});
  }
  generationRows.Add(new{seed,mode,calls,counter=Prop(rng,"Counter"),suffix=Call(rng,"NextDouble")});
 }
 var boundaries=new List<object>();
 foreach(bool distinct in new[]{false,true}) foreach(int count in new[]{0,1,5}) foreach(int size in new[]{0,1,3}) {
  if(!distinct&&size==0&&count>0)continue;
  var options=new[]{Get("Card","Cards.Anger"),Get("Card","Cards.IronWave"),Get("Card","Cards.Anger")}.Take(size).ToArray();
  var rng=Activator.CreateInstance(T("Random.Rng"),new object[]{42u,0})!;
  var generated=Items(factory.GetMethod(distinct?"GetDistinctForCombat":"GetForCombat")!.Invoke(null,new object[]{player,Typed(options,cardType),count,rng})!);
  boundaries.Add(new{distinct,count,inputs=options.Select(Id),selected=generated.Select(Id),counter=Prop(rng,"Counter"),suffix=Call(rng,"NextDouble")});
 }
 var potionRows=new List<object>();
 uint potionSeed=(uint)Prop(Prop(Activator.CreateInstance(T("Runs.RunRngSet"),new object[]{"2"})!,"CombatPotionGeneration"),"Seed");
 foreach(uint seed in new uint[]{0,1,2,42,4294967295,potionSeed}) foreach(bool inCombat in new[]{false,true}) {
  var rng=Activator.CreateInstance(T("Random.Rng"),new object[]{seed,0})!;var selected=new List<string>();
  for(int i=0;i<3;i++)selected.Add(Id(T("Factories.PotionFactory").GetMethod(inCombat?"CreateRandomPotionInCombat":"CreateRandomPotionOutOfCombat")!.Invoke(null,new object?[]{player,rng,null})!));
  potionRows.Add(new{seed,inCombat,selected,counter=Prop(rng,"Counter"),suffix=Call(rng,"NextDouble")});
 }
 Console.Write(JsonSerializer.Serialize(new{source="Actual pinned CardFactory combat generation in explicit solo all-unlocked contexts; no card play or insertion hooks",assemblySha256=digest,combatSeed,potionSeed,poolRows,generationRows,boundaries,potionRows},new JsonSerializerOptions{WriteIndented=true}));
} else {
Console.Write(JsonSerializer.Serialize(new{source="Pinned encounter generation, creature HP construction, and initial move selection; explicit in-memory A0 contexts",assemblySha256=digest,rows,shuffles},new JsonSerializerOptions{WriteIndented=true}));
}
public class Context:DispatchProxy {
 public Dictionary<string,object> Values=new();
 protected override object? Invoke(MethodInfo? method,object?[]? args)=>Values.TryGetValue(method!.Name,out var value)?value:throw new InvalidOperationException("Unexpected native context access: "+method.Name);
}

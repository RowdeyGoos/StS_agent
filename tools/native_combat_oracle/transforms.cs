using System.Reflection;
using System.Text.Json;

internal static class TransformOracle
{
    public static void Run(Assembly assembly, string digest, object player)
    {
        const BindingFlags flags = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.Static;
        Type T(string name) => assembly.GetType("MegaCrit.Sts2.Core." + name, true)!;
        object Prop(object o, string n) => o.GetType().GetProperty(n, flags)!.GetValue(o)!;
        object Call(object o, string n, params object?[] a) => o.GetType().GetMethods(flags).Single(m => m.Name == n && !m.IsGenericMethodDefinition && m.GetParameters().Length == a.Length && m.GetParameters().Select((p, i) => a[i] is null || p.ParameterType.IsInstanceOfType(a[i])).All(x => x)).Invoke(o, a)!;
        object[] Items(object o) => ((System.Collections.IEnumerable)o).Cast<object>().ToArray();
        string Id(object o) => Prop(Prop(o, "Id"), "Entry").ToString()!.ToLowerInvariant();
        object Get(string method, string suffix) => T("Models.ModelDb").GetMethods().Single(m => m.Name == method && m.IsGenericMethodDefinition).MakeGenericMethod(T("Models." + suffix)).Invoke(null, null)!;
        var unlock = Prop(player, "UnlockState");
        var single = Prop(Prop(player, "RunState"), "CardMultiplayerConstraint");
        var pools = new Dictionary<string, object[]>();
        foreach (var family in new[] { "Ironclad", "Colorless", "Curse", "Status", "Silent", "Regent", "Necrobinder", "Defect" })
            pools[family] = Items(Call(Get("CardPool", "CardPools." + family + "CardPool"), "GetUnlockedCards", unlock, single));
        var census = pools.Select(p => new { family = p.Key.ToLowerInvariant(), cards = p.Value.Select(c => new {
            id = Id(c), type = c.GetType().Name, kind = Prop(c, "Type").ToString(), rarity = Prop(c, "Rarity").ToString(),
            canGenerate = Prop(c, "CanBeGeneratedInCombat"), cost = Prop(Prop(c, "EnergyCost"), "Canonical"),
            maxUpgrade = Prop(c, "MaxUpgradeLevel"), keywords = Items(Prop(c, "CanonicalKeywords")).Select(k => k.ToString()).ToArray()
        }).ToArray() }).ToArray();
        var factory = T("Factories.CardFactory");
        var create = factory.GetMethods().Single(m => m.Name == "CreateRandomCardForTransform" && m.GetParameters().Length == 3);
        var cases = new List<object>();
        var originals = pools.Where(p => p.Key is "Ironclad" or "Colorless" or "Curse" or "Status").SelectMany(p => p.Value)
            .Concat(new[] { Get("Card", "Cards.Peck"), Get("Card", "Cards.ToricToughness"), Get("Card", "Cards.SpoilsMap"), Get("Card", "Cards.ByrdSwoop"), Get("Card", "Cards.ByrdonisEgg"), Get("Card", "Cards.GiantRock") });
        foreach (var canonical in originals)
        {
            var original = Call(canonical, "ToMutable");
            original.GetType().GetProperty("Owner")!.SetValue(original, player);
            var options = Items(factory.GetMethod("GetDefaultTransformationOptions")!.Invoke(null, new[] { original, (object)true })!);
            var samples = new List<object>();
            foreach (uint seed in new uint[] { 0, 1, 2, 42, uint.MaxValue })
            {
                var rng = Activator.CreateInstance(T("Random.Rng"), new object[] { seed, 0 })!;
                var selected = new List<string>();
                for (int i = 0; i < 3; i++) selected.Add(Id(create.Invoke(null, new[] { original, (object)true, rng })!));
                samples.Add(new { seed, selected, counter = Prop(rng, "Counter"), suffix = Call(rng, "NextDouble") });
            }
            cases.Add(new { original = Id(original), options = options.Select(Id).ToArray(), samples });
        }
        Console.Write(JsonSerializer.Serialize(new {
            source = "Actual pinned combat transformation options and replacement factory; explicit solo all-unlocked player, no CardCmd.Transform, UI, foreign card execution or saves",
            assemblySha256 = digest, census, cases
        }, new JsonSerializerOptions { WriteIndented = true }));
    }
}

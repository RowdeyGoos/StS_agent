using Godot;
using System.Reflection;
using System.Runtime.Loader;
using System.Security.Cryptography;

public partial class Oracle : Node
{
    public override async void _Ready()
    {
        try
        {
            var path = Path.Combine(AppContext.BaseDirectory, "sts2.dll");
            var digest = Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))).ToLowerInvariant();
            if (digest != "e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18")
                throw new InvalidOperationException("Unexpected native assembly.");
            // Component hosting initializes GodotSharp in this context. Loading sts2 in
            // Default would create another GodotSharp with uninitialized native callbacks.
            var context = AssemblyLoadContext.GetLoadContext(typeof(Oracle).Assembly)!;
            var assembly = context.LoadFromAssemblyPath(path);
            var godot = context.LoadFromAssemblyName(assembly.GetReferencedAssemblies().Single(a => a.Name == "GodotSharp"));
            if (!ReferenceEquals(godot, typeof(Node).Assembly))
                throw new InvalidOperationException("Native game resolved a different GodotSharp instance.");
            var result = OS.GetCmdlineUserArgs().Contains("draw-cards")
                ? await DeathDrawOracle.Run(assembly, digest, attackMode: true, drawCards: true)
                : OS.GetCmdlineUserArgs().Contains("autoplay-flak")
                ? await DeathDrawOracle.Run(assembly, digest, attackMode: true, autoplay: true, flak: true)
                : OS.GetCmdlineUserArgs().Contains("autoplay")
                ? await DeathDrawOracle.Run(assembly, digest, attackMode: true, autoplay: true)
                : OS.GetCmdlineUserArgs().Contains("enemy-turn")
                ? await DeathDrawOracle.Run(assembly, digest, attackMode: true, enemyTurn: true)
                : OS.GetCmdlineUserArgs().Contains("multiple-deaths")
                ? await DeathDrawOracle.Run(assembly, digest, attackMode: true, multipleDeaths: true)
                : OS.GetCmdlineUserArgs().Contains("attack-hooks")
                ? await DeathDrawOracle.Run(assembly, digest, attackMode: true)
                : OS.GetCmdlineUserArgs().Contains("death-draw")
                ? await DeathDrawOracle.Run(assembly, digest)
                : await PausedHookOracle.Run(assembly, digest);
            File.WriteAllText("queue-result.json", result + "\n");
            GetTree().Quit(0);
        }
        catch (Exception error)
        {
            Console.Error.WriteLine(error);
            GetTree().Quit(1);
        }
    }
}

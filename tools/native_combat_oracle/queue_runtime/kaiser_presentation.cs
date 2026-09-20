using Godot;
using System.Reflection;
using Expression = System.Linq.Expressions.Expression;

// UI-only support. Real native background methods use a real Spine skeleton
// containing empty animations. No monster, command or power method is replaced.
internal sealed class KaiserPresentation : IDisposable
{
    const BindingFlags Flags=BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance|BindingFlags.Static;
    readonly Assembly assembly;
    readonly object manager;
    readonly List<(object,EventInfo,Delegate)> listeners=new();
    readonly List<Node> nodes=new();
    readonly List<GodotObject> resources=new();
    object? background;
    public int ArmsAttached {get;private set;}
    public int ArmDeaths {get;private set;}
    public bool ListenersRemoved=>listeners.Count==0;
    public bool IsClear=>nodes.Count==0 && T("Nodes.NGame").GetProperty("Instance",Flags)!.GetValue(null) is null;
    public int NexusDeaths {get;private set;}
    readonly List<object> nexusCreatures=new();
    Type T(string n)=>assembly.GetType("MegaCrit.Sts2.Core."+n,true)!;
    object P(object o,string n)=>o.GetType().GetProperty(n,Flags)!.GetValue(o)!;
    void F(object o,string n,object? v)=>o.GetType().GetField(n,Flags)!.SetValue(o,v);
    Node NewNode(string n){var node=(Node)Activator.CreateInstance(T(n))!;nodes.Add(node);return node;}
    public KaiserPresentation(Assembly asm)
    {
        assembly=asm;
        if(GDExtensionManager.LoadExtension("res://fixture_spine.gdextension")!=GDExtensionManager.LoadStatus.Ok)
            throw new InvalidOperationException("Pinned Spine extension failed to load.");
        manager=T("Combat.CombatManager").GetProperty("Instance")!.GetValue(null)!;
        Listen(manager,"CombatSetUp",Attach);
        Listen(manager,"CombatEnded",_=>Clear());
    }
    void Listen(object owner,string name,Action<object> action)
    {
        var evt=owner.GetType().GetEvent(name)!;
        var arg=Expression.Parameter(evt.EventHandlerType!.GetMethod("Invoke")!.GetParameters()[0].ParameterType);
        var callback=Expression.Lambda(evt.EventHandlerType,Expression.Invoke(Expression.Constant(action),Expression.Convert(arg,typeof(object))),arg).Compile();
        evt.AddEventHandler(owner,callback);listeners.Add((owner,evt,callback));
    }
    void Attach(object combat)
    {
        var monsters=((System.Collections.IEnumerable)P(combat,"Enemies")).Cast<object>().Select(c=>P(c,"Monster")).ToArray();
        foreach(var nexus in monsters.Where(m=>m.GetType().Name=="SoulNexus"))
        {
            var creature=P(nexus,"Creature");nexusCreatures.Add(creature);
            Listen(creature,"Died",_=>{
                if(!IsClear)throw new InvalidOperationException("Nexus presentation already owned.");
                var game=NewNode("Nodes.NGame");var scene=NewNode("Nodes.NSceneContainer");
                var run=NewNode("Nodes.NRun");var rooms=NewNode("Nodes.NSceneContainer");
                var room=NewNode("Nodes.Rooms.NCombatRoom");
                T("Nodes.NGame").GetProperty("RootSceneContainer",Flags)!.SetValue(game,scene);
                T("Nodes.NSceneContainer").GetProperty("CurrentScene",Flags)!.SetValue(scene,run);
                F(run,"_roomContainer",rooms);
                T("Nodes.NSceneContainer").GetProperty("CurrentScene",Flags)!.SetValue(rooms,room);
                T("Nodes.NGame").GetProperty("Instance",Flags)!.SetValue(null,game);
                NexusDeaths++;
            });
        }
        var arms=monsters.Where(m=>m.GetType().Name is "Crusher" or "Rocket").ToArray();
        if(arms.Length==0)return;
        if(arms.Length!=2 || background is not null)throw new InvalidOperationException("Unexpected Kaiser presentation ownership.");
        var instance=T("Nodes.NGame").GetProperty("Instance",Flags)!;
        if(instance.GetValue(null) is not null)throw new InvalidOperationException("Fixture cannot replace an existing game UI.");
        var game=NewNode("Nodes.NGame");
        var audio=NewNode("Nodes.Audio.NAudioManager");
        var scene=NewNode("Nodes.NSceneContainer");
        T("Nodes.NGame").GetProperty("RootSceneContainer",Flags)!.SetValue(game,scene);
        var shake=NewNode("Nodes.Vfx.Utilities.NScreenShake");
        var target=new Control();nodes.Add(target);
        shake.GetType().GetMethod("_Ready")!.Invoke(shake,null);
        shake.GetType().GetMethod("SetTarget")!.Invoke(shake,new[]{target});
        T("Nodes.NGame").GetProperty("AudioManager",Flags)!.SetValue(game,audio);
        F(game,"_screenShake",shake);
        instance.SetValue(null,game);
        // Nodes remain off-tree: neither NGame._EnterTree nor _Ready runs.
        // Screen shake uses only presentation Rng.Chaotic, excluded from parity.
        var atlas=ClassDB.Instantiate("SpineAtlasResource").AsGodotObject();resources.Add(atlas);
        atlas.Call("load_from_atlas_file","res://kaiser_empty.atlas");
        var file=ClassDB.Instantiate("SpineSkeletonFileResource").AsGodotObject();resources.Add(file);
        if(file.Call("load_from_file","res://kaiser_skeleton.spjson").AsInt32()!=(int)Error.Ok)throw new InvalidOperationException("Authored skeleton file rejected.");
        var data=ClassDB.Instantiate("SpineSkeletonDataResource").AsGodotObject();resources.Add(data);
        data.Call("set_atlas_res",atlas);data.Call("set_skeleton_file_res",file);
        if(!data.Call("is_skeleton_data_loaded").AsBool())throw new InvalidOperationException("Authored Kaiser skeleton failed to load.");
        var sprite=(Node2D)ClassDB.Instantiate("SpineSprite").AsGodotObject();nodes.Add(sprite);
        sprite.Call("set_skeleton_data_res",data);
        var mega=Activator.CreateInstance(T("Bindings.MegaSpine.MegaSprite"),new object[]{Variant.From(sprite)})!;
        background=NewNode("Nodes.Vfx.Backgrounds.NKaiserCrabBossBackground");
        F(background,"_animController",mega);
        var deaths=new HashSet<object>();
        foreach(var arm in arms)
        {
            F(arm,"_background",background);ArmsAttached++;
            Listen(P(arm,"Creature"),"Died",creature=>{
                if(!deaths.Add(creature))throw new InvalidOperationException("Repeated Kaiser death.");
                ArmDeaths++;
                // Both native BeforeDeath/audio callbacks have completed. Remove
                // the temporary game UI before progress/epoch reward notifications.
                if(deaths.Count==2)instance.SetValue(null,null);
            });
        }
    }
    public void AfterCombatStarted()
    {
        // Native AfterAddedToRoom has subscribed SoulNexus.AfterDeath between our
        // setup and teardown callbacks. The actual synchronous callback runs.
        foreach(var creature in nexusCreatures)Listen(creature,"Died",_=>Clear());
        nexusCreatures.Clear();
    }
    void Clear()
    {
        if(background is null && nodes.Count==0)return;
        T("Nodes.NGame").GetProperty("Instance",Flags)!.SetValue(null,null);
        foreach(var node in nodes.AsEnumerable().Reverse())node.Free();nodes.Clear();
        foreach(var resource in resources.AsEnumerable().Reverse())resource.Dispose();resources.Clear();
        background=null;
    }
    public void Dispose()
    {
        foreach(var (owner,evt,callback) in listeners)evt.RemoveEventHandler(owner,callback);
        listeners.Clear();Clear();
    }
}

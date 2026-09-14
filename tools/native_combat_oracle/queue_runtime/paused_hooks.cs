using System.Reflection;
using System.Runtime.CompilerServices;
using System.Text.Json;

// Native queue/context semantics only. No UI, card draw, Horn, or run execution.
internal static class PausedHookOracle
{
    public static async Task<string> Run(Assembly assembly, string digest)
    {
        return await Probe(assembly, digest).WaitAsync(TimeSpan.FromSeconds(5));
    }

    private static async Task<string> Probe(Assembly assembly, string digest)
    {
        const BindingFlags flags = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.Static;
        Type T(string name) => assembly.GetType("MegaCrit.Sts2.Core." + name, true)!;
        object? Property(object instance, string name) => instance.GetType().GetProperty(name, flags)!.GetValue(instance);
        object? Call(object instance, string name, params object?[] args) => instance.GetType().GetMethods(flags).Single(m =>
            m.Name == name && !m.IsGenericMethodDefinition && m.GetParameters().Length == args.Length &&
            m.GetParameters().Select((p, i) => args[i] is null || p.ParameterType.IsInstanceOfType(args[i])).All(v => v)
        ).Invoke(instance, args);
        void Field(object instance, string name, object? value) => instance.GetType().GetField(name, flags)!.SetValue(instance, value);
        void Require(bool condition, string message) { if (!condition) throw new InvalidOperationException(message); }
        string State(object action) => Property(action, "State")!.ToString()!;
        async Task Until(Func<bool> condition) { while (!condition()) await Task.Yield(); }

        T("TestSupport.TestMode").GetProperty("IsOn")!.SetValue(null, true);
        var player = RuntimeHelpers.GetUninitializedObject(T("Entities.Players.Player"));
        var players = Array.CreateInstance(player.GetType(), 1);
        players.SetValue(player, 0);
        var queue = Activator.CreateInstance(T("GameActions.Multiplayer.ActionQueueSet"), new object[] { players })!;
        Call(queue, "CombatStarted");
        var sync = RuntimeHelpers.GetUninitializedObject(T("GameActions.Multiplayer.ActionQueueSynchronizer"));
        Field(sync, "_actionQueueSet", queue);
        Field(sync, "_logger", queue.GetType().GetField("_logger", flags)!.GetValue(queue));
        foreach (var name in new[] { "_hookActions", "_requestedActionsWaitingForPlayerTurn" })
        {
            var field = sync.GetType().GetField(name, flags)!;
            field.SetValue(sync, Activator.CreateInstance(field.FieldType));
        }
        var net = DispatchProxy.Create(T("Multiplayer.Game.INetGameService"), typeof(PausedHookNetProxy));
        ((PausedHookNetProxy)net).Singleplayer = Enum.Parse(T("Multiplayer.Game.NetGameType"), "Singleplayer");
        Field(sync, "_netService", net);
        // Only the action ownership field is used; the actual executor loop is outside this probe.
        var executor = RuntimeHelpers.GetUninitializedObject(T("GameActions.ActionExecutor"));
        var actionType = Enum.Parse(T("Entities.Multiplayer.GameActionType"), "Combat");
        var choiceOptions = Enum.ToObject(T("Entities.Multiplayer.PlayerChoiceOptions"), 0);
        var log = new List<string>();

        async Task<(object context, object action, Task work, TaskCompletionSource[] answers)> Begin(string name, int count)
        {
            var context = Activator.CreateInstance(T("GameActions.Multiplayer.HookPlayerChoiceContext"), new[] { player, (object)0UL, actionType })!;
            Call(context, "MockDependenciesForTest", sync, queue, executor);
            var answers = Enumerable.Range(0, count).Select(_ => new TaskCompletionSource()).ToArray();
            async Task Work()
            {
                for (int i = 0; i < count; i++)
                {
                    log.Add($"{name}:request:{i}");
                    await (Task)Call(context, "SignalPlayerChoiceBegun", choiceOptions)!;
                    log.Add($"{name}:visible:{i}");
                    await answers[i].Task;
                    await (Task)Call(context, "SignalPlayerChoiceEnded")!;
                    log.Add($"{name}:resumed:{i}");
                }
                log.Add($"{name}:finished");
            }
            var work = Work();
            var completed = await (Task<bool>)Call(context, "AssignTaskAndWaitForPauseOrCompletion", work)!;
            Require(!completed, "Synthetic choice should detach before its hook action starts.");
            return (context, Property(context, "GameAction")!, work, answers);
        }
        async Task Drive(object action)
        {
            Require(ReferenceEquals(Call(queue, "GetReadyAction"), action), "Expected FIFO ready action.");
            Field(executor, "<CurrentlyRunningAction>k__BackingField", action);
            await (Task)Call(action, "Execute")!;
        }

        var a = await Begin("A", 2);
        var b = await Begin("B", 1);
        log.Add("outer:continued");
        Require(!log.Any(x => x.Contains(":visible:")), "Choice became visible before its detached action started.");
        await Drive(a.action);
        await Until(() => log.Contains("A:visible:0"));
        Require(Call(queue, "GetReadyAction") is null, "A's selector must block B in the same owner's queue.");
        a.answers[0].SetResult();
        await Until(() => State(a.action) == "ReadyToResumeExecuting");
        await Drive(a.action);
        await Until(() => log.Contains("A:visible:1"));
        Require(ReferenceEquals(Property(a.context, "GameAction"), a.action), "Second choice must reuse its hook action.");
        Require(Call(queue, "GetReadyAction") is null, "Second A choice must still block B.");
        a.answers[1].SetResult();
        await Until(() => State(a.action) == "ReadyToResumeExecuting");
        await Drive(a.action);
        await a.work;
        await Drive(b.action);
        await Until(() => log.Contains("B:visible:0"));
        b.answers[0].SetResult();
        await Until(() => State(b.action) == "ReadyToResumeExecuting");
        await Drive(b.action);
        await b.work;
        Require(Call(queue, "GetReadyAction") is null && (bool)Property(queue, "IsEmpty")!, "Finished hooks must leave an empty queue.");

        var c = await Begin("C", 1);
        var d = await Begin("D", 1);
        Call(queue, "CombatEnded");
        Require(State(c.action) == "Canceled" && State(d.action) == "Canceled", "Combat end must cancel queued hooks.");
        Require(!log.Contains("C:visible:0") && !log.Contains("D:visible:0"), "Canceled queued choices became visible.");
        Require(Call(queue, "GetReadyAction") is null && (bool)Property(queue, "IsEmpty")!, "Canceled hooks remained ready.");
        Call(queue, "CombatStarted");
        var e = await Begin("E", 1);
        var f = await Begin("F", 1);
        await Drive(e.action);
        await Until(() => log.Contains("E:visible:0"));
        Call(queue, "CombatEnded");
        Require(State(e.action) == "Canceled" && State(f.action) == "Canceled", "Combat end must cancel gathering and waiting hooks.");
        Require(Call(queue, "GetReadyAction") is null && (bool)Property(queue, "IsEmpty")!, "Gathering cancellation left a ready hook.");

        return JsonSerializer.Serialize(new
        {
            source = "Actual pinned HookPlayerChoiceContext, GenericHookGameAction and ActionQueueSet; synthetic choice tasks, manual action driving, singleplayer-only proxy; no UI, Horn, card draw, ActionExecutor loop, RunManager or saves",
            assemblySha256 = digest,
            trace = log,
            fifo = true,
            activeChoiceBlocksLaterHooks = true,
            repeatedChoiceReusesHookAction = true,
            queuedCancellation = new[] { State(c.action), State(d.action) },
            gatheringCancellation = new[] { State(e.action), State(f.action) },
            canceledTasksRemainSuspended = new[] { !c.work.IsCompleted, !d.work.IsCompleted, !e.work.IsCompleted, !f.work.IsCompleted },
        }, new JsonSerializerOptions { WriteIndented = true });
    }
}

public class PausedHookNetProxy : DispatchProxy
{
    public object? Singleplayer;
    protected override object? Invoke(MethodInfo? method, object?[]? args) => method!.Name switch
    {
        "get_Type" => Singleplayer,
        "get_NetId" => 0UL,
        _ => throw new InvalidOperationException("Unexpected native network access: " + method.Name),
    };
}

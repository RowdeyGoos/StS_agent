using System;
using System.Linq;
using System.Text.Json;
using Sts2AgentBridge.Successors.GenericEventV1;

// Full production native-hook/card-adapter/parent/wire composition against inert
// target stubs. Python drives every native control; no fixture Finish shortcut.
internal static class GenericEventV1NativeIntegrationHost
{
    private static int Main(string[] args)
    {
        if (args.Length != 1 || !new[] { "FIRST_EVENT", "ANOTHER_EVENT", "HELD_OUT_EVENT", "DELAYED" }.Contains(args[0])) return 2;
        using var fixture = new Program.Fixture(args[0], delayed: args[0] == "DELAYED");
        using var wire = new GenericEventV1WireService(new string('a', 32), fixture.Session);
        bool released = false;
        for (int count = 0; count < 2200; count++)
        {
            string? line = ReadLineBounded();
            if (line is null) return 0;
            using var document = JsonDocument.Parse(line);
            var request = document.RootElement;
            if (!request.EnumerateObject().Select(p => p.Name).SequenceEqual(new[] { "method", "route", "body" })) return 3;
            byte[]? body = request.GetProperty("body").ValueKind == JsonValueKind.Null ? null :
                Convert.FromBase64String(request.GetProperty("body").GetString()!);
            byte[] response = wire.Handle(request.GetProperty("method").GetString(), request.GetProperty("route").GetString(), body);
            Console.WriteLine(JsonSerializer.Serialize(new {
                body = Convert.ToBase64String(response), event_type = fixture.Model.GetType().Name,
                upgraded_cards = fixture.Cards.Count(c => c.CurrentUpgradeLevel == 1),
                map_open = fixture.Map.IsOpen, overlay_count = fixture.Overlays.ScreenCount,
                chosen_calls = fixture.OptionCalls, select_calls = fixture.SelectCalls,
                confirm_calls = fixture.ConfirmCalls,
            }));
            using var reply = JsonDocument.Parse(response);
            if (args[0] == "DELAYED" && !released &&
                reply.RootElement.GetProperty("parent").ValueKind == JsonValueKind.Object &&
                reply.RootElement.GetProperty("parent").GetProperty("status").GetString() == "waiting")
            { released = true; fixture.Gate.SetResult(); }
            if (body is not null) Array.Clear(body);
            Array.Clear(response);
        }
        return 4;
    }
    private static string? ReadLineBounded()
    {
        var buffer = new char[8192]; int count = 0;
        while (true)
        {
            int c = Console.Read();
            if (c < 0) return count == 0 ? null : throw new InvalidOperationException("Truncated request.");
            if (c == '\n') return new string(buffer, 0, count);
            if (count == buffer.Length) throw new InvalidOperationException("Oversized request.");
            buffer[count++] = (char)c;
        }
    }
}

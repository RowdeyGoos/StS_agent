using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using Sts2AgentBridge.Successors.RoomFlowsV1;

namespace Sts2AgentBridge.Rooms.Rest;

public sealed record RestV2Option(string ActionId, int Counter, bool Enabled, int Amount = 0);
public sealed record RestV2Card(int Slot, string Key, int Upgrade, bool Removable);
public sealed record RestV2NativeOption(RestV2Option Public, object Option, object Relic, object Button, object? Witness = null);
public sealed record RestV2Surface(object Run, object Player, object Room, object Map,
    bool Foreground, IReadOnlyList<RestV2NativeOption> Options)
{
    public IReadOnlyList<RestV2Card> Cards { get; init; } = Array.Empty<RestV2Card>();
}
public readonly record struct RestV2Progress(bool Succeeded, bool Failed, int Counter);
public interface IRestV2NativeAdapter : IDisposable
{
    RestV2Surface Capture();
    void Begin(RestV2NativeOption option, string action);
    RestV2Progress Poll();
    void Finish();
}
public sealed record RestV2Result(string DecisionId, string ActionId, int Before, int After);
public sealed record RestV2Observation(string SessionNonce, string Status, string Phase,
    string DecisionId, IReadOnlyList<RestV2Option> Options, IReadOnlyList<string> LegalActions,
    RestV2Result? Result) : IRoomFlowReadValue
{
    public IReadOnlyList<RestV2Card> Cards { get; init; } = Array.Empty<RestV2Card>();
}

// One native option, through its exact asynchronous effect and rest continuation.
// Completion hands the rest site back to the shared router; it does not choose
// Proceed or consume another option when Miniature Tent leaves choices available.
public sealed class RestV2Session : IRoomFlowSession
{
    private readonly string _nonce;
    private readonly IRestV2NativeAdapter _native;
    private readonly int _owner = Environment.CurrentManagedThreadId;
    private RestV2Surface? _bound, _published;
    private RestV2Observation? _ready, _complete;
    private RestV2NativeOption? _selected;
    private string? _acceptedDecision;
    private string? _acceptedAction;
    private int _reads;
    private bool _failed, _disposed, _inside;
    public string FlowKind => "rest";

    public RestV2Session(string nonce, IRestV2NativeAdapter native)
    {
        if (!RoomFlowIdentity.IsNonce(nonce)) throw new ArgumentException("Invalid nonce.");
        _nonce = nonce; _native = native;
    }
    public static string Kind(string action) => action.StartsWith("cook:", StringComparison.Ordinal) ? "cook" : action;
    public static int Delta(string action, int amount = 0) => Kind(action) switch {
        "lift" or "dig" or "hatch" => 1, "kindle" => 5, "cook" => 9, "clone" => amount,
        _ => throw new ArgumentException("Unknown rest option.") };
    public static bool ValidCounter(string action, int value) => action switch {
        "lift" => value is >= 0 and < 3,
        "kindle" => value >= 0 && value <= int.MaxValue - 5,
        "dig" or "hatch" => value is >= 0 and < 128,
        "clone" => value is >= 0 and <= 64,
        "cook" => value > 0 && value <= int.MaxValue - 9,
        _ => false };

    public IRoomFlowReadValue Read()
    {
        if (!Enter()) return Fixed("unsupported");
        try
        {
            if (_complete is not null) return _complete;
            RestV2Surface surface = Capture();
            if (_selected is not null)
            {
                Require(++_reads <= RoomFlowLimits.MaximumPendingReads);
                RestV2Progress progress = _native.Poll();
                Require(!progress.Failed);
                if (!progress.Succeeded) return Fixed("waiting");
                surface = Capture(); // Selector confirmation may complete during Poll.
                Require(surface.Foreground && progress.Counter == checked(_selected.Public.Counter + Delta(_selected.Public.ActionId, _selected.Public.Amount)));
                _native.Finish(); // Cleanup must succeed before publishing completion.
                Require(!_failed);
                _complete = new(_nonce, "complete", "complete", "", Array.Empty<RestV2Option>(),
                    Array.Empty<string>(), new(_acceptedDecision!, _acceptedAction!,
                        _selected.Public.Counter, progress.Counter));
                return _complete;
            }
            if (!surface.Foreground) { _published = null; _ready = null; return Fixed("waiting"); }
            var options = surface.Options.Select(x => x.Public).ToArray();
            var legal = Actions(options, surface.Cards).ToArray();
            Require(legal.Length > 0);
            _published = surface;
            _ready = new(_nonce, "ready", "choose_option", Digest(_nonce, options, surface.Cards), options, legal, null) { Cards = surface.Cards };
            return _ready;
        }
        catch { _failed = true; return Fixed("unsupported"); }
        finally { _inside = false; }
    }

    public IRoomFlowApplyValue Apply(string? decisionId, string? actionId)
    {
        if (!Enter()) return new RoomFlowApplyFailure("rest", _nonce, "rejected");
        bool dispatched = false;
        try
        {
            Require(_selected is null && _complete is null && _ready is not null && _published is not null &&
                decisionId == _ready.DecisionId && _ready.LegalActions.Contains(actionId!));
            RestV2Surface fresh = Capture();
            Require(fresh.Foreground && SameOptions(_published!, fresh) &&
                Digest(_nonce, fresh.Options.Select(x => x.Public).ToArray(), fresh.Cards) == decisionId);
            _selected = fresh.Options.Single(x => x.Public.ActionId == Kind(actionId!));
            _acceptedDecision = decisionId;
            _acceptedAction = actionId;
            _ready = null; _published = null;
            dispatched = true; // Reserve before calling any native code; never retry.
            _native.Begin(_selected, actionId!);
            Require(!_failed);
            return new RoomFlowDispatchReceipt("rest", _nonce, decisionId!, actionId!);
        }
        catch { _failed = true; return new RoomFlowApplyFailure("rest", _nonce, dispatched ? "uncertain" : "rejected"); }
        finally { _inside = false; }
    }

    private RestV2Surface Capture()
    {
        RestV2Surface s = _native.Capture();
        Require(s.Run is not null && s.Player is not null && s.Room is not null && s.Map is not null && s.Options.Count <= 6);
        Require(s.Cards.Count <= 64 && s.Cards.Select(c => c.Slot).SequenceEqual(Enumerable.Range(0, s.Cards.Count)) &&
            s.Cards.All(c => RoomFlowIdentity.IsStableKey(c.Key) && c.Upgrade >= 0));
        if (_bound is null) _bound = s;
        Require(ReferenceEquals(s.Run, _bound.Run) && ReferenceEquals(s.Player, _bound.Player) &&
            ReferenceEquals(s.Room, _bound.Room) && ReferenceEquals(s.Map, _bound.Map));
        var seen = new HashSet<string>(StringComparer.Ordinal);
        foreach (var option in s.Options)
            Require(option.Option is not null && option.Relic is not null && option.Button is not null &&
                seen.Add(option.Public.ActionId) && ValidCounter(option.Public.ActionId, option.Public.Counter) &&
                option.Public.Amount is >= 0 and <= 64 && (option.Public.ActionId == "clone" || option.Public.Amount == 0));
        Require(!_failed);
        return s;
    }
    private static bool SameOptions(RestV2Surface before, RestV2Surface after) =>
        before.Cards.SequenceEqual(after.Cards) && before.Options.Count == after.Options.Count && before.Options.Zip(after.Options).All(pair =>
            pair.First.Public == pair.Second.Public && ReferenceEquals(pair.First.Option, pair.Second.Option) &&
            ReferenceEquals(pair.First.Relic, pair.Second.Relic) && ReferenceEquals(pair.First.Button, pair.Second.Button) && Equals(pair.First.Witness, pair.Second.Witness));
    private bool Enter()
    {
        if (_failed || _disposed || _inside || Environment.CurrentManagedThreadId != _owner) { _failed = true; return false; }
        _inside = true; return true;
    }
    private RestV2Observation Fixed(string status) => new(_nonce, status,
        status == "waiting" && _selected is not null ? "action_waiting" : "unknown", "",
        Array.Empty<RestV2Option>(), Array.Empty<string>(), null);
    private static void Require(bool value) { if (!value) throw new InvalidOperationException("rest_boundary"); }
    public static IEnumerable<string> Actions(IReadOnlyList<RestV2Option> options, IReadOnlyList<RestV2Card> cards)
    {
        foreach (var option in options.Where(o => o.Enabled))
        {
            if (option.ActionId != "cook") { yield return option.ActionId; continue; }
            var eligible = cards.Where(c => c.Removable).ToArray();
            for (int i = 0; i < eligible.Length; i++)
                for (int j = i + 1; j < eligible.Length; j++)
                    yield return "cook:" + eligible[i].Slot.ToString(CultureInfo.InvariantCulture) + ":" + eligible[j].Slot.ToString(CultureInfo.InvariantCulture);
        }
    }
    public static string Digest(string nonce, IReadOnlyList<RestV2Option> options, IReadOnlyList<RestV2Card>? cards = null)
    {
        var text = new StringBuilder("rest_v2;").Append(nonce).Append(';');
        foreach (var option in options)
            text.Append(option.ActionId).Append(';').Append(option.Counter.ToString(CultureInfo.InvariantCulture))
                .Append(';').Append(option.Enabled ? '1' : '0').Append(';').Append(option.Amount.ToString(CultureInfo.InvariantCulture)).Append(';');
        text.Append('|');
        foreach (var card in cards ?? Array.Empty<RestV2Card>())
            text.Append(card.Slot.ToString(CultureInfo.InvariantCulture)).Append(';').Append(card.Key).Append(';')
                .Append(card.Upgrade.ToString(CultureInfo.InvariantCulture)).Append(';').Append(card.Removable ? '1' : '0').Append(';');
        return Convert.ToHexString(SHA256.HashData(Encoding.ASCII.GetBytes(text.ToString()))).ToLowerInvariant();
    }
    public void Dispose()
    {
        Require(Environment.CurrentManagedThreadId == _owner && !_inside);
        _failed = true;
        if (_disposed) return;
        _native.Dispose(); // A failed cleanup remains retryable during owned host disposal.
        _disposed = true;
    }
}

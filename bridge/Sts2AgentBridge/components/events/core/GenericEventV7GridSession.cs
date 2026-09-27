using System;
using System.Collections.Generic;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using Sts2AgentBridge.Successors.CardSelectionV1;

namespace Sts2AgentBridge.Successors.GenericEventV7;

// Slots identify the complete public model domain, independently of recycled UI
// holders. The native owner alone certifies preview and selected-only effects.
public sealed record GenericEventV7GridCard(string Key, int UpgradeLevel);
public sealed record GenericEventV7GridCapture(string Status, IReadOnlyList<GenericEventV7GridCard> Cards, int? SelectedSlot);
public interface IGenericEventV7GridNative : IDisposable
{
    GenericEventV7GridCapture Read();
    void Apply(string operation, int? slot);
}

public sealed class GenericEventV7GridSession : IGenericEventV7CardChildSession
{
    private readonly IGenericEventV7GridNative _native;
    private readonly string _nonce, _operation, _origin;
    private readonly int _count, _thread = Environment.CurrentManagedThreadId;
    private readonly CardSelectionV1Enchantment? _enchantment;
    private readonly List<CardSelectionV1ActionResult> _history = new();
    private GenericEventV7GridCard[]? _domain;
    private CardSelectionV1ResolvedResult? _resolved;
    private string? _pending, _pendingDecision;
    private int? _selected;
    private int _reads, _pendingReads, _attempts;
    private bool _inside, _failed, _disposed;
    public string ContractVersion => "card_grid_v1";

    public GenericEventV7GridSession(string nonce, string parentDecision, string parentAction, string operation, int count,
        CardSelectionV1Enchantment? enchantment, IGenericEventV7GridNative native)
    {
        if (!GenericEventV7GridAdmission.Supports(operation, count) ||
            nonce.Length != 32 || nonce.Any(c => !(c is >= '0' and <= '9' or >= 'a' and <= 'f')) ||
            parentDecision.Length != 64 || parentDecision.Any(c => !(c is >= '0' and <= '9' or >= 'a' and <= 'f')) ||
            parentAction.Length != 8 || !parentAction.StartsWith("choose:", StringComparison.Ordinal) || parentAction[7] is < '0' or > '7' ||
            (operation == "enchant" ? enchantment is not { Amount: > 0 } : enchantment is not null))
            throw new ArgumentException("Grid contract boundary.");
        _nonce = nonce; _origin = parentDecision + ":" + parentAction; _operation = operation; _count = count; _enchantment = enchantment;
        _native = native ?? throw new ArgumentNullException(nameof(native));
    }
    private void Require(bool good) { if (!good) { _failed = true; throw new InvalidOperationException("event_grid_boundary"); } }
    private CardSelectionV1Observation Fixed(string status) => CardSelectionV1Observation.Fixed(_nonce, status, status, _history);
    public ICardSelectionV1ReadValue Read()
    {
        if (_inside || _disposed || _failed || Environment.CurrentManagedThreadId != _thread) { _failed = true; return Fixed("unsupported"); }
        _inside = true;
        try { return ReadCore(); } catch { _failed = true; return Fixed("unsupported"); } finally { _inside = false; }
    }
    private ICardSelectionV1ReadValue ReadCore()
    {
        Require(++_reads <= 1024);
        if (_resolved is not null) return _resolved;
        var view = _native.Read();
        Require(view.Status is "ready" or "waiting" or "resolved");
        Require(view.Cards.Count == _count && view.Cards.All(c => c.Key.Length is > 0 and <= 128 &&
            c.Key.All(x => x is >= 'a' and <= 'z' or >= 'A' and <= 'Z' or >= '0' and <= '9' or '_') && c.UpgradeLevel >= 0));
        _domain ??= view.Cards.ToArray();
        Require(view.Cards.SequenceEqual(_domain));
        if (_pending is not null) Require(++_pendingReads <= 256);
        if (view.Status == "waiting") return Fixed("waiting");
        if (_pending is not null)
        {
            Require(view.SelectedSlot == _selected);
            Require(_pending == "confirm" ? view.Status == "resolved" : view.Status == "ready");
            _history.Add(new(_pendingDecision!, _pending, _pending == "confirm" ? "committed" : "selected"));
            _pending = null; _pendingDecision = null;
        }
        Require(view.SelectedSlot == _selected);
        CardSelectionV1Candidate Candidate(int slot) => new(slot, _domain[slot].Key, _domain[slot].UpgradeLevel,
            true, true, slot == _selected); // visible means public domain member in card_grid_v1.
        if (view.Status == "resolved")
        {
            Require(_selected is not null && _history.Count == 2 && _history[^1].ActionId == "confirm");
            return _resolved = new(_nonce, _operation, new[] { Candidate(_selected!.Value) }, _history, _enchantment);
        }
        Require(_history.Count == (_selected is null ? 0 : 1));
        string decision = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(
            _nonce + ":card_grid_v1:" + _origin + ":" + _history.Count + ":" + _operation + ":" + _selected + ":" +
            _enchantment?.Key + ":" + _enchantment?.Amount + ":" + string.Join(";", _domain.Select(c => c.Key + ":" + c.UpgradeLevel))))).ToLowerInvariant();
        return new CardSelectionV1Observation(_nonce, "ready", _selected is null ? "selecting" : "preview", _operation,
            "preview_confirm", 1, 1, decision, Enumerable.Range(0, _count).Select(Candidate).ToArray(),
            _selected is null ? Array.Empty<int>() : new[] { _selected.Value },
            _selected is null ? Enumerable.Range(0, _count).Select(i => "select:" + i).ToArray() : new[] { "confirm" }, _history, _enchantment);
    }
    public ICardSelectionV1ApplyValue Apply(string? decision, string? action)
    {
        if (_inside || _disposed || _failed || Environment.CurrentManagedThreadId != _thread) { _failed = true; return new CardSelectionV1ApplyFailure(_nonce, "unsupported"); }
        _inside = true;
        try
        {
            var ready = ReadCore() as CardSelectionV1Observation;
            if (ready?.Status != "ready" || ready.DecisionId != decision || !ready.LegalActions.Contains(action ?? ""))
                return new CardSelectionV1ApplyFailure(_nonce, "rejected");
            Require(_pending is null && ++_attempts <= 2);
            _pending = action; _pendingDecision = decision; _pendingReads = 0;
            if (action != "confirm") _selected = int.Parse(action![7..]);
            _native.Apply(action == "confirm" ? "confirm" : "select", action == "confirm" ? null : _selected);
            return new CardSelectionV1DispatchReceipt(_nonce, decision!, action!);
        }
        catch { _failed = true; return new CardSelectionV1ApplyFailure(_nonce, "unsupported"); }
        finally { _inside = false; }
    }
    public void Dispose()
    {
        if (_disposed) return;
        Require(!_inside && Environment.CurrentManagedThreadId == _thread);
        _native.Dispose(); _disposed = true;
    }
}

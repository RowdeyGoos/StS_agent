using System;
using System.Collections.Generic;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace Sts2AgentBridge.Cards.Combat;

internal sealed record ChoiceCard(object Model, object Holder, string Key, int UpgradeLevel,
    bool Selected, bool Enabled);
internal sealed record ChoiceSurface(object Identity, string Pile, int MinSelect, int MaxSelect,
    bool ManualConfirmation, bool Ready, bool Closed, bool TaskSucceeded, bool TaskFailed,
    ChoiceCard[] Cards, object[] Result, bool ConfirmEnabled);
internal interface ICombatCardChoiceAdapter : IDisposable
{
    ChoiceSurface Capture();
    void Toggle(int slot);
    void Confirm();
}
internal readonly record struct ChoiceReply(byte[] Body, bool Terminal = false);

// A nested combat selection owns its native screen until the exact task result
// reconciles. It does not certify the calling card's later gameplay effects.
internal sealed class CombatCardChoiceService : IDisposable
{
    internal const string DecisionRoute = "/probe/combat-choice-v1/public/decision";
    internal const string ActionRoute = "/probe/combat-choice-v1/public/action";
    private readonly Func<ICombatCardChoiceAdapter?> _factory;
    private readonly string _nonce;
    private readonly int _thread = Environment.CurrentManagedThreadId;
    private readonly HashSet<object> _seen = new(ReferenceEqualityComparer.Instance);
    private ICombatCardChoiceAdapter? _adapter;
    private ChoiceSurface? _initial;
    private ChoiceCard[] _cards = Array.Empty<ChoiceCard>();
    private int[] _selected = Array.Empty<int>();
    private string? _decision, _choice, _pending;
    private int[]? _expected;
    private int _episodes, _reads, _pendingReads, _attempted, _accepted, _reconciled;
    private bool _done, _failed, _disposed;
    internal bool IsActive => _adapter is not null && !_done || _failed;

    internal CombatCardChoiceService(Func<ICombatCardChoiceAdapter?> factory, string nonce)
    { _factory = factory; _nonce = nonce; }
    internal static bool IsAction(string? decision, string? action) =>
        Hex(decision) && (action == "confirm" || Slot(action, out _, out _));
    private static bool Hex(string? value) => value is { Length: 64 } && value.All(c => c is >= '0' and <= '9' or >= 'a' and <= 'f');
    private static bool Slot(string? action, out int slot, out bool deselect)
    {
        slot = -1; deselect = action?.StartsWith("deselect:", StringComparison.Ordinal) == true;
        string prefix = deselect ? "deselect:" : "select:";
        return action?.StartsWith(prefix, StringComparison.Ordinal) == true &&
            int.TryParse(action[prefix.Length..], out slot) && slot is >= 0 and < 64 && action == prefix + slot;
    }
    private static string Hash(string text) => Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(text))).ToLowerInvariant();
    private void Require(bool value, string code) { if (!value) throw new InvalidOperationException(code); }

    internal ChoiceReply Read()
    {
        if (_failed || _disposed || Environment.CurrentManagedThreadId != _thread) return Fail("choice_stopped");
        try
        {
            if (_adapter is null || _done)
            {
                _adapter?.Dispose(); _adapter = null;
                _adapter = _factory();
                if (_adapter is null)
                {
                    _initial = null; _choice = _decision = null; _selected = Array.Empty<int>();
                    _attempted = _accepted = _reconciled = 0;
                    return Observation("waiting");
                }
                Require(++_episodes <= 32, "choice_limit");
                _initial = _adapter.Capture();
                Require(_seen.Add(_initial.Identity) && !_initial.Closed && !_initial.TaskSucceeded && !_initial.TaskFailed,
                    "choice_not_fresh");
                Require(_initial.Pile is "discard" or "exhaust" && _initial.Cards.Length is >= 1 and <= 64 &&
                    _initial.MinSelect >= 0 && _initial.MaxSelect is >= 1 and <= 8 &&
                    _initial.MinSelect <= _initial.MaxSelect && _initial.MaxSelect <= _initial.Cards.Length &&
                    _initial.Cards.All(c => !c.Selected), "unsupported_choice");
                Require(_initial.Cards.Select(c => c.Model).Distinct(ReferenceEqualityComparer.Instance).Count() == _initial.Cards.Length &&
                    _initial.Cards.Select(c => c.Holder).Distinct(ReferenceEqualityComparer.Instance).Count() == _initial.Cards.Length &&
                    _initial.Cards.All(c => c.Model is not null && c.Holder is not null && c.Key.Length is >= 1 and <= 96 &&
                        c.Key.All(x => x is >= 'A' and <= 'Z' or >= 'a' and <= 'z' or >= '0' and <= '9' or '_') &&
                        c.UpgradeLevel is >= 0 and <= 99), "invalid_candidates");
                _choice = Hash(_nonce + ":choice:" + _episodes);
                _attempted = _accepted = _reconciled = _reads = _pendingReads = 0;
                _pending = _decision = null; _expected = null;
                _selected = Array.Empty<int>(); _cards = _initial.Cards;
                _done = false;
            }
            Require(++_reads <= 2048, "choice_read_limit");
            ChoiceSurface surface = _adapter.Capture();
            Require(ReferenceEquals(surface.Identity, _initial!.Identity) && surface.Pile == _initial.Pile &&
                surface.MinSelect == _initial.MinSelect && surface.MaxSelect == _initial.MaxSelect &&
                surface.ManualConfirmation == _initial.ManualConfirmation && !surface.TaskFailed, "choice_identity_changed");
            if (surface.Closed || surface.TaskSucceeded)
            {
                Require(_pending is not null && _expected is not null &&
                    (_pending == "confirm" || !_initial.ManualConfirmation && _expected.Length == _initial.MaxSelect),
                    "unexpected_completion");
                if (!surface.Closed || !surface.TaskSucceeded) return PendingWait();
                object[] expected = _expected!.Select(i => _initial.Cards[i].Model).ToArray();
                Require(surface.Result.Length == expected.Length &&
                    surface.Result.Distinct(ReferenceEqualityComparer.Instance).Count() == expected.Length &&
                    surface.Result.All(r => expected.Any(e => ReferenceEquals(e, r))), "choice_result_mismatch");
                _selected = _expected!; _reconciled++; _pending = null; _decision = null;
                // Disposal must succeed before a clean completion releases core ownership.
                _adapter.Dispose(); _adapter = null; _done = true;
                return Observation("complete");
            }
            Require(surface.Cards.Length == _initial.Cards.Length && surface.Cards.Select((c, i) =>
                ReferenceEquals(c.Model, _initial.Cards[i].Model) && ReferenceEquals(c.Holder, _initial.Cards[i].Holder) &&
                c.Key == _initial.Cards[i].Key && c.UpgradeLevel == _initial.Cards[i].UpgradeLevel).All(x => x), "choice_candidates_changed");
            int[] selected = surface.Cards.Select((c, i) => (c, i)).Where(x => x.c.Selected).Select(x => x.i).ToArray();
            if (_pending is not null)
            {
                if (_pending == "confirm" || selected.SequenceEqual(_selected)) return PendingWait();
                Require(selected.SequenceEqual(_expected!), "choice_selection_mismatch");
                if (!_initial.ManualConfirmation && selected.Length == _initial.MaxSelect)
                    return PendingWait();
                _selected = selected; _reconciled++; _pending = null; _pendingReads = 0;
            }
            else Require(selected.SequenceEqual(_selected), "unsolicited_selection");
            _cards = surface.Cards;
            if (!surface.Ready) { _decision = null; return Observation("waiting"); }
            string[] legal = Legal(surface.ConfirmEnabled);
            _decision = Hash(_choice + ":" + _reconciled + ":" + string.Join(",", legal));
            return Observation("ready", legal);
        }
        catch (Exception error) { return Fail(error is InvalidOperationException ? error.Message : "choice_capture_failed"); }
    }
    private ChoiceReply PendingWait()
    {
        Require(++_pendingReads <= 200, "choice_reconciliation_timeout");
        _decision = null;
        return Observation("waiting");
    }
    private string[] Legal(bool confirm)
    {
        var result = new List<string>();
        for (int i = 0; i < _cards.Length; i++)
            if (_cards[i].Enabled && (_cards[i].Selected || _selected.Length < _initial!.MaxSelect))
                result.Add((_cards[i].Selected ? "deselect:" : "select:") + i);
        if (confirm && _selected.Length >= _initial!.MinSelect && _selected.Length <= _initial.MaxSelect) result.Add("confirm");
        return result.ToArray();
    }
    internal ChoiceReply Apply(string decision, string action)
    {
        if (_failed || _disposed || Environment.CurrentManagedThreadId != _thread) return Fail("choice_stopped");
        if (_adapter is null || _done || _pending is not null || !IsAction(decision, action)) return Fail("choice_not_actionable");
        ChoiceReply fresh = Read();
        try
        {
            if (fresh.Terminal) return fresh;
            using var parsed = JsonDocument.Parse(fresh.Body);
            if (_decision != decision || !parsed.RootElement.GetProperty("legal_actions").EnumerateArray().Any(a => a.GetString() == action))
                return Fail("stale_or_illegal_choice");
        }
        finally { if (!fresh.Terminal) Array.Clear(fresh.Body); }
        if (++_attempted > 32) return Fail("choice_action_limit");
        _expected = _selected.ToArray();
        if (Slot(action, out int slot, out bool deselect))
            _expected = deselect ? _selected.Where(i => i != slot).ToArray() : _selected.Append(slot).Order().ToArray();
        _pending = action; _decision = null;
        try
        {
            if (action == "confirm") _adapter!.Confirm(); else _adapter!.Toggle(slot);
            _accepted++;
            return new(JsonSerializer.SerializeToUtf8Bytes(new { schema_version = 1, protocol = "combat_card_choice_v1",
                status = "accepted", choice_id = _choice, decision_id = decision, action_id = action,
                attempted = _attempted, accepted = _accepted, reconciled = _reconciled }));
        }
        catch { return Fail("uncertain_choice"); }
    }
    private ChoiceReply Observation(string status, string[]? legal = null) => new(JsonSerializer.SerializeToUtf8Bytes(new {
        schema_version = 1, protocol = "combat_card_choice_v1", status,
        choice_id = _choice, decision_id = status == "ready" ? _decision : null,
        pile = _initial?.Pile, min_select = _initial?.MinSelect ?? 0, max_select = _initial?.MaxSelect ?? 0,
        manual_confirmation = _initial?.ManualConfirmation ?? false,
        candidates = status == "ready" ? _cards.Select((c, i) => new { slot = i, key = c.Key,
            upgrade_level = c.UpgradeLevel, selected = c.Selected, enabled = c.Enabled }).ToArray() : null,
        selected_slots = _selected, legal_actions = legal ?? Array.Empty<string>(),
        attempted = _attempted, accepted = _accepted, reconciled = _reconciled,
        result = status == "complete" ? "selection_verified" : null }));
    private ChoiceReply Fail(string code)
    {
        _failed = true;
        // Never serialize native exception details.
        string[] allowed = { "choice_stopped", "choice_limit", "choice_not_fresh", "unsupported_choice", "invalid_candidates",
            "choice_read_limit", "choice_identity_changed", "unexpected_completion", "choice_result_mismatch",
            "choice_candidates_changed", "choice_selection_mismatch", "unsolicited_selection", "choice_reconciliation_timeout",
            "choice_not_actionable", "stale_or_illegal_choice", "choice_action_limit", "uncertain_choice" };
        if (!allowed.Contains(code)) code = "choice_capture_failed";
        return new(JsonSerializer.SerializeToUtf8Bytes(new { schema_version = 1, protocol = "combat_card_choice_v1",
            status = "failed", code, choice_id = _choice, attempted = _attempted, accepted = _accepted, reconciled = _reconciled }), true);
    }
    public void Dispose()
    {
        Require(Environment.CurrentManagedThreadId == _thread, "owner_thread");
        _adapter?.Dispose(); _adapter = null; _disposed = true;
    }
}

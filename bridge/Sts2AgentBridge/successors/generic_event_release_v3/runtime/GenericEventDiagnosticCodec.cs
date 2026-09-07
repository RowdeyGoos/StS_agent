namespace Sts2AgentBridge.Successors.GenericEventReleaseV3;
// Closed mapping: native values can never become arbitrary HTTP text.
internal static class GenericEventDiagnosticCodec
{
    internal static GenericEventDiagnosticCode Normalize(GenericEventDiagnosticCode value) =>
        value is >= GenericEventDiagnosticCode.NotCaptured and <= GenericEventDiagnosticCode.DiagnosticUnavailable ? value : GenericEventDiagnosticCode.DiagnosticUnavailable;
    internal static string Encode(GenericEventDiagnosticCode value) => value switch
    {
        GenericEventDiagnosticCode.NotCaptured => "none",
        GenericEventDiagnosticCode.ParentReady => "parent_ready",
        GenericEventDiagnosticCode.ParentUnavailable => "parent_unavailable",
        GenericEventDiagnosticCode.ParentWaiting => "parent_waiting",
        GenericEventDiagnosticCode.PendingBindingFailed => "pending_binding_failed",
        GenericEventDiagnosticCode.PendingOwnership => "pending_ownership",
        GenericEventDiagnosticCode.PendingContext => "pending_context",
        GenericEventDiagnosticCode.PendingTaskFailed => "pending_task_failed",
        GenericEventDiagnosticCode.PendingChosenEntry => "pending_chosen_entry",
        GenericEventDiagnosticCode.PendingChosenTask => "pending_chosen_task",
        GenericEventDiagnosticCode.PendingChosenCompletion => "pending_chosen_completion",
        GenericEventDiagnosticCode.PendingRequestTask => "pending_request_task",
        GenericEventDiagnosticCode.PendingScreen => "pending_screen",
        GenericEventDiagnosticCode.PendingSelectorlessRequest => "pending_selectorless_request",
        GenericEventDiagnosticCode.PendingOverlay => "pending_overlay",
        GenericEventDiagnosticCode.PendingDeck => "pending_deck",
        GenericEventDiagnosticCode.PendingOffers => "pending_offers",
        GenericEventDiagnosticCode.PendingProceed => "pending_proceed",
        GenericEventDiagnosticCode.PrepareBinding => "prepare_binding",
        GenericEventDiagnosticCode.PrepareScreen => "prepare_screen",
        GenericEventDiagnosticCode.PrepareExternalSelector => "prepare_external_selector",
        GenericEventDiagnosticCode.PrepareDeck => "prepare_deck",
        GenericEventDiagnosticCode.PrepareForeground => "prepare_foreground",
        GenericEventDiagnosticCode.PrepareFamily => "prepare_family",
        GenericEventDiagnosticCode.PrepareGridNode => "prepare_grid_node",
        GenericEventDiagnosticCode.PrepareGridState => "prepare_grid_state",
        GenericEventDiagnosticCode.PrepareHolders => "prepare_holders",
        GenericEventDiagnosticCode.PrepareCandidates => "prepare_candidates",
        GenericEventDiagnosticCode.PrepareGeometry => "prepare_geometry",
        GenericEventDiagnosticCode.PreparePreviewNodes => "prepare_preview_nodes",
        GenericEventDiagnosticCode.PreparePreviewState => "prepare_preview_state",
        GenericEventDiagnosticCode.PrepareConfirm => "prepare_confirm",
        GenericEventDiagnosticCode.ChildReady => "child_ready",
        GenericEventDiagnosticCode.MapReady => "map_ready",
        GenericEventDiagnosticCode.CaptureDisposed => "capture_disposed",
        GenericEventDiagnosticCode.CaptureException => "capture_exception",
        GenericEventDiagnosticCode.DiagnosticUnavailable => "diagnostic_unavailable",
        _ => "diagnostic_unavailable",
    };
}

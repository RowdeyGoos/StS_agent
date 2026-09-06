namespace Sts2AgentBridge.Successors.ShopDiagnosticV1;

internal sealed class FirstFailureRecorder : IShopDiagnosticRecorder
{
    internal ShopDiagnosticStage Stage { get; private set; } = ShopDiagnosticStage.NativeContext;
    internal ShopDiagnosticReason Reason { get; private set; } = ShopDiagnosticReason.None;

    public void Enter(ShopDiagnosticStage stage)
    {
        if (stage < ShopDiagnosticStage.NativeContext || stage > ShopDiagnosticStage.Complete)
            throw new System.InvalidOperationException();
        if (Reason == ShopDiagnosticReason.None) Stage = stage;
    }

    public void Reject(ShopDiagnosticReason reason)
    {
        if (reason < ShopDiagnosticReason.None || reason > ShopDiagnosticReason.ProjectionException)
            throw new System.InvalidOperationException();
        if (Reason == ShopDiagnosticReason.None && reason != ShopDiagnosticReason.None)
            Reason = reason;
    }
}

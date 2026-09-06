using System;

namespace Sts2AgentBridge.Successors.ShopDiagnosticV1;

public sealed class ShopDiagnosticService : IShopDiagnosticService
{
    private readonly int _ownerThreadId;
    private IShopDiagnosticAdapter? _adapter;
    private bool _observed;
    private bool _disposed;
    private bool _inside;
    private bool _interfered;

    public ShopDiagnosticService(IShopDiagnosticAdapter adapter)
    {
        _adapter = adapter ?? throw new ArgumentNullException(nameof(adapter));
        _ownerThreadId = Environment.CurrentManagedThreadId;
    }

    public byte[] Observe()
    {
        if (Environment.CurrentManagedThreadId != _ownerThreadId || _disposed || _observed)
            throw new InvalidOperationException();
        _observed = true;
        IShopDiagnosticAdapter adapter = _adapter ?? throw new InvalidOperationException();
        var recorder = new FirstFailureRecorder();
        ShopDiagnosticCapture capture;
        try
        {
            _inside = true;
            capture = adapter.CaptureSurface(recorder);
            if (capture is null) throw new InvalidOperationException();
            if (_disposed || _interfered) throw new InvalidOperationException();
        }
        catch
        {
            recorder.Reject(ShopDiagnosticReason.NativeException);
            return ShopDiagnosticCodec.Encode("unsupported", recorder.Stage, recorder.Reason);
        }
        finally
        {
            _inside = false;
        }

        string status;
        try
        {
            status = ShopDiagnosticProjector.Project(capture, recorder);
        }
        catch
        {
            recorder.Reject(ShopDiagnosticReason.ProjectionException);
            status = "unsupported";
        }
        return ShopDiagnosticCodec.Encode(status, recorder.Stage, recorder.Reason);
    }

    public void Dispose()
    {
        if (Environment.CurrentManagedThreadId != _ownerThreadId)
            throw new InvalidOperationException();
        if (_disposed) return;
        _disposed = true;
        _adapter = null;
        if (_inside) _interfered = true;
    }
}

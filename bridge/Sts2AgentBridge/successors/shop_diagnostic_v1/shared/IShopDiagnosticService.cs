using System;

namespace Sts2AgentBridge.Successors.ShopDiagnosticV1;

public interface IShopDiagnosticService : IDisposable
{
    byte[] Observe();
}

using System;

namespace Sts2AgentBridge.Core.Public;

public interface IPublicScreenReader
{
    PublicScreenFacts Read();
}

public interface IPublicScreenService
{
    PublicScreenReadResult Read();
}

public sealed class PublicScreenService : IPublicScreenService
{
    private readonly IPublicScreenReader _reader;

    public PublicScreenService(IPublicScreenReader reader)
    {
        _reader = reader ?? throw new ArgumentNullException(nameof(reader));
    }

    public PublicScreenReadResult Read()
    {
        try
        {
            PublicScreenSnapshot snapshot = PublicScreenProjector.Project(_reader.Read());
            return PublicScreenReadResult.FromSnapshot(snapshot);
        }
        catch (Exception)
        {
            return PublicScreenReadResult.BackendFault();
        }
    }
}

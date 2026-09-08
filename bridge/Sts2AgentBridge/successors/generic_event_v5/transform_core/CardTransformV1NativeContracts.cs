using System;
using System.Collections.Generic;
using Sts2AgentBridge.Successors.CardSelectionV1;
namespace Sts2AgentBridge.Successors.CardTransformV1;
public enum CardTransformV1CommandState { NotStarted = 0, Running = 1, Succeeded = 2, Canceled = 3, Faulted = 4 }
public sealed record CardTransformV1Insertion(int Ordinal, object OriginalIdentity, object FinalIdentity, string FinalStableKey, int FinalUpgradeLevel);
public sealed record CardTransformV1CommandResult(bool Success, object FinalIdentity);
public sealed record CardTransformV1CommandWitness(object CommandIdentity, IReadOnlyList<object> OriginalIdentities, CardTransformV1CommandState State,
    bool AllOriginalsRemoved, IReadOnlyList<CardTransformV1Insertion> Insertions, IReadOnlyList<CardTransformV1CommandResult> CompletedResults);
public sealed record CardTransformV1EffectWitness(IReadOnlyList<CardTransformV1CommandWitness> Commands, IReadOnlyList<object> RemovedOriginals,
    IReadOnlyList<CardTransformV1Insertion> OrderedCommittedInsertions);
public sealed record CardTransformV1SurfaceCapture(CardSelectionV1SurfaceCapture Surface, CardTransformV1EffectWitness Effect);
public interface ICardTransformV1NativeAdapter : IDisposable { CardTransformV1SurfaceCapture CaptureSurface(); }

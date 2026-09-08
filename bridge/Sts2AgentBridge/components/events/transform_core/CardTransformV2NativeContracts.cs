using System;
using System.Collections.Generic;
using Sts2AgentBridge.Successors.CardSelectionV1;
namespace Sts2AgentBridge.Successors.CardTransformV2;
public enum CardTransformV2CommandState { NotStarted = 0, Running = 1, Succeeded = 2, Canceled = 3, Faulted = 4 }
public sealed record CardTransformV2Insertion(int Ordinal, object OriginalIdentity, object FinalIdentity, string FinalStableKey, int FinalUpgradeLevel);
public sealed record CardTransformV2CommandResult(bool Success, object FinalIdentity);
public sealed record CardTransformV2CommandWitness(object CommandIdentity, IReadOnlyList<object> OriginalIdentities, CardTransformV2CommandState State,
    bool AllOriginalsRemoved, IReadOnlyList<CardTransformV2Insertion> Insertions, IReadOnlyList<CardTransformV2CommandResult> CompletedResults);
public sealed record CardTransformV2EffectWitness(IReadOnlyList<CardTransformV2CommandWitness> Commands, IReadOnlyList<object> RemovedOriginals,
    IReadOnlyList<CardTransformV2Insertion> OrderedCommittedInsertions);
public sealed record CardTransformV2SurfaceCapture(CardSelectionV1SurfaceCapture Surface, CardTransformV2EffectWitness Effect);
public interface ICardTransformV2NativeAdapter : IDisposable { CardTransformV2SurfaceCapture CaptureSurface(); }

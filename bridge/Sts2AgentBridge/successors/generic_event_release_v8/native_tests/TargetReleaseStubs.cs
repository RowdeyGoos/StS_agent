using System;
namespace MegaCrit.Sts2.Core.Modding
{
    [AttributeUsage(AttributeTargets.Class)]
    public sealed class ModInitializerAttribute : Attribute { public ModInitializerAttribute(string method) { } }
}
namespace Godot
{
    public static class Engine { public static object? GetMainLoop() => null; }
    public enum Error { Ok }
    public readonly struct Callable { public static Callable From(Action callback) => new(); }
    public sealed class SceneTree
    {
        public static class SignalName { public const string ProcessFrame = "process_frame"; }
        public Error Connect(string signal, Callable callback, uint flags) => Error.Ok;
        public void Disconnect(string signal, Callable callback) { }
    }
}

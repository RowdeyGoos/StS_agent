"""Bounded macOS arm64 native queue oracle; never starts the game's project."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import time
import uuid
from zipfile import ZipFile


PINS = {
    "engine": "7fadae8d46f0074ba745bc3beebe31a13df5fafed2f2ac69cd68b3c5dd8508e6",
    "sts2.dll": "e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18",
    "GodotSharp.dll": "0e4897ecdfb31456a97c7d8028dfb8d7dbdc632e2f73fc9b438d7b266a139289",
}


def sha(path):
    with path.open("rb") as stream:
        digest = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("engine", "native-data", "godot-sdk", "godot-generators", "dotnet", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--mode", choices=("queue", "death-draw", "attack-hooks", "multiple-deaths", "enemy-turn", "autoplay", "autoplay-flak"), default="queue")
    args = parser.parse_args()
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        parser.error("This pinned exported-runtime fixture requires macOS arm64.")
    engine, native = args.engine.resolve(), args.native_data.resolve()
    for name in ("queue_oracle.dll", "queue_oracle.deps.json", "queue_oracle.runtimeconfig.json"):
        if (native / name).exists() or (native / name).is_symlink():
            parser.error("Fixture output would collide with native input: " + name)
    for name, path in (("engine", engine), ("sts2.dll", native / "sts2.dll"), ("GodotSharp.dll", native / "GodotSharp.dll")):
        if sha(path) != PINS[name]:
            parser.error("Pinned identity mismatch: " + name)
    source = Path(__file__).resolve().parent
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    project = output / "project"
    project.mkdir()
    data = output / "data_queue_oracle_macos_arm64"
    data.mkdir()
    staged_engine = output / "QueueOracle"
    shutil.copyfile(engine, staged_engine)
    staged_engine.chmod(0o755)
    # Only the native distribution's runtime directory is read. No game PCK,
    # autoload, extension manifest, profile, history or save directory is staged.
    native_hashes = {}
    for path in sorted(native.iterdir()):
        if path.is_file():
            (data / path.name).symlink_to(path)
            native_hashes[path.name] = sha(path)
    for name in ("queue_oracle.csproj", "Oracle.cs", "paused_hooks.cs", "death_draw.cs", "enemy_turn.cs", "autoplay.cs", "empty.tscn"):
        shutil.copyfile(source / name, project / name)
    user_name = "StsNativeQueueOracle-" + uuid.uuid4().hex
    user_dir = Path.home() / "Library" / "Application Support" / user_name
    settings = f'''config_version=5
_custom_features="dotnet"
[application]
config/name="StsNativeQueueOracle"
config/features=PackedStringArray("4.5", "C#")
config/use_custom_user_dir=true
config/custom_user_dir_name="{user_name}"
run/main_scene="res://empty.tscn"
[rendering]
renderer/rendering_method="gl_compatibility"
[debug]
file_logging/enable_file_logging=false
[dotnet]
project/assembly_name="queue_oracle"
'''
    (project / "project.godot").write_text(settings)
    command = [str(args.dotnet.resolve()), "build", str(project / "queue_oracle.csproj"),
               "-c", "ExportRelease", "--nologo", "-v:q",
               f"-p:GodotSdkDir={args.godot_sdk.resolve()}",
               f"-p:GodotGeneratorsDir={args.godot_generators.resolve()}",
               f"-p:NativeDataDir={data}"]
    started = time.monotonic()
    build = subprocess.run(command, cwd=project, capture_output=True, text=True, timeout=120)
    (output / "build.log").write_text(build.stdout + build.stderr)
    build.check_returncode()
    build_seconds = time.monotonic() - started
    compiled = project / ".godot/mono/temp/bin/ExportRelease"
    shutil.copyfile(compiled / "queue_oracle.dll", data / "queue_oracle.dll")
    # Exported hosting needs the bundled self-contained runtime metadata. Compose
    # fixture metadata explicitly; do not claim these files are a native export.
    shutil.copyfile(native / "sts2.runtimeconfig.json", data / "queue_oracle.runtimeconfig.json")
    deps = json.loads((native / "sts2.deps.json").read_text())
    own = json.loads((compiled / "queue_oracle.deps.json").read_text())
    for target in deps["targets"].values():
        target["queue_oracle/1.0.0"] = {"runtime": {"queue_oracle.dll": {}}, "dependencies": {}}
    deps["libraries"]["queue_oracle/1.0.0"] = own["libraries"]["queue_oracle/1.0.0"]
    (data / "queue_oracle.deps.json").write_text(json.dumps(deps))
    pack = output / "queue.zip"
    with ZipFile(pack, "w") as archive:
        for name in ("project.godot", "empty.tscn", "Oracle.cs"):
            archive.write(project / name, name)
        archive.writestr(".godot/global_script_class_cache.cfg", "list=[]\n")
    # Godot's custom name is relative to Application Support. Own one new empty
    # directory, then remove only that directory. Never change HOME or touch saves.
    user_dir.mkdir()
    started = time.monotonic()
    try:
        run = subprocess.run([str(staged_engine), "--headless", "--main-pack", str(pack),
                              "--path", str(project), "--log-file", str(output / "engine.log"), "--", args.mode],
                             cwd=project, capture_output=True, text=True, timeout=15)
        (output / "stdout.log").write_text(run.stdout)
        (output / "stderr.log").write_text(run.stderr)
        run.check_returncode()
        result = json.loads((project / "queue-result.json").read_text())
    finally:
        # rmdir deliberately fails if unexpected files appeared; no recursive cleanup.
        user_dir.rmdir()
    elapsed = time.monotonic() - started
    record = {
        "pins": PINS, "nativeDependencies": native_hashes,
        "fixtureSources": {p.name: sha(p) for p in sorted(source.iterdir()) if p.is_file()},
        "generatorSha256": sha(args.godot_generators / "analyzers/dotnet/cs/Godot.SourceGenerators.dll"),
        "compiledFixtureSha256": sha(data / "queue_oracle.dll"),
        "buildSeconds": build_seconds, "executionSeconds": elapsed,
        "userDirectoryRemoved": not user_dir.exists(), "result": result,
    }
    (output / "evidence.json").write_text(json.dumps(record, indent=2) + "\n")
    print(f"Native queue assertions passed in {elapsed:.3f}s; build {build_seconds:.3f}s.")
    print(output / "evidence.json")


if __name__ == "__main__":
    main()

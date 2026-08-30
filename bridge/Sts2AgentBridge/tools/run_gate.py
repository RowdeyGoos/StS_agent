#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

from tool_common import (
    EXIT_INTERNAL,
    EXIT_INVALID_INVOCATION,
    EXIT_MISMATCH,
    EXIT_UNSAFE_BOUNDARY,
    absolute_path,
    fail,
    main,
    require_directory,
    require_executable_file,
    require_regular_file,
    sha256_file,
)

PARITY_VERSION = "9.0.303"
SERVICING_VERSION = "9.0.317"
STS2_SHA256 = "e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18"
GODOT_SHA256 = "0e4897ecdfb31456a97c7d8028dfb8d7dbdc632e2f73fc9b438d7b266a139289"


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    subparsers = root.add_subparsers(dest="gate", required=True)

    def common(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument("--source-root", required=True)
        subparser.add_argument("--dotnet", required=True)
        subparser.add_argument("--game-data-dir", required=True)
        subparser.add_argument("--work-root", required=True)

    test = subparsers.add_parser("test")
    common(test)

    build = subparsers.add_parser("build")
    common(build)
    build.add_argument("--sdk-role", required=True, choices=("parity", "servicing"))
    build.add_argument("--output-dir", required=True)

    surface = subparsers.add_parser("surface")
    common(surface)
    surface.add_argument("--assembly", required=True)
    surface.add_argument("--policy", required=True)
    return root


def write_text(path: Path, value: str) -> None:
    try:
        with path.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(value)
    except OSError:
        fail(EXIT_UNSAFE_BOUNDARY, "work_root_write")


def prepare_environment(work_root: Path) -> dict[str, str]:
    cli_home = work_root / "cli-home"
    nuget_packages = work_root / "nuget-packages"
    artifacts = work_root / "artifacts"
    for directory in (cli_home, nuget_packages, artifacts):
        try:
            directory.mkdir(mode=0o700)
        except OSError:
            fail(EXIT_UNSAFE_BOUNDARY, "work_root_write")
    environment = {
        "DOTNET_CLI_HOME": str(cli_home),
        "DOTNET_SKIP_FIRST_TIME_EXPERIENCE": "1",
        "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
        "DOTNET_GENERATE_ASPNET_CERTIFICATE": "false",
        "DOTNET_NOLOGO": "1",
        "DOTNET_MULTILEVEL_LOOKUP": "0",
        "MSBUILDDISABLENODEREUSE": "1",
        "NUGET_PACKAGES": str(nuget_packages),
        "PATH": "/usr/bin:/bin",
        "LANG": "C",
        "LC_ALL": "C",
    }
    return environment


def run_process(
    command: list[str],
    environment: dict[str, str],
    work_root: Path,
    log_name: str,
    *,
    timeout: int = 300,
) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=environment,
        )
        write_text(work_root / log_name, completed.stdout)
        return completed
    except subprocess.TimeoutExpired:
        fail(EXIT_MISMATCH, "gate_timeout")
    except OSError:
        fail(EXIT_INTERNAL, "process_start_failed")


def validate_source(source_root: Path) -> None:
    require_directory(source_root, "source_root")
    required = (
        source_root / "Directory.Build.props",
        source_root / "global.json",
        source_root / "src" / "Sts2AgentBridge" / "Sts2AgentBridge.csproj",
        source_root / "tests" / "Sts2AgentBridge.Tests" / "Sts2AgentBridge.Tests.csproj",
    )
    for path in required:
        require_regular_file(path, "source_file", max_bytes=1024 * 1024)


def validate_game_data(game_data_dir: Path) -> None:
    require_directory(game_data_dir, "game_data_dir")
    sts2 = game_data_dir / "sts2.dll"
    godot = game_data_dir / "GodotSharp.dll"
    require_regular_file(sts2, "sts2", max_bytes=10 * 1024 * 1024)
    require_regular_file(godot, "godot", max_bytes=6 * 1024 * 1024)
    if sha256_file(sts2) != STS2_SHA256:
        fail(EXIT_MISMATCH, "sts2_hash")
    if sha256_file(godot) != GODOT_SHA256:
        fail(EXIT_MISMATCH, "godot_hash")


def dotnet_properties(source_root: Path, game_data_dir: Path, work_root: Path) -> list[str]:
    empty_targets = work_root / "Directory.Build.targets"
    write_text(empty_targets, "<Project />\n")
    return [
        f"-p:STS2GameDataDir={game_data_dir}",
        f"-p:DirectoryBuildPropsPath={source_root / 'Directory.Build.props'}",
        f"-p:DirectoryBuildTargetsPath={empty_targets}",
        "-p:RestoreIgnoreFailedSources=true",
        "-p:RestoreNoCache=true",
        "-p:NuGetAudit=false",
        "-p:UseSharedCompilation=false",
        "-p:IncludeSourceRevisionInInformationalVersion=false",
    ]


def write_nuget_config(work_root: Path) -> Path:
    path = work_root / "NuGet.Config"
    write_text(
        path,
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<configuration><packageSources><clear /></packageSources></configuration>\n',
    )
    return path


def restore_and_build(
    dotnet: Path,
    project: Path,
    output_dir: Path,
    source_root: Path,
    game_data_dir: Path,
    work_root: Path,
    environment: dict[str, str],
    prefix: str,
    *,
    extra_properties: list[str] | None = None,
    artifacts_name: str = "artifacts",
) -> None:
    properties = dotnet_properties(source_root, game_data_dir, work_root)
    if extra_properties is not None:
        properties.extend(extra_properties)
    nuget_config = write_nuget_config(work_root)
    artifacts = work_root / artifacts_name
    restore = [
        str(dotnet),
        "restore",
        str(project),
        "--configfile",
        str(nuget_config),
        "--packages",
        str(work_root / "nuget-packages"),
        "--artifacts-path",
        str(artifacts),
        "--ignore-failed-sources",
        *properties,
    ]
    if run_process(restore, environment, work_root, f"{prefix}-restore.log").returncode != 0:
        fail(EXIT_MISMATCH, "restore_failed")
    build = [
        str(dotnet),
        "build",
        str(project),
        "--no-restore",
        "--configuration",
        "Release",
        "--output",
        str(output_dir),
        "--artifacts-path",
        str(artifacts),
        "--disable-build-servers",
        "--nologo",
        *properties,
    ]
    if run_process(build, environment, work_root, f"{prefix}-build.log").returncode != 0:
        fail(EXIT_MISMATCH, "build_failed")


def operation() -> dict[str, object]:
    args = parser().parse_args()
    source_root = absolute_path(args.source_root, "source_root")
    dotnet = absolute_path(args.dotnet, "dotnet")
    game_data_dir = absolute_path(args.game_data_dir, "game_data_dir")
    work_root = absolute_path(args.work_root, "work_root")
    require_executable_file(dotnet, "dotnet")
    validate_source(source_root)
    validate_game_data(game_data_dir)
    require_directory(work_root, "work_root", empty=True)
    environment = prepare_environment(work_root)

    expected_version = PARITY_VERSION
    if args.gate == "build" and args.sdk_role == "servicing":
        expected_version = SERVICING_VERSION
    version_result = run_process(
        [str(dotnet), "--version"],
        environment,
        work_root,
        "dotnet-version.log",
        timeout=30,
    )
    if version_result.returncode != 0 or version_result.stdout.strip() != expected_version:
        fail(EXIT_MISMATCH, "sdk_version")

    if args.gate == "build":
        output_dir = absolute_path(args.output_dir, "output_dir")
        require_directory(output_dir, "output_dir", empty=True)
        project = source_root / "src" / "Sts2AgentBridge" / "Sts2AgentBridge.csproj"
        restore_and_build(
            dotnet,
            project,
            output_dir,
            source_root,
            game_data_dir,
            work_root,
            environment,
            "production",
        )
        assembly = output_dir / "Sts2AgentBridge.dll"
        require_regular_file(assembly, "assembly")
        return {
            "schema_version": 1,
            "status": "passed",
            "gate": "build",
            "sdk_role": args.sdk_role,
            "sdk_version": expected_version,
            "assembly_sha256": sha256_file(assembly),
        }

    if args.gate == "test":
        output_dir = work_root / "test-output"
        output_dir.mkdir(mode=0o700)
        project = source_root / "tests" / "Sts2AgentBridge.Tests" / "Sts2AgentBridge.Tests.csproj"
        restore_and_build(
            dotnet,
            project,
            output_dir,
            source_root,
            game_data_dir,
            work_root,
            environment,
            "tests",
        )
        test_assembly = output_dir / "Sts2AgentBridge.Tests.dll"
        require_regular_file(test_assembly, "test_assembly")
        result = run_process(
            [str(dotnet), str(test_assembly)],
            environment,
            work_root,
            "test-run.log",
            timeout=300,
        )
        if result.returncode != 0:
            fail(EXIT_MISMATCH, "tests_failed")
        return {
            "schema_version": 1,
            "status": "passed",
            "gate": "test",
            "sdk_version": expected_version,
        }

    assembly = absolute_path(args.assembly, "assembly")
    policy = absolute_path(args.policy, "policy")
    require_regular_file(assembly, "assembly")
    require_regular_file(policy, "policy", max_bytes=1024 * 1024)
    verifier_project = source_root / "tools" / "Sts2AgentBridge.Verifier" / "Sts2AgentBridge.Verifier.csproj"
    require_regular_file(verifier_project, "verifier_project", max_bytes=1024 * 1024)
    output_dir = work_root / "verifier-output"
    output_dir.mkdir(mode=0o700)
    restore_and_build(
        dotnet,
        verifier_project,
        output_dir,
        source_root,
        game_data_dir,
        work_root,
        environment,
        "verifier",
    )
    verifier = output_dir / "Sts2AgentBridge.Verifier.dll"
    require_regular_file(verifier, "verifier")
    result = run_process(
        [
            str(dotnet),
            str(verifier),
            "--assembly",
            str(assembly),
            "--policy",
            str(policy),
            "--source-root",
            str(source_root),
        ],
        environment,
        work_root,
        "surface-run.log",
        timeout=300,
    )
    if result.returncode != 0:
        fail(EXIT_MISMATCH, "surface_failed")

    fixture_count = run_verifier_fixtures(
        dotnet,
        verifier,
        assembly,
        source_root,
        game_data_dir,
        policy,
        work_root,
        environment,
    )
    return {
        "schema_version": 1,
        "status": "passed",
        "gate": "surface",
        "sdk_version": expected_version,
        "assembly_sha256": sha256_file(assembly),
        "fixture_count": fixture_count,
    }


def run_verifier_fixtures(
    dotnet: Path,
    verifier: Path,
    production_assembly: Path,
    source_root: Path,
    game_data_dir: Path,
    policy: Path,
    work_root: Path,
    environment: dict[str, str],
) -> int:
    fixtures_root = (
        source_root
        / "tests"
        / "Sts2AgentBridge.Tests"
        / "VerifierFixtures"
    )
    fixture_project = fixtures_root / "Sts2AgentBridge.VerifierFixture.csproj"
    catalog_path = fixtures_root / "fixture_catalog.json"
    require_regular_file(fixture_project, "fixture_project", max_bytes=1024 * 1024)
    catalog_bytes = require_regular_file(catalog_path, "fixture_catalog", max_bytes=1024 * 1024)
    try:
        catalog = json.loads(catalog_bytes.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        fail(EXIT_MISMATCH, "fixture_catalog_invalid")
    if not isinstance(catalog, dict) or catalog.get("schema_version") != "br0_verifier_fixtures_v1":
        fail(EXIT_MISMATCH, "fixture_catalog_invalid")
    fixtures = catalog.get("fixtures")
    if not isinstance(fixtures, list) or len(fixtures) < 1:
        fail(EXIT_MISMATCH, "fixture_catalog_invalid")

    positive_output = work_root / "fixture-positive-output"
    try:
        positive_output.mkdir(mode=0o700)
    except OSError:
        fail(EXIT_UNSAFE_BOUNDARY, "fixture_output_write")
    restore_and_build(
        dotnet,
        fixture_project,
        positive_output,
        source_root,
        game_data_dir,
        work_root,
        environment,
        "fixture-positive",
        artifacts_name="fixture-positive-artifacts",
    )
    positive_assembly = positive_output / "Sts2AgentBridge.dll"
    require_regular_file(positive_assembly, "fixture_positive_assembly")
    positive_verification = run_process(
        [
            str(dotnet),
            str(verifier),
            "--assembly",
            str(positive_assembly),
            "--policy",
            str(policy),
            "--source-root",
            str(source_root),
        ],
        environment,
        work_root,
        "fixture-positive-verify.log",
        timeout=300,
    )
    try:
        positive_payload = json.loads(positive_verification.stdout)
    except json.JSONDecodeError:
        fail(EXIT_MISMATCH, "fixture_positive_verifier_output")
    if (
        positive_verification.returncode != 0
        or not isinstance(positive_payload, dict)
        or positive_payload.get("schema_version") != 1
        or positive_payload.get("status") != "passed"
        or not isinstance(positive_payload.get("configuration_structure_sha256"), str)
        or not isinstance(positive_payload.get("build_guard_structure_sha256"), str)
        or not isinstance(positive_payload.get("transport_structure_sha256"), str)
        or not isinstance(positive_payload.get("source_projection_sha256"), str)
        or not isinstance(positive_payload.get("release_assembly_structure_sha256"), str)
    ):
        fail(EXIT_MISMATCH, "fixture_positive_unexpected_result")

    for index, fixture in enumerate(fixtures):
        if not isinstance(fixture, dict):
            fail(EXIT_MISMATCH, "fixture_catalog_invalid")
        source_name = fixture.get("source")
        mutation = fixture.get("mutation")
        expected_code = fixture.get("expected_code")
        exclude_initializer = fixture.get("exclude_initializer", False)
        include_bad_dependency = fixture.get("include_bad_dependency", False)
        version_mutation = fixture.get("version_mutation")
        if (
            source_name is not None and not isinstance(source_name, str)
            or mutation is not None and not isinstance(mutation, dict)
            or not isinstance(expected_code, str)
            or not isinstance(exclude_initializer, bool)
            or not isinstance(include_bad_dependency, bool)
            or version_mutation not in (None, "assembly", "file", "informational")
            or (
                source_name is None
                and mutation is None
                and not exclude_initializer
                and version_mutation is None
            )
            or (source_name is not None and mutation is not None)
            or (
                version_mutation is not None
                and (source_name is not None or mutation is not None or exclude_initializer)
            )
        ):
            fail(EXIT_MISMATCH, "fixture_catalog_invalid")

        extra_properties: list[str] = []
        if source_name is not None:
            if Path(source_name).name != source_name or source_name in (".", ".."):
                fail(EXIT_MISMATCH, "fixture_catalog_invalid")
            fixture_source = fixtures_root / source_name
            require_regular_file(fixture_source, "fixture_source", max_bytes=1024 * 1024)
            extra_properties.append(f"-p:FixtureSource={fixture_source}")
        elif mutation is not None:
            base_name = mutation.get("base")
            old = mutation.get("old")
            new = mutation.get("new")
            replace_count = mutation.get("replace_count", 1)
            if (
                not isinstance(base_name, str)
                or not isinstance(old, str)
                or not isinstance(new, str)
                or not isinstance(replace_count, int)
                or replace_count < 1
                or Path(base_name).is_absolute()
                or ".." in Path(base_name).parts
                or not base_name.startswith("src/Sts2AgentBridge/")
            ):
                fail(EXIT_MISMATCH, "fixture_catalog_invalid")
            base_source = source_root / base_name
            base_bytes = require_regular_file(
                base_source,
                "fixture_mutation_base",
                max_bytes=1024 * 1024,
            )
            try:
                base_text = base_bytes.decode("utf-8")
            except UnicodeError:
                fail(EXIT_MISMATCH, "fixture_mutation_encoding")
            if base_text.count(old) != replace_count:
                fail(EXIT_MISMATCH, "fixture_mutation_match_count")
            mutated_text = base_text.replace(old, new)
            fixture_source = work_root / f"fixture-{index:02d}-mutated.cs"
            write_text(fixture_source, mutated_text)
            excluded_source = os.path.relpath(base_source, fixtures_root)
            extra_properties.extend(
                (
                    f"-p:FixtureSource={fixture_source}",
                    f"-p:ExcludedProductionSource={excluded_source}",
                )
            )
        elif version_mutation == "assembly":
            extra_properties.append("-p:AssemblyVersion=0.2.0.0")
        elif version_mutation == "file":
            extra_properties.append("-p:FileVersion=0.2.0.0")
        elif version_mutation == "informational":
            extra_properties.append("-p:InformationalVersion=0.2.0")
        if exclude_initializer:
            extra_properties.append("-p:ExcludeInitializer=true")
        if include_bad_dependency:
            extra_properties.append("-p:IncludeBadDependency=true")

        output_dir = work_root / f"fixture-{index:02d}-output"
        try:
            output_dir.mkdir(mode=0o700)
        except OSError:
            fail(EXIT_UNSAFE_BOUNDARY, "fixture_output_write")
        restore_and_build(
            dotnet,
            fixture_project,
            output_dir,
            source_root,
            game_data_dir,
            work_root,
            environment,
            f"fixture-{index:02d}",
            extra_properties=extra_properties,
            artifacts_name=f"fixture-{index:02d}-artifacts",
        )
        fixture_assembly = output_dir / "Sts2AgentBridge.dll"
        require_regular_file(fixture_assembly, "fixture_assembly")
        verification = run_process(
            [
                str(dotnet),
                str(verifier),
                "--assembly",
                str(fixture_assembly),
                "--policy",
                str(policy),
                "--source-root",
                str(source_root),
            ],
            environment,
            work_root,
            f"fixture-{index:02d}-verify.log",
            timeout=300,
        )
        try:
            payload = json.loads(verification.stdout)
        except json.JSONDecodeError:
            fail(EXIT_MISMATCH, "fixture_verifier_output")
        if (
            verification.returncode != EXIT_MISMATCH
            or not isinstance(payload, dict)
            or payload.get("schema_version") != 1
            or payload.get("status") != "failed"
            or payload.get("code") != expected_code
        ):
            fail(EXIT_MISMATCH, f"fixture_{index:02d}_unexpected_result")

    source_fixture_root = work_root / "source-fixture-root"
    source_fixture_tree = source_fixture_root / "src" / "Sts2AgentBridge"
    try:
        source_fixture_tree.parent.mkdir(parents=True, mode=0o700)
        shutil.copytree(
            source_root / "src" / "Sts2AgentBridge",
            source_fixture_tree,
            symlinks=True,
            ignore=shutil.ignore_patterns("bin", "obj"),
        )
    except OSError:
        fail(EXIT_UNSAFE_BOUNDARY, "source_fixture_copy")
    write_text(
        source_fixture_tree / "Core" / "ForbiddenSourceFixture.cs",
        "using System.Net.Http;\nnamespace SourceFixture;\ninternal static class ForbiddenSourceFixture {}\n",
    )
    source_verification = run_process(
        [
            str(dotnet),
            str(verifier),
            "--assembly",
            str(production_assembly),
            "--policy",
            str(policy),
            "--source-root",
            str(source_fixture_root),
        ],
        environment,
        work_root,
        "source-fixture-verify.log",
        timeout=300,
    )
    try:
        source_payload = json.loads(source_verification.stdout)
    except json.JSONDecodeError:
        fail(EXIT_MISMATCH, "source_fixture_verifier_output")
    if (
        source_verification.returncode != EXIT_MISMATCH
        or not isinstance(source_payload, dict)
        or source_payload.get("status") != "failed"
        or source_payload.get("code") != "source_forbidden_fragment"
    ):
        fail(EXIT_MISMATCH, "source_fixture_unexpected_result")

    return len(fixtures) + 2


if __name__ == "__main__":
    main(operation)

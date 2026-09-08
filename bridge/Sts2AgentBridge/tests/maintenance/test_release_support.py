"""Regressions for the new release boundary, independent of historical checkers."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from release_support import (collect_sources, inventory, project_closure, read_regular,
                             sha, validate_sources, verify_release_sources)


class ReleaseBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="sts-release-test-", dir="/private/tmp")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        for name in ("check.py", "release_support.py", "global.json", "Directory.Build.props",
                     "apps/bridge/client/run_live.py", "components/cards/host/card_selection_host.py"):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("source\n")
        hashes, digest = inventory(collect_sources(self.root, ["bridge"]))
        self.release = {"schema_version": 1, "status": "passed", "suite": "release", "target": "bridge",
                        "files": hashes, "source_inventory_sha256": digest,
                        "checks": {"behavior": {"status": "passed"}}}
        self.manifest = self.root / "release.json"

    def seal(self):
        data = json.dumps(self.release).encode()
        self.manifest.write_bytes(data)
        return sha(data)

    def verify(self, digest):
        verify_release_sources(self.root, "bridge", self.manifest, digest)

    def test_current_release_requires_no_history(self):
        self.verify(self.seal())
        self.assertFalse((self.root / "successors").exists())

    def test_transitive_host_change_rejected(self):
        digest = self.seal()
        (self.root / "components/cards/host/card_selection_host.py").write_text("changed\n")
        with self.assertRaisesRegex(ValueError, "release_source_mismatch"):
            self.verify(digest)

    def test_added_source_rejected_but_documentation_does_not_rebind_release(self):
        digest = self.seal()
        (self.root / "apps/bridge/README.md").write_text("usage\n")
        self.verify(digest)
        (self.root / "apps/bridge/client/additional.py").write_text("new\n")
        with self.assertRaisesRegex(ValueError, "release_source_mismatch"):
            self.verify(digest)

    def test_changed_manifest_requires_retained_digest(self):
        digest = self.seal()
        self.release["target"] = "cards"
        self.seal()
        with self.assertRaisesRegex(ValueError, "release_identity"):
            self.verify(digest)

    def test_failed_or_incomplete_gate_is_not_a_release(self):
        for field, value in (("status", "failed"), ("suite", "python"), ("checks", {}),
                             ("checks", {"behavior": {"status": "failed"}}), ("target", "cards")):
            with self.subTest(field=field, value=value):
                before = self.release[field]
                self.release[field] = value
                with self.assertRaises(ValueError):
                    self.verify(self.seal())
                self.release[field] = before

    def test_links_and_nonregular_inputs_rejected(self):
        digest = self.seal()
        original = self.root / "apps/bridge/client/run_live.py"
        original.unlink()
        original.symlink_to(self.root / "check.py")
        with self.assertRaisesRegex(ValueError, "source_link"):
            self.verify(digest)
        original.unlink()
        original.mkdir()
        with self.assertRaisesRegex(ValueError, "source_shape"):
            read_regular(original)


class ProjectBoundaryTests(unittest.TestCase):
    def test_development_does_not_require_frozen_release_policy(self):
        files = self.project('<Compile Include="../../../components/events/core/Core.cs" />')
        files['apps/bridge/production/Sts2AgentBridge.csproj'] = files.pop(
            'apps/bridge/production/bridge.csproj')
        validate_sources(files, ['bridge'])
        validate_sources(files, ['bridge'], release=True)

    def project(self, entry):
        return {"apps/bridge/production/bridge.csproj": (
            '<Project><PropertyGroup><EnableDefaultCompileItems>false</EnableDefaultCompileItems>'
            '</PropertyGroup><ItemGroup>' + entry + '</ItemGroup></Project>').encode(),
                "components/events/core/Core.cs": b"[MegaCrit.Sts2.Core.Modding.ModInitializer(\"Initialize\")] public class Core {}"}

    def test_explicit_current_dependency(self):
        files = self.project('<Compile Include="../../../components/events/core/Core.cs" />')
        _, compiled = project_closure(files, "apps/bridge/production/bridge.csproj")
        self.assertEqual(compiled, {"components/events/core/Core.cs"})

    def test_missing_dynamic_external_and_historical_inputs_rejected(self):
        entries = (
            '<Compile Include="../../../successors/generic_event_v7/core/Core.cs" />',
            '<Compile Include="/private/tmp/Core.cs" />', '<Compile Include="*.cs" />',
            '<ProjectReference Include="missing.csproj" />', '<Import Project="unsafe.props" />',
            '<PackageReference Include="Unexpected" />', '<Exec Command="unexpected" />',
            '<Reference Include="sts2"><HintPath>$(STS2GameDataDir)/sts2.dll</HintPath><Private>true</Private></Reference>',
        )
        for entry in entries:
            with self.subTest(entry=entry), self.assertRaises(ValueError):
                project_closure(self.project(entry), "apps/bridge/production/bridge.csproj")


if __name__ == "__main__":
    unittest.main()

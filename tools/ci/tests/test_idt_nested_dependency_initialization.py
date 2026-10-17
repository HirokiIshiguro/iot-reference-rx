"""Exercise the production nested initializer and unchanged capture guard."""
from pathlib import Path
import hashlib
import importlib.util
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
PWSH = shutil.which("pwsh")
CLI = ROOT / "tools/rx_e2studio_cli.ps1"
MATRIX = ROOT / "tools/test_build_rx_idt.ps1"
AGENT_PATH = "Middleware/FreeRTOS/coreMQTT-Agent"
spec = importlib.util.spec_from_file_location("nested_capture_guard", ROOT / "tools/idt_source_manifest.py")
manifest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manifest)


def ps_quote(value):
    return "'" + str(value).replace("'", "''") + "'"


@unittest.skipUnless(PWSH and shutil.which("git"), "PowerShell 7 and Git required")
class IdtNestedInitializationTests(unittest.TestCase):
    def setUp(self):
        self.allowed_temp_root = Path(tempfile.gettempdir()).resolve()
        self.temporary = tempfile.TemporaryDirectory(prefix="idt-nested-init-")
        self.folder = Path(self.temporary.name).resolve()
        self.assertTrue(self.folder.is_relative_to(self.allowed_temp_root))
        self.addCleanup(self.safe_cleanup)

    def safe_cleanup(self):
        # Verify the absolute recursive-cleanup target is the allocated fixture.
        self.assertEqual(self.folder, Path(self.temporary.name).resolve())
        self.assertTrue(self.folder.is_relative_to(self.allowed_temp_root))
        self.temporary.cleanup()

    def git(self, folder, *arguments):
        result = subprocess.run(["git", "-c", "protocol.file.allow=always",
            "-c", "safe.directory=" + str(folder), "-C", str(folder), *arguments],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def repository(self, folder):
        folder.mkdir(parents=True)
        self.git(folder, "init", "-b", "main")
        self.git(folder, "config", "user.name", "Codex")
        self.git(folder, "config", "user.email", "codex@openai.com")
        return folder

    def commit(self, folder, message):
        self.git(folder, "add", "-A")
        self.git(folder, "commit", "-m", message)
        return self.git(folder, "rev-parse", "HEAD")

    def nested_pin_fixture(self):
        child = self.repository(self.folder / "child-origin")
        (child / "body.c").write_text("int fixture_child = 1;\n", encoding="utf-8")
        child_a = self.commit(child, "Fixture child A")
        (child / "body.c").write_text("int fixture_child = 2;\n", encoding="utf-8")
        child_b = self.commit(child, "Fixture child B")
        parent = self.repository(self.folder / "agent-origin")
        (parent / "body.c").write_text("int fixture_agent = 1;\n", encoding="utf-8")
        self.git(parent, "submodule", "add", child.as_uri(), "source/dependency/coreMQTT")
        self.git(parent / "source/dependency/coreMQTT", "checkout", child_a)
        parent_a = self.commit(parent, "Fixture parent A")
        self.git(parent / "source/dependency/coreMQTT", "checkout", child_b)
        parent_b = self.commit(parent, "Fixture parent B")
        source = self.repository(self.folder / "source")
        self.git(source, "submodule", "add", parent.as_uri(), AGENT_PATH)
        agent = source / AGENT_PATH
        self.git(agent, "checkout", parent_a)
        self.git(agent, "submodule", "update", "--init", "--recursive")
        self.commit(source, "Fixture source old pin")
        self.git(agent, "checkout", parent_b)
        self.commit(source, "Fixture source new parent with old nested HEAD")
        self.assertEqual(self.git(agent / "source/dependency/coreMQTT", "rev-parse", "HEAD"), child_a)
        # Deliberately invalid nested descriptors prove the two source-only
        # monorepos remain excluded by the existing production helper.
        for excluded in ("Middleware/FreeRTOS-Plus-CLI", "Middleware/freertos_plus"):
            folder = source / excluded
            folder.mkdir(parents=True)
            (folder / ".gitmodules").write_text("invalid fixture descriptor\n", encoding="utf-8")
            with (source / ".gitmodules").open("a", encoding="utf-8") as handle:
                handle.write('\n[submodule "' + excluded + '"]\n path = ' + excluded + '\n url = file:///unused\n')
        policy = self.folder / "fixture-git-policy.cfg"
        policy.write_text("[protocol \"file\"]\n allow = always\n", encoding="utf-8")
        self.git(source, "config", "include.path", str(policy))
        return source, agent, parent_b, child_b

    def initialize(self, source):
        harness = self.folder / "initialize.ps1"
        harness.write_text("$ErrorActionPreference='Stop'\n. " + ps_quote(CLI) +
            "\nInitialize-RxBuildDependencies -ProjectRoot " + ps_quote(source) + "\n", encoding="utf-8")
        result = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-File", str(harness)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=40)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def capture(self, source):
        agent_body = source / AGENT_PATH / "body.c"
        with patch.object(manifest, "dependency_paths", return_value=[AGENT_PATH]), \
             patch.object(manifest, "_files", return_value={AGENT_PATH + "/body.c": agent_body}):
            return manifest.capture_dependency_provenance(source, "rx72n-ethernet")

    def test_parent_upgrade_is_initialized_before_pristine_capture(self):
        source, agent, parent_b, child_b = self.nested_pin_fixture()
        with self.assertRaisesRegex(ValueError, "Dependency original sources changed before capture"):
            self.capture(source)
        self.initialize(source)
        self.assertEqual(self.git(agent / "source/dependency/coreMQTT", "rev-parse", "HEAD"), child_b)
        result = self.capture(source)
        self.assertEqual(result["submodule_shas"][AGENT_PATH], parent_b)
        text = MATRIX.read_text(encoding="utf-8-sig")
        self.assertLess(text.index("Initialize-RxBuildDependencies -ProjectRoot $root"),
                        text.index("'idt_source_manifest.py') capture"))

    def test_initializer_preserves_body_change_and_guard_still_rejects_it(self):
        source, agent, _, _ = self.nested_pin_fixture()
        self.initialize(source)
        self.capture(source)
        body = agent / "body.c"
        body.write_text("int deliberately_changed_fixture = 7;\n", encoding="utf-8")
        before = hashlib.sha256(body.read_bytes()).hexdigest()
        self.initialize(source)
        self.assertEqual(hashlib.sha256(body.read_bytes()).hexdigest(), before)
        with self.assertRaisesRegex(ValueError, "Dependency original sources changed before capture"):
            self.capture(source)


if __name__ == "__main__":
    unittest.main()

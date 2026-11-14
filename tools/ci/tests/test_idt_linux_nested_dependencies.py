"""Use local Git repositories to check Linux nested-pin initialization."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.idt import initialize_linux_dependencies as nested

ROOT = Path(__file__).resolve().parents[3]
GIT = shutil.which("git")


@unittest.skipUnless(GIT, "Git required")
class LinuxNestedDependenciesTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="idt-linux-nested-")
        self.root = Path(self.temporary.name).resolve()
        self.addCleanup(self.cleanup_fixture)
        self.env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1",
                    "GIT_CONFIG_GLOBAL": os.devnull, "GIT_ALLOW_PROTOCOL": "file"}

    def cleanup_fixture(self):
        self.assertEqual(self.root, Path(self.temporary.name).resolve())
        self.assertTrue(self.root.is_relative_to(Path(tempfile.gettempdir()).resolve()))
        self.temporary.cleanup()

    def git(self, folder, *arguments):
        return subprocess.check_output([GIT, "-C", str(folder), *arguments], env=self.env,
                                       stderr=subprocess.PIPE, text=True).strip()

    def repository(self, name):
        path = self.root / name
        path.mkdir()
        self.git(path, "init", "-b", "main")
        self.git(path, "config", "user.name", "Codex")
        self.git(path, "config", "user.email", "codex@openai.com")
        return path

    def commit(self, path):
        self.git(path, "add", "-A")
        self.git(path, "commit", "-m", "fixture")
        return self.git(path, "rev-parse", "HEAD")

    def test_windows_exclusions_are_read_and_other_syntax_is_rejected(self):
        helper = ROOT / "tools/rx_e2studio_cli.ps1"
        self.assertEqual(nested.source_only_paths(helper), ("Middleware/FreeRTOS-Plus-CLI", "Middleware/freertos_plus"))
        invalid = self.root / "invalid.ps1"
        invalid.write_text("$sourceOnly = @('first', $dynamic)\n", encoding="utf-8")
        with self.assertRaises(ValueError): nested.source_only_paths(invalid)

    def test_git_environment_drops_oidc_and_keeps_runner_git_inputs(self):
        config = SimpleNamespace(search_path="/reviewed/bin", home="/reviewed/home")
        env = nested.git_environment({"CI_JOB_TOKEN": "fixture", "RX_OIDC_ID_TOKEN": "discard",
                                      "AWS_SECRET_ACCESS_KEY": "discard", "GIT_CONFIG_COUNT": "1",
                                      "GIT_TRACE": "discard", "GIT_DIR": "/unreviewed", "PATH": "/unreviewed"}, config)
        self.assertEqual(env["CI_JOB_TOKEN"], "fixture")
        self.assertEqual(env["GIT_CONFIG_COUNT"], "1")
        self.assertEqual(env["PATH"], "/reviewed/bin")
        for name in ("RX_OIDC_ID_TOKEN", "AWS_SECRET_ACCESS_KEY", "GIT_TRACE", "GIT_DIR"):
            self.assertNotIn(name, env)

    def test_nested_pin_is_initialized_but_windows_source_only_roots_are_not(self):
        child = self.repository("child")
        (child / "body.c").write_text("public fixture\n", encoding="utf-8")
        child_sha = self.commit(child)
        parent = self.repository("parent")
        (parent / "parent.c").write_text("parent\n", encoding="utf-8")
        self.git(parent, "submodule", "add", child.as_uri(), "source/dependency/coreMQTT")
        self.git(parent, "submodule", "add", child.as_uri(), "test/disabled")
        self.git(parent, "config", "--file", ".gitmodules", "submodule.test/disabled.update", "none")
        self.commit(parent)
        source = self.repository("source")
        paths = ("Middleware/FreeRTOS/coreMQTT-Agent", "Middleware/FreeRTOS-Plus-CLI", "Middleware/freertos_plus")
        for relative in paths:
            self.git(source, "submodule", "add", parent.as_uri(), relative)
        (source / "tools").mkdir()
        shutil.copyfile(ROOT / "tools/rx_e2studio_cli.ps1", source / "tools/rx_e2studio_cli.ps1")
        self.commit(source)
        policy = self.root / "policy.cfg"
        policy.write_text('[protocol "file"]\n allow = always\n', encoding="utf-8")
        self.git(source, "config", "include.path", str(policy))
        agent_child = source / paths[0] / "source/dependency/coreMQTT"
        self.assertFalse((agent_child / "body.c").exists())
        actual_run = subprocess.run
        def skip_update(command, **kwargs):
            if "submodule" in command and "update" in command:
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            return actual_run(command, **kwargs)
        with patch.object(nested.subprocess, "run", side_effect=skip_update):
            with self.assertRaisesRegex(RuntimeError, "missing or differs"):
                nested.initialize(source, GIT, self.env)
        self.assertEqual(nested.initialize(source, GIT, self.env), 1)
        self.assertEqual(self.git(agent_child, "rev-parse", "HEAD"), child_sha)
        self.assertTrue((agent_child / "body.c").is_file())
        self.assertFalse((source / paths[0] / "test/disabled/body.c").exists())
        for relative in paths[1:]:
            self.assertFalse((source / relative / "source/dependency/coreMQTT/body.c").exists())
        self.assertEqual(self.git(source, "status", "--porcelain=v1", "--untracked-files=all"), "")


if __name__ == "__main__":
    unittest.main()

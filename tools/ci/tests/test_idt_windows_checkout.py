"""Keep all Windows RX build entry points on the fresh checkout policy."""
from pathlib import Path
import os
import re
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ".rx_windows_canonical_checkout"
WINDOWS_BUILD_JOBS = {
    "build_rx72n_ether",
    "build_rx65n_bg96",
    "idt_source_matrix",
    "build_rx671_wifi",
    "build_rx671_wifi_fleet",
    "test_rx671_wifi_idt",
    "package_rx671_ota_artifacts",
}


def sections(text):
    starts = list(re.finditer(r"(?m)^([\w.-]+):\s*$", text))
    return {
        match.group(1): text[match.end():starts[index + 1].start()
                            if index + 1 < len(starts) else len(text)]
        for index, match in enumerate(starts)
    }


def fields(text, indent):
    pairs = re.findall(r"(?m)^" + " " * indent + r"(\w+):[ \t]*([^\n]+)$", text)
    return {key: value.strip().strip('"') for key, value in pairs}


def parents(block):
    match = re.search(r"(?m)^  extends:[ \t]*([^\n]*)$", block)
    if not match:
        return []
    if match.group(1):
        return [match.group(1)]
    values = []
    for line in block[match.end():].splitlines():
        if not line.strip():
            continue
        item = re.fullmatch(r"    - ([\w.-]+)", line)
        if not item:
            break
        values.append(item.group(1))
    return values


class IdtWindowsCheckoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.blocks = sections((ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8"))
        cls.policy = fields(cls.blocks[TEMPLATE], 4)

    def variables(self, name):
        result = {}
        for parent in parents(self.blocks[name]):
            result.update(self.variables(parent))
        result.update(fields(self.blocks[name], 4))
        return result

    def test_all_rx_build_entry_points_get_fresh_checkout_before_sources(self):
        users = {name for name, block in self.blocks.items() if TEMPLATE in parents(block)}
        self.assertEqual(users, WINDOWS_BUILD_JOBS)
        for name in WINDOWS_BUILD_JOBS:
            with self.subTest(job=name):
                variables = self.variables(name)
                self.assertEqual(variables["GIT_STRATEGY"], "clone")
                count = int(variables["GIT_CONFIG_COUNT"])
                options = {variables[f"GIT_CONFIG_KEY_{i}"]: variables[f"GIT_CONFIG_VALUE_{i}"]
                           for i in range(count)}
                self.assertEqual(options, {
                    "core.longpaths": "true",
                    "core.autocrlf": "false",
                    "core.eol": "lf",
                })

    def test_existing_native_fleet_and_matrix_settings_survive_inheritance(self):
        self.assertIn(".rx_idt_job", parents(self.blocks["test_rx671_wifi_idt"]))
        self.assertIn(".rx671_wifi_fleet_rules", parents(self.blocks["build_rx671_wifi_fleet"]))
        for name in ("idt_source_matrix", "test_rx671_wifi_idt"):
            with self.subTest(job=name):
                variables = self.variables(name)
                self.assertEqual(variables["GIT_SUBMODULE_STRATEGY"], "normal")
                self.assertEqual(variables["PYTHONUTF8"], "1")
        self.assertNotIn(TEMPLATE, parents(self.blocks[".rx_idt_job"]))
        self.assertNotIn("GIT_STRATEGY", fields(self.blocks["variables"], 2))

    @unittest.skipUnless(shutil.which("git"), "Git is required to check config inheritance")
    def test_git_config_environment_preserves_other_url_rewrite(self):
        environment = dict(os.environ)
        environment.update(self.policy)

        def git(*arguments):
            return subprocess.check_output(
                ["git", "-C", str(ROOT), *arguments], env=environment,
                text=True, encoding="utf-8", timeout=10,
            ).strip()

        self.assertEqual(git("config", "--get", "core.longpaths"), "true")
        self.assertEqual(git("config", "--get", "core.autocrlf"), "false")
        self.assertEqual(git("config", "--get", "core.eol"), "lf")
        # --get-url resolves a harmless URL locally; it makes no network call.
        self.assertEqual(git(
            "-c", "url.https://example.invalid/checkout/.insteadOf=fixture://checkout/",
            "ls-remote", "--get-url", "fixture://checkout/source.git",
        ), "https://example.invalid/checkout/source.git")


if __name__ == "__main__":
    unittest.main()

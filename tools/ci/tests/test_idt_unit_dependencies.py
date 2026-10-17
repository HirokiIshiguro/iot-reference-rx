"""The source-only CI job uses exactly the original inputs its host tests read."""
from pathlib import Path
import hashlib
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[3]
BOOT_PIN = "8e19b0cdeeaab06f22fa0636f4cd469218edc6c1"
REQUIRED = {
    "Middleware/FreeRTOS/FreeRTOS-Kernel": (
        "9b777ae5c5b8e9e456065a00294d1e5f5f9facf5", ("include/task.h",)),
    "Middleware/FreeRTOS-Plus-CLI": (
        "152cf36d6775bce6026a791845af12201aae703d", (
            "FreeRTOS-Plus/Source/FreeRTOS-Plus-CLI/FreeRTOS_CLI.c",
            "FreeRTOS-Plus/Source/FreeRTOS-Plus-CLI/FreeRTOS_CLI.h")),
    "Test/Unity": ("22777c4810de3e3a4cb521a05eca2752fccd00ea", (
        "src/unity.h", "src/unity.c", "extras/fixture/src/unity_fixture.h",
        "extras/fixture/src/unity_fixture.c", "extras/memory/src/unity_memory.c")),
    "Test/FreeRTOS-Libraries-Integration-Tests": (
        "0a0a92160a81c5cba008e472203513bd0cfb4c7a", ("src/pkcs11/core_pkcs11_test.c",)),
    "Projects/boot_loader_ck_rx65n/e2studio_ccrx/lib/rx_bootloader": (BOOT_PIN, ("config/rx65n.h",)),
    "Projects/boot_loader_rx671_ek/e2studio_ccrx/lib/rx_bootloader": (BOOT_PIN, ("config/rx671.h",)),
    "Projects/boot_loader_rx72n_envision_kit/e2studio_ccrx/lib/rx_bootloader": (BOOT_PIN, ("config/rx72n.h",)),
}


class IdtUnitDependencyTests(unittest.TestCase):
    def test_ci_initializes_only_the_seven_root_dependencies_before_source_only_tests(self):
        text = (ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8")
        job = text[text.index("idt_ci_contract:\n"):text.index(".rx_idt_job:\n")]
        self.assertRegex(job, r"(?m)^  stage: dependency_check$")
        self.assertRegex(job, r"(?m)^    GIT_SUBMODULE_STRATEGY: normal$")
        self.assertRegex(job, r'(?m)^    GIT_SUBMODULE_DEPTH: "1"$')
        paths = re.search(r"(?m)^    GIT_SUBMODULE_PATHS: >-\n((?:      [^\n]+\n)+)", job)
        self.assertIsNotNone(paths)
        selected = paths.group(1).split()
        self.assertEqual(set(REQUIRED), set(selected))
        self.assertEqual(len(REQUIRED), len(selected), "Duplicate path or broad selection")
        self.assertNotIn("recursive", paths.group())
        self.assertNotIn("--remote", job)
        self.assertNotIn("--recursive", job)
        self.assertNotIn("GIT_SUBMODULE_FORCE_HTTPS", job, "No custom authentication rewrite is needed")
        self.assertIn("tools.ci.tests.test_idt_unit_dependencies", job)
        self.assertNotIn("tools/idt/run_idt.py", job, "Unit job may not launch hardware/native qualification")

    def test_required_headers_and_runner_are_bytes_from_the_registered_original_gitlinks(self):
        for relative, (expected, files) in REQUIRED.items():
            with self.subTest(dependency=relative):
                tree = subprocess.check_output(
                    ["git", "ls-tree", "HEAD", "--", relative], cwd=ROOT
                ).decode("utf-8").strip()
                self.assertEqual("160000 commit " + expected + "\t" + relative, tree)
                folder = ROOT / relative
                self.assertTrue((folder / ".git").exists(), "CI must initialize original gitlink: " + relative)
                actual = subprocess.check_output(
                    ["git", "-C", str(folder), "rev-parse", "HEAD"], cwd=ROOT
                ).decode("ascii").strip()
                self.assertEqual(expected, actual, "Cached checkout is not the registered pin: " + relative)
                for name in files:
                    original = subprocess.check_output(
                        ["git", "-C", str(folder), "show", expected + ":" + name], cwd=ROOT)
                    path = folder / name
                    self.assertTrue(path.is_file(), "Original input absent: " + relative + "/" + name)
                    self.assertEqual(hashlib.sha256(original).hexdigest(),
                                     hashlib.sha256(path.read_bytes()).hexdigest(),
                                     "Original input differs: " + relative + "/" + name)


if __name__ == "__main__":
    unittest.main()

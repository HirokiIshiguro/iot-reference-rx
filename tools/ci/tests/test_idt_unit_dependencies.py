"""The source-only CI job uses exactly the original inputs its host tests read."""
from pathlib import Path
import hashlib
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[3]
BOOT_PIN = "b46927ea19b6b0a3b69d4790c13ca50a67b9c155"
REQUIRED = {
    "Middleware/FreeRTOS/FreeRTOS-Kernel": (
        "9b777ae5c5b8e9e456065a00294d1e5f5f9facf5", ("include/task.h",)),
    "Middleware/FreeRTOS-Plus-CLI": (
        "152cf36d6775bce6026a791845af12201aae703d", (
            "FreeRTOS-Plus/Source/FreeRTOS-Plus-CLI/FreeRTOS_CLI.c",
            "FreeRTOS-Plus/Source/FreeRTOS-Plus-CLI/FreeRTOS_CLI.h")),
    "Middleware/Renesas/r_flash_rx": (
        "5304d35e22002d0b0b0d24ae7773c64788ede5b3", (
            "Makefile", "r_flash_rx_vx.xx_extend.mdf", "r_flash_rx_vx.xx.xml",
            "r_flash_rx_vx.xx/r_config/r_flash_rx_config.h",
            "r_flash_rx_vx.xx/r_flash_rx/r_flash_rx_if.h")),
    "Middleware/Renesas/rm_littlefs_rx": (
        "85d3dbb719138e4e677a66767e8776e762b3643e", (
            "rm_littlefs_rx_vx.xx/rm_littlefs_rx/rm_littlefs_rx_if.h",
            "rm_littlefs_rx_vx.xx/rm_littlefs_rx/src/rm_littlefs_rx.c",)),
    "Middleware/Renesas/rm_rtos_abstraction_rx": (
        "5818cdfbda661d098fd028bf6975847d5af2c491", (
            "rm_rtos_abstraction_rx_vx.xx/rm_rtos_abstraction_rx/rm_rtos_abstraction_rx_if.h",)),
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

    def test_littlefs_replay_uses_the_registered_child_bytes(self):
        parent = ROOT / "Middleware/Renesas/rm_littlefs_rx"
        relative = "rm_littlefs_rx_vx.xx/rm_littlefs_rx/third_party/littlefs"
        expected = "6cb4e86540eca0d9ba62500a298385c9d863c8be"
        tree = subprocess.check_output(["git", "ls-tree", "HEAD", "--", relative], cwd=parent).decode().strip()
        self.assertEqual("160000 commit " + expected + "\t" + relative, tree)
        child = parent / relative
        self.assertEqual(expected, subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=child).decode().strip())
        for name in ("lfs.c", "lfs.h", "lfs_util.c", "lfs_util.h"):
            original = subprocess.check_output(["git", "show", expected + ":" + name], cwd=child)
            self.assertEqual(hashlib.sha256(original).digest(), hashlib.sha256((child / name).read_bytes()).digest())


if __name__ == "__main__":
    unittest.main()

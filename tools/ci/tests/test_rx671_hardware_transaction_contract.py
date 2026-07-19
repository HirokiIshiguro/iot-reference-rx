from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def job_block(ci: str, name: str, next_name: str) -> str:
    return ci.split(f"{name}:\n", maxsplit=1)[1].split(
        f"\n{next_name}:\n", maxsplit=1
    )[0]


class Rx671HardwareTransactionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ci = (ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8")

    def test_rpi1_jobs_hold_the_standalone_benchmark_lock(self) -> None:
        template = job_block(
            self.ci, ".rx671_wifi_linux_hw_job", ".aws_cli_windows_job"
        )

        self.assertIn(
            'RX671_RPI1_HARDWARE_LOCK_PATH: '
            '"/tmp/ek-rx671-rpi1-hardware.lock"',
            self.ci,
        )
        self.assertIn('exec 9>>"${RX671_RPI1_HARDWARE_LOCK_PATH}"', template)
        self.assertIn(
            'flock -w "${RX671_RPI1_HARDWARE_LOCK_TIMEOUT_SECONDS}" 9',
            template,
        )
        self.assertGreater(
            template.index("exec 9>"), template.index("python -m pip install")
        )

    def test_uart_observation_reflashes_inside_the_job_lock(self) -> None:
        job = job_block(self.ci, "test_rx671_wifi", "test_rx72n_ether_mqtt")

        ordered_tokens = (
            'mot="$CI_PROJECT_DIR/artifacts/build_rx671_wifi/aws_wifi_rx671_ek.mot"',
            "Atomic RX671 reflash before UART observation",
            "-p -v -reset -noquery",
            "tools/ci/test_rx671_wifi_uart.py",
        )
        positions = [job.index(token) for token in ordered_tokens]
        self.assertEqual(positions, sorted(positions))

    def test_both_split_jobs_extend_the_locked_template(self) -> None:
        flash = job_block(self.ci, "flash_rx671_wifi", "flash_rx72n_ether")
        test = job_block(self.ci, "test_rx671_wifi", "test_rx72n_ether_mqtt")

        for job in (flash, test):
            self.assertIn("- .rx671_wifi_linux_hw_job", job)


if __name__ == "__main__":
    unittest.main()

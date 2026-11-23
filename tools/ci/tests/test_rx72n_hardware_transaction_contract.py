from __future__ import annotations

import unittest
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def job_block(ci: str, name: str, next_name: str | None = None) -> str:
    match = re.search(r"(?m)^" + re.escape(name) + r":\n", ci)
    if match is None:
        raise AssertionError("Missing CI job: " + name)
    following = re.search(r"(?m)^[A-Za-z0-9_.-]+:[ \t]*\n", ci[match.end():])
    end = match.end() + following.start() if following else len(ci)
    return ci[match.start():end]


class Rx72nHardwareTransactionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ci = (ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8")
        cls.rfp_wrapper = (ROOT / "tools" / "rfp_cli_locked.sh").read_text(
            encoding="utf-8"
        )


    def test_rfp_wrapper_uses_a_distinct_per_call_lock(self) -> None:
        self.assertIn(
            "RX72N_RFP_CLI_LOCK_DIR:-/tmp/rx72n-e2lite-rfp-cli.lock.d",
            self.rfp_wrapper,
        )
        self.assertIn('LOCK_FILE="${LOCK_DIR}/rfp-cli.lock"', self.rfp_wrapper)
        self.assertNotIn("RFP_CLI_LOCK_HELD", self.rfp_wrapper)
        self.assertNotIn("/tmp/e2lite-rfp-cli.lock.d", self.rfp_wrapper)











if __name__ == "__main__":
    unittest.main()

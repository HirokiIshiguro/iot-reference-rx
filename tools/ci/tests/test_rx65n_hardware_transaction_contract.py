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


class Rx65nHardwareTransactionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ci = (ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8")








    def test_tsip_ota_alias_overrides_static_thing_name(self) -> None:
        source = (
            ROOT / "tools" / "bg96_bootloader_integration.py"
        ).read_text(encoding="utf-8")
        provision = source.split(
            "def provision_mqtt_credentials(", maxsplit=1
        )[1].split("\ndef ", maxsplit=1)[0]
        skip_private_key = provision.split(
            "if args.skip_private_key:", maxsplit=1
        )[1].split("\n    else:", maxsplit=1)[0]

        self.assertIn(
            "env_text(\n            DYNAMIC_THING_NAME_VARS\n        )",
            skip_private_key,
        )
        self.assertIn("if dynamic_thing_name:", skip_private_key)
        self.assertLess(
            skip_private_key.index("if dynamic_thing_name:"),
            skip_private_key.index("env_text(THING_NAME_VARS)"),
        )
        self.assertIn(
            "client_cert, cert_var = env_text(CLIENT_CERT_VARS)",
            skip_private_key,
        )


if __name__ == "__main__":
    unittest.main()

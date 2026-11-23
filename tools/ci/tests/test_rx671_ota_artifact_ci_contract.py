from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
CI_PATH = REPO_ROOT / ".gitlab-ci.yml"
GITIGNORE_PATH = REPO_ROOT / ".gitignore"
ROOT_README_PATH = REPO_ROOT / "README.md"
README_PATH = REPO_ROOT / "Projects" / "aws_wifi_rx671_ek" / "README.md"
LAYOUT_PATH = (
    REPO_ROOT
    / "Projects"
    / "aws_wifi_rx671_ek"
    / "e2studio_ccrx"
    / "OTA_FLASH_LAYOUT.md"
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="strict")


class Rx671OtaArtifactCiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ci = read(CI_PATH)
        cls.root_readme = read(ROOT_README_PATH)
        cls.readme = read(README_PATH)
        cls.layout = read(LAYOUT_PATH)
        cls.gitignore = read(GITIGNORE_PATH)





    def test_downloaded_ci_artifacts_do_not_dirty_formal_source_provenance(self) -> None:
        self.assertRegex(self.gitignore, r"(?m)^/artifacts/$")

    def test_user_docs_define_temporary_profile_and_scope_boundary(self) -> None:
        combined = self.readme + "\n" + self.layout
        for marker in (
            "bank.single",
            "bank.dual",
            "0x000F0000",
            "0xFFF00300",
            "PFRAM2",
            "RPFRAM2",
            "0.1.0",
            "0.1.1",
            "build/rx671-ota",
            "SDHI_DIV_2",
            "SDHI_DIV_8",
        ):
            self.assertIn(marker, combined)

        self.assertRegex(
            combined,
            r"(?is)byte.for.byte|byte-for-byte|バイト単位|バイト列",
        )
        self.assertRegex(
            combined,
            r"(?is)package job alone does not prove.*hardware OTA success|"
            r"package job単体は実機AWS OTA成功を証明しない",
        )
        self.assertRegex(
            combined,
            r"(?is)fixed-SHA focused hardware pipeline.*proves|"
            r"focused hardware pipeline.*実機AWS OTA",
        )
        self.assertIn("test_rx671_wifi_ota_atomic", combined)
        self.assertIn("cleanup_rx671_wifi_ota", combined)
        self.assertIn("LIBRARY_LOG_LEVEL=LOG_NONE", combined)
        self.assertIn("configPRINTF", combined)
        for boundary in (
            "0xFFE00000-0xFFEEFFFF",
            "0xFFF00000-0xFFFEFFFF",
            "0xFFEF0000-0xFFEFFFFF",
            "0xFFFF0000-0xFFFFFFFF",
        ):
            self.assertIn(boundary, combined)
        self.assertRegex(
            self.layout,
            r"(?is)-range.*-erase.*-erase-chip.*(?:not|preserve|使用しない)",
        )
        self.assertRegex(
            combined,
            r"(?is)key-load.*found\.|key load.*found\.|key-load開始.*found\.",
        )
        self.assertRegex(
            combined,
            r"(?is)32 KiB.*(?:progress|進捗).*(?:ACK|flow-control)|"
            r"(?:ACK|flow-control).*32 KiB",
        )
        self.assertIn("(768/768KB)", combined)
        self.assertIn("completed installing firmware", combined)
        self.assertRegex(
            self.layout,
            r"(?is)208 KiB.*32 KiB.*TLS 1\.2|"
            r"32 KiB.*208 KiB.*TLS 1\.2",
        )
        for stream_memory_contract in (
            "blocks/request",
            "OTA event data buffer",
            "192",
            "785,920 bytes",
            "pipeline #9580",
            "callback",
            "30,116 bytes",
            "0x00058A5B",
        ):
            self.assertIn(stream_memory_contract, self.layout)
        self.assertIn("AWS_IOT_MQTT_REQUIRE_TLS_VERSION_1_2=1", combined)
        self.assertIn("RX671 OTA fatal:", combined)
        for notification_contract in (
            "configTASK_NOTIFICATION_ARRAY_ENTRIES",
            "index 2",
            "index 3",
            "4要素",
            "Smart Configurator",
            "compile-time guard",
        ):
            self.assertIn(notification_contract, self.layout)
        self.assertRegex(
            self.layout,
            r"(?s)OTAだけの\s*一時profileではなく",
        )
        for event_policy_contract in (
            "$aws/events/job/<jobId>/cancellation_in_progress",
            "iot:Subscribe",
            "iot:Receive",
            "topicfilter/",
            "pipeline専用policy",
            "preflight journal",
            "480秒",
            "DeleteConflictException",
            "最大300秒",
        ):
            self.assertIn(event_policy_contract, self.layout)
        self.assertRegex(
            self.layout,
            r"(?s)`#` / `\*` wildcard.*追加しない",
        )
        self.assertRegex(
            self.layout,
            r"(?is)(?:ServerHello|最初の受信).*pvPortMalloc|"
            r"pvPortMalloc.*(?:ServerHello|最初の受信)",
        )
        self.assertRegex(
            combined,
            r"(?is)same source SHA.*hardware job.*cleanup job|"
            r"同一source SHA.*hardware.*cleanup",
        )
        self.assertRegex(
            self.readme,
            r"(?is)TSIP and TLS 1\.3\s+OTA remain\s+unverified",
        )
        self.assertRegex(
            self.layout,
            r"(?is)TSIP OTA.*software / TSIP TLS 1\.3 OTA.*証明範囲外.*`—`",
        )

        for csp_boundary in (
            "-erase-chip",
            "claim-free",
            ".rx671-ota-secrets",
            "証明しない",
        ):
            self.assertIn(csp_boundary, self.layout)

        published_docs = self.root_readme + "\n" + combined
        for fixed_evidence in (
            "d505b3fd",
            "pipeline #9584",
            "package #61361",
            "create #61362",
            "hardware #61363",
            "cleanup #61364",
            "192/192 block",
            "25,584 bytes",
            "minimum 16 network buffers",
            "WHD maximum use 1/8",
            "Job execution `SUCCEEDED`",
        ):
            self.assertIn(fixed_evidence, published_docs)

        for stale_false_success in (
            "pipeline #9562",
            "b61640f3",
            "#61197",
            "#61198",
            "#61199",
            "#61200",
        ):
            self.assertNotIn(stale_false_success, published_docs)

        self.assertIn("image_commit_observed=false", self.layout)
        self.assertIn("Accepted and committed final image.", combined)
        self.assertRegex(
            combined,
            r"(?is)(?:optional|任意).*Accepted and committed final image|"
            r"Accepted and committed final image.*(?:optional|任意)",
        )
        self.assertRegex(
            self.layout,
            r"(?is)image acceptance.*OTA成功通知.*AWS.*SUCCEEDED|"
            r"image acceptance.*AWS.*SUCCEEDED",
        )


if __name__ == "__main__":
    unittest.main()

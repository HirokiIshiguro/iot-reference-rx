from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PROJECT = ROOT / "Projects/aws_wifi_rx671_ek/e2studio_ccrx"


class Rx671OtaBuildProfileContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.build = (ROOT / "tools/build_headless_rx671_wifi.ps1").read_text(
            encoding="utf-8"
        )
        cls.demo_config = (
            PROJECT / "src/frtos_config/demo_config.h"
        ).read_text(encoding="utf-8")
        cls.identity = (
            PROJECT / "src/application_code/ota_image_identity.c"
        ).read_text(encoding="utf-8")
        cls.identity_header = (
            PROJECT / "src/application_code/ota_image_identity.h"
        ).read_text(encoding="utf-8")

    def test_version_input_is_optional_and_strictly_parsed(self) -> None:
        self.assertIn('[string]$OtaImageVersion = ""', self.build)
        self.assertIn("function ConvertFrom-OtaImageVersion", self.build)
        self.assertIn(
            "'^(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)$'",
            self.build,
        )
        self.assertIn("Major -gt 255", self.build)
        self.assertIn("Minor -gt 255", self.build)
        self.assertIn("Build -gt 65535", self.build)
        self.assertIn(
            "expected x.y.z with major/minor 0..255 and build 0..65535",
            self.build,
        )

    def test_default_e2studio_matches_current_rx_ci_toolchain(self) -> None:
        self.assertIn(
            '[string]$E2Studio = '
            '"C:\\Renesas\\e2_studio_2026_04_2\\eclipse\\e2studioc.exe"',
            self.build,
        )

    def test_ota_build_can_explicitly_disable_wifi_credentials(self) -> None:
        self.assertIn("[switch]$SkipWifiConfig", self.build)
        self.assertIn(
            "$useLocalJoinConfigForBuild = (-not $SkipWifiConfig.IsPresent)",
            self.build,
        )
        self.assertIn(
            "-SkipWifiConfig cannot be combined with "
            "-UseLocalJoinConfig or -WifiConfigFile.",
            self.build,
        )

    def test_version_is_passed_as_temporary_cproject_defines(self) -> None:
        self.assertIn('"APP_VERSION_MAJOR=$($otaImageVersionParts.Major)"', self.build)
        self.assertIn('"APP_VERSION_MINOR=$($otaImageVersionParts.Minor)"', self.build)
        self.assertIn('"APP_VERSION_BUILD=$($otaImageVersionParts.Build)"', self.build)
        self.assertRegex(
            self.build,
            re.compile(
                r"if \(\$null -ne \$otaImageVersionParts\) \{"
                r".*?APP_VERSION_MAJOR=.*?APP_VERSION_MINOR=.*?APP_VERSION_BUILD=",
                re.DOTALL,
            ),
        )
        self.assertIn(
            "[System.IO.File]::WriteAllBytes($cproject, $cprojectBytes)",
            self.build,
        )

    def test_normal_build_keeps_guarded_default_version(self) -> None:
        defaults = {
            "APP_VERSION_MAJOR": "0",
            "APP_VERSION_MINOR": "1",
            "APP_VERSION_BUILD": "0",
        }
        for macro, value in defaults.items():
            self.assertRegex(
                self.demo_config,
                rf"#ifndef {macro}\s+#define {macro}\s+\({value}\)\s+#endif",
            )

    def test_linked_identity_contains_human_readable_marker(self) -> None:
        self.assertIn(
            'extern const volatile char g_rx671_ota_image_version_marker[];',
            self.identity_header,
        )
        self.assertIn(
            "const volatile char g_rx671_ota_image_version_marker[]",
            self.identity,
        )
        self.assertIn('"RX671_OTA_IMAGE_VERSION="', self.identity)
        self.assertIn("RX671_OTA_STRINGIFY(APP_VERSION_MAJOR)", self.identity)
        self.assertIn("RX671_OTA_STRINGIFY(APP_VERSION_MINOR)", self.identity)
        self.assertIn("RX671_OTA_STRINGIFY(APP_VERSION_BUILD)", self.identity)
        self.assertIn("function Add-CProjectLinkerOption", self.build)
        self.assertIn(
            '"-symbol_forbid=_g_rx671_ota_image_version_marker"',
            self.build,
        )

    def test_build_fails_closed_when_mot_marker_is_missing(self) -> None:
        self.assertIn("function Assert-SRecordContainsAsciiMarker", self.build)
        self.assertIn(
            '$expectedOtaImageMarker = "RX671_OTA_IMAGE_VERSION=$effectiveOtaImageVersion"',
            self.build,
        )
        self.assertIn(
            "Assert-SRecordContainsAsciiMarker "
            "-Path $motOutput -Marker $expectedOtaImageMarker",
            self.build,
        )
        self.assertIn("OTA image marker was not found in generated MOT", self.build)


if __name__ == "__main__":
    unittest.main()

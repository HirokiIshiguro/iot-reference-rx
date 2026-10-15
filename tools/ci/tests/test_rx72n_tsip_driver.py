"""Reject stale/custom TSIP inputs while accepting the official RDP selection."""
import hashlib
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from tools.ci import check_rx72n_tsip_driver as checker


ROOT = Path(__file__).resolve().parents[3]
PROJECT = Path("Projects/aws_ether_rx72n_envision_kit_tsip/e2studio_ccrx")


def oid(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


class Rx72nTsipDriverTests(unittest.TestCase):
    def setUp(self):
        self.allowed = ROOT.parent.resolve()
        self.temporary = tempfile.TemporaryDirectory(prefix="tsip-checker-", dir=self.allowed)
        self.root = Path(self.temporary.name).resolve()
        self.assertTrue(self.root.is_relative_to(self.allowed))
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.assertEqual(self.root, Path(self.temporary.name).resolve())
        self.assertTrue(self.root.is_relative_to(self.allowed))
        self.temporary.cleanup()

    def driver_fixture(self):
        rdp = self.root / checker.RDP_PATH
        source = rdp / checker.DRIVER_PATH / "source.c"
        source.parent.mkdir(parents=True)
        source.write_bytes(b"/* official fixture with original CRLF */\r\n")
        return rdp, source, {source.relative_to(rdp).as_posix(): oid(source.read_bytes())}

    def metadata_fixture(self):
        project = self.root / PROJECT
        for relative in (".project", ".cproject", "aws_ether_rx72n_envision_kit_tsip.scfg",
                         ".settings/com.renesas.smc.e2studio.qe.xml",
                         "src/smc_gen/r_config/r_tsip_rx_config.h"):
            destination = project / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / PROJECT / relative, destination)
        component = next(n for n in ET.parse(project / "aws_ether_rx72n_envision_kit_tsip.scfg")
                         .getroot().iter("component") if n.get("display") == "r_tsip_rx")
        rdp = self.root / checker.RDP_PATH
        mdf = rdp / checker.MDF_PATH
        mdf.parent.mkdir(parents=True)
        mdf.write_text("<module>" + "".join('<property id="' + n.get("id") + '"/>'
                       for n in component.findall("gridItem")) + "</module>", encoding="utf-8")
        interface = rdp / checker.DRIVER_PATH / "r_tsip_rx_if.h"
        interface.parent.mkdir(parents=True)
        interface.write_text("#define TSIP_VERSION_MAJOR (1u)\n#define TSIP_VERSION_MINOR (24u)\n",
                             encoding="utf-8")
        return project

    def test_pinned_file_bytes_preserve_original_line_endings(self):
        rdp, source, expected = self.driver_fixture()
        checker.verify_pinned_files(rdp, expected)
        source.write_bytes(source.read_bytes().replace(b"\r\n", b"\n"))
        with self.assertRaisesRegex(RuntimeError, "official RDP bytes changed"):
            checker.verify_pinned_files(rdp, expected)

    def test_extra_or_missing_driver_files_are_rejected(self):
        rdp, source, expected = self.driver_fixture()
        extra = source.with_name("copied.c")
        extra.write_bytes(b"extra")
        with self.assertRaisesRegex(RuntimeError, "file set differs"):
            checker.verify_pinned_files(rdp, expected)
        extra.unlink()
        source.unlink()
        with self.assertRaisesRegex(RuntimeError, "file set differs"):
            checker.verify_pinned_files(rdp, expected)

    def test_custom_wait_hook_is_explicitly_rejected(self):
        rdp, source, expected = self.driver_fixture()
        source.write_bytes(b"TSIP_PRV_WAIT_LOOP_HOOK();\n")
        expected[source.relative_to(rdp).as_posix()] = oid(source.read_bytes())
        with self.assertRaisesRegex(RuntimeError, "custom wait hook"):
            checker.verify_pinned_files(rdp, expected)

    def test_root_gitlink_and_checkout_head_must_both_match_reviewed_pin(self):
        with patch.object(checker, "git", return_value=b"160000 commit wrong\tpath\n"):
            with self.assertRaisesRegex(RuntimeError, "root gitlink"):
                checker.verify_original_driver(self.root)
        gitlink = ("160000 commit " + checker.EXPECTED_RDP_SHA + "\t" + checker.RDP_PATH).encode()
        with patch.object(checker, "git", side_effect=[gitlink,
                          str(self.root / checker.RDP_PATH).encode(), b"wrong"]):
            with self.assertRaisesRegex(RuntimeError, "checkout HEAD"):
                checker.verify_original_driver(self.root)

    def test_official_metadata_selection_is_accepted(self):
        self.metadata_fixture()
        with patch.object(checker, "verify_original_driver"):
            result = checker.check(self.root)
        self.assertEqual(result["version"], "1.24")
        self.assertEqual(result["smart_config_settings"], 72)
        self.assertEqual(result["qe_settings"], 72)
        self.assertEqual(result["custom_wait_hook_present"], 0)

    def test_legacy_source_copy_is_rejected(self):
        project = self.metadata_fixture()
        legacy = project / "src/smc_gen/r_tsip_rx/copied.c"
        legacy.parent.mkdir(parents=True)
        legacy.write_bytes(b"old source")
        with patch.object(checker, "verify_original_driver"):
            with self.assertRaisesRegex(RuntimeError, "legacy copied"):
                checker.check(self.root)

    def test_custom_config_and_stale_qe_component_are_rejected(self):
        project = self.metadata_fixture()
        config = project / "src/smc_gen/r_config/r_tsip_rx_config.h"
        original = config.read_bytes()
        config.write_bytes(original + b"\n#define TSIP_CFG_WAIT_LOOP_HOOK_ENABLE (0)\n")
        with patch.object(checker, "verify_original_driver"):
            with self.assertRaisesRegex(RuntimeError, "custom wait-hook selectors"):
                checker.check(self.root)
        config.write_bytes(original)
        qe = project / ".settings/com.renesas.smc.e2studio.qe.xml"
        qe.write_bytes(qe.read_bytes().replace(b'r_tsip_rx1.24', b'r_tsip_rx1.23.saffti-custom'))
        with patch.object(checker, "verify_original_driver"):
            with self.assertRaisesRegex(RuntimeError, "QE TSIP component"):
                checker.check(self.root)

    def test_wrong_source_link_and_target_selection_are_rejected(self):
        project = self.metadata_fixture()
        link = project / ".project"
        original = link.read_bytes()
        link.write_bytes(original.replace(checker.DRIVER_PATH.encode(), b"old-copy"))
        with patch.object(checker, "verify_original_driver"):
            with self.assertRaisesRegex(RuntimeError, "canonical official"):
                checker.check(self.root)
        link.write_bytes(original)
        cproject = project / ".cproject"
        cproject.write_bytes(cproject.read_bytes().replace(checker.SOURCE_ENTRY.encode(),
                              b"Vendor/r_tsip_rx/src/targets/rx65n"))
        with patch.object(checker, "verify_original_driver"):
            with self.assertRaisesRegex(RuntimeError, "only the official RX72N TSIP target"):
                checker.check(self.root)


if __name__ == "__main__":
    unittest.main()

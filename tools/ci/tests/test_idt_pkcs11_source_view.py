"""Exercise the native editable facade/private pristine input boundary locally."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import idt_source_manifest as manifest
from tools.idt import pkcs11_source_view as view
from tools.ci.tests import test_idt_source_manifest as fixtures


@unittest.skipUnless(fixtures.GIT, "Local Git fixture objects required")
class Pkcs11SourceViewTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="pkcs11-source-view-")
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.source = self.folder / "source"
        self.runtime = self.folder / "runtime"
        self.runtime.mkdir()
        self.native = self.runtime / "source" / "native-source"
        self.native.parent.mkdir()
        self.target = "rx65n-bg96"
        # Two real submodule fixture objects are enough for this routing test;
        # the complete production dependency set is tested by manifest tests.
        self.dependencies = patch.object(manifest, "dependency_paths", return_value=manifest.TEST)
        self.dependencies.start()
        self.addCleanup(self.dependencies.stop)
        fixtures.make_source(self.source, self.target)
        runner = self.source / manifest.PKCS11_RUNNER_FILE
        runner.parent.mkdir(parents=True)
        runner.write_bytes(b"/* Exact original SDK test fixture; never edited. */\r\n")
        dependency = self.source / manifest.TEST[1]
        fixtures.git(dependency, "add", "--", "src/pkcs11/core_pkcs11_test.c")
        pin = fixtures.commit_fixture_tree(dependency)
        fixtures.git(self.source, "update-index", "--cacheinfo", "160000,"+pin+","+manifest.TEST[1])
        fixtures.commit_fixture_tree(self.source)
        for relative in view.CONFIG_FILES:
            path = self.source / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(("version: \"202604.00-LTS\"\n" if relative == "manifest.yml" else
                             "#define PRODUCT_TEST_SETTING 0\n").encode())
        self.provenance = manifest.capture_dependency_provenance(self.source, self.target)
        self.provenance["source_sha"] = "a" * 40
        view.create_source_view(self.source, self.native)
        self.original = runner.read_bytes()

    def select(self, argument):
        selected = ({"Full_PKCS11_StartFinish", "Full_PKCS11_Capabilities"} if argument == "StartFinish"
                    else {"Full_PKCS11_Capabilities", "Full_PKCS11_NoObject"})
        text = view.FACADE
        for name in view.GROUPS:
            if name not in selected:
                # Actual FRQ 2.5 replaces disabled calls with two tabs + //.
                text = text.replace("    RUN_TEST_GROUP( " + name, "\t\t//RUN_TEST_GROUP( " + name)
        (self.native / view.FACADE_FILE).write_text(text, encoding="utf-8")
        (self.native / "Test/include/test_param_config.h").write_bytes(b"#define PRODUCT_TEST_SETTING 123\n")

    def test_mutable_view_contains_no_borrowed_sdk_or_unity_body(self):
        actual = {path.relative_to(self.native).as_posix() for path in self.native.rglob("*") if path.is_file()}
        self.assertEqual(set((*view.CONFIG_FILES, view.FACADE_FILE, view.MARKER_FILE)), actual)
        self.assertEqual(view.FACADE.encode(), (self.native / manifest.PKCS11_RUNNER_FILE).read_bytes())
        self.assertFalse((self.native / "Test/Unity").exists())
        with self.assertRaisesRegex(ValueError, "supported native Core selection"):
            view.selected_group(self.native)

    def test_both_native_core_selections_bind_owned_config_and_original_test_bytes(self):
        for argument, groups, cases in (("StartFinish", [view.GROUPS[0], view.GROUPS[1]], 6),
                                       ("NoObject", [view.GROUPS[1], view.GROUPS[2]], 5)):
            if argument == "NoObject":
                self.native = self.runtime / "source" / "second-native-source"
                view.create_source_view(self.source, self.native)
            self.select(argument)
            result = view.prepare_build_tree(self.native, self.source, self.runtime, self.target, self.provenance)
            built = Path(result["build_source"])
            self.assertEqual(argument, result["selection"]["argument"])
            self.assertEqual(groups, result["selection"]["groups"])
            self.assertEqual(cases, result["selection"]["assertion_cases"])
            self.assertEqual(self.original, (built / manifest.PKCS11_RUNNER_FILE).read_bytes())
            self.assertEqual(self.original, (self.source / manifest.PKCS11_RUNNER_FILE).read_bytes())
            self.assertEqual(b"#define PRODUCT_TEST_SETTING 123\n", (built / "Test/include/test_param_config.h").read_bytes())
            self.assertEqual(built, view.resolve_build_tree(self.native, self.runtime, self.target))
            self.assertFalse((built / ".git").exists())
            self.assertNotEqual(view.FACADE.encode(), (built / view.FACADE_FILE).read_bytes())
            manifest_path = built / "artifacts/idt/build_transport/build_manifest.json"
            manifest_path.parent.mkdir(parents=True)
            manifest_path.write_text(json.dumps({"source_sha": self.provenance["source_sha"],
                "pkcs11_selection": {key: value for key, value in result["selection"].items() if key != "argument"}}))
            view.record_build_binding(self.native, self.runtime, self.target)
            recorded = json.loads(manifest_path.read_text())["pkcs11_source_view"]
            self.assertEqual(hashlib.sha256(self.original).hexdigest(), recorded["original_test_runner_sha256"])
            self.assertEqual("not-established", recorded["qualification"])

    def test_unknown_or_extra_selector_edits_fail_without_altering_original(self):
        self.select("StartFinish")
        original_facade = (self.native / view.FACADE_FILE).read_bytes()
        for changed in (original_facade + b"/* unexpected */\n",
                        original_facade.replace(b"Full_PKCS11_Capabilities", b"Unknown_Group"),
                        original_facade.replace(b"RUN_TEST_GROUP( Full_PKCS11_Capabilities", b"//RUN_TEST_GROUP( Full_PKCS11_Capabilities")):
            (self.native / view.FACADE_FILE).write_bytes(changed)
            with self.assertRaises(ValueError):
                view.prepare_build_tree(self.native, self.source, self.runtime, self.target, self.provenance)
            self.assertEqual(self.original, (self.source / manifest.PKCS11_RUNNER_FILE).read_bytes())
            self.assertEqual(changed, (self.native / view.FACADE_FILE).read_bytes())

    def test_sdk_body_changes_still_fail_original_source_gate(self):
        self.select("NoObject")
        (self.source / manifest.PKCS11_RUNNER_FILE).write_bytes(b"changed SDK body\n")
        with self.assertRaisesRegex(ValueError, "differs from captured"):
            view.prepare_build_tree(self.native, self.source, self.runtime, self.target, self.provenance)

    def test_after_build_selector_and_effective_config_changes_fail_flash_resolution(self):
        self.select("NoObject")
        result = view.prepare_build_tree(self.native, self.source, self.runtime, self.target, self.provenance)
        built = Path(result["build_source"])
        path = self.native / "Test/include/test_param_config.h"
        before = path.read_bytes()
        path.write_bytes(before+b"#define STALE 1\n")
        with self.assertRaisesRegex(ValueError, "private build binding"):
            view.resolve_build_tree(self.native, self.runtime, self.target)
        path.write_bytes(before)
        (built / "Test/include/test_param_config.h").write_bytes(b"changed effective config\n")
        with self.assertRaisesRegex(ValueError, "effective product configuration"):
            view.resolve_build_tree(self.native, self.runtime, self.target)

    def test_existing_build_inputs_are_preserved_and_external_view_is_rejected(self):
        self.select("NoObject")
        result = view.prepare_build_tree(self.native, self.source, self.runtime, self.target, self.provenance)
        with self.assertRaises(FileExistsError):
            view.prepare_build_tree(self.native, self.source, self.runtime, self.target, self.provenance)
        self.assertEqual(self.original, (Path(result["build_source"]) / manifest.PKCS11_RUNNER_FILE).read_bytes())
        external = self.folder / "unowned-native-view"
        view.create_source_view(self.source, external)
        with self.assertRaisesRegex(ValueError, "direct private runtime"):
            view.build_directory(external, self.runtime)


if __name__ == "__main__":
    unittest.main()

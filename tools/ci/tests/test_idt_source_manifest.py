"""Exercise source-copy provenance with local Git objects, without a board or network."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
import io
from unittest.mock import patch

from tools import idt_source_manifest as manifest


ROOT = Path(__file__).resolve().parents[3]
GIT = shutil.which("git")


def git(root: Path, *arguments: str, input_text: str | None = None) -> str:
    """Only create/read fixture objects; do not inherit repository identity or hooks."""
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith("GIT_")}
    environment.update(GIT_AUTHOR_NAME="Codex", GIT_AUTHOR_EMAIL="codex@openai.com",
                       GIT_COMMITTER_NAME="Codex", GIT_COMMITTER_EMAIL="codex@openai.com")
    result = subprocess.run(
        [GIT, "-c", f"safe.directory={root.resolve().as_posix()}",
         "-c", "core.autocrlf=false", "-c", "core.longpaths=true", "-C", str(root),
         *arguments], input=input_text, env=environment, text=True, encoding="utf-8",
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
    )
    return result.stdout.strip()


def commit_fixture_tree(root: Path) -> str:
    tree = git(root, "write-tree")
    commit = git(root, "commit-tree", tree, input_text="Local provenance test fixture\n")
    git(root, "update-ref", "HEAD", commit)
    return commit


def make_source(root: Path, target: str) -> dict[str, str]:
    root.mkdir()
    git(root, "init", "--quiet", "--template=")
    pins = {}
    for relative in manifest.dependency_paths(target):
        dependency = root / relative
        dependency.mkdir(parents=True)
        git(dependency, "init", "--quiet", "--template=")
        (dependency / "source.c").write_bytes(("/* " + relative + " */\r\n").encode())
        (dependency / "firmware.bin").write_bytes(b"\x00\xff\x80\n\r\n")
        git(dependency, "add", "--", "source.c", "firmware.bin")
        pins[relative] = commit_fixture_tree(dependency)
        git(root, "update-index", "--add", "--cacheinfo",
            "160000," + pins[relative] + "," + relative)
    commit_fixture_tree(root)
    return pins


def copy_without_git(source: Path, destination: Path) -> None:
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns(".git", "__pycache__"))


@unittest.skipUnless(GIT, "Git is required to construct local provenance fixtures")
class DependencyProvenanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.templates = tempfile.TemporaryDirectory(prefix="idt-git-fixtures-")
        cls.addClassCleanup(cls.templates.cleanup)
        cls.template_pins = {}

    def fixture(self, target: str, destination: Path) -> dict[str, str]:
        template = Path(self.templates.name) / target
        if target not in self.template_pins:
            self.template_pins[target] = make_source(template, target)
        shutil.copytree(template, destination)
        return dict(self.template_pins[target])

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="idt-provenance-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.target = "rx65n-bg96"
        self.source = self.root / "s"
        self.pins = self.fixture(self.target, self.source)

    def capture(self):
        return manifest.capture_dependency_provenance(self.source, self.target)

    def snapshot(self):
        provenance = self.capture()
        destination = self.root / "copy"
        copy_without_git(self.source, destination)
        return destination, provenance

    def pkcs11_snapshot(self):
        dependency = self.source / 'Test/FreeRTOS-Libraries-Integration-Tests'
        runner = self.source / manifest.PKCS11_RUNNER_FILE
        runner.parent.mkdir(parents=True)
        # Capture original group-runner bytes. All subsequent changes must fail,
        # including a native selector comment or line-ending change.
        groups = ('Full_PKCS11_StartFinish', 'Full_PKCS11_NoObject',
                  'Full_PKCS11_RSA', 'Full_PKCS11_EC')
        body = 'int unchanged(void) { return 7; }\r\nvoid runner(void) {\r\n'
        body += ''.join('    RUN_TEST_GROUP( ' + group + ' );\r\n' for group in groups)
        body += '}\r\n'
        runner.write_bytes(body.encode('ascii'))
        git(dependency, 'add', '--', 'src/pkcs11/core_pkcs11_test.c')
        sha = commit_fixture_tree(dependency)
        git(self.source, 'update-index', '--cacheinfo',
            '160000,' + sha + ',Test/FreeRTOS-Libraries-Integration-Tests')
        commit_fixture_tree(self.source)
        destination, provenance = self.snapshot()
        return destination / manifest.PKCS11_RUNNER_FILE, destination, provenance, groups

    def test_native_pkcs11_selector_edits_are_rejected_and_preserved(self):
        runner, destination, provenance, groups = self.pkcs11_snapshot()
        original = runner.read_bytes()
        for selected in ('Full_PKCS11_StartFinish', 'Full_PKCS11_NoObject'):
            native = original.decode('ascii').replace('    RUN_TEST_GROUP( ' + selected + ' );',
                                                     '    //RUN_TEST_GROUP( ' + selected + ' );')
            runner.write_bytes(native.encode('ascii'))
            for scope in (None, 'Transport', 'PKCS11'):
                with self.assertRaisesRegex(ValueError, 'differs from captured'):
                    manifest.verify_dependency_provenance(destination, self.target, provenance, test_group=scope)
            self.assertEqual(native.encode('ascii'), runner.read_bytes())

    def test_pkcs11_line_ending_changes_are_rejected(self):
        runner, destination, provenance, groups = self.pkcs11_snapshot()
        runner.write_bytes(runner.read_bytes().replace(b'\r\n', b'\n'))
        with self.assertRaisesRegex(ValueError, 'differs from captured'):
            manifest.verify_dependency_provenance(destination, self.target, provenance, test_group='PKCS11')

    def test_pkcs11_cli_json_reports_only_exact_original_bytes(self):
        runner, destination, provenance, groups = self.pkcs11_snapshot()
        path = self.root / 'provenance.json'
        path.write_text(json.dumps(provenance), encoding='utf-8')
        result = subprocess.run([sys.executable, str(ROOT / 'tools/idt_source_manifest.py'),
                                 'verify', '--source', str(destination), '--target', self.target,
                                 '--provenance', str(path), '--test-group', 'PKCS11', '--json-output'],
                                capture_output=True, text=True, check=True)
        evidence = json.loads(result.stdout)['pkcs11_runner']
        self.assertTrue(evidence['byte_verified'])
        self.assertEqual(evidence['captured_sha256'], evidence['effective_sha256'])
        self.assertNotIn('canonical_selection_used', evidence)
        self.assertNotIn('enabled_groups', evidence)
        self.assertNotIn('dependency_pkcs11_runner_sha256', provenance)

    def test_pkcs11_body_or_group_name_changes_are_rejected(self):
        runner, destination, provenance, groups = self.pkcs11_snapshot()
        original = runner.read_bytes()
        for changed in (original.replace(b'return 7', b'return 8'),
                        original.replace(b'Full_PKCS11_EC', b'Unknown_PKCS11_Group'),
                        original + b'RUN_TEST_GROUP( Full_PKCS11_EC );\n'):
            runner.write_bytes(changed)
            with self.assertRaisesRegex(ValueError, 'differs from captured'):
                manifest.verify_dependency_provenance(destination, self.target, provenance, test_group='PKCS11')

    def test_all_targets_capture_the_common_root_libraries(self):
        for target in ("rx65n-bg96", "rx72n-ethernet", "rx671-wifi"):
            with self.subTest(target=target):
                selected = set(manifest.dependency_paths(target))
                self.assertTrue(set(manifest.COMMON).issubset(selected))
                self.assertTrue(set(manifest.TEST).issubset(selected))
                self.assertIn(manifest.BOOT[target], selected)
                self.assertIn('/lib/rx_bootloader', manifest.BOOT[target])
                self.assertEqual(target == "rx671-wifi", set(manifest.WIFI).issubset(selected))
        with self.assertRaises(ValueError):
            manifest.dependency_paths("rx65n-ethernet")

    def test_capture_binds_target_schema_gitlinks_and_exact_bytes(self):
        provenance = self.capture()
        self.assertEqual(1, provenance["dependency_manifest_schema_version"])
        self.assertEqual(self.target, provenance["dependency_target_id"])
        self.assertEqual(self.pins, provenance["submodule_shas"])
        expected = {}
        for relative in manifest.dependency_paths(self.target):
            for filename in ("source.c", "firmware.bin"):
                path = self.source / relative / filename
                expected[path.relative_to(self.source).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(expected, provenance["dependency_files_sha256"])

    def test_all_targets_verify_after_copy_without_git(self):
        for target in manifest.BOOT:
            with self.subTest(target=target):
                source = self.root / target
                pins = self.fixture(target, source)
                # The fixture's real commit replaces the reviewed production SHA only
                # for this roundtrip; the production pin is tested independently below.
                with patch.object(manifest, "BOOT_RX671_SHA", pins[manifest.BOOT[target]]):
                    provenance = manifest.capture_dependency_provenance(source, target)
                    destination = self.root / (target + "-copy")
                    copy_without_git(source, destination)
                    self.assertFalse(any(path.name == ".git" for path in destination.rglob("*")))
                    with patch.object(manifest, "_git", side_effect=AssertionError("verification invoked Git")):
                        count = manifest.verify_dependency_provenance(destination, target, provenance)
                self.assertEqual(2 * len(manifest.dependency_paths(target)), count)

    def test_git_metadata_and_python_cache_are_excluded(self):
        dependency = self.source / manifest.TEST[0]
        cache = dependency / "__pycache__"
        cache.mkdir()
        (cache / "fixture.pyc").write_bytes(b"runtime cache")
        provenance = self.capture()
        self.assertFalse(any(".git" in name.split("/") or "__pycache__" in name.split("/")
                             for name in provenance["dependency_files_sha256"]))
        destination = self.root / "copy"
        copy_without_git(self.source, destination)
        # A copied .git pointer may reference a checkout that does not exist here.
        (destination / manifest.TEST[0] / ".git").write_text("gitdir: /not-present\n")
        with patch.object(manifest, "_git", side_effect=AssertionError("verification invoked Git")):
            self.assertEqual(2 * len(manifest.dependency_paths(self.target)),
                             manifest.verify_dependency_provenance(destination, self.target, provenance))

    def test_content_added_or_removed_after_capture_is_rejected(self):
        provenance = self.capture()
        relative = manifest.TEST[0]
        for mutation in ("change", "add", "remove"):
            with self.subTest(mutation=mutation):
                destination = self.root / mutation
                copy_without_git(self.source, destination)
                path = destination / relative / "source.c"
                if mutation == "change":
                    path.write_bytes(path.read_bytes() + b"changed\n")
                elif mutation == "add":
                    (path.parent / "unexpected.c").write_bytes(b"unrecorded\n")
                else:
                    path.unlink()
                with self.assertRaises(ValueError):
                    manifest.verify_dependency_provenance(destination, self.target, provenance)

    def test_schema_and_target_must_match_before_using_hashes(self):
        destination, provenance = self.snapshot()
        for field, value in (("dependency_manifest_schema_version", None),
                             ("dependency_manifest_schema_version", 2),
                             ("dependency_target_id", "rx72n-ethernet"),
                             ("dependency_target_id", None)):
            with self.subTest(field=field, value=value):
                invalid = copy.deepcopy(provenance)
                if value is None:
                    invalid.pop(field)
                else:
                    invalid[field] = value
                with self.assertRaises(ValueError):
                    manifest.verify_dependency_provenance(destination, self.target, invalid)

    def test_pin_and_hash_sets_cannot_have_extra_or_missing_members(self):
        destination, provenance = self.snapshot()
        for field in ("submodule_shas", "dependency_files_sha256"):
            for mutation in ("extra", "missing"):
                with self.subTest(field=field, mutation=mutation):
                    invalid = copy.deepcopy(provenance)
                    if mutation == "extra":
                        invalid[field]["unrelated/dependency"] = "a" * (40 if field == "submodule_shas" else 64)
                    else:
                        invalid[field].pop(next(iter(invalid[field])))
                    with self.assertRaises(ValueError):
                        manifest.verify_dependency_provenance(destination, self.target, invalid)

    def test_invalid_pin_or_hash_and_missing_manifest_fail_closed(self):
        destination, provenance = self.snapshot()
        for field, bad_value in (("submodule_shas", "not-a-commit"),
                                 ("submodule_shas", "A" * 40),
                                 ("dependency_files_sha256", "not-a-hash")):
            with self.subTest(field=field, bad_value=bad_value):
                invalid = copy.deepcopy(provenance)
                invalid[field][next(iter(invalid[field]))] = bad_value
                with self.assertRaises(ValueError):
                    manifest.verify_dependency_provenance(destination, self.target, invalid)
        with self.assertRaises(ValueError):
            manifest.verify_dependency_provenance(destination, self.target, {})

    def test_gitlink_must_match_dependency_head(self):
        dependency = self.source / manifest.TEST[0]
        (dependency / "source.c").write_bytes(b"new commit\n")
        git(dependency, "add", "--", "source.c")
        changed = commit_fixture_tree(dependency)
        self.assertNotEqual(self.pins[manifest.TEST[0]], changed)
        with self.assertRaises(ValueError):
            self.capture()

    def test_missing_source_gitlink_is_rejected(self):
        git(self.source, "update-index", "--force-remove", "--", manifest.TEST[0])
        commit_fixture_tree(self.source)
        with self.assertRaises(ValueError):
            self.capture()

    def test_dependency_must_have_its_own_initialized_git_root(self):
        dependency = self.source / manifest.TEST[0]
        metadata = dependency / ".git"
        metadata.rename(self.root / "detached-git-metadata")
        with self.assertRaises(ValueError):
            self.capture()

    def test_modified_library_is_rejected_before_hash_capture(self):
        relative = manifest.TEST[0] + "/source.c"
        patched = b"unexpected local patch\n"
        (self.source / relative).write_bytes(patched)
        with self.assertRaisesRegex(ValueError, "original sources changed"):
            self.capture()
        self.assertEqual(patched, (self.source / relative).read_bytes())

    def test_rx671_boot_pin_must_match_reviewed_production_helper(self):
        target = "rx671-wifi"
        source = self.root / "wifi"
        pins = self.fixture(target, source)
        self.assertNotEqual(manifest.BOOT_RX671_SHA, pins[manifest.BOOT[target]])
        with self.assertRaisesRegex(ValueError, "boot-loader pin"):
            manifest.capture_dependency_provenance(source, target)
        with patch.object(manifest, "BOOT_RX671_SHA", pins[manifest.BOOT[target]]):
            provenance = manifest.capture_dependency_provenance(source, target)
        destination = self.root / "wifi-copy"
        copy_without_git(source, destination)
        with self.assertRaisesRegex(ValueError, "boot-loader pin"):
            manifest.verify_dependency_provenance(destination, target, provenance)

    def test_external_symlink_content_cannot_be_captured(self):
        external = self.root / "external.c"
        external.write_bytes(b"outside dependency\n")
        link = self.source / manifest.TEST[0] / "external.c"
        try:
            link.symlink_to(external)
        except OSError as error:
            self.skipTest("Host cannot create an unprivileged symlink: " + str(error))
        with self.assertRaises(ValueError):
            self.capture()

    def test_linked_dependency_root_and_ancestor_are_rejected(self):
        provenance = self.capture()
        for relative in (manifest.TEST[0], "Test"):
            with self.subTest(relative=relative):
                destination = self.root / ("linked-" + relative.replace("/", "-"))
                shutil.copytree(self.source, destination)
                link = destination / relative
                external = self.root / ("external-" + relative.replace("/", "-"))
                link.rename(external)
                try:
                    if os.name == "nt":
                        import _winapi
                        _winapi.CreateJunction(str(external), str(link))
                    else:
                        link.symlink_to(external, target_is_directory=True)
                except OSError as error:
                    self.skipTest("Host cannot create a directory link: " + str(error))
                with self.assertRaises(ValueError):
                    manifest.capture_dependency_provenance(destination, self.target)
                with self.assertRaises(ValueError):
                    manifest.verify_dependency_provenance(destination, self.target, provenance)

    def test_linked_directory_member_is_rejected_before_content_capture(self):
        provenance = self.capture()
        external = self.root / "external-member"
        external.mkdir()
        (external / "outside.c").write_bytes(b"outside dependency\n")
        link = self.source / manifest.TEST[0] / "linked-member"
        try:
            if os.name == "nt":
                import _winapi
                _winapi.CreateJunction(str(external), str(link))
            else:
                link.symlink_to(external, target_is_directory=True)
        except OSError as error:
            self.skipTest("Host cannot create a directory link: " + str(error))
        with self.assertRaisesRegex(ValueError, "Linked dependency path"):
            self.capture()
        with self.assertRaisesRegex(ValueError, "Linked dependency path"):
            manifest.verify_dependency_provenance(self.source, self.target, provenance)

    def test_cli_capture_does_not_trust_preexisting_arbitrary_pins(self):
        provenance_path = self.root / "provenance.json"
        provenance_path.write_text(json.dumps({"source_git_sha": "fixture-host-sha",
            "submodule_shas": {relative: "a" * 40 for relative in self.pins}}), encoding="utf-8")
        result = subprocess.run([sys.executable, str(ROOT / "tools/idt_source_manifest.py"),
            "capture", "--source", str(self.source), "--target", self.target,
            "--provenance", str(provenance_path)], text=True, capture_output=True)
        self.assertEqual(0, result.returncode, result.stderr)
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        self.assertEqual(self.pins, provenance["submodule_shas"])
        self.assertEqual("fixture-host-sha", provenance["source_git_sha"])
        # The same caller-provided pin list cannot reconstruct absent Git metadata.
        destination = self.root / "copy"
        copy_without_git(self.source, destination)
        result = subprocess.run([sys.executable, str(ROOT / "tools/idt_source_manifest.py"),
            "capture", "--source", str(destination), "--target", self.target,
            "--provenance", str(provenance_path)], text=True, capture_output=True)
        self.assertNotEqual(0, result.returncode)

    def test_cli_verification_succeeds_when_git_is_unavailable(self):
        destination, provenance = self.snapshot()
        provenance_path = self.root / "provenance.json"
        provenance_path.write_text(json.dumps(provenance), encoding="utf-8")
        environment = dict(os.environ, PATH="")
        result = subprocess.run([sys.executable, str(ROOT / "tools/idt_source_manifest.py"),
            "verify", "--source", str(destination), "--target", self.target,
            "--provenance", str(provenance_path)], env=environment, text=True, capture_output=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("no Git/network action", result.stdout)


@unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 is required for the WHD byte gate")
class GitFreeWhdOriginTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="idt-whd-origin-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "native-copy" / "whd"
        self.source.mkdir(parents=True)
        self.original = {"WiFi_Host_Driver/src/a.c": b"upstream source\n",
                         "LICENSE.txt": b"upstream license\n"}
        for relative, raw in self.original.items():
            path = self.source / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        # Source copies can carry an unusable Git pointer; byte verification
        # neither reads that repository nor modifies the dependency.
        (self.source / ".git").write_text("gitdir: absent.git\n", encoding="utf-8")
        self.manifest_path = self.root / "origin.json"
        self.manifest_path.write_text(json.dumps({"schema_version": 1,
            "upstream_commit": "7" * 40,
            "files_sha256": {name: hashlib.sha256(raw).hexdigest()
                             for name, raw in self.original.items()}}), encoding="utf-8")

    def check(self):
        def ps(value):
            return "'" + str(value).replace("'", "''") + "'"
        helper = ROOT / "tools/build_headless_rx671_wifi.ps1"
        script = f"""$ErrorActionPreference = 'Stop'
$tokens = $null; $errors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile({ps(helper)}, [ref]$tokens, [ref]$errors)
if ($errors.Count) {{ throw 'Helper has PowerShell syntax errors.' }}
$function = $ast.Find({{param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Assert-PristineWhdInputs'}}, $true)
Invoke-Expression $function.Extent.Text
Assert-PristineWhdInputs -DependencyRoot {ps(self.source)} -ManifestPath {ps(self.manifest_path)} -GitFree
"""
        return subprocess.run([shutil.which("pwsh"), "-NoProfile", "-Command", script],
            text=True, encoding="utf-8", errors="replace", capture_output=True)

    def test_git_free_before_and_after_checks_preserve_all_origin_bytes(self):
        for _ in range(2):
            result = self.check()
            self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(self.original,
                         {name: (self.source / name).read_bytes() for name in self.original})

    def test_post_build_change_is_rejected_and_preserved(self):
        self.assertEqual(0, self.check().returncode)
        target = self.source / next(iter(self.original))
        target.write_bytes(b"unexpected modified source\n")
        result = self.check()
        self.assertNotEqual(0, result.returncode)
        self.assertIn("differs from upstream bytes", result.stderr)
        self.assertEqual(b"unexpected modified source\n", target.read_bytes())

    def test_unrecorded_file_and_missing_origin_file_are_rejected(self):
        extra = self.source / "unexpected.c"
        extra.write_bytes(b"replacement body\n")
        self.assertNotEqual(0, self.check().returncode)
        extra.unlink()
        (self.source / "LICENSE.txt").unlink()
        result = self.check()
        self.assertNotEqual(0, result.returncode)
        self.assertIn("missing an upstream file", result.stderr)

    def test_manifest_path_cannot_escape_dependency(self):
        self.manifest_path.write_text(json.dumps({"schema_version": 1,
            "upstream_commit": "7" * 40,
            "files_sha256": {"../outside.c": "a" * 64}}), encoding="utf-8")
        result = self.check()
        self.assertNotEqual(0, result.returncode)
        self.assertIn("invalid file path", result.stderr)


class OfflineSourcePlanTests(unittest.TestCase):
    def test_plan_without_dependency_trees_records_unavailable_stack_and_does_not_install_idt(self):
        from tools.idt import run_idt
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source"
            source.mkdir()
            (source / "manifest.yml").write_text('version: "202604.00-LTS"\n', encoding="utf-8")
            for target_id in manifest.BOOT:
                output = Path(folder) / target_id
                arguments = ["run_idt.py", "--target", target_id, "--scope", "transport",
                             "--plan-only", "--output", str(output)]
                with patch.object(run_idt, "SOURCE", source), patch.object(sys, "argv", arguments), \
                     patch.object(run_idt, "install_idt") as install, redirect_stdout(io.StringIO()):
                    self.assertEqual(0, run_idt.main())
                install.assert_not_called()
                plan = json.loads((output / "plan.json").read_text(encoding="utf-8"))
                self.assertEqual("not_run", plan["status"])
                self.assertEqual(target_id, plan["target_id"])
                self.assertEqual("unavailable", plan["production_stack"]["status"])
                self.assertEqual("not-run", plan["production_stack"]["native_result"])
                self.assertEqual("not-established", plan["qualification"])
                self.assertFalse((output / "FRQ_Report.xml").exists())


if __name__ == "__main__":
    unittest.main()

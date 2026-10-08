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
        # Replay the exact native comment/line-ending transformation observed
        # in job70883, while keeping a separate untouched function in the hash.
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

    def test_native_pkcs11_selection_is_scope_bound_and_read_only(self):
        runner, destination, provenance, groups = self.pkcs11_snapshot()
        original = runner.read_bytes()
        for selected in ('Full_PKCS11_StartFinish', 'Full_PKCS11_NoObject'):
            native = original.decode('ascii').replace('\r\n', '\n')
            for group in groups:
                if group != selected:
                    native = native.replace('    RUN_TEST_GROUP( ' + group + ' );',
                                            '\t\t//RUN_TEST_GROUP( ' + group + ' );')
            runner.write_bytes(native.encode('ascii'))
            with self.assertRaisesRegex(ValueError, 'differs from captured'):
                manifest.verify_dependency_provenance(destination, self.target, provenance)
            with self.assertRaisesRegex(ValueError, 'differs from captured'):
                manifest.verify_dependency_provenance(destination, self.target, provenance, test_group='Transport')
            manifest.verify_dependency_provenance(destination, self.target, provenance, test_group='PKCS11')
            self.assertEqual(native.encode('ascii'), runner.read_bytes())
            missing = dict(provenance)
            missing.pop('dependency_pkcs11_runner_sha256')
            with self.assertRaisesRegex(ValueError, 'differs from captured'):
                manifest.verify_dependency_provenance(destination, self.target, missing, test_group='PKCS11')
            runner.write_bytes(native.replace('return 7', 'return 8').encode('ascii'))
            with self.assertRaisesRegex(ValueError, 'differs from captured'):
                manifest.verify_dependency_provenance(destination, self.target, provenance, test_group='PKCS11')

    def test_pkcs11_unknown_or_noncore_selection_is_rejected(self):
        runner, destination, provenance, groups = self.pkcs11_snapshot()
        original = runner.read_bytes().decode('ascii').replace('\r\n', '\n')
        native = original
        for group in groups:
            if group != 'Full_PKCS11_RSA':
                native = native.replace('    RUN_TEST_GROUP( ' + group + ' );',
                                        '\t\t//RUN_TEST_GROUP( ' + group + ' );')
        runner.write_bytes(native.encode('ascii'))
        with self.assertRaisesRegex(ValueError, 'differs from captured'):
            manifest.verify_dependency_provenance(destination, self.target, provenance, test_group='PKCS11')

    def test_pkcs11_cli_json_records_effective_selection(self):
        runner, destination, provenance, groups = self.pkcs11_snapshot()
        native = runner.read_text(encoding='ascii')
        for group in groups:
            if group != 'Full_PKCS11_NoObject':
                native = native.replace('    RUN_TEST_GROUP( ' + group + ' );',
                                        '\t\t//RUN_TEST_GROUP( ' + group + ' );')
        runner.write_bytes(native.encode('ascii'))
        path = self.root / 'provenance.json'
        path.write_text(json.dumps(provenance), encoding='utf-8')
        result = subprocess.run([sys.executable, str(ROOT / 'tools/idt_source_manifest.py'),
                                 'verify', '--source', str(destination), '--target', self.target,
                                 '--provenance', str(path), '--test-group', 'PKCS11', '--json-output'],
                                capture_output=True, text=True, check=True)
        evidence = json.loads(result.stdout)['pkcs11_runner']
        self.assertEqual(['Full_PKCS11_NoObject'], evidence['enabled_groups'])
        self.assertTrue(evidence['canonical_selection_used'])
        self.assertEqual(hashlib.sha256(runner.read_bytes()).hexdigest(), evidence['effective_sha256'])

    def test_pkcs11_invalid_structure_and_all_enabled_are_rejected(self):
        runner, destination, provenance, groups = self.pkcs11_snapshot()
        original = runner.read_bytes().decode('ascii').replace('\r\n', '\n')
        for text in (original.replace('Full_PKCS11_EC', 'Unknown_PKCS11_Group'),
                     original + 'RUN_TEST_GROUP( Full_PKCS11_EC );\n',
                     original.replace('RUN_TEST_GROUP( Full_PKCS11_EC );', 'RUN_TEST_GROUP( Full_PKCS11_EC ); extra')):
            runner.write_bytes(text.encode('ascii'))
            with self.assertRaisesRegex(ValueError, 'selection structure'):
                manifest.verify_dependency_provenance(destination, self.target, provenance, test_group='PKCS11')
        # LF-only normalization must not authorize all four groups for Core.
        runner.write_bytes(original.encode('ascii'))
        with self.assertRaisesRegex(ValueError, 'differs from captured'):
            manifest.verify_dependency_provenance(destination, self.target, provenance, test_group='PKCS11')

    def test_dependency_selection_uses_bg96_self_contained_stack(self):
        bg96 = manifest.dependency_paths(self.target)
        self.assertEqual(set(manifest.TEST) | {manifest.BOOT[self.target]}, set(bg96))
        self.assertTrue(set(manifest.COMMON).isdisjoint(bg96))
        for target in ("rx72n-ethernet", "rx671-wifi"):
            with self.subTest(target=target):
                selected = set(manifest.dependency_paths(target))
                self.assertTrue(set(manifest.COMMON).issubset(selected))
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
            self.assertEqual(6, manifest.verify_dependency_provenance(destination, self.target, provenance))

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

    def test_uncommitted_reviewed_patch_bytes_are_captured(self):
        # WHD may carry a reviewed forward patch; gitlink identity and content
        # are independent checks, so capture must retain those exact bytes.
        relative = manifest.TEST[0] + "/source.c"
        patched = b"reviewed local patch\n"
        (self.source / relative).write_bytes(patched)
        provenance = self.capture()
        self.assertEqual(self.pins, provenance["submodule_shas"])
        self.assertEqual(hashlib.sha256(patched).hexdigest(), provenance["dependency_files_sha256"][relative])

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


@unittest.skipUnless(GIT, "Git apply is required for the WHD portability patch fixture")
class GitFreeWhdPatchTests(unittest.TestCase):
    def setUp(self):
        whd = ROOT / "Projects/aws_wifi_rx671_ek/external/wifi-host-driver"
        self.patch = ROOT / "Projects/aws_wifi_rx671_ek/external/patches/whd-v1.70.0-ccrx-portability.patch"
        pairs = re.findall(r"(?m)^diff --git a/(\S+) b/(\S+)$", self.patch.read_text(encoding="utf-8"))
        self.assertTrue(pairs, "Reviewed WHD patch must have explicit target paths")
        self.paths = []
        for old, new in pairs:
            self.assertEqual(old, new)
            self.assertTrue(old.startswith("WiFi_Host_Driver/"))
            self.assertNotIn("..", Path(old).parts)
            if not (whd / old).is_file():
                self.skipTest("Initialized WHD fixture is unavailable: " + old)
            self.paths.append(old)
        self.temporary = tempfile.TemporaryDirectory(prefix="idt-whd-patch-")
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.source = root / "native-copy" / "whd"
        self.stage = root / "neutral-targets"
        self.source.mkdir(parents=True)
        self.stage.mkdir()
        # A native source copy may contain Git pointers with no referenced repo.
        (self.source.parent / ".git").write_text("gitdir: " + (root / "absent.git").as_posix() + "\n")
        for relative in self.paths:
            for destination in (self.source, self.stage):
                target = destination / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((whd / relative).read_bytes())
        self.original = {relative: (self.source / relative).read_bytes() for relative in self.paths}
        if self.apply("--check").returncode:
            reverse = self.apply("--reverse", "--check")
            self.assertEqual(0, reverse.returncode, reverse.stderr)
            result = self.apply("--reverse")
            self.assertEqual(0, result.returncode, result.stderr)

    def apply(self, *arguments):
        environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        return subprocess.run([GIT, "-c", f"safe.directory={self.stage.as_posix()}",
            "-C", str(self.stage), "apply", "--no-index", "--ignore-space-change",
            "--ignore-whitespace", *arguments, str(self.patch)],
            env=environment, text=True, encoding="utf-8", errors="replace", capture_output=True)

    def test_reviewed_patch_forward_and_reverse_checks_use_only_staged_targets(self):
        staged = {path.relative_to(self.stage).as_posix() for path in self.stage.rglob("*") if path.is_file()}
        self.assertEqual(set(self.paths), staged)
        self.assertEqual(0, self.apply("--check").returncode)
        self.assertNotEqual(0, self.apply("--reverse", "--check").returncode)
        result = self.apply()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertNotEqual(0, self.apply("--check").returncode)
        reverse = self.apply("--reverse", "--check")
        self.assertEqual(0, reverse.returncode, reverse.stderr)
        self.assertFalse((self.stage / ".git").exists())
        self.assertEqual(self.original, {relative: (self.source / relative).read_bytes() for relative in self.paths})

    def test_unrecognized_whd_content_fails_both_patch_checks(self):
        (self.stage / self.paths[0]).write_bytes(b"unrecognized WHD fixture\n")
        self.assertNotEqual(0, self.apply("--check").returncode)
        self.assertNotEqual(0, self.apply("--reverse", "--check").returncode)
        self.assertEqual(self.original, {relative: (self.source / relative).read_bytes() for relative in self.paths})


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

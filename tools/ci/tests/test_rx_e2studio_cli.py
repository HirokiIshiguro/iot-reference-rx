"""Exercise RX launcher orchestration without an IDE or firmware build."""
import os
from contextlib import contextmanager
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[3]
HELPER = ROOT / "tools/rx_e2studio_cli.ps1"
CSC = Path(os.environ.get("WINDIR", "C:/Windows")) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
PWSH = shutil.which("pwsh")


def literal(value):
    return "'" + str(value).replace("'", "''") + "'"


@unittest.skipUnless(os.name == "nt" and PWSH and CSC.is_file(), "Windows PowerShell 7/C# fixture required")
class RxCliProcessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="rx-e2-cli-tests-")
        cls.directory = Path(cls.temporary.name)
        source = cls.directory / "launcher.cs"
        cls.executable = cls.directory / "e2studio-cli.exe"
        source.write_text(r'''
using System;
using System.IO;
using System.Threading;
using System.Diagnostics;
public class Launcher {
    public static int Main(string[] args) {
        if (args.Length == 1 && args[0] == "--fixture-child") {
            Thread.Sleep(30000);
            return 0;
        }
        if (args.Length == 1 && args[0] == "--fixture-middle") {
            var grandchild = Process.Start(new ProcessStartInfo(
                Process.GetCurrentProcess().MainModule.FileName, "--fixture-child") {
                UseShellExecute = false, CreateNoWindow = true
            });
            File.WriteAllText(Environment.GetEnvironmentVariable("RXCLI_FIXTURE_CHILD_PID"), grandchild.Id.ToString());
            return 0;
        }
        File.AppendAllText(Environment.GetEnvironmentVariable("RXCLI_FIXTURE_ARGUMENTS"),
            String.Join("|", args) + "\n");
        Console.WriteLine("RAW_TOOL_OUTPUT_SENTINEL");
        string mode = Environment.GetEnvironmentVariable("RXCLI_FIXTURE_MODE");
        int importFlag = Array.IndexOf(args, "-import");
        int buildFlag = Array.IndexOf(args, "-build");
        if (mode == "delay-child") {
            var child = Process.Start(new ProcessStartInfo(
                Process.GetCurrentProcess().MainModule.FileName, "--fixture-child") {
                UseShellExecute = false, CreateNoWindow = true
            });
            File.WriteAllText(Environment.GetEnvironmentVariable("RXCLI_FIXTURE_CHILD_PID"), child.Id.ToString());
        }
        if (mode == "orphan-pipe") {
            var middle = Process.Start(new ProcessStartInfo(
                Process.GetCurrentProcess().MainModule.FileName, "--fixture-middle") {
                UseShellExecute = false, CreateNoWindow = true
            });
            if (!middle.WaitForExit(1000)) return 90;
            Thread.Sleep(200);
            File.WriteAllText(Environment.GetEnvironmentVariable("RXCLI_FIXTURE_EXIT_MARKER"), "0");
            return 0;
        }
        if (mode == "delay" || mode == "delay-child") Thread.Sleep(2000);
        if (mode == "reject" && importFlag >= 0) {
            Console.WriteLine("Project: file:/fixture can't be found");
            return 0;
        }
        if (mode == "warning") {
            Console.WriteLine("Warning: NLS unused message: failedReadDuringWrite in: org.eclipse.core.internal.filesystem.messages");
            Console.WriteLine("fixture.c(1): W0520198: fixture warning");
            Console.WriteLine("M0520001: fixture information");
        }
        if (mode == "build-error" && buildFlag >= 0) return 23;
        if (mode.StartsWith("typed-")) Console.WriteLine("fixture.c(1): " + mode.Substring(6) + ": fixture diagnostic");
        if (mode == "source-drift") File.WriteAllText(Path.Combine(args[importFlag+1], ".cproject"), "UNEXPECTED_PROFILE");
        if (mode == "project-drift") File.AppendAllText(Path.Combine(args[importFlag+1], ".project"), "\n");
        if (mode == "scfg-drift") File.WriteAllText(Path.Combine(args[importFlag+1], "fixture.scfg"), "UNEXPECTED_SC_CONFIG");
        if (mode == "generated-header-drift") File.WriteAllText(Path.Combine(args[importFlag+1], "smc_gen", "r_config", "r_bsp_config.h"), "UNEXPECTED_HEADER");
        if (mode == "rcpc-named-header-drift") File.WriteAllText(Path.Combine(args[importFlag+1], "src", "profile.rcpc.h"), "UNEXPECTED_HEADER");
        if (mode == "new-source") File.WriteAllText(Path.Combine(args[importFlag+1], "src", "new-generated.c"), "UNEXPECTED_SOURCE");
        if (mode == "deleted-source") File.Delete(Path.Combine(args[importFlag+1], "src", "fixture.c"));
        if (mode.StartsWith("rcpc-")) {
            for (int i = 0; i < args.Length - 1; i++) {
                if (args[i] != "-import") continue;
                string project = args[i + 1];
                string rcpc = Path.Combine(project, Path.GetFileName(project) + ".rcpc");
                if (mode == "rcpc-modified") File.WriteAllText(rcpc, "REGENERATED_RCPC");
                if (mode == "rcpc-deleted") File.Delete(rcpc);
                if (mode == "rcpc-added") File.WriteAllText(Path.Combine(project, "src", "new-generated.rcpc"), "REGENERATED_RCPC");
            }
        }
        string outputs = Environment.GetEnvironmentVariable("RXCLI_FIXTURE_OUTPUTS");
        if (!String.IsNullOrEmpty(outputs) && mode != "missing-output") {
            foreach (string output in outputs.Split('|')) {
                Directory.CreateDirectory(Path.GetDirectoryName(output));
                File.WriteAllText(output, mode == "empty-output" ? "" : "FRESH_OUTPUT");
                if (mode == "stale-output") File.SetLastWriteTimeUtc(output, DateTime.UtcNow.AddDays(-1));
            }
        }
        if (mode == "no-config" && buildFlag >= 0) {
            File.WriteAllText(Path.Combine(args[importFlag + 1], ".cproject"), "AFTER_HEADLESS");
            File.WriteAllText(Path.Combine(args[importFlag + 1], Path.GetFileName(args[importFlag + 1]) + ".rcpc"), "AFTER_HEADLESS_RCPC");
            string workspace = args[Array.IndexOf(args, "-data") + 1];
            Directory.CreateDirectory(Path.Combine(workspace, ".metadata"));
            File.WriteAllText(Path.Combine(workspace, ".metadata", ".log"), "WORKSPACE_DIAGNOSTIC");
            Console.WriteLine("No Config matched " + args[buildFlag + 1] + ". Skipping...");
            Console.WriteLine("Build completed successfully");
            return 0;
        }
        return 0;
    }
}
''', encoding="utf-8")
        subprocess.run([str(CSC), "/nologo", "/target:exe", "/out:" + str(cls.executable), str(source)],
                       check=True, capture_output=True, timeout=30)
        cls.projects = []
        for name in ("a.project", "b.project"):
            project = cls.directory / name
            project.mkdir()
            (project / ".project").write_text(
                "<projectDescription><name>" + name + "</name></projectDescription>", encoding="utf-8")
            (project / ".cproject").write_text("EFFECTIVE_" + name, encoding="utf-8")
            (project / (name + ".rcpc")).write_text("GENERATED_INPUT", encoding="utf-8")
            cls.projects.append(project)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def setUp(self):
        for project in self.projects:
            (project / ".project").write_text(
                "<projectDescription><name>" + project.name + "</name></projectDescription>", encoding="utf-8")
            (project / ".cproject").write_text("EFFECTIVE_" + project.name, encoding="utf-8")
            (project / (project.name + ".rcpc")).write_text("GENERATED_INPUT", encoding="utf-8")
            (project / "fixture.scfg").write_text("EXPECTED_SC_CONFIG", encoding="utf-8")
            source = project / "src"
            source.mkdir(exist_ok=True)
            (source / "fixture.c").write_text("EXPECTED_SOURCE", encoding="utf-8")
            (source / "profile.rcpc.h").write_text("EXPECTED_HEADER", encoding="utf-8")
            (source / "new-generated.c").unlink(missing_ok=True)
            (source / "new-generated.rcpc").unlink(missing_ok=True)
            generated = project / "smc_gen" / "r_config"
            generated.mkdir(parents=True, exist_ok=True)
            (generated / "r_bsp_config.h").write_text("EXPECTED_HEADER", encoding="utf-8")

    def invoke(self, mode="success", timeout=5, allow_timeout=False, targets=None, expected_outputs=None, preserve_calls=False):
        calls = self.directory / (self._testMethodName + ".arguments")
        log = self.directory / (self._testMethodName + ".log")
        targets = targets or ["a.project/HardwareDebug", "b.project/HardwareDebug"]
        code = (
            "$ErrorActionPreference='Stop'; . " + literal(HELPER) + "; "
            "$result=Invoke-RxE2StudioBuild -Executable " + literal(self.executable)
            + " -WorkspacePath " + literal(self.directory / "workspace")
            + " -ProjectPaths @(" + ",".join(map(literal, self.projects)) + ")"
            + " -BuildTargets @(" + ",".join(map(literal, targets)) + ")"
            + " -OutputLog " + literal(log) + " -TimeoutSeconds " + str(timeout)
            + (" -AllowTimeoutExitCode" if allow_timeout else "")
            + (" -ExpectedOutputs @(" + ",".join(map(literal, expected_outputs)) + ")" if expected_outputs else "")
            + "; Write-Output ('RESULT=' + $result)"
        )
        if not preserve_calls:
            calls.unlink(missing_ok=True)
        environment = dict(os.environ, RXCLI_FIXTURE_OUTPUTS="|".join(map(str, expected_outputs or [])), RXCLI_FIXTURE_MODE=mode, RXCLI_FIXTURE_ARGUMENTS=str(calls),
                           RXCLI_FIXTURE_CHILD_PID=str(self.directory / (self._testMethodName + ".child-pid")),
                           RXCLI_FIXTURE_EXIT_MARKER=str(self.directory / (self._testMethodName + ".exit-marker")))
        # File capture lets the harness wait for pwsh itself. The orphan fixture
        # can also inherit outer standard handles, which must not make Python's
        # own communicate() wait for the fixture grandchild to close a pipe.
        stdout_path = self.directory / (self._testMethodName + ".stdout")
        stderr_path = self.directory / (self._testMethodName + ".stderr")
        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            result = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-Command", code],
                                    stdout=stdout, stderr=stderr, env=environment, timeout=20)
        result.stdout = stdout_path.read_text(encoding="utf-8", errors="replace")
        result.stderr = stderr_path.read_text(encoding="utf-8", errors="replace")
        return result, calls, log

    def test_imports_precede_exact_configuration_builds(self):
        result, calls, _ = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("RESULT=0", result.stdout)
        rows = [line.split("|") for line in calls.read_text().splitlines()]
        self.assertEqual(1, len(rows))
        self.assertEqual(rows[0], [
            "-nosplash", "-data", str(self.directory / "workspace"), "-application",
            "org.eclipse.cdt.managedbuilder.core.headlessbuild",
            "-import", str(self.projects[0]), "-import", str(self.projects[1]),
            "-build", r"^a\.project/HardwareDebug$", "-build", r"^b\.project/HardwareDebug$",
        ])

    def test_raw_tool_output_stays_in_log(self):
        result, _, log = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("RAW_TOOL_OUTPUT_SENTINEL", result.stdout + result.stderr)
        self.assertIn("RAW_TOOL_OUTPUT_SENTINEL", log.read_text(encoding="utf-8"))

    def test_zero_exit_import_rejection_is_rejected(self):
        result, calls, _ = self.invoke("reject")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("was rejected", result.stderr)
        self.assertEqual(len(calls.read_text().splitlines()), 1)

    def test_build_exit_code_is_terminal(self):
        result, calls, _ = self.invoke("build-error")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("failed with exit code 23", result.stderr)
        self.assertNotIn("RESULT=", result.stdout)
        self.assertEqual(len(calls.read_text().splitlines()), 1)

    def test_zero_exit_typed_internal_error_error_and_fatal_are_terminal(self):
        for diagnostic in ("C0520000", "E0520020", "F0520035"):
            with self.subTest(diagnostic=diagnostic):
                result, calls, log = self.invoke("typed-" + diagnostic)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("reported a compiler, assembler or linker error", result.stderr)
                self.assertIn(diagnostic, log.read_text(encoding="utf-8"))
                self.assertEqual(len(calls.read_text().splitlines()), 1)

    def test_source_copy_profile_changes_new_and_deleted_sources_are_terminal(self):
        for mode in ("source-drift", "project-drift", "scfg-drift", "generated-header-drift",
                     "rcpc-named-header-drift", "new-source", "deleted-source"):
            with self.subTest(mode=mode):
                self.setUp()
                result, calls, log = self.invoke(mode)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("changed project inputs unexpectedly", result.stderr)
                detail = log.read_text(encoding="utf-8")
                self.assertIn("Unexpected RX project input changes:", detail)
                self.assertIn('"before_sha256":', detail)
                self.assertIn('"after_sha256":', detail)
                self.assertNotIn("UNEXPECTED_PROFILE", detail)
                self.assertNotIn("UNEXPECTED_SOURCE", detail)
                self.assertEqual(len(calls.read_text().splitlines()), 1)

    @contextmanager
    def git_project(self, *, track_rcpc):
        project = self.projects[0]
        subprocess.run(["git", "init", "-q", str(project)], check=True, capture_output=True)
        try:
            (project / ".gitignore").write_text("HardwareDebug/\n*.rcpc\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(project), "add", ".project", ".cproject", "src", "smc_gen",
                            "fixture.scfg", ".gitignore"], check=True, capture_output=True)
            if track_rcpc:
                subprocess.run(["git", "-C", str(project), "add", "-f", project.name + ".rcpc"],
                               check=True, capture_output=True)
            yield project
        finally:
            # Git objects are readonly on Windows. Only this owned temporary
            # fixture's .git is removed; no source repository is affected.
            git_dir = project / ".git"
            self.assertTrue(git_dir.resolve().is_relative_to(self.directory.resolve()))
            for entry in git_dir.rglob("*"):
                if entry.is_file():
                    entry.chmod(0o666)
            shutil.rmtree(git_dir)
            (project / ".gitignore").unlink(missing_ok=True)

    def test_source_copy_generated_rcpc_changes_are_not_source_drift(self):
        for mode in ("rcpc-modified", "rcpc-added", "rcpc-deleted"):
            with self.subTest(mode=mode):
                self.setUp()
                result, calls, log = self.invoke(mode)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("RESULT=0", result.stdout)
                self.assertNotIn("Unexpected RX project input changes:", log.read_text(encoding="utf-8"))
                self.assertEqual(len(calls.read_text().splitlines()), 1)

    def test_git_ignored_rcpc_and_source_copy_have_same_drift_policy(self):
        for mode in ("rcpc-modified", "rcpc-added", "rcpc-deleted"):
            with self.subTest(mode=mode):
                self.setUp()
                with self.git_project(track_rcpc=False):
                    result, calls, log = self.invoke(mode)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertNotIn("Unexpected RX project input changes:", log.read_text(encoding="utf-8"))
                    self.assertEqual(len(calls.read_text().splitlines()), 1)

    def test_git_tracked_rcpc_remains_protected_even_when_ignored(self):
        for mode in ("rcpc-modified", "rcpc-deleted"):
            with self.subTest(mode=mode):
                self.setUp()
                with self.git_project(track_rcpc=True) as project:
                    result, calls, log = self.invoke(mode)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("changed project inputs unexpectedly", result.stderr)
                    self.assertIn(project.name + ".rcpc", log.read_text(encoding="utf-8"))
                    self.assertEqual(len(calls.read_text().splitlines()), 1)

    def test_git_project_generated_source_cannot_become_next_run_baseline(self):
        with self.git_project(track_rcpc=True) as project:
            result, calls, log = self.invoke("new-source")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("changed project inputs unexpectedly", result.stderr)
            self.assertEqual(len(calls.read_text().splitlines()), 1)
            self.assertTrue((project / "src/new-generated.c").is_file())
            first_log = log.read_bytes()
            second, second_calls, _ = self.invoke(preserve_calls=True)
            self.assertNotEqual(second.returncode, 0)
            self.assertIn("unregistered source inputs", second.stderr)
            self.assertEqual(second_calls, calls)
            self.assertEqual(log.read_bytes(), first_log, "preflight rejection must preserve the first drift evidence")
            self.assertEqual(len(calls.read_text().splitlines()), 1, "second run must stop before the launcher")

    def test_declared_outputs_must_be_nonempty_and_fresh(self):
        for mode in ("success", "missing-output", "empty-output", "stale-output"):
            with self.subTest(mode=mode):
                output = self.projects[0] / "HardwareDebug" / (mode + ".mot")
                output.unlink(missing_ok=True)
                result, calls, _ = self.invoke(mode, expected_outputs=[output])
                self.assertEqual(result.returncode == 0, mode == "success", result.stderr)
                if mode != "success":
                    self.assertIn("Expected RX build output is", result.stderr)
                self.assertEqual(len(calls.read_text().splitlines()), 1)

    def test_zero_exit_with_no_configuration_preserves_private_snapshots(self):
        result, calls, log = self.invoke("no-config")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("build was rejected", result.stderr)
        self.assertEqual(len(calls.read_text().splitlines()), 1)
        self.assertIn("No Config matched", log.read_text(encoding="utf-8"))
        lines = log.read_text(encoding="utf-8").splitlines()
        diagnostic = Path(next(line.split(": ",1)[1] for line in lines if line.startswith("Private import metadata diagnostics: ")))
        try:
            snapshots = json.loads((diagnostic/"index.json").read_text(encoding="utf-8"))
            self.assertEqual(["before-imports", "after-headless-run"], [item["phase"] for item in snapshots])
            source = str(self.projects[0]/".cproject")
            self.assertEqual("EFFECTIVE_a.project",(diagnostic/snapshots[0]["files"][source]).read_text())
            self.assertEqual("AFTER_HEADLESS",(diagnostic/snapshots[1]["files"][source]).read_text())
            rcpc = str(self.projects[0] / (self.projects[0].name + ".rcpc"))
            self.assertEqual("GENERATED_INPUT", (diagnostic/snapshots[0]["files"][rcpc]).read_text())
            self.assertEqual("AFTER_HEADLESS_RCPC", (diagnostic/snapshots[1]["files"][rcpc]).read_text())
            self.assertEqual("WORKSPACE_DIAGNOSTIC", (diagnostic / "workspace.log").read_text())
        finally:
            self.assertEqual(diagnostic.parent,Path(tempfile.gettempdir()))
            self.assertTrue(diagnostic.name.startswith("rx-e2-import-"))
            shutil.rmtree(diagnostic)

    def test_nonfatal_plugin_warning_is_not_import_failure(self):
        result, _, _ = self.invoke("warning")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("RESULT=0", result.stdout)

    def test_timeout_is_terminal_even_with_compatibility_switch(self):
        result, calls, log = self.invoke("delay", timeout=1, allow_timeout=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("import/build timed out", result.stderr)
        self.assertNotIn("RESULT=124", result.stdout)
        self.assertEqual(len(calls.read_text().splitlines()), 1)
        self.assertIn("RAW_TOOL_OUTPUT_SENTINEL", log.read_text(encoding="utf-8"))
        self.assertNotIn("RAW_TOOL_OUTPUT_SENTINEL", result.stdout + result.stderr)

    @contextmanager
    def fixture_child(self):
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD),
        ]
        kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
        kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel.TerminateProcess.restype = wintypes.BOOL
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]

        def running(pid):
            handle = kernel.OpenProcess(0x1000, False, pid)
            if not handle:
                return False
            try:
                code = wintypes.DWORD()
                if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
                    raise ctypes.WinError(ctypes.get_last_error())
                return code.value == 259
            finally:
                kernel.CloseHandle(handle)

        child_file = self.directory / (self._testMethodName + ".child-pid")
        try:
            yield child_file, running
        finally:
            if child_file.is_file():
                pid = int(child_file.read_text())
                # Keep one handle for identity verification and termination so
                # PID reuse cannot redirect cleanup to an unrelated process.
                handle = kernel.OpenProcess(0x1000 | 0x0001 | 0x00100000, False, pid)
                if handle:
                    try:
                        image = ctypes.create_unicode_buffer(32768)
                        length = wintypes.DWORD(len(image))
                        if not kernel.QueryFullProcessImageNameW(handle, 0, image, ctypes.byref(length)):
                            raise ctypes.WinError(ctypes.get_last_error())
                        self.assertEqual(Path(image.value).resolve(), self.executable.resolve())
                        code = wintypes.DWORD()
                        if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
                            raise ctypes.WinError(ctypes.get_last_error())
                        if code.value == 259:
                            if not kernel.TerminateProcess(handle, 1):
                                raise ctypes.WinError(ctypes.get_last_error())
                            self.assertEqual(0, kernel.WaitForSingleObject(handle, 10000))
                    finally:
                        kernel.CloseHandle(handle)

    def test_timeout_terminates_the_owned_launcher_child(self):
        with self.fixture_child() as (child_file, running):
            result, calls, log = self.invoke("delay-child", timeout=1, allow_timeout=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("RESULT=124", result.stdout)
            self.assertIn("import/build timed out", result.stderr)
            self.assertIn("RAW_TOOL_OUTPUT_SENTINEL", log.read_text(encoding="utf-8"))
            self.assertNotIn("RAW_TOOL_OUTPUT_SENTINEL", result.stdout + result.stderr)
            self.assertEqual(1, len(calls.read_text().splitlines()))
            self.assertTrue(child_file.is_file(), "fixture must spawn its owned child before timeout")
            pid = int(child_file.read_text())
            deadline = time.monotonic() + 3
            while running(pid) and time.monotonic() < deadline:
                time.sleep(0.03)
            self.assertFalse(running(pid), "owned child survived the timed-out launcher")

    def test_orphan_pipe_after_zero_exit_fails_within_global_budget(self):
        with self.fixture_child() as (child_file, running):
            result, calls, log = self.invoke("orphan-pipe", timeout=1, allow_timeout=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("output drain timed out", result.stderr)
            self.assertNotIn("RESULT=124", result.stdout)
            self.assertEqual(1, len(calls.read_text().splitlines()))
            marker = self.directory / (self._testMethodName + ".exit-marker")
            self.assertEqual("0", marker.read_text(encoding="utf-8"))
            # The fixture launcher exited before the deadline; its orphan still
            # owns the pipe. Failure must arrive within the remaining 1s budget.
            self.assertLess(time.time() - marker.stat().st_mtime, 1.0)
            self.assertTrue(running(int(child_file.read_text())), "fixture orphan must still hold the pipe")
            self.assertIn("Output drain timed out", log.read_text(encoding="utf-8"))

    def test_strict_timeout_throws(self):
        result, _, log = self.invoke("delay", timeout=1)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("import/build timed out", result.stderr)
        self.assertIn("RAW_TOOL_OUTPUT_SENTINEL", log.read_text(encoding="utf-8"))
        self.assertNotIn("RAW_TOOL_OUTPUT_SENTINEL", result.stdout + result.stderr)

    def test_unimported_build_target_is_rejected_before_process(self):
        result, calls, _ = self.invoke(targets=["other/HardwareDebug"])
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(calls.exists())


if __name__ == "__main__":
    unittest.main()

"""Exercise RX launcher orchestration without an IDE or firmware build."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
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
public class Launcher {
    public static int Main(string[] args) {
        File.AppendAllText(Environment.GetEnvironmentVariable("RXCLI_FIXTURE_ARGUMENTS"),
            String.Join("|", args) + "\n");
        Console.WriteLine("RAW_TOOL_OUTPUT_SENTINEL");
        string mode = Environment.GetEnvironmentVariable("RXCLI_FIXTURE_MODE");
        if (mode == "delay") Thread.Sleep(700);
        if (mode == "reject" && args[4] == "import") {
            Console.WriteLine("Project: file:/fixture can't be found");
            return 0;
        }
        if (mode == "warning") Console.WriteLine(
            "Warning: NLS unused message: failedReadDuringWrite in: org.eclipse.core.internal.filesystem.messages");
        if (mode == "build-error" && args[4] == "build") return 23;
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
            cls.projects.append(project)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def invoke(self, mode="success", timeout=5, allow_timeout=False, targets=None):
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
            + "; Write-Output ('RESULT=' + $result)"
        )
        environment = dict(os.environ, RXCLI_FIXTURE_MODE=mode, RXCLI_FIXTURE_ARGUMENTS=str(calls))
        result = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-Command", code],
                                capture_output=True, text=True, encoding="utf-8", errors="replace",
                                env=environment, timeout=20)
        return result, calls, log

    def test_imports_precede_exact_configuration_builds(self):
        result, calls, _ = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("RESULT=0", result.stdout)
        rows = [line.split("|") for line in calls.read_text().splitlines()]
        self.assertEqual([row[4] for row in rows], ["import", "import", "build", "build"])
        self.assertEqual([row[5] for row in rows[2:]], [r"^a\.project/HardwareDebug$", r"^b\.project/HardwareDebug$"])
        self.assertTrue(all(row[:2] == ["-nosplash", "-data"] and row[3] == "project" for row in rows))

    def test_raw_tool_output_stays_in_log(self):
        result, _, log = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("RAW_TOOL_OUTPUT_SENTINEL", result.stdout + result.stderr)
        self.assertIn("RAW_TOOL_OUTPUT_SENTINEL", log.read_text(encoding="utf-8"))

    def test_zero_exit_import_rejection_stops_build(self):
        result, calls, _ = self.invoke("reject")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("was rejected", result.stderr)
        self.assertEqual(len(calls.read_text().splitlines()), 1)

    def test_build_exit_code_reaches_artifact_validating_caller(self):
        result, calls, _ = self.invoke("build-error")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("RESULT=23", result.stdout)
        self.assertEqual(len(calls.read_text().splitlines()), 3)

    def test_nonfatal_plugin_warning_is_not_import_failure(self):
        result, _, _ = self.invoke("warning")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("RESULT=0", result.stdout)

    def test_timeout_returns_124_only_when_fallback_allowed(self):
        result, calls, _ = self.invoke("delay", timeout=1, allow_timeout=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("RESULT=124", result.stdout)
        self.assertLess(len(calls.read_text().splitlines()), 4)

    def test_strict_timeout_throws(self):
        result, _, _ = self.invoke("delay", timeout=1)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("timed out", result.stderr)

    def test_unimported_build_target_is_rejected_before_process(self):
        result, calls, _ = self.invoke(targets=["other/HardwareDebug"])
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(calls.exists())


if __name__ == "__main__":
    unittest.main()

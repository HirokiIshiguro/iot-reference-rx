"""Exercise the real mismatch check with no Python available on PATH."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
PWSH = shutil.which("pwsh")


def quote(value):
    return "'" + str(value).replace("'", "''") + "'"


@unittest.skipUnless(os.name == "nt" and PWSH, "Windows PowerShell 7 required")
class ExplicitPythonTests(unittest.TestCase):
    def test_common_kernel_guard_uses_runner_python_with_empty_path(self):
        runner = ROOT / 'tools/idt/rpi4_windows_python.ps1'
        guard_functions = ROOT / 'tools/rx_e2studio_cli.ps1'
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            (work / 'tools/ci').mkdir(parents=True)
            (work / 'tools/ci/check_common_kernel.py').write_text(
                "import sys\nassert sys.argv[1] == '--repo-root'\nprint('GUARD_OK')\n", encoding='utf-8')
            fixture = work / 'runner.ps1'
            source = runner.read_text(encoding='utf-8')
            pinned = 'C:/ProgramData/SAFFTI-IdtRxRunner/work/tools/venv-3.14.10/Scripts/python.exe'
            self.assertEqual(source.count(pinned), 1)
            fixture.write_text(source.replace(pinned, str(Path(sys.executable)).replace('\\', '/')),
                               encoding='utf-8')
            harness = work / 'guard-check.ps1'
            harness.write_text('\n'.join([
                "$ErrorActionPreference = 'Stop'", "$env:PATH = ''",
                "Remove-Item Env:RX72N_IDT_PYTHON -ErrorAction SilentlyContinue",
                '. ' + quote(guard_functions),
                "$missing = $false",
                "try { Assert-RxCommonKernel -ProjectRoot " + quote(work) + " } "
                "catch [System.Management.Automation.CommandNotFoundException] { $missing = $true }",
                "if (-not $missing) { throw 'Expected missing PATH python.' }",
                '. ' + quote(fixture),
                "if ($env:RX72N_IDT_PYTHON -cne $script:IdtWorkerPython) { throw 'Python selection differs.' }",
                'Assert-RxCommonKernel -ProjectRoot ' + quote(work),
            ]), encoding='utf-8')
            result = subprocess.run([PWSH, '-NoProfile', '-NonInteractive', '-File', str(harness)],
                                    cwd=work, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('GUARD_OK', result.stdout)

    def test_suite_mismatch_check_uses_the_supplied_python(self):
        source = (ROOT / "tools/test_build_rx_idt.ps1").read_text(encoding="utf-8")
        start = source.index("    $rejected = $false\n")
        end = source.index("    foreach ($path in $projectSnapshots.Keys)", start)
        mismatch_check = source[start:end]
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            builder = work / "builder.ps1"
            builder.write_text("""param([string]$ProjectRoot, [string]$Target, [string]$TestGroup,
 [string]$Python='python', [string]$ProvenanceFile, [switch]$ValidateOnly)
$ErrorActionPreference = 'Stop'
& $Python -c 'import sys; sys.exit(0)'
if ($LASTEXITCODE -ne 0) { throw 'Selected Python failed.' }
throw 'build requires suite mismatch'
""", encoding="utf-8")
            harness = work / "check.ps1"
            harness.write_text("\n".join([
                "$ErrorActionPreference = 'Stop'", "$env:PATH = ''", "$root = " + quote(work),
                "$builder = " + quote(builder), "$Python = " + quote(sys.executable),
                "$provenances = @{'rx72n-ethernet' = 'fixture'}", mismatch_check,
            ]), encoding="utf-8")
            result = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-File", str(harness)],
                                    cwd=work, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()

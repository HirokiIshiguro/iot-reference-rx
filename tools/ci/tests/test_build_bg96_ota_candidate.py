"""BG96 OTA uses the RX CLI adapter while preserving its temporary profile."""
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from tools import build_bg96_ota_candidate as builder

ROOT = Path(__file__).resolve().parents[3]
WRAPPER = ROOT / "tools/build_rx_e2studio_project.ps1"
PWSH = shutil.which("pwsh")


class Bg96CandidateTests(unittest.TestCase):
    def test_cli_wrapper_keeps_selected_executable_and_collects_private_log(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            cli = base / "e2studio-cli.exe"
            cli.touch()
            (base / "e2studioc.exe").touch()
            log_path = base / "candidate.log"
            def launch(command, *_args, **_kwargs):
                Path(command[command.index("-OutputLog") + 1]).write_text("CLI fixture detail\n")
            with log_path.open("w", encoding="utf-8") as log, mock.patch.object(builder, "run_logged", side_effect=launch) as run:
                builder.run_e2studio_managed_build(cli, base / "workspace", base, log, 7)
            command = run.call_args.args[0]
            self.assertEqual(command[:4], ["pwsh", "-NoProfile", "-NonInteractive", "-File"])
            self.assertEqual(Path(command[4]), WRAPPER)
            self.assertEqual(command[command.index("-Executable") + 1], str(cli.resolve()))
            self.assertEqual(command[-2:], ["-TimeoutSeconds", "7"])
            self.assertNotIn("-application", command)
            self.assertNotIn("all", command)
            self.assertEqual(run.call_args.args[4], 37)  # original IDE budget + metadata cleanup grace
            self.assertEqual(run.call_args.kwargs["timeout_exit_code"], 124)
            self.assertIn("CLI fixture detail", log_path.read_text())

    def test_console_launcher_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            console = Path(temporary) / "e2studioc.exe"
            console.touch()
            with self.assertRaisesRegex(RuntimeError, "e2studio-cli.exe"):
                builder.resolve_e2studio_cli(console)

    def test_adapter_timeout_is_terminal_but_other_exits_allow_makefile_validation(self):
        for code in (124, 23):
            with self.subTest(code=code), mock.patch.object(builder.subprocess, "run", return_value=SimpleNamespace(returncode=code)):
                if code == 124:
                    with self.assertRaisesRegex(RuntimeError, "timed out"):
                        builder.run_logged(["fixture"], ROOT, io.StringIO(), {}, 30, True, 124)
                else:
                    builder.run_logged(["fixture"], ROOT, io.StringIO(), {}, 30, True, 124)

    def test_parent_tls_version_and_make_flow_are_preserved_and_restored(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            app = base / "Projects/aws_bg96_ck_rx65n_tsip/e2studio_ccrx"
            config = app / "src/frtos_config/demo_config.h"
            config.parent.mkdir(parents=True)
            original_version = b"#define APP_VERSION_MAJOR 0\r\n#define APP_VERSION_MINOR 1\r\n#define APP_VERSION_BUILD 0\r\n"
            config.write_bytes(original_version)
            original_profile = b'<option value="MBEDTLS_CONFIG_FILE=&lt;&quot;aws_mbedtls_config_with_tsip.h&quot;&gt;"/>\r\n'
            (app / ".cproject").write_bytes(original_profile)
            for name in ("key.fixture", "e2studio-cli.exe", "make.exe", "tools/create_bg96_rsu.py", "tools/generate_bg96_ota_signer_cert.py"):
                path = base / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
            args = SimpleNamespace(repo_root=base, app_dir=app, output_dir=base/"output", signing_key=base/"key.fixture",
                e2studio_cli=base/"e2studio-cli.exe", workspace=base/"workspace", e2studio_timeout=5,
                make=base/"make.exe", ccrx_bin=None, tls_backend="tsip", require_tls_version="TLSv1.3", version=(3, 4, 5))
            def managed(*_args):
                self.assertIn("aws_mbedtls_config_with_tsip13.h", (app/".cproject").read_text())
                (app/"HardwareDebug").mkdir()
                (app/"HardwareDebug/makefile").touch()
            def make(command, *_args, **_kwargs):
                self.assertIn("#define APP_VERSION_MAJOR 3", config.read_text())
                self.assertIn("#define APP_VERSION_MINOR 4", config.read_text())
                self.assertIn("#define APP_VERSION_BUILD 5", config.read_text())
                if command[-1].endswith(".mot"):
                    for suffix in ("mot", "abs"):
                        (app/f"HardwareDebug/aws_bg96_ck_rx65n_tsip.{suffix}").touch()
            with mock.patch.object(builder, "parse_args", return_value=args), \
                 mock.patch.object(builder, "resolve_make", return_value=args.make), \
                 mock.patch.object(builder, "build_environment", return_value={}), \
                 mock.patch.object(builder, "run_e2studio_managed_build", side_effect=managed) as ide, \
                 mock.patch.object(builder, "run_logged", side_effect=make) as make_run, \
                 mock.patch.object(builder, "run"):
                self.assertEqual(builder.main(), 0)
                self.assertEqual(ide.call_count, 1)
                self.assertEqual([call.args[0][1:] for call in make_run.call_args_list],
                                 [["clean"], ["-j2", "aws_bg96_ck_rx65n_tsip.mot"]])
                self.assertEqual(config.read_bytes(), original_version)
                self.assertEqual((app/".cproject").read_bytes(), original_profile)
                # Existing generated makefiles still bypass the IDE phase.
                self.assertEqual(builder.main(), 0)
                self.assertEqual(ide.call_count, 1)


@unittest.skipUnless(os.name == "nt" and PWSH, "Windows PowerShell 7 required")
class SingleProjectWrapperTests(unittest.TestCase):
    def test_cold_workspace_exact_project_and_metadata_restoration_on_all_exits(self):
        workspace_root = Path("C:/ai/codex/ws")
        workspace_root.mkdir(parents=True, exist_ok=True)
        for mode, expected_exit in (("success", 0), ("build-error", 23), ("timeout", 124), ("throw", 124),
                                    ("restore-error", 124), ("bad-path", 124), ("overlap", 124), ("bad-timeout", 124)):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory(prefix="bg96-cli-mock-", dir=workspace_root) as temporary:
                base = Path(temporary)
                wrapper = base / WRAPPER.name
                shutil.copyfile(WRAPPER, wrapper)
                actual_helper = str(ROOT/"tools/rx_e2studio_cli.ps1").replace("'", "''")
                (base/"rx_e2studio_cli.ps1").write_text(". '"+actual_helper+"'\n"+r'''
function Invoke-RxE2StudioBuild {
    param($Executable, $WorkspacePath, $ProjectPaths, $BuildTargets, $OutputLog, $TimeoutSeconds, [switch]$AllowTimeoutExitCode)
    if (Test-Path -LiteralPath $WorkspacePath) { throw 'Workspace was not cold.' }
    $p=$ProjectPaths[0]
    if ([IO.File]::ReadAllText((Join-Path $p '.cproject')) -ne 'PARENT-TSIP13-PROFILE') { throw 'Parent TLS profile lost.' }
    @{ targets=@($BuildTargets); timeout=$TimeoutSeconds; allow_timeout=[bool]$AllowTimeoutExitCode } | ConvertTo-Json | Set-Content -LiteralPath $OutputLog
    foreach($file in @('.project','.cproject','fixture.rcpc')) { [IO.File]::WriteAllText((Join-Path $p $file),'IDE MUTATION') }
    switch($env:BG96_CLI_FIXTURE_MODE) {
        'throw' { throw 'Fixture import failure' }
        'build-error' { return 23 }
        'timeout' { return 124 }
        'restore-error' {
            $script:fixtureLock = [IO.File]::Open((Join-Path $p '.project'), [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::None)
            return 0
        }
    }
    return 0
}
''', encoding="utf-8")
                project = base/"source"
                project.mkdir()
                snapshots = {".project":b"<projectDescription><name>actual.ota.project</name></projectDescription>\r\n",
                             ".cproject":b"PARENT-TSIP13-PROFILE", "fixture.rcpc":b"\xff\x00ORIGINAL\r\n"}
                for name, content in snapshots.items():
                    (project/name).write_bytes(content)
                workspace = base/"workspace"
                workspace.mkdir()
                (workspace/"stale").touch()
                log = base/"calls.json"
                result = subprocess.run([PWSH,"-NoProfile","-NonInteractive","-File",str(wrapper),
                    "-Executable","fixture-e2studio-cli.exe","-Workspace",str(project if mode == "overlap" else workspace),
                    "-ProjectPath",str(base/"missing" if mode == "bad-path" else project),
                    "-OutputLog",str(log),"-TimeoutSeconds","0" if mode == "bad-timeout" else "11"], env=dict(os.environ,BG96_CLI_FIXTURE_MODE=mode),
                    capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=20)
                self.assertEqual(result.returncode, expected_exit, result.stderr)
                if mode in ("bad-path", "overlap", "bad-timeout"):
                    self.assertFalse(log.exists(), "pre-launch rejection must not invoke the IDE")
                    for name, original in snapshots.items():
                        self.assertEqual((project/name).read_bytes(), original)
                    continue
                calls=json.loads(log.read_text(encoding="utf-8-sig"))
                self.assertEqual(calls["targets"],["actual.ota.project/HardwareDebug"])
                self.assertEqual(calls["timeout"],11)
                self.assertFalse(calls["allow_timeout"])
                for name, original in snapshots.items():
                    if mode == "restore-error" and name == ".project":
                        self.assertEqual((project/name).read_bytes(), b"IDE MUTATION")
                        self.assertIn("metadata restoration failed", result.stderr)
                        continue
                    self.assertEqual((project/name).read_bytes(),original)


if __name__ == "__main__":
    unittest.main()

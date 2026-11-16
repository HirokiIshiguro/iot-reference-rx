from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from tools.idt import windows_build_job as job

CHILD_TREE = ("import sys,pathlib,subprocess,os,time,json; "
              "assert sys.stdin.buffer.readline()==b'go\\n'; "
              "c=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
              "p=pathlib.Path(sys.argv[1]); t=p.with_suffix('.tmp'); "
              "t.write_text(json.dumps([os.getpid(),c.pid])); os.replace(t,p); "
              "time.sleep(60)")


@unittest.skipUnless(os.name == "nt", "requires Windows Job Objects")
class WindowsBuildJobTests(unittest.TestCase):
    def test_normal_child_runs_only_after_go(self):
        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary) / "started"
            source = ("import sys,pathlib; "
                      "assert sys.stdin.buffer.readline()==b'go\\n'; "
                      "pathlib.Path(sys.argv[1]).write_text('started')")
            job.run_managed([sys.executable, "-c", source, str(marker)], timeout=10, env=os.environ.copy())
            self.assertEqual(marker.read_text(), "started")

    def test_failed_job_assignment_never_sends_go(self):
        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary) / "must-not-exist"
            source = ("import sys,pathlib; "
                      "data=sys.stdin.buffer.readline(); "
                      "pathlib.Path(sys.argv[1]).write_text('started') if data==b'go\\n' else None")
            real = job._kernel()

            class FailedAssignment:
                def __getattr__(self, name):
                    if name == "AssignProcessToJobObject":
                        return lambda *_args: 0
                    return getattr(real, name)

            with patch.object(job, "_kernel", return_value=FailedAssignment()):
                with self.assertRaises(OSError):
                    job.run_managed([sys.executable, "-c", source, str(marker)], timeout=10, env=os.environ.copy())
            self.assertFalse(marker.exists())

    def test_timeout_kills_child_and_grandchild(self):
        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary) / "pids.json"
            errors = []

            def run():
                try:
                    job.run_managed([sys.executable, "-c", CHILD_TREE, str(marker)], timeout=5, env=os.environ.copy())
                except BaseException as error:
                    errors.append(error)

            thread = threading.Thread(target=run)
            thread.start()
            deadline = time.monotonic() + 4
            while not marker.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(marker.exists(), "dummy process did not start")
            pids = json.loads(marker.read_text())
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.OpenProcess.argtypes = (ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong)
            kernel.OpenProcess.restype = ctypes.c_void_p
            kernel.WaitForSingleObject.argtypes = (ctypes.c_void_p, ctypes.c_ulong)
            kernel.WaitForSingleObject.restype = ctypes.c_ulong
            kernel.CloseHandle.argtypes = (ctypes.c_void_p,)
            handles = [kernel.OpenProcess(0x00100000, False, pid) for pid in pids]
            try:
                self.assertTrue(all(handles))
                thread.join(timeout=15)
                self.assertFalse(thread.is_alive())
                self.assertEqual(len(errors), 1)
                self.assertIsInstance(errors[0], subprocess.TimeoutExpired)
                self.assertEqual([kernel.WaitForSingleObject(h, 10000) for h in handles], [0, 0])
            finally:
                for handle in handles:
                    if handle:
                        kernel.CloseHandle(handle)

    def test_forcibly_killed_worker_closes_its_job_and_dummy_tree(self):
        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary) / "pids.json"
            owner = subprocess.Popen([sys.executable, "-B", "-m", "tools.ci.tests.test_windows_build_job",
                                      "--dummy-controller", str(marker)], stdin=subprocess.DEVNULL,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                     creationflags=subprocess.CREATE_NO_WINDOW)
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.OpenProcess.argtypes = (ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong)
            kernel.OpenProcess.restype = ctypes.c_void_p
            kernel.WaitForSingleObject.argtypes = (ctypes.c_void_p, ctypes.c_ulong)
            kernel.WaitForSingleObject.restype = ctypes.c_ulong
            kernel.TerminateProcess.argtypes = (ctypes.c_void_p, ctypes.c_uint)
            kernel.CloseHandle.argtypes = (ctypes.c_void_p,)
            handles = []
            try:
                deadline = time.monotonic() + 10
                while not marker.exists() and owner.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(marker.exists(), "dummy controller did not start its tree")
                pids = json.loads(marker.read_text())
                handles = [kernel.OpenProcess(0x00100001, False, pid) for pid in pids]
                self.assertTrue(all(handles))
                owner.kill()
                owner.wait(timeout=10)
                self.assertEqual([kernel.WaitForSingleObject(h, 10000) for h in handles], [0, 0])
            finally:
                if owner.poll() is None:
                    owner.kill()
                    owner.wait(timeout=10)
                for handle in handles:
                    if handle:
                        if kernel.WaitForSingleObject(handle, 0) != 0:
                            kernel.TerminateProcess(handle, 1)
                            kernel.WaitForSingleObject(handle, 10000)
                        kernel.CloseHandle(handle)

    def test_build_script_rejects_without_handshake(self):
        root = Path(__file__).resolve().parents[2] / "idt"
        for name, extra in (("rpi4_windows_build.ps1", ["-ProvenanceFile", "unused"]),
                            ("rpi4_windows_public_build.ps1", ["-Output", "unused"])):
            args = ["pwsh", "-NoProfile", "-NonInteractive", "-File", str(root / name),
                    "-ProjectRoot", "unused", "-Python", "unused", "-Workspace", "unused",
                    "-PrivateLog", "unused", *extra]
            result = subprocess.run(args, input=b"", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b"Build containment was not established", result.stdout)

    def test_transport_wrapper_ignores_stale_git_status_and_propagates_exceptions(self):
        tools = Path(__file__).resolve().parents[2]
        wrapper = tools / 'idt/rpi4_windows_build.ps1'
        input_state = str(tools / 'rx_e2studio_cli.ps1').replace("'", "''")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'tools').mkdir()
            project = root / 'git-free-project'
            project.mkdir()
            (project / '.project').write_text('<projectDescription/>', encoding='utf-8')
            builder = root / 'tools/build_rx72n_idt_transport.ps1'
            builder.write_text(
                "param($ProjectRoot,$Target,$TestGroup,$ProvenanceFile,$Workspace,$E2Studio,$Python)\n"
                f". '{input_state}'\n"
                "$global:LASTEXITCODE=0\n"
                "$null=Get-RxE2StudioProjectInputState -ProjectPaths @("
                "(Join-Path $ProjectRoot 'git-free-project')) "
                "-BuildDirectories @('HardwareDebug') -ExcludedPaths @()\n"
                "if ($LASTEXITCODE -eq 0) { throw 'fixture did not exercise the Git fallback' }\n"
                "Write-Output 'BUILD_HELPER_SUCCEEDED'\n", encoding='utf-8')
            log = root / 'build.log'
            args = ['pwsh', '-NoProfile', '-NonInteractive', '-File', str(wrapper),
                    '-ProjectRoot', str(root), '-Python', sys.executable,
                    '-ProvenanceFile', 'unused', '-Workspace', str(root),
                    '-PrivateLog', str(log)]
            env = dict(os.environ, GIT_CEILING_DIRECTORIES=str(root))
            result = subprocess.run(args, input=b'go\n', stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, env=env, timeout=30)
            self.assertEqual(result.returncode, 0, 'successful helper left a stale Git exit code')
            self.assertIn('BUILD_HELPER_SUCCEEDED', log.read_text(encoding='utf-8-sig'))

            builder.write_text(
                "param($ProjectRoot,$Target,$TestGroup,$ProvenanceFile,$Workspace,$E2Studio,$Python)\n"
                "throw 'synthetic build failure'\n", encoding='utf-8')
            result = subprocess.run(args, input=b'go\n', stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, env=env, timeout=30)
            self.assertNotEqual(result.returncode, 0, 'terminating build error was swallowed')

    def test_public_build_records_safe_failure_stage(self):
        helper = Path(__file__).resolve().parents[2] / 'idt/rpi4_windows_public_build.ps1'
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'tools').mkdir()
            (root / 'tools/test_build_rx_idt.ps1').write_text(
                "param($ProjectRoot,$Python,$CompileTargets,$OutputDirectory,$WorkspaceRoot,[ref]$DiagnosticStage)\n"
                "$DiagnosticStage.Value='target-build'\nthrow [IO.IOException]::new('private fixture')\n",
                encoding='utf-8')
            harness = root / 'harness.ps1'
            harness.write_text(
                "function global:Get-FileHash { param($LiteralPath,$Algorithm) "
                "if ($LiteralPath -like '*e2studio-cli.exe') { $h='6b021cc60f8736f4124f2ff61586bf883a415d1957b0a584346403cc91de2320' } "
                "else { $h='64c3daf4cd80557efa98071378dbe13fb4ba9f78da80560f5616bbb22ff5bc0a' }; "
                "[pscustomobject]@{Hash=$h} }\n"
                "& $args[0] -ProjectRoot $args[1] -Python $args[2] -Workspace $args[1] "
                "-Output $args[1] -PrivateLog $args[3]\n", encoding='utf-8')
            log = root / 'build.log'
            args = ['pwsh', '-NoProfile', '-NonInteractive', '-File', str(harness),
                    str(helper), str(root), sys.executable, str(log)]
            result = subprocess.run(args, input=b'go\n', stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
            self.assertNotEqual(result.returncode, 0)
            contents = log.read_text(encoding='utf-8-sig')
            self.assertIn('PUBLIC_BUILD_FAILURE stage=target-build type=IOException source=test_build_rx_idt.ps1 line=3', contents)
            from tools.idt.rpi4_windows_worker import PUBLIC_FAILURE
            self.assertTrue(any(PUBLIC_FAILURE.fullmatch(line) for line in contents.splitlines()))


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--dummy-controller":
        job.run_managed([sys.executable, "-c", CHILD_TREE, sys.argv[2]], timeout=60, env=os.environ.copy())
    else:
        unittest.main()

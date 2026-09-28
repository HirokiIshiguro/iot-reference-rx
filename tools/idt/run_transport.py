#!/usr/bin/env python3
"""Run a selected FRQ development group through a guarded RPi1 PTY."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import pty
import re
import secrets
import select
import shlex
import signal
import subprocess
import sys
import threading
import time
import tty
from datetime import datetime, timezone
import xml.etree.ElementTree as ET
from test_selection import parse_test_ids
from ota_witness import UartWitness
from flash_failure import raise_if_flash_failed

GROUPS = ("FullTransportInterfaceTLS", "FullCloudIoT", "OTADataplaneMQTT", "FullPKCS11_Core", "OTACore")
SUITE = "FRQ_2.5.0"
SSH = os.environ.get("IDT_WINDOWS_SSH", "/mnt/c/Windows/System32/OpenSSH/ssh.exe")


def write_all(fd, data):
    while data:
        written = os.write(fd, data)
        if written <= 0:
            raise OSError("raw stream write failed")
        data = data[written:]


def wrapper_command(path):
    path = Path(path).resolve(strict=True)
    interpreter = {".sh": "/bin/bash", ".py": sys.executable}.get(path.suffix)
    parts = ([interpreter] if interpreter else []) + [str(path), "{{testData.sourcePath}}"]
    # FRQ 2.5 splits this string into argv; quote characters are not shell syntax.
    if any(any(char.isspace() for char in part) for part in parts):
        raise ValueError("FRQ callback paths must not contain whitespace")
    return " ".join(parts)


def stop_idt(process, timeout):
    if process is None or process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGINT)  # Let IDT clean up its AWS resources first.
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                return
            process.wait()


def inspect_junit(results):
    reports = sorted(results.rglob("FRQ_Report.xml"))
    if len(reports) != 1:
        raise RuntimeError(f"expected one current JUnit report, found {len(reports)}")
    root = ET.parse(reports[0]).getroot()
    failures = max(int(root.get("failures", "0")), len(root.findall(".//failure")))
    errors = max(int(root.get("errors", "0")), len(root.findall(".//error")))
    tests = max(int(root.get("tests", "0")), len(root.findall(".//testcase")))
    skipped = max(int(root.get("skipped", "0")), len(root.findall(".//skipped")))
    for suite in root.findall(".//testsuite"):
        failures = max(failures, int(suite.get("failures", "0")))
        errors = max(errors, int(suite.get("errors", "0")))
        skipped = max(skipped, int(suite.get("skipped", "0")))
    return {"report": str(reports[0]), "tests": tests, "failures": failures,
            "errors": errors, "skipped": skipped}


def wait_for_native(process, bridge, run_dir, timeout_seconds):
    deadline = time.monotonic() + timeout_seconds
    while process.poll() is None:
        raise_if_flash_failed(run_dir)
        if bridge.failed.is_set() or bridge.remote.poll() is not None:
            raise RuntimeError(bridge.failure_reason or "UART bridge exited during IDT execution")
        if time.monotonic() > deadline:
            raise RuntimeError("IDT run exceeded its time budget")
        time.sleep(0.2)
    # Native IDT may exit zero before the next poll after ignoring a failed callback.
    raise_if_flash_failed(run_dir)


class Bridge:
    def __init__(self, token, capture_dir):
        self.ready = threading.Event()
        self.failed = threading.Event()
        self.closed = threading.Event()
        self.closing = threading.Event()
        self.forward_stopped = threading.Event()
        self.failure_reason = None
        self.master, self.slave = pty.openpty()
        tty.setraw(self.slave)
        os.set_blocking(self.master, False)
        self.device = os.ttyname(self.slave)
        source = Path(__file__).with_name("rpi_uart_bridge.py").read_bytes()
        bootstrap = "exec(bytes.fromhex('" + source.hex() + "'))"
        command = "python3 -u -c " + shlex.quote(bootstrap) + " " + shlex.quote(token)
        env = {key: value for key, value in os.environ.items() if not key.startswith("AWS_")}
        self.capture = None
        try:
            self.capture = UartWitness(capture_dir)
            self.remote = subprocess.Popen(
                [SSH, "-T", "-o", "BatchMode=yes", "-o", "ServerAliveInterval=10",
                 "-o", "ServerAliveCountMax=3", "rpi1", command],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                bufsize=0, env=env)
        except Exception:
            if self.capture is not None:
                self.capture.finish()
            os.close(self.master)
            os.close(self.slave)
            raise
        self.threads = [threading.Thread(target=target, daemon=True)
                        for target in (self.status, self.from_uart, self.to_uart)]
        for thread in self.threads:
            thread.start()

    def status(self):
        for raw in self.remote.stderr:
            line = raw.decode("utf-8", "replace").strip()
            if line == "IDT_UART_READY":
                self.ready.set()
            if line:
                print("[bridge] " + line, file=sys.stderr, flush=True)
        if not self.closing.is_set():
            self.failed.set()

    def pump(self, source, destination):
        try:
            while not self.closing.is_set():
                if not select.select([source], [], [], 0.2)[0]:
                    continue
                try:
                    data = os.read(source, 65536)
                except BlockingIOError:
                    continue
                if not data:
                    break
                write_all(destination, data)
        except OSError as error:
            if not self.closing.is_set():
                print("[bridge] stream failure: " + str(error), file=sys.stderr, flush=True)
        finally:
            if not self.closing.is_set():
                self.failed.set()

    def forward_uart(self, data):
        remaining = memoryview(data)
        while remaining and not self.closing.is_set() and not self.forward_stopped.is_set():
            if not select.select([], [self.master], [], 0.2)[1]:
                continue
            try:
                written = os.write(self.master, remaining)
            except BlockingIOError:
                continue
            if written <= 0:
                raise OSError("PTY forwarding failed")
            remaining = remaining[written:]

    def from_uart(self):
        tail = b""
        capture_failed = False
        try:
            while not self.closed.is_set():
                data = os.read(self.remote.stdout.fileno(), 65536)
                if not data:
                    break
                # Capture before the native reader. After IDT exits, keep
                # draining SSH stdout through EOF instead of losing its tail.
                if not capture_failed:
                    try:
                        self.capture.feed(data)
                    except (OSError, ValueError, RuntimeError):
                        capture_failed = True
                        self.failure_reason = "private UART capture failed"
                        self.failed.set()
                if not capture_failed:
                    self.forward_uart(data)
                tail = (tail + data)[-1024:]
                if b"IDT_PORT_FATAL:" in tail:
                    self.failure_reason = "device reported a fatal IDT port error"
                    self.failed.set()
                    self.forward_stopped.set()
        except OSError:
            self.failure_reason = "UART RX stream failed"
            self.failed.set()
        finally:
            if not self.closing.is_set():
                self.failed.set()

    def to_uart(self):
        self.pump(self.master, self.remote.stdin.fileno())

    def close(self):
        self.closing.set()
        self.forward_stopped.set()
        # EOF makes the remote helper close UART, unlink its owner file, and unlock.
        if self.remote.stdin:
            try:
                self.remote.stdin.close()
            except BrokenPipeError:
                pass
        try:
            self.remote.wait(timeout=135)  # Remote reset may wait for the shared RFP lock.
        except subprocess.TimeoutExpired:
            self.remote.terminate()
            try:
                self.remote.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.remote.kill()
                self.remote.wait()
        self.threads[1].join(timeout=5)
        self.closed.set()
        for descriptor in (self.master, self.slave):
            os.close(descriptor)
        for thread in self.threads:
            thread.join(timeout=1)
        if self.threads[1].is_alive():
            raise RuntimeError("UART capture did not drain before closing")
        for stream in (self.remote.stdout, self.remote.stderr):
            if stream:
                stream.close()
        capture = self.capture.finish()
        (self.capture.directory.parent / "uart-capture.json").write_text(
            json.dumps(capture, indent=2) + "\n", encoding="utf-8")
        if not capture["complete"] or self.failure_reason:
            raise RuntimeError(self.failure_reason or "UART capture did not complete")
        if self.remote.returncode != 0:
            raise RuntimeError("RPi bridge/end-state cleanup failed, exit " + str(self.remote.returncode))


def interrupted(_signum, _frame):
    raise KeyboardInterrupt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--idt-root", required=True)
    parser.add_argument("--source-path", required=True)
    parser.add_argument("--userdata-template", required=True)
    parser.add_argument("--device-template", required=True)
    parser.add_argument("--region", default=os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION"))
    parser.add_argument("--output", required=True, help="new, nonexistent run output directory")
    parser.add_argument("--group", choices=GROUPS, default=GROUPS[0])
    parser.add_argument("--test-id", help="Optional comma-separated OTA cases; omitted runs the group")
    parser.add_argument("--timeout-seconds", type=int, default=4500)
    parser.add_argument("--cleanup-timeout-seconds", type=int, default=120)
    args = parser.parse_args()
    try:
        selected_test_ids = parse_test_ids(args.test_id)
    except ValueError as error:
        parser.error(str(error))
    args.test_id = ",".join(selected_test_ids) if selected_test_ids else None
    if args.test_id and args.group != "OTADataplaneMQTT":
        parser.error("The selected test ID belongs to OTADataplaneMQTT")
    if sys.platform != "linux" or not Path(SSH).is_file():
        parser.error("this prototype requires WSL and Windows OpenSSH")
    if not args.region or not os.getenv("AWS_ACCESS_KEY_ID") or not os.getenv("AWS_SECRET_ACCESS_KEY"):
        parser.error("AWS region and inherited AWS credential environment variables are required")
    if args.timeout_seconds <= 0 or args.cleanup_timeout_seconds <= 0:
        parser.error("timeouts must be positive")
    idt_root = Path(args.idt_root).resolve(strict=True)
    source = Path(args.source_path).resolve(strict=True)
    run_dir = Path(args.output).resolve()
    if not os.getenv("IDT_RUNTIME_DIR") or Path(os.environ["IDT_RUNTIME_DIR"]).resolve() != run_dir:
        parser.error("IDT_RUNTIME_DIR must match --output")
    if run_dir == source or source in run_dir.parents:
        parser.error("runtime files must be outside the source repository")
    if any(any(char.isspace() for char in str(path)) for path in (idt_root, source, run_dir)):
        parser.error("FRQ paths must not contain whitespace")
    for key in ("IDT_PROVENANCE_FILE", "IDT_PRIVATE_KEY_FILE", "IDT_WINDOWS_PYTHON", "IDT_WINDOWS_PWSH"):
        if not os.getenv(key):
            parser.error(key + " must be inherited from the Windows launcher")
    binary = idt_root / "bin/devicetester_linux_x86-64"
    if not binary.is_file() or not source.is_dir():
        parser.error("IDT binary or source checkout is missing")
    userdata = json.loads(Path(args.userdata_template).read_text(encoding="utf-8-sig"))
    devices = json.loads(Path(args.device_template).read_text(encoding="utf-8-sig"))
    template_text = json.dumps([userdata, devices])
    for key in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        if os.getenv(key) and os.environ[key] in template_text:
            parser.error("AWS credentials must not be embedded in a configuration template")
    manifest_version = re.search(r'^version:\s*["\']?([^"\'\s]+)',
                                 (source / "manifest.yml").read_text(encoding="utf-8"), re.MULTILINE)
    if not manifest_version or userdata.get("freeRTOSVersion") != manifest_version.group(1):
        parser.error("userdata FreeRTOS version must match the source manifest")
    if len(devices) != 1 or len(devices[0].get("devices", [])) != 1:
        parser.error("device template must contain exactly one pool and one device")
    userdata["sourcePath"] = str(source)
    userdata["retainModifiedSourceDirectories"] = True
    for field, wrapper in (("buildTool", Path(__file__).with_name("build_transport.sh")),
                           ("flashTool", Path(__file__).with_name("flash_transport.py"))):
        userdata.setdefault(field, {})["command"] = [wrapper_command(wrapper)]
    run_dir.mkdir(parents=True, exist_ok=False)
    for folder in ("logs", "results", "certificates"):
        (run_dir / folder).mkdir()
    temporary_sources = run_dir / "source"
    temporary_sources.mkdir()
    config_path = idt_root / "configs/config.json"
    package_lock = open(idt_root / ".codex-prototype.lock", "a+b")
    bridge = process = None
    original_config = None
    config_written = False
    result = {"group": args.group, "testId": args.test_id, "suite": SUITE, "qualification": "not_evaluated",
              "sourcePath": str(source), "startedUtc": datetime.now(timezone.utc).isoformat()}
    exit_code = 1
    try:
        fcntl.flock(package_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        original_config = config_path.read_bytes()
        signal.signal(signal.SIGINT, interrupted)
        signal.signal(signal.SIGTERM, interrupted)
        token = secrets.token_hex(16)
        bridge = Bridge(token, run_dir / "uart-witness")
        deadline = time.monotonic() + 30
        while not bridge.ready.wait(0.1):
            if bridge.failed.is_set() or bridge.remote.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError("RPi UART bridge did not become ready")
        devices[0]["id"] = "rx72n-ether-prototype"
        devices[0]["devices"][0]["connectivity"] = {
            "protocol": "uart", "serialPort": bridge.device, "baudRate": 921600}
        for filename, data in (("device.json", devices), ("userdata.json", userdata)):
            (run_dir / filename).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        config = {"log": {"location": str(run_dir / "logs")},
                  "configFiles": {"root": str(run_dir), "device": str(run_dir / "device.json")},
                  "testPath": str(idt_root / "tests"), "reportPath": str(run_dir / "results"),
                  "certificatePath": str(run_dir / "certificates"),
                  "awsRegion": args.region, "auth": {"method": "environment"}}
        config_written = True
        config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        env = os.environ.copy()
        env.update(TMPDIR=str(temporary_sources), IDT_BENCH_TOKEN=token, AWS_REGION=args.region,
                   AWS_DEFAULT_REGION=args.region, IDT_SOURCE_PATH=str(source),
                   IDT_RUNTIME_DIR=str(run_dir))
        command = [str(binary), "run-suite", "--suite-id", SUITE, "--group-id", args.group,
                   "--pool-id", devices[0]["id"], "--userdata", "userdata.json",
                   "--upgrade-test-suite", "n", "--update-idt", "n", "--update-managed-policy", "n"]
        if args.test_id:
            command += ["--test-id", args.test_id]
        print("Starting development-only " + args.group + "; this cannot qualify a release.", flush=True)
        sensitive = [env[key] for key in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN") if env.get(key)]
        process = subprocess.Popen(command, cwd=idt_root / "bin", env=env,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   start_new_session=True)

        def console():
            for raw in process.stdout:
                line = raw.decode("utf-8", "replace")
                for value in sensitive:
                    line = line.replace(value, "[REDACTED]")
                print(line, end="", flush=True)

        output_thread = threading.Thread(target=console, daemon=True)
        output_thread.start()
        wait_for_native(process, bridge, run_dir, args.timeout_seconds)
        bridge.forward_stopped.set()
        output_thread.join(timeout=5)
        result["idtExitCode"] = process.returncode
        result.update(inspect_junit(run_dir / "results"))
        passed = (process.returncode == 0 and result["tests"] > 0 and
                  result["failures"] == result["errors"] == result["skipped"] == 0)
        selected_verdict = "SINGLE_CASE_PASS" if len(selected_test_ids) == 1 else "SELECTED_CASES_PASS"
        result["verdict"] = (selected_verdict if args.test_id else "SELECTED_GROUP_PASS") if passed else "FAIL"
        exit_code = 0 if passed else 1
    except KeyboardInterrupt:
        result.update(verdict="INTERRUPTED", reason="signal received")
        exit_code = 130
    except Exception as error:
        result.update(verdict="FAIL", reason=str(error))
        print("IDT prototype failed: " + str(error), file=sys.stderr, flush=True)
    finally:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        try:
            stop_idt(process, args.cleanup_timeout_seconds)
        finally:
            try:
                if bridge is not None:
                    try:
                        bridge.close()
                    except Exception as error:
                        result.update(verdict="FAIL", cleanupError=str(error))
                        exit_code = 1
                        print("IDT cleanup failed: " + str(error), file=sys.stderr, flush=True)
            finally:
                try:
                    if config_written and original_config is not None:
                        config_path.write_bytes(original_config)
                finally:
                    package_lock.close()
                    result["finishedUtc"] = datetime.now(timezone.utc).isoformat()
                    (run_dir / "transport-result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

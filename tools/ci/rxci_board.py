"""Board side of tools/ci/rxci.py (Raspberry Pi runner next to the board).

One test = one process: take the board lock, install the firmware, provision,
observe, and always park the board at the end. The lock is released when the
process exits. There is no other lock, no sudo and no persistent state.
"""
from __future__ import annotations

import fcntl
import json
import os
import shlex
import socket
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from xml.sax.saxutils import escape, quoteattr

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
LOCK_WAIT_SECONDS = 3000
RFP_SECONDS = 300          # one rfp-cli command; the slowest measured one takes 54 s
# Start and size of one bank of the dual-bank code flash (tools/idt/public_signer_provision.py LAYOUTS).
BANK = {"rx72n-ethernet": (0xFFE00000, 0x200000), "rx65n-bg96": (0xFFF00000, 0x100000),
        "rx671-wifi": (0xFFF00000, 0x100000)}


class Board:
    def __init__(self, registry: dict, name: str):
        self.name = name
        self.config = registry["boards"][name]
        targets = json.loads((TOOLS / "idt" / "targets.json").read_text(encoding="utf-8"))["targets"]
        self.target = targets[self.config["target"]]
        self.uart = self.target["uart"]
        self.baud = self.target["baud"]
        self._lock = None
        sys.path.insert(0, str(TOOLS))
        import rx671_ota_host as host  # shared RFP and UART helpers of this repository

        start, size = BANK[self.target["id"]]
        self.host = host
        self.rfp = host.RfpConfig(
            executable="rfp-cli", device=self.target["rfp_device"], tool="e2l:" + self.target["e2lite"],
            speed=self.target["rfp_speed"],
            install_ranges=((start - size, 0xFFFBFFFF - size), (start, 0xFFFBFFFF)))

    # -- exclusive use ---------------------------------------------------
    def lock(self) -> None:
        if socket.gethostname() != self.target["hostname"]:
            raise SystemExit(f"{self.name} is attached to {self.target['hostname']}, not to this host.")
        path = Path(self.target["bench_lock"])
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = open(path, "a")
        deadline = time.monotonic() + LOCK_WAIT_SECONDS
        waited = False
        while True:
            try:
                fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() > deadline:
                    raise SystemExit(f"{self.name} stayed in use for {LOCK_WAIT_SECONDS} s.") from None
                if not waited:
                    print(f"{self.name} is in use by another job; waiting.", flush=True)
                    waited = True
                time.sleep(5)
        print(f"{self.name}: board lock taken ({path})", flush=True)

    # -- programmer --------------------------------------------------------
    def run(self, command: list, *, timeout: int = RFP_SECONDS, label: str = "") -> None:
        print(f"+ {label or 'run'}: {' '.join(str(part) for part in command)}", flush=True)
        subprocess.run([str(part) for part in command], cwd=ROOT, check=True, timeout=timeout)

    def reset_command(self) -> str:
        """Command line that releases the board from reset (used by the UART tools)."""
        return shlex.join(self.rfp.run_command())

    def park(self) -> None:
        """Hold the board in reset so that it stays quiet until the next test."""
        self.run([*self.rfp.common_command(), "-sig", "-reset", "-noquery"], label="park")

    # -- firmware ------------------------------------------------------------
    def install(self, common: Path, app: Path, logs: Path) -> None:
        """Erase the chip and install public boot trust, the boot loader and the signed application."""
        import provision_rx671_ota as provisioner

        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True,
                             text=True).stdout.strip()
        # RX72N builds the boot loader together with the application; RX671 builds it once per commit.
        bootloader = next(folder / "bootloader.mot" for folder in (app, common)
                          if (folder / "bootloader.mot").is_file())
        bank1 = bootloader.with_name("bootloader_bank1.mot")
        self.run([*self.rfp.common_command(), "-erase-chip", "-reset", "-noquery"], label="erase chip")
        args = SimpleNamespace(
            artifact_dir=logs / "provisioner", rfp_cli=self.rfp.executable, rfp_device=self.rfp.device,
            rfp_tool=self.rfp.tool, rfp_interface=self.rfp.interface, rfp_speed=self.rfp.speed,
            rfp_auth_id=self.rfp.auth_id, rfp_timeout=RFP_SECONDS,
            provisioner_mot=common / "public_signer_provisioner.mot", bootloader_mot=bootloader,
            port=self.uart, baud=self.baud, boot_timeout=45, command_timeout=15, commit_timeout=30,
            char_delay=0.002, codesigner_certificate=common / "signer.crt.pem",
            codesigner_public_key=common / "signer.pub.pem")
        summary = provisioner.provision(
            args, signer_only=True, rfp_config=self.rfp, ready_source_sha=sha,
            runner=lambda command, *, label, timeout: self.run(command, timeout=timeout, label=label))
        if summary.get("success") is not True:
            raise RuntimeError("Storing the signer's public key did not complete.")
        if bank1.is_file():
            self.run(self.rfp.program_command(bank1, leave_reset=True), label="boot loader, bank 1")
        command = [sys.executable, TOOLS / "test_uart_download_rx72n.py", "--rsu", app / "app.rsu",
                   "--port", self.uart, "--baud", self.baud, "--timeout", 420, "--post-tx-wait", 120,
                   "--wait-for-ready", "--ready-timeout", 90,
                   "--ready-message", 'send "userprog.rsu" via UART.', "--reset-cmd", self.reset_command(),
                   "--success-message", "jump to user program", "--success-timeout", 90, "--strict-success"]
        if self.name in ("rx65n", "rx671"):
            command += ["--ack-each-chunk", "--send-chunk-size", 32768, "--ack-prefix", "installing firmware..."]
        self.run(command, timeout=700, label="send the signed application over UART")


def endpoint(registry: dict, tls: str) -> str:
    entry = registry["endpoints"][tls]
    value = entry.get("value") or os.environ.get(entry["variable"], "")
    if not value:
        raise SystemExit(f"The AWS IoT endpoint for {tls} is not set ({entry.get('variable')}).")
    return value


def required_file(variable: str) -> str:
    path = os.environ.get(variable, "")
    if not path or not Path(path).is_file():
        raise SystemExit(f"CI variable {variable} (type File) is not available to this job.")
    return path


def mqtt_rx72n(registry: dict, board: Board, test: dict, common: Path, app: Path, logs: Path) -> None:
    board.install(common, app, logs)
    provision = [sys.executable, TOOLS / "provision_rx72n.py", "--port", board.uart, "--baud", board.baud,
                 "--thing-name", board.config["thing"], "--endpoint", endpoint(registry, test["tls"]),
                 "--cert", required_file(board.config["certificate_variable"]),
                 "--key", required_file(board.config["private_key_variable"]),
                 "--reset-cmd", board.reset_command(), "--reset-after-open", "--boot-wait", 12,
                 "--cli-timeout", 25, "--attempts", 3, "--no-reset"]
    board.run(provision, timeout=400, label="provision the device credentials")
    observe = [sys.executable, TOOLS / "test_mqtt_rx72n.py", "--log-port", board.uart, "--log-baud", board.baud,
               "--timeout", 600, "--reset-cmd", board.reset_command()]
    if test["tls"] == "tls13":
        observe += ["--require-tls-version", "TLSv1.3"]
    board.run(observe, timeout=700, label="observe MQTT on the UART")


def mqtt_rx671(registry: dict, board: Board, test: dict, common: Path, app: Path, logs: Path) -> None:
    """The application carries its credentials, so the test starts right after the install."""
    board.install(common, app, logs)
    observe = [sys.executable, TOOLS / "ci" / "test_rx671_wifi_uart.py", "--port", board.uart, "--baud", board.baud,
               "--timeout", 300, "--mode", "mqtt", "--reset-cmd", board.reset_command(), "--startup-retries", 1,
               "--output-log", logs / "uart.log", "--junit-output", logs / "uart-junit.xml"]
    if test["tls"] == "tls13":
        observe += ["--require-tls-version", "TLSv1.3"]
    board.run(observe, timeout=500, label="observe Wi-Fi and MQTT on the UART")


RECIPES = {("rx72n", "mqtt"): mqtt_rx72n, ("rx671", "mqtt"): mqtt_rx671}


def write_junit(path: Path, name: str, seconds: float, failure: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = f"<failure message={quoteattr(failure[:200])}>{escape(failure)}</failure>" if failure else ""
    path.write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<testsuite name="rxci" tests="1" failures="{1 if failure else 0}">'
        f'<testcase classname="rxci" name={quoteattr(name)} time="{seconds:.1f}">{body}</testcase></testsuite>\n',
        encoding="utf-8")


def run_test(registry: dict, test: dict, common: Path, app: Path, logs: Path) -> int:
    recipe = RECIPES.get((test["board"], test["feature"]))
    if recipe is None or test["backend"] != "sw":
        raise SystemExit(f"Test is not implemented yet: {test['name']}")
    logs.mkdir(parents=True, exist_ok=True)
    board = Board(registry, test["board"])
    started = time.monotonic()
    failure = ""
    board.lock()
    try:
        recipe(registry, board, test, common, app, logs)
    except subprocess.CalledProcessError as error:
        failure = f"step failed with exit code {error.returncode}: {Path(str(error.cmd[1])).name if len(error.cmd) > 1 else error.cmd[0]}"
    except subprocess.TimeoutExpired as error:
        failure = f"step exceeded {error.timeout} s: {Path(str(error.cmd[1])).name if len(error.cmd) > 1 else error.cmd[0]}"
    except (RuntimeError, OSError, ValueError) as error:
        failure = f"{type(error).__name__}: {error}"
    except SystemExit as error:
        failure = str(error)
    finally:
        try:
            board.park()
        except (subprocess.SubprocessError, OSError) as error:
            failure = failure or f"could not park the board: {error}"
    seconds = time.monotonic() - started
    write_junit(logs / "junit.xml", test["name"], seconds, failure)
    print(f"{'FAIL' if failure else 'PASS'}  {test['name']}  {seconds:.0f} s  {failure}", flush=True)
    return 1 if failure else 0

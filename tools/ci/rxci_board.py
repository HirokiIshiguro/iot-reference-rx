"""Board side of tools/ci/rxci.py (Raspberry Pi runner next to the board).

One test = one process: take the board lock, install the firmware, provision,
observe, and always park the board at the end. The lock is released when the
process exits. There is no other lock, no sudo and no persistent state.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shlex
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from xml.sax.saxutils import escape, quoteattr

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
LOCK_WAIT_SECONDS = 3000
RFP_SECONDS = 300          # one rfp-cli command; the slowest measured one takes 54 s
# Start and size of one bank of the dual-bank code flash (tools/idt/public_signer_provision.py LAYOUTS).
BANK = {"rx72n-ethernet": (0xFFE00000, 0x200000, 0xFFFBFFFF), "rx65n-bg96": (0xFFF00000, 0x100000, 0xFFFBFFFF),
        "rx671-wifi": (0xFFF00000, 0x100000, 0xFFFDFFFF)}


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

        start, size, end = BANK[self.target["id"]]
        self.host = host
        self.rfp = host.RfpConfig(
            executable="rfp-cli", device=self.target["rfp_device"], tool="e2l:" + self.target["e2lite"],
            speed=self.target["rfp_speed"],
            install_ranges=((start - size, end - size), (start, end)))

    # -- exclusive use ---------------------------------------------------
    def try_lock(self) -> bool:
        """Take the board lock only if nobody holds it."""
        path = Path(self.target["bench_lock"])
        if socket.gethostname() != self.target["hostname"] or not path.exists():
            return False
        self._lock = open(path, "a")
        try:
            fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        return True

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
    def run(self, command: list, *, timeout: int = RFP_SECONDS, label: str = "", env: dict | None = None,
            log: Path | None = None) -> None:
        """Run one step. With log, its output goes to that file and only the end is printed.

        The UART observers read the port in the same loop that prints. If printing blocks on the
        job log, the port is not read and lines are lost, so their output never goes to the job log.
        """
        print(f"+ {label or 'run'}: {' '.join(str(part) for part in command)}", flush=True)
        arguments = [str(part) for part in command]
        environment = {**os.environ, **env} if env else None
        if log is None:
            subprocess.run(arguments, cwd=ROOT, check=True, timeout=timeout, env=environment)
            return
        log.parent.mkdir(parents=True, exist_ok=True)
        started = time.monotonic()
        try:
            with open(log, "wb") as stream:
                subprocess.run(arguments, cwd=ROOT, check=True, timeout=timeout, env=environment,
                               stdout=stream, stderr=subprocess.STDOUT)
        finally:
            lines = log.read_text(encoding="utf-8", errors="replace").splitlines() if log.is_file() else []
            print(f"  {time.monotonic() - started:.0f} s, {len(lines)} lines in {log.name}; the last lines:", flush=True)
            for line in lines[-25:]:
                print("  | " + line[:200], flush=True)

    def reset_command(self) -> str:
        """Command line that releases the board from reset (used by the UART tools)."""
        return shlex.join(self.rfp.run_command())

    def park(self) -> None:
        """Hold the board in reset so that it stays quiet until the next test."""
        self.run([*self.rfp.common_command(), "-sig", "-reset", "-noquery"], label="park")

    # -- firmware ------------------------------------------------------------
    def install(self, common: Path, app: Path, logs: Path, rsu: Path | None = None) -> None:
        """Erase the chip and install public boot trust, the boot loader and the signed application."""
        import provision_rx671_ota as provisioner

        # The provisioner announces the commit it was built from. A reused build comes from an
        # earlier commit with the same build inputs, so the build says which one (build.json).
        made = common / "build.json"
        if made.is_file():
            sha = json.loads(made.read_text(encoding="utf-8"))["commit"]
        else:
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
        command = [sys.executable, TOOLS / "test_uart_download_rx72n.py", "--rsu", rsu or app / "app.rsu",
                   "--port", self.uart, "--baud", self.baud, "--timeout", 420, "--post-tx-wait", 120,
                   "--wait-for-ready", "--ready-timeout", 180 if self.name == "rx65n" else 90,
                   "--ready-message", 'send "userprog.rsu" via UART.', "--reset-cmd", self.reset_command(),
                   "--success-message", "jump to user program", "--success-timeout", 90, "--strict-success"]
        if self.name in ("rx65n", "rx671"):
            command += ["--ack-each-chunk", "--send-chunk-size", 32768, "--ack-prefix", "installing firmware..."]
        self.run(command, timeout=700, label="send the signed application over UART", log=logs / "uart-download.log")


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


def private_key_arguments(board: Board, test: dict) -> list:
    """A TSIP build never receives the private key in the clear; it gets the wrapped key afterwards."""
    if test["backend"] == "tsip":
        return ["--skip-private-key"]
    return ["--key", required_file(board.config["private_key_variable"])]


def provision_tsip_keys(board: Board, test: dict, *, reset_after: bool = False) -> None:
    """Send the wrapped TLS keys of a TSIP build. The application must be waiting in its CLI.

    The wrapped client key belongs to the fixed certificate of the board, so a TSIP test
    cannot use a certificate created for the run.
    """
    if test["backend"] != "tsip":
        return
    board.run([sys.executable, TOOLS / "provision_tsip_over_uart.py", "--target", board.name, "--port", board.uart,
               "--baud", board.baud, "--chunk-size", 128, "--timeout", 30, "--no-enter-cli",
               "--reset-after" if reset_after else "--no-reset-after"], timeout=600,
              label="provision the wrapped TLS keys (TSIP)")


def mqtt_rx72n(registry: dict, board: Board, test: dict, builds: list, logs: Path) -> None:
    common, app = builds
    board.install(common, app, logs)
    provision = [sys.executable, TOOLS / "provision_rx72n.py", "--port", board.uart, "--baud", board.baud,
                 "--thing-name", board.config["thing"], "--endpoint", endpoint(registry, test["tls"]),
                 "--cert", required_file(board.config["certificate_variable"]),
                 *private_key_arguments(board, test),
                 "--reset-cmd", board.reset_command(), "--reset-after-open", "--boot-wait", 12,
                 "--cli-timeout", 25, "--attempts", 3, "--no-reset"]
    board.run(provision, timeout=400, label="provision the device credentials")
    provision_tsip_keys(board, test, reset_after=True)
    observe = [sys.executable, TOOLS / "test_mqtt_rx72n.py", "--log-port", board.uart, "--log-baud", board.baud,
               "--timeout", 600, "--reset-cmd", board.reset_command()]
    if test["tls"] == "tls13":
        observe += ["--require-tls-version", "TLSv1.3"]
    board.run(observe, timeout=700, label="observe MQTT on the UART", log=logs / "observe.log")


def fleet_rx72n(registry: dict, board: Board, test: dict, builds: list, logs: Path) -> None:
    """The board registers itself with the claim certificate; what it created is deleted at the end."""
    import rxci
    import rxci_aws

    common, app = builds
    template = os.environ.get(board.config["fleet_template_variable"], "")
    if not template:
        raise SystemExit(f"CI variable {board.config['fleet_template_variable']} is not available to this job.")
    board.install(common, app, logs)
    provision = [sys.executable, TOOLS / "provision_rx72n.py", "--fleet-provisioning", "--port", board.uart,
                 "--baud", board.baud, "--endpoint", endpoint(registry, test["tls"]), "--template-name", template,
                 "--claim-cert", required_file(board.config["claim_certificate_variable"]),
                 "--claim-key", required_file(board.config["claim_private_key_variable"]),
                 "--no-reset", "--reset-cmd", board.reset_command(), "--reset-after-open", "--boot-wait", 12,
                 "--cli-timeout", 25, "--attempts", 3]
    board.run(provision, timeout=400, label="provision the claim credentials")
    observe = [sys.executable, TOOLS / "test_fleet_rx72n.py", "--log-port", board.uart, "--log-baud", board.baud,
               "--timeout", 600, "--reset-cmd", board.reset_command(), "--summary-json", logs / "fleet_summary.json"]
    if test["tls"] == "tls13":
        observe += ["--require-tls-version", "TLSv1.3"]
    try:
        board.run(observe, timeout=700, label="observe Fleet Provisioning on the UART", log=logs / "observe.log")
    finally:
        rxci_aws.delete_fleet_resources(rxci.aws_session(), logs / "fleet_summary.json")


def cleanup_ota(logs: Path, aws_session) -> None:
    """Delete the OTA update, its job and files, and the pipeline-owned thing. Safe to call twice."""
    import rxci_aws

    folder = logs / "ota"
    update, alias = folder / "ota_job_meta.json", folder / "ephemeral_thing_meta.json"
    if not update.is_file() and not alias.is_file():
        return
    env = {**os.environ, **rxci_aws.environment(aws_session())}
    steps = []
    if update.is_file():
        steps.append([sys.executable, TOOLS / "verify_ota_aws_state.py", "cleanup", "--meta-json", update,
                      "--output-json", folder / "post_cleanup_state.json"])
    if alias.is_file():
        steps.append([sys.executable, TOOLS / "manage_ephemeral_iot_thing.py", "cleanup", "--meta-json", alias,
                      "--output-json", folder / "ephemeral_thing_cleanup.json"])
    failed = 0
    for step in steps:
        print(f"+ aws cleanup: {Path(str(step[1])).name}", flush=True)
        failed += subprocess.run([str(part) for part in step], cwd=ROOT, env=env, timeout=600).returncode != 0
    if failed:
        raise RuntimeError("AWS resources of the OTA test could not be deleted; see the job log.")
    update.unlink(missing_ok=True)
    alias.unlink(missing_ok=True)


def ota_rx72n(registry: dict, board: Board, test: dict, builds: list, logs: Path) -> None:
    """The board runs the normal application and updates itself to the candidate through AWS IoT OTA."""
    import rxci
    import rxci_aws

    common, app, candidate = builds
    config = board.config
    thing = config["thing"]
    alias = f"{thing}-ota-{os.environ.get('CI_PIPELINE_ID', '0')}-{os.environ.get('CI_JOB_ID', '0')}"
    role = os.environ.get(config["ota_service_role_variable"], "")
    values = {name: os.environ.get(config[name], "") for name in ("ota_bucket_variable", "ota_signing_profile_variable")}
    if not role or not all(values.values()):
        raise SystemExit("The OTA bucket, signing profile and service role variables are not available to this job.")
    if not role.startswith("arn:"):
        role = "arn:aws:iam::" + role
    folder = logs / "ota"
    folder.mkdir(parents=True, exist_ok=True)
    env = rxci_aws.environment(rxci.aws_session())
    try:
        # A thing of its own keeps other pipelines from consuming this one-shot OTA job.
        board.run([sys.executable, TOOLS / "manage_ephemeral_iot_thing.py", "create", "--base-thing-name", thing,
                   "--thing-name", alias, "--region", rxci.REGION,
                   "--owner-project-id", os.environ.get("CI_PROJECT_ID", "0"),
                   "--owner-pipeline-id", os.environ.get("CI_PIPELINE_ID", "0"),
                   "--owner-job-id", os.environ.get("CI_JOB_ID", "0"),
                   "--meta-json", folder / "ephemeral_thing_meta.json"], timeout=300,
                  label="create the thing of this run", env=env)
        board.run([sys.executable, TOOLS / "create_ota_update.py", "--artifact-dir", folder, "--thing-name", alias,
                   "--input-rsu", candidate / "candidate.rsu", "--file-version", config["ota_candidate_version"],
                   "--bucket", values["ota_bucket_variable"], "--signing-profile", values["ota_signing_profile_variable"],
                   "--role-arn", role, "--region", rxci.REGION, "--ota-id-prefix", f"{thing}-ota"], timeout=600,
                  label="create the OTA update", env=env)
        board.install(common, app, logs)
        provision = [sys.executable, TOOLS / "provision_rx72n.py", "--port", board.uart, "--baud", board.baud,
                     "--thing-name", alias, "--endpoint", endpoint(registry, test["tls"]),
                     "--cert", required_file(config["certificate_variable"]),
                     *private_key_arguments(board, test),
                     "--codesigner-cert", candidate / "codesign_cert.pem", "--format",
                     "--reset-cmd", board.reset_command(), "--reset-after-open", "--boot-wait", 12,
                     "--cli-timeout", 25, "--attempts", 3, "--no-reset"]
        board.run(provision, timeout=400, label="provision the device credentials")
        provision_tsip_keys(board, test)
        observe = [sys.executable, TOOLS / "test_ota.py", "--port", board.uart, "--baud", board.baud,
                   "--timeout", 900, "--expected-version", config["ota_candidate_version"],
                   "--reset-cmd", board.reset_command(), "--reset-after-open", "--no-reset",
                   "--raw-log", folder / "ota_uart_raw.log", "--summary-json", folder / "ota_summary.json"]
        if test["tls"] == "tls13":
            observe += ["--require-tls-version", "TLSv1.3"]
        board.run(observe, timeout=1100, label="observe the OTA update on the UART", log=logs / "observe.log")
    finally:
        cleanup_ota(logs, rxci.aws_session)


def ota_rx65n(registry: dict, board: Board, test: dict, builds: list, logs: Path) -> None:
    """OTA over the cellular link with a thing and certificate created for this run."""
    import rxci
    import rxci_aws

    common, app, candidate = builds
    config = board.config
    role = os.environ.get(config["ota_service_role_variable"], "")
    if not role:
        raise SystemExit(f"CI variable {config['ota_service_role_variable']} is not available to this job.")
    if not role.startswith("arn:"):
        role = "arn:aws:iam::" + role
    folder = logs / "ota"
    folder.mkdir(parents=True, exist_ok=True)
    board.install(common, app, logs)
    session = rxci.aws_session()
    name = f"{rxci_aws.owner()}-rx65n"
    tool = [sys.executable, TOOLS / "bg96_bootloader_integration.py"]
    serial = ["--uart-port", board.uart, "--baud", board.baud]
    programmer = ["--rfp-cli", board.rfp.executable, "--rfp-device", board.rfp.device, "--rfp-tool", board.rfp.tool,
                  "--rfp-interface", board.rfp.interface, "--rfp-speed", board.rfp.speed,
                  "--rfp-auth-id", board.rfp.auth_id]
    tsip = test["backend"] == "tsip"
    try:
        if tsip:
            base = os.environ.get(config["thing_variable"], "")
            if not base:
                raise SystemExit(f"CI variable {config['thing_variable']} is not available to this job.")
            name = f"{base}-ota-{os.environ.get('CI_PIPELINE_ID', '0')}-{os.environ.get('CI_JOB_ID', '0')}"
            board.run([sys.executable, TOOLS / "manage_ephemeral_iot_thing.py", "create", "--base-thing-name", base,
                       "--thing-name", name, "--region", rxci.REGION,
                       "--owner-project-id", os.environ.get("CI_PROJECT_ID", "0"),
                       "--owner-pipeline-id", os.environ.get("CI_PIPELINE_ID", "0"),
                       "--owner-job-id", os.environ.get("CI_JOB_ID", "0"),
                       "--meta-json", folder / "ephemeral_thing_meta.json"], timeout=300,
                      label="create the thing of this run", env=rxci_aws.environment(session))
            credentials = None
        else:
            credentials = rxci_aws.create_thing(session, name, config["iot_policy"])
        board.run([sys.executable, TOOLS / "create_bg96_ota_update.py", "--artifact-dir", folder, "--thing-name", name,
                   "--input-payload", candidate / "candidate_payload.bin",
                   "--file-version", config["ota_candidate_version"], "--bucket", config["ota_bucket"],
                   "--custom-signature-der", candidate / "candidate_payload.sig.der",
                   "--code-signer-cert", candidate / "codesign_cert.pem", "--role-arn", role,
                   "--region", rxci.REGION, "--ota-id-prefix", "rx65n-bg96-ota"], timeout=600,
                  label="create the OTA update", env=rxci_aws.environment(session))
        provision = [*tool, "--action", "provision-mqtt", *serial, *programmer, "--provision-cli-timeout", 25,
                     "--provision-char-delay", 0.002, "--provision-line-delay", 0.5, "--no-reset-after-provision"]
        env = {"RX65N_BG96_AWS_IOT_THING_NAME": name,
               "RX65N_BG96_AWS_IOT_ENDPOINT_OVERRIDE": endpoint(registry, test["tls"])}
        if tsip:
            # The tool takes the fixed certificate of the board from its CI variable.
            board.run([*provision, "--skip-private-key"], timeout=400, label="provision the device credentials",
                      env=env)
            provision_tsip_keys(board, test)
        else:
            with tempfile.TemporaryDirectory(prefix="rxci-") as temporary:
                certificate, key = Path(temporary) / "certificate.pem", Path(temporary) / "private_key.pem"
                certificate.write_text(credentials["certificate"], encoding="utf-8")
                key.write_text(credentials["private_key"], encoding="utf-8")
                board.run(provision, timeout=400, label="provision the device credentials",
                          env={**env, "AWS_IOT_CERT": str(certificate), "AWS_IOT_PRIVKEY": str(key)})
        board.run([sys.executable, TOOLS / "bg96_ota_prepare.py", *serial, *programmer,
                   "--code-signer-cert", candidate / "codesign_cert.pem"], timeout=300,
                  label="provision the code signing certificate")
        observe = [sys.executable, TOOLS / "bg96_ota_monitor.py", *serial, *programmer,
                   "--expected-version", config["ota_candidate_version"], "--timeout", 900, "--app-reset-retries", 2,
                   "--activate-reset-delay", 15, "--raw-log", folder / "ota_uart_raw.log", "--summary-json", folder / "ota_summary.json"]
        if test["tls"] == "tls13":
            observe += ["--require-tls-version", "TLSv1.3"]
        board.run(observe, timeout=1100, label="observe the OTA update on the UART", log=logs / "observe.log")
    finally:
        try:
            cleanup_ota(logs, rxci.aws_session)
        finally:
            rxci_aws.sweep(rxci.aws_session(), prefix=rxci_aws.owner())


def fleet_rx65n(registry: dict, board: Board, test: dict, builds: list, logs: Path) -> None:
    """Fleet Provisioning over the cellular link. The claim credentials come from CI variables."""
    import rxci
    import rxci_aws

    common, app = builds
    board.install(common, app, logs)
    tool = [sys.executable, TOOLS / "bg96_bootloader_integration.py"]
    target = ["--uart-port", board.uart, "--baud", board.baud, "--rfp-cli", board.rfp.executable,
              "--rfp-device", board.rfp.device, "--rfp-tool", board.rfp.tool, "--rfp-interface", board.rfp.interface,
              "--rfp-speed", board.rfp.speed, "--rfp-auth-id", board.rfp.auth_id]
    env = {"RX65N_BG96_AWS_IOT_ENDPOINT_OVERRIDE": endpoint(registry, test["tls"])}
    board.run([*tool, "--action", "provision-fleet", *target], timeout=400,
              label="provision the claim credentials", env=env)
    observe = [sys.executable, TOOLS / "test_fleet_rx72n.py", "--label", "CK-RX65N BG96", "--log-port", board.uart,
               "--log-baud", board.baud, "--timeout", 900, "--app-reset-retries", 2,
               "--reset-cmd", board.reset_command(), "--summary-json", logs / "fleet_summary.json"]
    if test["tls"] == "tls13":
        observe += ["--require-tls-version", "TLSv1.3"]
    try:
        board.run(observe, timeout=1500, label="observe Fleet Provisioning on the UART", log=logs / "observe.log")
    finally:
        rxci_aws.delete_fleet_resources(rxci.aws_session(), logs / "fleet_summary.json")


def mqtt_rx65n(registry: dict, board: Board, test: dict, builds: list, logs: Path) -> None:
    """Cellular board: the device credentials are created for this run and deleted at the end."""
    import rxci
    import rxci_aws

    common, app = builds
    board.install(common, app, logs)
    session = rxci.aws_session()
    name = f"{rxci_aws.owner()}-rx65n"
    tool = [sys.executable, TOOLS / "bg96_bootloader_integration.py"]
    target = ["--uart-port", board.uart, "--baud", board.baud, "--rfp-cli", board.rfp.executable,
              "--rfp-device", board.rfp.device, "--rfp-tool", board.rfp.tool, "--rfp-interface", board.rfp.interface,
              "--rfp-speed", board.rfp.speed, "--rfp-auth-id", board.rfp.auth_id]
    provision = [*tool, "--action", "provision-mqtt", *target, "--provision-cli-timeout", 25,
                 "--provision-char-delay", 0.002, "--provision-line-delay", 0.5, "--no-reset-after-provision"]
    env = {"RX65N_BG96_AWS_IOT_ENDPOINT_OVERRIDE": endpoint(registry, test["tls"])}
    try:
        if test["backend"] == "tsip":
            # The fixed thing and certificate of the board: the tool reads them from their CI variables.
            board.run([*provision, "--skip-private-key"], timeout=400, label="provision the device credentials",
                      env=env)
            provision_tsip_keys(board, test)
        else:
            credentials = rxci_aws.create_thing(session, name, board.config["iot_policy"])
            with tempfile.TemporaryDirectory(prefix="rxci-") as folder:
                certificate, key = Path(folder) / "certificate.pem", Path(folder) / "private_key.pem"
                certificate.write_text(credentials["certificate"], encoding="utf-8")
                key.write_text(credentials["private_key"], encoding="utf-8")
                board.run(provision, timeout=400, label="provision the device credentials",
                          env={**env, "RX65N_BG96_AWS_IOT_THING_NAME": name, "AWS_IOT_CERT": str(certificate),
                               "AWS_IOT_PRIVKEY": str(key)})
        board.run([*tool, "--action", "reset-app", *target], timeout=120, label="start the application")
        observe = [*tool, "--action", "verify-mqtt", *target, "--require-mqtt-pubsub", "--app-startup-timeout", 420,
                   "--mqtt-timeout", 900, "--app-reset-retries", 2]
        if test["tls"] == "tls13":
            observe += ["--require-tls-version", "TLSv1.3"]
        board.run(observe, timeout=1500, label="observe cellular attach and MQTT on the UART", log=logs / "observe.log")
    finally:
        rxci_aws.sweep(session, prefix=rxci_aws.owner())


def install_rx671(registry: dict, board: Board, kind: str, common: Path, app: Path, logs: Path) -> None:
    """Decrypt the application (it carries credentials) just for the install."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    key = hashlib.sha256(b"rxci image v1\0" + Path(
        required_file(board.config["image_secret_variable"][kind])).read_bytes().replace(b"\r", b"").strip()).digest()
    blob = (app / "app.rsu.enc").read_bytes()
    with tempfile.TemporaryDirectory(prefix="rxci-") as folder:
        rsu = Path(folder) / "app.rsu"
        rsu.write_bytes(AESGCM(key).decrypt(blob[:12], blob[12:], b"rxci"))
        board.install(common, app, logs, rsu=rsu)


def erase_application(board: Board) -> None:
    """Remove an application that carries credentials from the board."""
    board.run(board.rfp.erase_ota_install_areas_command(), label="erase the application (it carries credentials)")


def fleet_rx671(registry: dict, board: Board, test: dict, builds: list, logs: Path) -> None:
    """The application carries the Wi-Fi and claim credentials and registers itself."""
    import rxci
    import rxci_aws

    common, app = builds
    install_rx671(registry, board, "fleet", common, app, logs)
    observe = [sys.executable, TOOLS / "test_fleet_rx72n.py", "--log-port", board.uart, "--log-baud", board.baud,
               "--timeout", 900, "--reset-cmd", board.reset_command(), "--app-reset-retries", 2,
               "--label", "RX671/Type 1YN software", "--summary-json", logs / "fleet_summary.json",
               "--junit-output", logs / "fleet-junit.xml"]
    if test["tls"] == "tls13":
        observe += ["--require-tls-version", "TLSv1.3", "--minimum-tls-handshakes", 2]
    try:
        board.run(observe, timeout=1500, label="observe Fleet Provisioning on the UART", log=logs / "observe.log")
    finally:
        try:
            erase_application(board)
        finally:
            rxci_aws.delete_fleet_resources(rxci.aws_session(), logs / "fleet_summary.json")


def ota_rx671(registry: dict, board: Board, test: dict, builds: list, logs: Path) -> None:
    """OTA over Wi-Fi. Wi-Fi and device credentials are entered through the provisioner, not compiled in."""
    import rxci
    import rxci_aws

    (bundle,) = builds
    config = board.config
    role = os.environ.get(config["ota_service_role_variable"], "")
    bucket = os.environ.get(config["ota_bucket_variable"], "")
    if not role or not bucket:
        raise SystemExit("The OTA bucket and service role variables are not available to this job.")
    if not role.startswith("arn:"):
        role = "arn:aws:iam::" + role
    folder = logs / "ota"
    folder.mkdir(parents=True, exist_ok=True)
    session = rxci.aws_session()
    name = f"{rxci_aws.owner()}-rx671"
    programmer = ["--rfp-cli", board.rfp.executable, "--rfp-device", board.rfp.device, "--rfp-tool", board.rfp.tool,
                  "--rfp-interface", board.rfp.interface, "--rfp-speed", board.rfp.speed,
                  "--rfp-auth-id", board.rfp.auth_id]
    erase_chip = [*board.rfp.common_command(), "-erase-chip", "-reset", "-noquery"]
    try:
        credentials = rxci_aws.create_thing(session, name, config["iot_policy"])
        board.run([sys.executable, TOOLS / "create_bg96_ota_update.py", "--artifact-dir", folder, "--thing-name", name,
                   "--input-payload", bundle / "candidate.ota.bin", "--file-version", config["ota_candidate_version"],
                   "--bucket", bucket, "--custom-signature-der", bundle / "candidate.ota-signature.der",
                   "--code-signer-cert", bundle / "signer.crt.pem", "--certificate-name", "rx671-ota-signer.crt.pem",
                   "--role-arn", role, "--region", rxci.REGION, "--ota-id-prefix", "rx671-ota"], timeout=600,
                  label="create the OTA update", env=rxci_aws.environment(session))
        board.run(erase_chip, label="erase chip")
        with tempfile.TemporaryDirectory(prefix="rxci-") as temporary:
            certificate, key = Path(temporary) / "certificate.pem", Path(temporary) / "private_key.pem"
            certificate.write_text(credentials["certificate"], encoding="utf-8")
            key.write_text(credentials["private_key"], encoding="utf-8")
            board.run([sys.executable, TOOLS / "provision_rx671_ota.py", "--provisioner-mot", bundle / "provisioner.mot",
                       "--bootloader-mot", bundle / "bootloader.mot", "--endpoint", endpoint(registry, test["tls"]),
                       "--thing-name", name, "--certificate", certificate, "--private-key", key,
                       "--codesigner-certificate", bundle / "signer.crt.pem",
                       "--codesigner-public-key", bundle / "signer.pub.pem", "--port", board.uart, "--baud", board.baud,
                       *programmer, "--boot-timeout", 180, "--artifact-dir", logs / "provisioner"], timeout=900,
                      label="provision Wi-Fi, device credentials and the code signing key")
        observe = [sys.executable, TOOLS / "test_rx671_ota.py", "--baseline-rsu", bundle / "baseline.rsu",
                   "--baseline-version", config["ota_baseline_version"],
                   "--candidate-version", config["ota_candidate_version"],
                   "--require-tls-version", "TLSv1.3" if test["tls"] == "tls13" else "TLSv1.2",
                   "--port", board.uart, "--baud", board.baud, *programmer, "--boot-timeout", 180,
                   "--startup-reset-retries", 2, "--ota-timeout", 900, "--raw-log", folder / "ota_uart_raw.log",
                   "--summary-json", folder / "ota_summary.json", "--junit-output", folder / "ota-junit.xml"]
        board.run(observe, timeout=1500, label="observe the OTA update on the UART", log=logs / "observe.log")
    finally:
        try:
            # The data flash holds the Wi-Fi passphrase and the device key of this run.
            board.run(erase_chip, label="erase chip (it holds credentials)")
        finally:
            try:
                cleanup_ota(logs, rxci.aws_session)
            finally:
                rxci_aws.sweep(rxci.aws_session(), prefix=rxci_aws.owner())


def mqtt_rx671(registry: dict, board: Board, test: dict, builds: list, logs: Path) -> None:
    """The application carries its credentials, so the test starts right after the install."""
    common, app = builds
    install_rx671(registry, board, "app", common, app, logs)
    observe = [sys.executable, TOOLS / "ci" / "test_rx671_wifi_uart.py", "--port", board.uart, "--baud", board.baud,
               "--timeout", 300, "--mode", "mqtt", "--reset-cmd", board.reset_command(), "--startup-retries", 1,
               "--output-log", logs / "uart.log", "--junit-output", logs / "uart-junit.xml"]
    if test["tls"] == "tls13":
        observe += ["--require-tls-version", "TLSv1.3"]
    try:
        board.run(observe, timeout=500, label="observe Wi-Fi and MQTT on the UART", log=logs / "observe.log")
    finally:
        erase_application(board)


RECIPES = {("rx72n", "mqtt"): mqtt_rx72n, ("rx72n", "fleet"): fleet_rx72n, ("rx72n", "ota"): ota_rx72n,
           ("rx65n", "mqtt"): mqtt_rx65n, ("rx65n", "fleet"): fleet_rx65n, ("rx65n", "ota"): ota_rx65n,
           ("rx671", "mqtt"): mqtt_rx671, ("rx671", "fleet"): fleet_rx671, ("rx671", "ota"): ota_rx671}


def write_junit(path: Path, name: str, seconds: float, failure: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = f"<failure message={quoteattr(failure[:200])}>{escape(failure)}</failure>" if failure else ""
    path.write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<testsuite name="rxci" tests="1" failures="{1 if failure else 0}">'
        f'<testcase classname="rxci" name={quoteattr(name)} time="{seconds:.1f}">{body}</testcase></testsuite>\n',
        encoding="utf-8")


def run_test(registry: dict, test: dict, builds: list, logs: Path) -> int:
    recipe = RECIPES.get((test["board"], test["feature"]))
    if recipe is None or not test["ready"]:
        raise SystemExit(f"Test is not implemented yet: {test['name']}")
    logs.mkdir(parents=True, exist_ok=True)
    board = Board(registry, test["board"])
    started = time.monotonic()
    failure = ""
    # A cancelled job receives SIGTERM: leave through the finally blocks instead of dying in place.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit("the job was cancelled"))
    board.lock()
    try:
        recipe(registry, board, test, builds, logs)
    except subprocess.CalledProcessError as error:
        failure = f"step failed with exit code {error.returncode}: {Path(str(error.cmd[1])).name if len(error.cmd) > 1 else error.cmd[0]}"
    except subprocess.TimeoutExpired as error:
        failure = f"step exceeded {error.timeout} s: {Path(str(error.cmd[1])).name if len(error.cmd) > 1 else error.cmd[0]}"
    except (RuntimeError, OSError, ValueError) as error:
        failure = f"{type(error).__name__}: {error}"
    except SystemExit as error:
        failure = str(error)
    finally:
        # LCD check (experiment branch only, never merged): the board is not held in reset after the test,
        # so that a person can look at the LCD later.
        print("LCD check: the board is left running", flush=True)
    seconds = time.monotonic() - started
    write_junit(logs / "junit.xml", test["name"], seconds, failure)
    (logs / "finished").write_text("the test process parked the board and cleaned up\n", encoding="utf-8")
    print(f"{'FAIL' if failure else 'PASS'}  {test['name']}  {seconds:.0f} s  {failure}", flush=True)
    return 1 if failure else 0


def finish_test(registry: dict, test: dict, logs: Path, aws_session) -> int:
    """after_script of a test job. Does the cleanup again when the test process could not finish it."""
    import rxci_aws

    if (logs / "finished").is_file():
        return 0
    print("The test process did not finish its cleanup (cancelled or timed out). Cleaning up now.", flush=True)
    board = Board(registry, test["board"])
    if board.try_lock():
        try:
            board.park()
        except (subprocess.SubprocessError, OSError) as error:
            print(f"could not park the board: {error}", flush=True)
    else:
        print(f"{board.name} is in use by another job; it is not parked here.", flush=True)
    try:
        session = aws_session()
        deleted = rxci_aws.sweep(session, prefix=rxci_aws.owner())
        deleted += rxci_aws.delete_fleet_resources(session, logs / "fleet_summary.json")
        cleanup_ota(logs, aws_session)
        print(f"deleted {len(deleted)} AWS resource(s) of this job", flush=True)
    except SystemExit as error:
        print(f"AWS cleanup skipped: {error}", flush=True)
    return 0

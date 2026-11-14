#!/usr/bin/env python3
"""FRQ RX72N Transport build callback over the private paired-worker socket."""
from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys

try:
    from .prepare_transport_key import validate_source
    from .rpi4_pair import create_request, read_frame, sha256, validate_response, write_frame
    from .targets import get_target, target_fingerprint
    from .ota_support import record_packaging, validate_packaging
except ImportError:
    from prepare_transport_key import validate_source
    from rpi4_pair import create_request, read_frame, sha256, validate_response, write_frame
    from targets import get_target, target_fingerprint
    from ota_support import record_packaging, validate_packaging


def validate_build(files, source, provenance, target):
    """Validate the fixed Windows outputs before putting them in the runtime."""
    try:
        manifest = json.loads(files["build_manifest.json"].decode("utf-8-sig"))
        if (manifest["target_id"] != target["id"] or manifest["target_sha256"] != target_fingerprint(target)
                or manifest["source_sha"] != provenance["source_sha"] or manifest["source_tree_dirty"] is not False
                or manifest["submodule_shas"] != provenance["submodule_shas"]
                or manifest["dependency_target_id"] != provenance["dependency_target_id"]
                or manifest["mode"] != "idt-transport-only"
                or manifest["execution_config_sha256"] != sha256((source / "Test/include/test_execution_config.h").read_bytes())
                or manifest["parameter_config_sha256"] != sha256((source / "Test/include/test_param_config.h").read_bytes())
                or manifest["outputs"]["mot"]["sha256"] != sha256(files["rx72n_idt_transport.mot"])
                or manifest["outputs"]["bootloader"]["sha256"] != sha256(files["bootloader.mot"])):
            raise ValueError("build output identity mismatch")
    except (KeyError, TypeError, UnicodeError, json.JSONDecodeError):
        raise ValueError("invalid build output manifest") from None


def install_outputs(source, files):
    directory = source / "artifacts/idt/build_transport"
    directory.mkdir(parents=True, exist_ok=False)
    for name, data in files.items():
        path = directory / name
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(fd, "wb") as output:
            output.write(data)
    return directory


def package(source, output, target):
    validate_packaging(source, target)
    commands = [
        [sys.executable, str(source / target["packager"]), "--mot", str(output / "rx72n_idt_transport.mot"),
         "--key", str(source / target["signing_key"]), "--prm", str(source / target["prm"]),
         "--output", str(output / "rx72n_idt_transport.rsu")],
        [sys.executable, str(source / "tools/shift_srec_addresses.py"), "--input", str(output / "bootloader.mot"),
         "--output", str(output / "bootloader_bank1.mot"), "--range-start", target["bank_range_start"],
         "--range-end", target["bank_range_end"], "--shift=" + target["bank_shift"], "--drop-out-of-range"],
    ]
    for command in commands:
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    record_packaging(source, target)


def build(source, baseline, provenance, stream, *, prepare=True, package_output=True):
    if prepare:
        script = Path(__file__).with_name("prepare_transport_key.py")
        subprocess.run([sys.executable, str(script), str(source)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    request_id = secrets.token_hex(16)
    request = create_request(source, baseline, provenance, request_id)
    write_frame(stream, request)
    files = validate_response(read_frame(stream), request_id)
    target = get_target("rx72n-ethernet")
    validate_build(files, source, provenance, target)
    output = install_outputs(source, files)
    if package_output:
        package(source, output, target)
    return output


def main():
    if len(sys.argv) != 2 or os.environ.get("IDT_TARGET") != "rx72n-ethernet" or os.environ.get("IDT_SCOPE") != "transport":
        raise ValueError("this callback supports only RX72N Transport")
    source = validate_source(sys.argv[1])
    provenance = json.loads(Path(os.environ["IDT_PROVENANCE_FILE"]).read_text(encoding="utf-8-sig"))
    baseline = json.loads(Path(os.environ["IDT_PAIR_BASELINE"]).read_text(encoding="utf-8"))
    seconds = int(os.environ["IDT_PAIR_BUILD_SECONDS"])
    if seconds <= 0:
        raise ValueError("missing paired build budget")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(seconds)
        connection.connect(os.environ["IDT_PAIR_SOCKET"])
        with connection.makefile("rwb", buffering=0) as stream:
            build(source, baseline, provenance, stream)
    print("RX72N Transport paired build completed", flush=True)


if __name__ == "__main__":
    try:
        main()
    except BaseException as error:
        # Exceptions can contain runtime paths or private source data.
        print("RX72N paired build failed: " + type(error).__name__, file=sys.stderr, flush=True)
        raise SystemExit(1) from None

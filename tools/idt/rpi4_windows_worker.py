#!/usr/bin/env python3
"""Windows side of the private RPi4 Transport build pilot."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.idt import rpi4_pair as pair
from tools.idt.run_idt import restrict_runtime
from tools.idt_source_manifest import verify_dependency_provenance

# Replace in reviewed source only after the project-specific Windows execution
# account has been established. An environment variable cannot grant admission.
REVIEWED_WINDOWS_SID = None
# Cancellation of the compiler tree and safe removal after interruption still
# require verification under the dedicated runner. Keep actual execution off.
COMPILER_CANCELLATION_VERIFIED = False


def scrubbed_environment():
    return {key: value for key, value in os.environ.items()
            if not (key.upper().startswith("AWS_") or key.upper().startswith("CI_JOB_")
                    or any(word in key.upper() for word in ("TOKEN", "SECRET", "PRIVATE_KEY", "PASSWORD"))
                    or key.upper().startswith("RX_OIDC_"))}


def build_request(request, checkout, temporary_parent, workspace_parent, lease_definition, *, run=None):
    """Build the request in a private source copy using the fixed helper."""
    checkout = Path(checkout).resolve(strict=True)
    sha = subprocess.check_output(["git", "--no-optional-locks", "-C", str(checkout),
                                   "rev-parse", "HEAD"], text=True).strip()
    if sha != os.environ.get("CI_COMMIT_SHA"):
        raise ValueError("Windows checkout differs from CI source")
    changed = subprocess.check_output(["git", "--no-optional-locks", "-C", str(checkout), "status",
                                       "--porcelain=v1", "--untracked-files=all", "--ignore-submodules=none"])
    if changed:
        raise ValueError("Windows checkout is not clean")
    overlays = pair.validate_request(request, sha)
    baseline = request["provenance"]["paired_source_files_sha256"]
    if pair.snapshot(checkout) != baseline:
        raise ValueError("Windows source differs from native source")
    verify_dependency_provenance(checkout, pair.TARGET, request["provenance"], test_group="Transport")
    temporary_parent = Path(temporary_parent).resolve(strict=True)
    workspace_parent = Path(workspace_parent).resolve(strict=True)
    private = Path(tempfile.mkdtemp(prefix="idt-pair-", dir=temporary_parent)).resolve(strict=True)
    workspace_path = None
    completed = False
    try:
        if private.parent != temporary_parent:
            raise ValueError("private build directory escaped its parent")
        restrict_runtime(private)
        source = private / "source"
        shutil.copytree(checkout, source, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"))
        if pair.snapshot(source) != baseline:
            raise ValueError("private source copy differs from native source")
        for name, data in overlays.items():
            source.joinpath(*name.split("/")).write_bytes(data)
        provenance = private / "source-provenance.json"
        provenance.write_text(json.dumps(request["provenance"], ensure_ascii=True), encoding="utf-8")
        workspace_path = Path(tempfile.mkdtemp(prefix="idt-pair-workspace-", dir=workspace_parent)).resolve(strict=True)
        if workspace_path.parent != workspace_parent:
            raise ValueError("build workspace escaped its parent")
        restrict_runtime(workspace_path)
        command = ["pwsh", "-NoProfile", "-NonInteractive", "-File",
                   str(checkout / "tools/idt/rpi4_windows_build.ps1"),
                   "-ProjectRoot", str(source), "-ProvenanceFile", str(provenance),
                   "-Workspace", str(workspace_path), "-PrivateLog", str(private / "build.log"),
                   "-LeaseDefinition", str(lease_definition)]
        runner = subprocess.run if run is None else run
        runner(command, check=True, env=scrubbed_environment(),
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        output = source / "artifacts/idt/build_transport"
        files = {name: (output / name).read_bytes() for name in pair.OUTPUTS}
        result = pair.response(request["request_id"], files)
        completed = True
        return result
    finally:
        # Failed/interrupted builds are retained: a vanished parent is not proof
        # that its compiler descendants have stopped using these files.
        if completed:
            if workspace_path is not None:
                if workspace_path.parent != workspace_parent or workspace_path.is_symlink():
                    raise ValueError("unsafe build workspace cleanup")
                shutil.rmtree(workspace_path)
            if private.parent != temporary_parent or private.is_symlink():
                raise ValueError("unsafe private source cleanup")
            shutil.rmtree(private)


def serve(reader, writer, builder):
    while True:
        request = pair.read_frame(reader)
        if request == {"kind": "shutdown"}:
            pair.write_frame(writer, {"kind": "shutdown_ack"})
            return
        try:
            result = builder(request)
        except Exception:
            # Do not include exception text, input, source paths, or build log.
            pair.write_frame(writer, {"kind": "error"})
            raise RuntimeError("paired Windows build failed") from None
        pair.write_frame(writer, result)


def main():
    if os.name != "nt" or REVIEWED_WINDOWS_SID is None or not COMPILER_CANCELLATION_VERIFIED:
        raise RuntimeError("reviewed dedicated Windows execution identity is not configured")
    import csv
    import io
    user = subprocess.check_output(["whoami.exe", "/user", "/fo", "csv", "/nh"], text=True)
    if next(csv.reader(io.StringIO(user)))[1] != REVIEWED_WINDOWS_SID:
        raise RuntimeError("Windows execution identity differs")
    pipeline = os.environ["CI_PIPELINE_ID"]
    if os.environ.get("CI_PROJECT_ID") != "38" or not pipeline.isascii() or not pipeline.isdigit():
        raise RuntimeError("unexpected project or pipeline")
    remote = ('python3 -u "$HOME/.cache/idt-rx72n-pair/' + pipeline +
              '/rpi4_pair_agent.py" attach ' + pipeline)
    command = ["ssh.exe", "-T", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
               "rpi4-idt", remote]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, env=scrubbed_environment())
    try:
        serve(process.stdout, process.stdin,
              lambda request: build_request(request, ROOT, r"C:\ai\codex\tmp", r"C:\ai\codex\ws",
                                            os.environ["IDT_PAIR_LEASE_DEFINITION"]))
        process.stdin.close()
        if process.wait(timeout=30) != 0:
            raise RuntimeError("paired SSH worker did not finish")
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)


if __name__ == "__main__":
    try:
        main()
    except BaseException as error:
        print("Windows paired worker failed: " + type(error).__name__, file=sys.stderr, flush=True)
        raise SystemExit(1) from None

#!/usr/bin/env python3
"""Windows side of the private RPi4 Transport build pilot."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
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
from tools.idt.windows_build_job import run_managed
from tools.idt.oidc_job import current_job_metadata

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
        if run is None:
            run_managed(command, timeout=int(os.environ["IDT_PAIR_BUILD_SECONDS"]),
                        env=scrubbed_environment())
        else:
            run(command, check=True, env=scrubbed_environment(),
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


def public_build(request, source_sha, build):
    """Run the placeholder-only build after a matching public request."""
    if (not isinstance(request, dict) or set(request) != {"kind", "request_id", "source_sha"}
            or request["kind"] != "public-build" or request["source_sha"] != source_sha
            or not isinstance(request["request_id"], str)
            or not re.fullmatch(r"[0-9a-f]{32}", request["request_id"])):
        raise ValueError("unexpected public build request")
    build()
    return {"kind": "public-result", "request_id": request["request_id"], "source_sha": source_sha}


def parent_pipeline(env):
    """The child pipeline connects to the session created by its parent."""
    parent = env.get("IDT_PAIR_PARENT_PIPELINE", "")
    session = env.get("IDT_PAIR_SESSION", "")
    if not re.fullmatch(r"[0-9]{1,20}", parent) or not re.fullmatch(r"[0-9]{1,20}", session):
        raise ValueError("invalid paired parent pipeline")
    sha = env.get("IDT_PAIR_PARENT_SHA", "")
    if not re.fullmatch(r"[0-9a-f]{40}", sha) or sha != env.get("CI_COMMIT_SHA"):
        raise ValueError("paired pipelines have different source revisions")
    return session


def run_connection(pipeline, builder):
    remote = ('python3 -u "$HOME/.cache/idt-rx72n-pair/' + pipeline +
              '/rpi4_pair_agent.py" attach ' + pipeline)
    command = ["ssh.exe", "-T", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
               "rpi4-idt", remote]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, env=scrubbed_environment())
    try:
        serve(process.stdout, process.stdin, builder)
        process.stdin.close()
        if process.wait(timeout=30) != 0:
            raise RuntimeError("paired SSH worker did not finish")
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)


def verify_public_job(env, job, username):
    session = parent_pipeline(env)
    if (env.get("CI_PROJECT_ID") != "38" or env.get("CI_RUNNER_ID") != "29"
            or env.get("CI_PIPELINE_SOURCE") != "pipeline" or env.get("CI_COMMIT_REF_PROTECTED") != "true"
            or env.get("IDT_PAIR_MODE") != "public" or username.lower() != "svc-idt-rx"):
        raise ValueError("unexpected public worker identity")
    try:
        if (job["status"] != "running" or str(job["id"]) != env["CI_JOB_ID"]
                or str(job["pipeline"]["id"]) != env["CI_PIPELINE_ID"] or job["runner"]["id"] != 29
                or job["commit"]["id"] != env["CI_COMMIT_SHA"]
                or "project38-idt-windows-protected" not in job["tag_list"]):
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise ValueError("public worker job metadata mismatch") from None
    return session


def public_placeholder_build():
    """Compile public placeholder inputs; remove only this job's outputs on success."""
    temporary_parent = Path(r"C:\ai\codex\tmp").resolve(strict=True)
    workspace_parent = Path(r"C:\ai\codex\ws").resolve(strict=True)
    generated = [ROOT / "Projects/aws_ether_rx72n_envision_kit/e2studio_ccrx/HardwareDebug",
                 ROOT / "Projects/boot_loader_rx72n_envision_kit/e2studio_ccrx/HardwareDebug"]
    if any(path.exists() or path.is_symlink() for path in generated):
        raise ValueError("public build output already exists")
    private = Path(tempfile.mkdtemp(prefix="idt-public-", dir=temporary_parent)).resolve(strict=True)
    workspace = Path(tempfile.mkdtemp(prefix="idt-public-", dir=workspace_parent)).resolve(strict=True)
    completed = False
    try:
        restrict_runtime(private)
        restrict_runtime(workspace)
        command = ["pwsh", "-NoProfile", "-NonInteractive", "-File",
                   str(ROOT / "tools/idt/rpi4_windows_public_build.ps1"), "-ProjectRoot", str(ROOT),
                   "-Python", sys.executable, "-Workspace", str(workspace), "-Output", str(private),
                   "-LeaseDefinition", os.environ["IDT_PAIR_LEASE_DEFINITION"]]
        run_managed(command, timeout=3600, env=scrubbed_environment())
        completed = True
    finally:
        if completed:
            for path, parent in [(private, temporary_parent), (workspace, workspace_parent),
                                 *((path, path.parent) for path in generated)]:
                if path.exists():
                    if path.is_symlink() or path.resolve(strict=True) != path or path.parent.resolve(strict=True) != parent:
                        raise ValueError("unsafe public output cleanup")
                    shutil.rmtree(path)


def main():
    if os.name != "nt":
        raise RuntimeError("Windows worker required")
    if os.environ.get("IDT_PAIR_MODE") == "public":
        job = current_job_metadata(os.environ.get("CI_JOB_TOKEN", ""))
        username = subprocess.check_output(["whoami.exe"], text=True).strip().rsplit("\\", 1)[-1]
        pipeline = verify_public_job(os.environ, job, username)
        sha = os.environ["CI_COMMIT_SHA"]
        actual_sha = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
        status = subprocess.check_output(["git", "-C", str(ROOT), "status", "--porcelain=v1",
                                          "--untracked-files=all", "--ignore-submodules=none"], text=True)
        if sha != actual_sha or status:
            raise ValueError("public worker source differs from its pipeline")
        clean = scrubbed_environment()
        os.environ.clear()
        os.environ.update(clean)
        run_connection(pipeline, lambda request: public_build(request, sha, public_placeholder_build))
        return
    if REVIEWED_WINDOWS_SID is None or not COMPILER_CANCELLATION_VERIFIED:
        raise RuntimeError("reviewed dedicated Windows execution identity is not configured")
    import csv
    import io
    user = subprocess.check_output(["whoami.exe", "/user", "/fo", "csv", "/nh"], text=True)
    if next(csv.reader(io.StringIO(user)))[1] != REVIEWED_WINDOWS_SID:
        raise RuntimeError("Windows execution identity differs")
    pipeline = parent_pipeline(os.environ)
    if os.environ.get("CI_PROJECT_ID") != "38":
        raise RuntimeError("unexpected project or pipeline")
    run_connection(pipeline, lambda request: build_request(request, ROOT, r"C:\ai\codex\tmp", r"C:\ai\codex\ws",
                                                           os.environ["IDT_PAIR_LEASE_DEFINITION"]))


if __name__ == "__main__":
    try:
        main()
    except BaseException as error:
        print("Windows paired worker failed: " + type(error).__name__, file=sys.stderr, flush=True)
        raise SystemExit(1) from None

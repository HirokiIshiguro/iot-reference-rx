#!/usr/bin/env python3
"""CI driver for iot-reference-rx.

One tool, four jobs:
  plan   decide which builds and tests to run and write the child pipeline
  build  build one firmware variant on the Windows runner        (added per board)
  test   run one test on a board, from flashing to cleanup       (added per board)
  sweep  delete AWS resources owned by a pipeline                (added with the AWS tests)

The list of tests lives in tools/ci/tests.json. Nothing else decides what runs.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROFILES = ("check", "build", "smoke", "full", "doctor")
TOOL = "tools/ci/rxci.py"
# The shared OIDC setup of the oss group: jobs issue GITLAB_OIDC_TOKEN and assume the
# role named by the protected group variable AWS_ROLE_ARN (see hardware-config, docs/ci-variables.md).
OIDC = {"GITLAB_OIDC_TOKEN": {"aud": "sts.amazonaws.com"}}
REGION = os.environ.get("AWS_DEFAULT_REGION", "ap-northeast-1")


# --------------------------------------------------------------------------
# Python environment of the Linux runners
# --------------------------------------------------------------------------

def enter_venv() -> None:
    """Re-run this tool inside a virtualenv that has tools/ci/requirements.txt.

    The virtualenv is kept per runner user and rebuilt only when the requirements
    change. Windows runners use their own Python and are left alone.
    """
    if os.name == "nt" or os.environ.get("RXCI_VENV") == "1":
        return
    import fcntl

    requirements = HERE / "requirements.txt"
    digest = hashlib.sha256(requirements.read_bytes()).hexdigest()[:16]
    root = Path.home() / ".cache" / "rxci"
    root.mkdir(parents=True, exist_ok=True)
    venv = root / f"venv-{digest}"
    python = venv / "bin" / "python"
    with open(root / "venv.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not (venv / "ready").exists():
            shutil.rmtree(venv, ignore_errors=True)
            subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
            subprocess.run([str(python), "-m", "pip", "install", "--quiet", "--disable-pip-version-check",
                            "-r", str(requirements)], check=True)
            (venv / "ready").write_text(digest)
    os.environ["RXCI_VENV"] = "1"
    os.execv(str(python), [str(python), str(Path(__file__).resolve()), *sys.argv[1:]])


# --------------------------------------------------------------------------
# AWS access (OIDC only)
# --------------------------------------------------------------------------

def aws_session():
    """Session of the CI role, obtained from the GitLab ID token of this job."""
    token = os.environ.get("GITLAB_OIDC_TOKEN")
    role = os.environ.get("AWS_ROLE_ARN")
    if not token:
        raise SystemExit("AWS access needs GITLAB_OIDC_TOKEN (id_tokens of the job).")
    if not role:
        raise SystemExit("AWS_ROLE_ARN is not set. It is a protected variable: run on main or a protected branch.")
    import boto3
    from botocore import UNSIGNED
    from botocore.config import Config

    name = "gitlab-{}-{}-{}".format(os.environ.get("CI_PROJECT_ID", "0"), os.environ.get("CI_PIPELINE_ID", "0"),
                                    os.environ.get("CI_JOB_ID", "0"))
    sts = boto3.client("sts", region_name=REGION, config=Config(signature_version=UNSIGNED))
    credentials = sts.assume_role_with_web_identity(
        RoleArn=role, RoleSessionName=name, WebIdentityToken=token, DurationSeconds=3600)["Credentials"]
    return boto3.Session(aws_access_key_id=credentials["AccessKeyId"],
                         aws_secret_access_key=credentials["SecretAccessKey"],
                         aws_session_token=credentials["SessionToken"], region_name=REGION)


def load_registry(path: Path | None = None) -> dict:
    registry = json.loads((path or HERE / "tests.json").read_text(encoding="utf-8"))
    axes = registry["axes"]
    tests = []
    number = 0
    for board, backend, tls, feature in itertools.product(
            axes["board"], axes["backend"], axes["tls"], axes["feature"]):
        number += 1
        name = f"{board}:{backend}:{tls}:{feature}"
        tests.append({
            "id": f"RXCI-{number:03d}",
            "name": name,
            "board": board,
            "backend": backend,
            "tls": tls,
            "feature": feature,
            "ready": name in registry["ready"],
            "smoke": name in registry["smoke"],
        })
    registry["tests"] = tests
    return registry


def build_variant(test: dict) -> str:
    """Firmware variant a test needs. Software builds do not depend on the TLS version."""
    backend = "software" if test["backend"] == "sw" else f"tsip-{test['tls']}"
    kind = {"mqtt": "app", "ota": "ota", "fleet": "fleet"}[test["feature"]]
    return f"{test['board']}/{backend}/{kind}"


def select(registry: dict, profile: str, pattern: str) -> tuple[list[dict], list[dict]]:
    """Return (tests to run, tests that matched but are not implemented yet)."""
    tests = registry["tests"]
    if pattern:
        regex = re.compile(pattern)
        matched = [test for test in tests if regex.search(test["name"])]
        if not matched:
            raise SystemExit(f"TEST={pattern!r} matches no test. Run '{TOOL} list' to see the names.")
    elif profile == "full":
        matched = list(tests)
    elif profile == "smoke":
        matched = [test for test in tests if test["smoke"]]
    else:
        matched = []
    return [t for t in matched if t["ready"]], [t for t in matched if not t["ready"]]


def child_pipeline(registry: dict, profile: str, pattern: str, repeat: int) -> tuple[dict, dict]:
    """Build the child pipeline (a dict that is dumped as JSON, which GitLab reads as YAML)."""
    run, pending = select(registry, profile, pattern)
    if pattern and pending and not run:
        names = ", ".join(test["name"] for test in pending)
        raise SystemExit(f"Selected tests are not implemented yet: {names}")

    if pattern:
        variants = sorted({build_variant(test) for test in run})
    elif profile in ("build", "smoke", "full"):
        variants = sorted({build_variant(test) for test in registry["tests"] if test["ready"]})
    else:
        variants = []

    jobs: dict = {
        "stages": ["check", "build", "test"],
        "default": {"interruptible": True},
        "check": {
            "stage": "check",
            "tags": registry["runners"]["check"],
            "variables": {"GIT_SUBMODULE_STRATEGY": "none", "GIT_DEPTH": "1"},
            "script": ["python3 -B -m unittest discover -s tools/ci -p 'test_rxci*.py' -v"],
        },
    }
    for variant in variants:
        board = variant.split("/")[0]
        jobs[f"build {variant}"] = {
            "stage": "build",
            "tags": registry["runners"]["build"],
            "resource_group": registry["build_resource_group"],
            "needs": [],
            "variables": {"GIT_STRATEGY": "fetch", "GIT_SUBMODULE_STRATEGY": "none"},
            "script": [f"python {TOOL} build {variant} --out out/{variant}"],
            "artifacts": {"paths": [f"out/{variant}/"], "expire_in": "3 days"},
            "timeout": "40 minutes",
            "interruptible": True,
            "rxci_board": board,
        }
    for test in run:
        board = registry["boards"][test["board"]]
        for index in range(1, repeat + 1):
            suffix = f" #{index}" if repeat > 1 else ""
            jobs[f"{test['name']}{suffix}"] = {
                "stage": "test",
                "tags": board["runner_tags"],
                "resource_group": board["resource_group"],
                "needs": [{"job": f"build {build_variant(test)}", "artifacts": True}],
                "variables": {"GIT_STRATEGY": "fetch", "GIT_SUBMODULE_STRATEGY": "none", "GIT_DEPTH": "1"},
                "script": [f"python3 {TOOL} test {test['name']} --artifacts out/{build_variant(test)} --log-dir out/logs"],
                "artifacts": {"when": "always", "paths": ["out/logs/"],
                              "reports": {"junit": "out/logs/junit.xml"}, "expire_in": "14 days"},
                "timeout": "30 minutes",
                "interruptible": False,
            }
    for job in jobs.values():
        if isinstance(job, dict):
            job.pop("rxci_board", None)

    if profile == "doctor":
        runners = {"check runner": registry["runners"]["check"], "build runner": registry["runners"]["build"]}
        for name, board in registry["boards"].items():
            runners.setdefault("runner of " + "+".join(
                other for other, config in registry["boards"].items()
                if config["runner_tags"] == board["runner_tags"]), board["runner_tags"])
        for name, tags in runners.items():
            python = "python" if "os-windows" in tags else "python3"
            jobs[f"doctor: {name}"] = {
                "stage": "check",
                "tags": tags,
                "needs": [],
                "id_tokens": OIDC,
                "variables": {"GIT_STRATEGY": "fetch", "GIT_SUBMODULE_STRATEGY": "none", "GIT_DEPTH": "1"},
                "script": [f"{python} {TOOL} doctor"],
            }

    summary = {
        "profile": profile,
        "test": pattern,
        "repeat": repeat,
        "builds": variants,
        "tests": [test["name"] for test in run],
        "not_implemented": [test["name"] for test in pending],
    }
    return jobs, summary


def command_plan(args: argparse.Namespace) -> int:
    if args.profile not in PROFILES:
        raise SystemExit(f"PROFILE must be one of {', '.join(PROFILES)} (got {args.profile!r})")
    if args.repeat < 1 or args.repeat > 50:
        raise SystemExit("REPEAT must be between 1 and 50")
    registry = load_registry()
    jobs, summary = child_pipeline(registry, args.profile, args.test, args.repeat)
    Path(args.output).write_text(json.dumps(jobs, indent=2) + "\n", encoding="utf-8")
    Path(args.summary).write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"profile={summary['profile']} test={summary['test'] or '(all in profile)'} repeat={summary['repeat']}")
    print(f"builds: {len(summary['builds'])}  tests: {len(summary['tests'])} x {args.repeat}")
    for name in summary["tests"]:
        print(f"  run   {name}")
    for name in summary["not_implemented"]:
        print(f"  todo  {name}")
    return 0


def command_doctor(args: argparse.Namespace) -> int:
    """Print what this runner has. Touches no board and changes nothing in AWS."""
    enter_venv()
    failures = 0

    def report(ok: bool, label: str, detail: str = "") -> None:
        nonlocal failures
        failures += 0 if ok else 1
        print(f"{'ok     ' if ok else 'MISSING'}  {label}  {detail}".rstrip())

    print(f"host: {platform.system()} {platform.machine()}  python {platform.python_version()}")
    for module in ("serial", "cryptography", "boto3"):
        try:
            __import__(module)
            report(True, f"python module {module}")
        except ImportError:
            report(False, f"python module {module}")
    if os.name == "nt":
        cli = os.environ.get("E2STUDIO_CLI", "")
        report(bool(cli) and Path(cli).exists(), "E2STUDIO_CLI points to e2studio-cli")
        report(shutil.which("pwsh") is not None, "pwsh")
    else:
        report(shutil.which("rfp-cli") is not None, "rfp-cli on PATH")
        report(shutil.which("flock") is not None, "flock")
        serial_dir = Path("/dev/serial/by-id")
        count = len(list(serial_dir.iterdir())) if serial_dir.is_dir() else 0
        print(f"info     USB serial devices: {count}")
        for name, board in load_registry()["boards"].items():
            lock = Path(board["lock"])
            print(f"info     lock of {name}: {'present' if lock.exists() else 'absent'}")
    try:
        session = aws_session()
        identity = session.client("sts").get_caller_identity()
        report(True, "AWS role assumed through OIDC", identity["Arn"].split(":")[-1].split("/")[1])
        session.client("iot").describe_endpoint(endpointType="iot:Data-ATS")
        report(True, "iot:DescribeEndpoint")
    except SystemExit as error:
        report(False, "AWS access", str(error))
    except Exception as error:  # botocore errors carry the reason in their text
        report(False, "AWS access", f"{type(error).__name__}: {str(error)[:160]}")
    return 1 if failures else 0


def command_list(args: argparse.Namespace) -> int:
    for test in load_registry()["tests"]:
        state = "ready" if test["ready"] else "todo "
        smoke = " smoke" if test["smoke"] else ""
        print(f"{test['id']}  {state}  {test['name']}{smoke}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)

    plan = commands.add_parser("plan", help="write the child pipeline")
    plan.add_argument("--profile", default="check")
    plan.add_argument("--test", default="")
    plan.add_argument("--repeat", type=int, default=1)
    plan.add_argument("--output", default="child-pipeline.yml")
    plan.add_argument("--summary", default="plan.json")
    plan.set_defaults(run=command_plan)

    listing = commands.add_parser("list", help="print every test name")
    listing.set_defaults(run=command_list)

    doctor = commands.add_parser("doctor", help="print what this runner has (tools, modules, AWS access)")
    doctor.set_defaults(run=command_doctor)

    args = parser.parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())

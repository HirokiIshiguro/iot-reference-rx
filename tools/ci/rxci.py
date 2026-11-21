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
sys.path.insert(0, str(HERE))
PROFILES = ("check", "build", "smoke", "full", "benchmark", "doctor")
TOOL = "tools/ci/rxci.py"
# The shared OIDC setup of the oss group: jobs issue GITLAB_OIDC_TOKEN and assume the
# role named by the protected group variable AWS_ROLE_ARN (see hardware-config, docs/ci-variables.md).
OIDC = {"GITLAB_OIDC_TOKEN": {"aud": "sts.amazonaws.com"}}
REGION = os.environ.get("AWS_DEFAULT_REGION", "ap-northeast-1")
# A test job first waits for its board, which jobs of other projects on the same host also use, and then runs.
# The job timeout is the sum of the two, so that the wait can never use up the time of the test itself.
LOCK_WAIT_SECONDS = 3000
TEST_SECONDS = 2400
# AWS STS fetches the keys that sign the ID token from GitLab on each call. When GitLab answers late,
# STS gives up with IDPCommunicationError or with InvalidIdentityToken "Couldn't retrieve verification
# key ..."; the token itself is fine. The job then waits and asks again, up to about two minutes in all.
STS_ATTEMPTS = 7
STS_WAIT_SECONDS = 20


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
    credentials = assume_role(sts, RoleArn=role, RoleSessionName=name, WebIdentityToken=token, DurationSeconds=3600)
    return boto3.Session(aws_access_key_id=credentials["AccessKeyId"],
                         aws_secret_access_key=credentials["SecretAccessKey"],
                         aws_session_token=credentials["SessionToken"], region_name=REGION)


def identity_provider_unreachable(error: Exception) -> bool:
    """True when STS failed only because it could not get the keys of the ID token from GitLab."""
    detail = getattr(error, "response", None) or {}
    code = detail.get("Error", {}).get("Code", "")
    message = detail.get("Error", {}).get("Message", "")
    return code == "IDPCommunicationError" or (
        code == "InvalidIdentityToken" and "retrieve verification key" in message)


def assume_role(sts, sleep=None, **request) -> dict:
    """Credentials of AssumeRoleWithWebIdentity, asking again while GitLab cannot be reached by STS."""
    import time
    for attempt in range(1, STS_ATTEMPTS + 1):
        try:
            return sts.assume_role_with_web_identity(**request)["Credentials"]
        except Exception as error:
            if attempt == STS_ATTEMPTS or not identity_provider_unreachable(error):
                raise
            print(f"rxci: AWS STS could not get the keys of the ID token from GitLab "
                  f"(attempt {attempt} of {STS_ATTEMPTS}): {error}; asking again in {STS_WAIT_SECONDS} s",
                  file=sys.stderr, flush=True)
            (sleep or time.sleep)(STS_WAIT_SECONDS)
    raise AssertionError("unreachable")


def load_registry(path: Path | None = None) -> dict:
    registry = json.loads((path or HERE / "tests.json").read_text(encoding="utf-8"))
    axes = registry["axes"]
    ids = registry["ids"]
    tests = []
    for board, backend, tls, feature in itertools.product(
            axes["board"], axes["backend"], axes["tls"], axes["feature"]):
        name = f"{board}:{backend}:{tls}:{feature}"
        if name not in ids:
            raise SystemExit(f"tests.json has no test number (ids) for {name}.")
        tests.append({
            "id": ids[name],
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


def endpoint(registry: dict, tls: str) -> str:
    """AWS IoT endpoint that serves one TLS version: the fixed value of tests.json, or the CI variable it names.

    Every build and every test takes the endpoint from here, so that a test named after a TLS version connects
    to the endpoint of that version and to no other.
    """
    entry = registry["endpoints"][tls]
    value = entry.get("value") or os.environ.get(entry["variable"], "")
    if not value:
        raise SystemExit(f"The AWS IoT endpoint for {tls} is not set ({entry.get('variable')}).")
    return value


def tls_version(tls: str) -> str:
    """Version string that the firmware logs for a test axis value: "tls12" -> "TLSv1.2"."""
    return {"tls12": "TLSv1.2", "tls13": "TLSv1.3"}[tls]


def build_variant(test: dict, registry: dict | None = None) -> str:
    """Application variant a test needs.

    A software build serves both TLS versions unless the board compiles the version in
    (software_build_per_tls in tests.json).
    """
    per_tls = bool(registry and registry["boards"][test["board"]].get("software_build_per_tls"))
    if test["backend"] == "sw":
        backend = f"software-{test['tls']}" if per_tls else "software"
    else:
        backend = f"tsip-{test['tls']}"
    kind = {"mqtt": "app", "ota": "ota", "fleet": "fleet"}[test["feature"]]
    if test["feature"] == "mqtt" and mqtt_from_ota_bundle(test, registry):
        kind = "ota"
    return f"{test['board']}/{backend}/{kind}"


def mqtt_from_ota_bundle(test: dict, registry: dict | None) -> bool:
    """A board that keeps its device credentials out of the build starts its MQTT test from the OTA bundle.

    The bundle holds the provisioner, the boot loader and the baseline application, which connects to AWS IoT
    and asks for a job. Only the TSIP backend of such a board works this way (tests.json: tsip_mqtt_from_ota_bundle).
    """
    board = registry["boards"][test["board"]] if registry else {}
    return test["backend"] == "tsip" and bool(board.get("tsip_mqtt_from_ota_bundle"))


def build_variants(test: dict, registry: dict | None = None) -> list[str]:
    """Every build a test needs: the per-commit files of the board and its application.

    An OTA test also needs the normal application: the board starts from it and updates itself
    to the OTA candidate.
    """
    board = registry["boards"][test["board"]] if registry else {}
    if (test["feature"] == "ota" and board.get("ota_is_self_contained")) or (
            test["feature"] == "mqtt" and mqtt_from_ota_bundle(test, registry)):
        # One build holds everything of the OTA test: provisioner, boot loader, baseline and candidate.
        return [build_variant(test, registry)]
    variants = [f"{test['board']}/common", build_variant(test, registry)]
    if test["feature"] == "ota":
        variants.insert(1, build_variant({**test, "feature": "mqtt"}, registry))
    return variants


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
    return ([t for t in matched if t["ready"]],
            [t for t in matched if not t["ready"]])


def benchmark_boards(registry: dict, profile: str, board: str, whole_boards: bool, benchmark: bool) -> list[str]:
    """Boards whose benchmark projects the child pipeline starts.

    PROFILE=benchmark runs only the benchmarks. PROFILE=full runs them after the tests, unless BENCHMARK=false
    or the selection takes only part of a board (a backend, a TLS version, a feature or TEST): a benchmark
    measures the whole board, and a run that asks for a few tests should not take hours longer.
    """
    if profile not in ("full", "benchmark") or not whole_boards or (profile == "full" and not benchmark):
        return []
    boards = registry["axes"]["board"] if board == "all" else [board]
    return [name for name in boards if any(entry["board"] == name for entry in registry.get("benchmarks", []))]


def benchmark_jobs(registry: dict, boards: list[str]) -> dict:
    """Trigger jobs that start the benchmark projects of the boards (multi-project downstream pipelines).

    The first benchmark of a board waits for the whole test stage (it has no needs), so that it does not take
    a board from the tests; the next ones of the same board wait for the one before, because they use the
    same board. The variables are fixed values from tests.json. A secret is not passed from here: GitLab does
    not keep the masking of a forwarded variable in the downstream project, so a downstream pipeline that needs
    a secret takes it from a masked variable of its own project or group.
    """
    jobs: dict = {}
    for board in boards:
        previous = None
        for entry in (e for e in registry.get("benchmarks", []) if e["board"] == board):
            name = f"benchmark {entry['name']}"
            variables = dict(entry.get("variables", {}))
            job = {
                "stage": "benchmark",
                "when": "always",       # a failed test does not make the measurement of the board meaningless
                "trigger": {"project": entry["project"], "branch": entry.get("ref", "main"), "strategy": "depend",
                            "forward": {"yaml_variables": True, "pipeline_variables": False}},
                "variables": variables,
                "interruptible": False,  # the downstream pipeline writes to the board
            }
            if previous:
                job["needs"] = [{"job": previous, "artifacts": False}]
            jobs[name] = job
            previous = name
    return jobs


def child_pipeline(registry: dict, profile: str, pattern: str, repeat: int,
                   keep: bool = False, rebuild: bool = False, benchmarks: list[str] | None = None) -> tuple[dict, dict]:
    """Build the child pipeline (a dict that is dumped as JSON, which GitLab reads as YAML).

    benchmarks: boards whose benchmark projects run after the tests (benchmark_boards).
    """
    run, pending = select(registry, profile, pattern)
    if pattern and pending and not run:
        names = ", ".join(test["name"] for test in pending)
        raise SystemExit(f"Selected tests are not implemented yet: {names}")

    if pattern or profile == "smoke":
        variants = sorted({variant for test in run for variant in build_variants(test, registry)})
    elif profile in ("build", "full"):
        variants = sorted({variant for test in registry["tests"] if test["ready"]
                           for variant in build_variants(test, registry)})
    else:
        variants = []

    jobs: dict = {
        "stages": ["check", "build", "test", "benchmark", "cleanup"],
        # GitLab cancels older pipelines of a branch when a newer pipeline is created, child pipelines
        # included. A run that a person or a schedule started (keep) must survive that.
        "workflow": {"auto_cancel": {"on_new_commit": "none" if keep else "interruptible"}},
        "default": {"interruptible": not keep},
        "check": {
            "stage": "check",
            "tags": registry["runners"]["check"],
            "variables": {"GIT_SUBMODULE_STRATEGY": "none", "GIT_DEPTH": "1"},
            "script": ["python3 -B -m unittest discover -s tools/ci -p 'test_rxci*.py' -v"],
        },
    }
    lanes = int(registry.get("build_lanes", 1))
    for index, variant in enumerate(variants):
        jobs[f"build {variant}"] = {
            "stage": "build",
            "tags": registry["runners"]["build"],
            # The build machine takes a few builds at a time. A lane is a resource group, so the
            # limit also holds across pipelines.
            "resource_group": f"{registry['build_resource_group']}-{index % lanes + 1}",
            "needs": [],
            # A fresh clone keeps the line endings as committed (CC-RX needs them). The job checks out
            # only this repository: the build clones the dependencies itself, and only when it cannot
            # reuse an earlier build with the same inputs (rxci_build.py).
            "variables": {"GIT_STRATEGY": "clone", "GIT_SUBMODULE_STRATEGY": "none",
                          "RXCI_REBUILD": "1" if rebuild else "0",
                          "GIT_CONFIG_COUNT": "3",
                          "GIT_CONFIG_KEY_0": "core.longpaths", "GIT_CONFIG_VALUE_0": "true",
                          "GIT_CONFIG_KEY_1": "core.autocrlf", "GIT_CONFIG_VALUE_1": "false",
                          "GIT_CONFIG_KEY_2": "core.eol", "GIT_CONFIG_VALUE_2": "lf"},
            "script": [f"python {TOOL} build {variant} --out out/{variant}"],
            "artifacts": {"when": "always", "paths": [f"out/{variant}/"], "expire_in": "3 days"},
            "timeout": "50 minutes",
        }
    for test in run:
        board = registry["boards"][test["board"]]
        for index in range(1, repeat + 1):
            suffix = f" #{index}" if repeat > 1 else ""
            jobs[f"{test['name']}{suffix}"] = {
                "stage": "test",
                "tags": board["runner_tags"],
                "resource_group": board["resource_group"],
                "needs": [{"job": f"build {variant}", "artifacts": True} for variant in build_variants(test, registry)],
                "id_tokens": OIDC,
                "variables": {"GIT_STRATEGY": "fetch", "GIT_SUBMODULE_STRATEGY": "none", "GIT_DEPTH": "1"},
                "script": [f"python3 {TOOL} test {test['name']} --out out --log-dir out/logs"],
                # Runs also after a cancelled or timed-out script: parks the board and deletes AWS resources.
                "after_script": [f"python3 {TOOL} finish {test['name']} --log-dir out/logs"],
                "artifacts": {"when": "always", "paths": ["out/logs/"],
                              "reports": {"junit": "out/logs/junit.xml"}, "expire_in": "14 days"},
                "timeout": f"{(LOCK_WAIT_SECONDS + TEST_SECONDS) // 60} minutes",
                "interruptible": False,     # never stop a job that is writing to a board
            }
    if run:
        # Removes the AWS resources of this pipeline even when a test job was cancelled, and
        # whatever older pipelines left behind.
        jobs["sweep"] = {
            "stage": "cleanup",
            "tags": registry["runners"]["check"],
            "when": "always",
            "id_tokens": OIDC,
            "variables": {"GIT_STRATEGY": "fetch", "GIT_SUBMODULE_STRATEGY": "none", "GIT_DEPTH": "1"},
            "script": [f"python3 {TOOL} sweep --pipeline $CI_PIPELINE_ID --stale-hours 6"],
            "interruptible": False,
        }

    bench = benchmark_jobs(registry, benchmarks or [])
    jobs.update(bench)

    if profile == "doctor":
        runners = {"check runner": registry["runners"]["check"], "build runner": registry["runners"]["build"]}
        for name, board in registry["boards"].items():
            runners.setdefault("runner of " + "+".join(
                other for other, config in registry["boards"].items()
                if config["runner_tags"] == board["runner_tags"]), board["runner_tags"])
        for name, tags in runners.items():
            python = "python" if "os-windows" in tags else "python3"
            role = "build" if "os-windows" in tags else ("board" if "hw-raspi" in tags else "check")
            jobs[f"doctor: {name}"] = {
                "stage": "check",
                "tags": tags,
                "needs": [],
                "id_tokens": OIDC,
                "variables": {"GIT_STRATEGY": "fetch", "GIT_SUBMODULE_STRATEGY": "none", "GIT_DEPTH": "1"},
                "script": [f"{python} {TOOL} doctor --role {role}"],
            }

    # A job without rules is created only for a branch or a tag. The child of a merge request pipeline
    # runs on the merge request ref, so without rules it would have no job and GitLab could not create it.
    for name, job in jobs.items():
        if name not in ("stages", "workflow", "default"):
            job["rules"] = [{"when": job.pop("when", "on_success")}]

    summary = {
        "profile": profile,
        "test": pattern,
        "repeat": repeat,
        "builds": variants,
        "tests": [test["name"] for test in run],
        "benchmarks": list(bench),
        "not_implemented": [test["name"] for test in pending],
    }
    return jobs, summary


def selection_pattern(registry: dict, board: str, backend: str, tls: str, feature: str, test: str) -> str:
    """Regular expression of the tests that the run variables select; "" when they select nothing.

    BOARD, BACKEND, TLS and FEATURE are the lists of the "New pipeline" page (all = no restriction).
    TEST is free text for what the lists cannot express. Using both at once would be ambiguous.
    """
    chosen = {"BOARD": board, "BACKEND": backend, "TLS": tls, "FEATURE": feature}
    for (name, value), axis in zip(chosen.items(), ("board", "backend", "tls", "feature")):
        allowed = ["all", *registry["axes"][axis]]
        if value not in allowed:
            raise SystemExit(f"{name} must be one of {', '.join(allowed)} (got {value!r})")
    if all(value == "all" for value in chosen.values()):
        return test
    if test:
        raise SystemExit("TEST and BOARD/BACKEND/TLS/FEATURE both select tests. "
                         "Leave the four lists at all, or leave TEST empty.")
    return "^" + ":".join("[^:]+" if value == "all" else re.escape(value) for value in chosen.values()) + "$"


# Run variables of the CI that this one replaced. Nothing here reads them, so a pipeline started with
# one of them would quietly run something else (by default the unit tests only) and look green.
RETIRED_VARIABLE = re.compile(
    r"^(PIPELINE_PROFILE|RUN_[A-Z0-9_]+|IDT_[A-Z0-9_]+|NIGHTLY_[A-Z0-9_]+"
    r"|[A-Z0-9_]+_(TEST_SCOPE|IDT_SCOPE|SKIP_HW_TESTS|SKIP_OTA_TESTS|REQUIRE_TLS_VERSION|TLS_BACKEND|TLS13_0RTT_ENABLE))$")


def retired_variables(environment) -> list[str]:
    """Names of set variables that belonged to the old CI and select nothing in this one."""
    return sorted(name for name, value in environment.items() if value and RETIRED_VARIABLE.match(name))


def command_plan(args: argparse.Namespace) -> int:
    retired = retired_variables(os.environ)
    if retired:
        raise SystemExit(f"{', '.join(retired)}: the CI no longer reads {'this variable' if len(retired) == 1 else 'these variables'}. "
                         f"Choose what runs with PROFILE, BOARD, BACKEND, TLS and FEATURE (docs/details/ci-pipeline.md).")
    if args.profile not in PROFILES:
        raise SystemExit(f"PROFILE must be one of {', '.join(PROFILES)} (got {args.profile!r})")
    if args.repeat < 1 or args.repeat > 50:
        raise SystemExit("REPEAT must be between 1 and 50")
    registry = load_registry()
    pattern = selection_pattern(registry, args.board, args.backend, args.tls, args.feature, args.test)
    # A pipeline that looks green but ran nothing of what was asked for is worse than one that stops here.
    whole_boards = not args.test and all(value == "all" for value in (args.backend, args.tls, args.feature))
    if args.profile == "benchmark":
        if not whole_boards:
            raise SystemExit("PROFILE=benchmark runs the benchmarks of whole boards: choose them with BOARD, "
                             "and leave BACKEND, TLS and FEATURE at all and TEST empty.")
        pattern = ""
    elif pattern and args.profile != "full":
        raise SystemExit(f"BOARD/BACKEND/TLS/FEATURE or TEST select tests, and only PROFILE=full runs a "
                         f"selection (got PROFILE={args.profile}). Set PROFILE=full, or clear the selection.")
    if args.benchmark not in ("true", "false"):
        raise SystemExit(f"BENCHMARK must be true or false (got {args.benchmark!r})")
    if args.repeat > 1 and args.profile not in ("full", "smoke"):
        raise SystemExit(f"REPEAT repeats tests, and PROFILE={args.profile} runs none. "
                         f"Set PROFILE=full, or leave REPEAT at 1.")
    boards = benchmark_boards(registry, args.profile, args.board, whole_boards, args.benchmark == "true")
    if args.profile == "benchmark" and not boards:
        with_benchmarks = [name for name in registry["axes"]["board"]
                           if any(entry["board"] == name for entry in registry.get("benchmarks", []))]
        raise SystemExit(f"PROFILE=benchmark: BOARD={args.board} has no benchmark project in tools/ci/tests.json. "
                         f"Choose one of {', '.join(with_benchmarks) or '(none)'}, or all.")
    jobs, summary = child_pipeline(registry, args.profile, pattern, args.repeat, keep=args.keep == "true",
                                   rebuild=args.rebuild == "true", benchmarks=boards)
    Path(args.output).write_text(json.dumps(jobs, indent=2) + "\n", encoding="utf-8")
    Path(args.summary).write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"profile={summary['profile']} test={summary['test'] or '(all in profile)'} repeat={summary['repeat']}")
    print(f"builds: {len(summary['builds'])}  tests: {len(summary['tests'])} x {args.repeat}  "
          f"benchmarks: {len(summary['benchmarks'])}")
    for name in summary["tests"]:
        print(f"  run   {name}")
    for name in summary["benchmarks"]:
        print(f"  start {name}")
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
    registry = load_registry()
    if args.role == "build":
        cli = os.environ.get("E2STUDIO_CLI") or registry["e2studio_cli"]
        report(Path(cli).exists(), "e2 studio command line", cli)
        report(Path(registry["workspace_root"]).is_dir(), "workspace root", registry["workspace_root"])
        report(shutil.which("pwsh") is not None, "pwsh")
    if args.role == "board":
        report(shutil.which("rfp-cli") is not None, "rfp-cli on PATH")
        serial_dir = Path("/dev/serial/by-id")
        count = len(list(serial_dir.iterdir())) if serial_dir.is_dir() else 0
        print(f"info     USB serial devices: {count}")
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


def command_build(args: argparse.Namespace) -> int:
    import rxci_build

    rxci_build.build(load_registry(), args.variant, Path(args.out).resolve())
    return 0


def command_test(args: argparse.Namespace) -> int:
    enter_venv()
    import rxci_board

    registry = load_registry()
    matches = [test for test in registry["tests"] if test["name"] == args.name]
    if not matches:
        raise SystemExit(f"Unknown test: {args.name}")
    test = matches[0]
    out = Path(args.out).resolve()
    builds = [out / variant for variant in build_variants(test, registry)]
    return rxci_board.run_test(registry, test, builds, Path(args.log_dir).resolve())


def command_finish(args: argparse.Namespace) -> int:
    enter_venv()
    import rxci_board

    registry = load_registry()
    test = next(test for test in registry["tests"] if test["name"] == args.name)
    return rxci_board.finish_test(registry, test, Path(args.log_dir).resolve(), aws_session)


def command_sweep(args: argparse.Namespace) -> int:
    enter_venv()
    import rxci_aws

    prefix = f"{rxci_aws.PREFIX}{args.pipeline}-" if args.pipeline else ""
    deleted = rxci_aws.sweep(aws_session(), prefix=prefix, stale_hours=args.stale_hours)
    print(f"sweep: deleted {len(deleted)} thing(s)")
    return 0


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
    plan.add_argument("--board", default="all", help="all, or the board of the tests to run")
    plan.add_argument("--backend", default="all", help="all, sw or tsip")
    plan.add_argument("--tls", default="all", help="all, tls12 or tls13")
    plan.add_argument("--feature", default="all", help="all, mqtt, ota or fleet")
    plan.add_argument("--test", default="", help="regular expression of test names, instead of the four lists")
    plan.add_argument("--repeat", type=int, default=1)
    plan.add_argument("--keep", default="false", choices=("true", "false"),
                      help="true: newer commits do not cancel this pipeline")
    plan.add_argument("--rebuild", default="false", choices=("true", "false"),
                      help="true: build every firmware again instead of reusing a build with the same inputs")
    plan.add_argument("--benchmark", default="true",
                      help="true: PROFILE=full also starts the benchmark projects of the boards it tests")
    plan.add_argument("--output", default="child-pipeline.yml")
    plan.add_argument("--summary", default="plan.json")
    plan.set_defaults(run=command_plan)

    listing = commands.add_parser("list", help="print every test name")
    listing.set_defaults(run=command_list)

    doctor = commands.add_parser("doctor", help="print what this runner has (tools, modules, AWS access)")
    doctor.add_argument("--role", choices=("check", "build", "board"), default="check")
    doctor.set_defaults(run=command_doctor)

    build = commands.add_parser("build", help="build one firmware variant (Windows runner)")
    build.add_argument("variant")
    build.add_argument("--out", required=True)
    build.set_defaults(run=command_build)

    finish = commands.add_parser("finish", help="after a test job: park the board and delete its AWS resources")
    finish.add_argument("name")
    finish.add_argument("--log-dir", default="out/logs")
    finish.set_defaults(run=command_finish)

    sweep = commands.add_parser("sweep", help="delete AWS resources that tests of a pipeline created")
    sweep.add_argument("--pipeline", default="", help="pipeline whose resources are deleted")
    sweep.add_argument("--stale-hours", type=float, default=0, help="also delete resources older than this")
    sweep.set_defaults(run=command_sweep)

    test = commands.add_parser("test", help="run one test on its board, from flashing to parking")
    test.add_argument("name")
    test.add_argument("--out", default="out", help="directory that holds the build outputs")
    test.add_argument("--log-dir", default="out/logs")
    test.set_defaults(run=command_test)

    args = parser.parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())

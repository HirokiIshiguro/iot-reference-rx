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
import itertools
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROFILES = ("check", "build", "smoke", "full")
TOOL = "tools/ci/rxci.py"


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

    args = parser.parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())

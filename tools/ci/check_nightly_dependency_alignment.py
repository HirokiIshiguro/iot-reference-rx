#!/usr/bin/env python3
"""Fail closed when benchmark children use different FreeRTOS/AWS sources."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable
from urllib.parse import quote, urlsplit, urlunsplit


SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
ENV_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
GITLAB_PROJECT_RE = re.compile(
    r"^[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+$"
)
SENSITIVE_ENV_NAME_RE = re.compile(
    r"(?:TOKEN|PASSWORD|PASSPHRASE|SECRET|PRIVATE_KEY|CREDENTIAL)",
    re.IGNORECASE,
)
URL_USERINFO_RE = re.compile(r"(?i)\b(https?://)[^/\s@]+@")
GITLINK_RE = re.compile(
    r"^160000 commit ([0-9a-f]{40})\t(.+)$"
)
TREE_RE = re.compile(
    r"^040000 tree ([0-9a-f]{40})\t(.+)$"
)
SUPPORTED_MODES = {"parent_gitlinks"}


class AlignmentError(RuntimeError):
    """A deterministic dependency-alignment failure."""


def redact_sensitive_text(value: str) -> str:
    """Remove URL userinfo and configured secret values from diagnostics."""

    redacted = URL_USERINFO_RE.sub(r"\1[redacted]@", value)
    secrets: set[str] = set()
    for name, secret in os.environ.items():
        if not SENSITIVE_ENV_NAME_RE.search(name) or len(secret) < 4:
            continue
        secrets.add(secret)
        encoded = quote(secret, safe="")
        if len(encoded) >= 4:
            secrets.add(encoded)
    for secret in sorted(secrets, key=len, reverse=True):
        redacted = redacted.replace(secret, "[redacted]")
    return redacted


def sanitized_repository_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname:
        raise AlignmentError("repository must be an absolute HTTPS URL")
    if parsed.username or parsed.password:
        raise AlignmentError("repository URL must not contain credentials")
    return urlunsplit(
        (parsed.scheme, parsed.hostname + (f":{parsed.port}" if parsed.port else ""),
         parsed.path, "", "")
    )


def safe_relative_path(value: str, label: str) -> str:
    path = PurePosixPath(value)
    if (
        not value
        or path.is_absolute()
        or "\\" in value
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise AlignmentError(f"{label} must be a safe repository-relative path")
    return path.as_posix()


def run_git(
    args: Iterable[str],
    cwd: Path,
    *,
    capture: bool = True,
) -> str:
    command = ["git", *list(args)]
    completed = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        stderr = redact_sensitive_text((completed.stderr or "").strip())
        if len(stderr) > 1000:
            stderr = stderr[-1000:]
        raise AlignmentError(
            f"git {' '.join(command[1:])} failed with exit "
            f"{completed.returncode}: {stderr}"
        )
    return (completed.stdout or "").strip()


def require_sha40(value: str, label: str) -> str:
    normalized = value.strip().lower()
    if not SHA40_RE.fullmatch(normalized):
        raise AlignmentError(f"{label} is not a 40-character commit SHA")
    return normalized


def load_config(path: Path) -> dict[str, Any]:
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AlignmentError(f"cannot read config: {exc}") from exc

    if config.get("schema_version") != 1:
        raise AlignmentError("config schema_version must be 1")
    targets = config.get("targets")
    if not isinstance(targets, list) or not targets:
        raise AlignmentError("config targets must be a non-empty list")

    names: set[str] = set()
    resolved_ref_envs: set[str] = set()
    for target in targets:
        if not isinstance(target, dict):
            raise AlignmentError("each target must be an object")
        name = target.get("name")
        if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name):
            raise AlignmentError("target name must use lowercase letters, digits, or hyphens")
        if name in names:
            raise AlignmentError(f"duplicate target name: {name}")
        names.add(name)

        target["repository"] = sanitized_repository_url(target.get("repository", ""))
        project = target.get("project")
        if not isinstance(project, str) or not GITLAB_PROJECT_RE.fullmatch(project):
            raise AlignmentError(f"{name}: invalid GitLab project path")
        target["project"] = project
        ref_env = target.get("ref_env")
        if not isinstance(ref_env, str) or not ENV_NAME_RE.fullmatch(ref_env):
            raise AlignmentError(f"{name}: invalid ref_env")
        resolved_ref_env = target.get("resolved_ref_env")
        if (
            not isinstance(resolved_ref_env, str)
            or not ENV_NAME_RE.fullmatch(resolved_ref_env)
        ):
            raise AlignmentError(f"{name}: invalid resolved_ref_env")
        if resolved_ref_env in resolved_ref_envs:
            raise AlignmentError(f"{name}: duplicate resolved_ref_env")
        resolved_ref_envs.add(resolved_ref_env)
        target["resolved_ref_env"] = resolved_ref_env
        if not isinstance(target.get("default_ref"), str) or not target["default_ref"]:
            raise AlignmentError(f"{name}: default_ref is required")
        if target.get("mode") not in SUPPORTED_MODES:
            raise AlignmentError(f"{name}: unsupported mode")

        dependencies = target.get("dependencies")
        if not isinstance(dependencies, list) or not dependencies:
            raise AlignmentError(f"{name}: dependencies must be non-empty")
        normalized = [
            safe_relative_path(item, f"{name} dependency")
            if isinstance(item, str)
            else ""
            for item in dependencies
        ]
        if "" in normalized or len(normalized) != len(set(normalized)):
            raise AlignmentError(f"{name}: dependencies must be unique paths")
        target["dependencies"] = normalized

        source_roots = target.get("source_roots")
        if not isinstance(source_roots, list) or not source_roots:
            raise AlignmentError(f"{name}: source_roots must be non-empty")
        normalized_source_roots = [
            safe_relative_path(item, f"{name} source root")
            if isinstance(item, str)
            else ""
            for item in source_roots
        ]
        if (
            "" in normalized_source_roots
            or len(normalized_source_roots) != len(set(normalized_source_roots))
        ):
            raise AlignmentError(f"{name}: source_roots must be unique paths")
        target["source_roots"] = normalized_source_roots

        if target.get("allowed_patches"):
            raise AlignmentError(
                f"{name}: allowed_patches is not valid for gitlink alignment"
            )
        link = target.get("iot_reference_gitlink")
        if not isinstance(link, str):
            raise AlignmentError(f"{name}: iot_reference_gitlink is required")
        target["iot_reference_gitlink"] = safe_relative_path(
            link, f"{name} iot_reference_gitlink"
        )
    return config


def parse_gitlink_line(line: str, expected_path: str) -> str:
    match = GITLINK_RE.fullmatch(line.strip())
    if not match:
        if not line.strip():
            raise AlignmentError(f"missing gitlink: {expected_path}")
        raise AlignmentError(f"path is not a mode 160000 gitlink: {expected_path}")
    if match.group(2) != expected_path:
        raise AlignmentError(f"gitlink path mismatch for {expected_path}")
    return require_sha40(match.group(1), f"gitlink {expected_path}")


def read_gitlink(repo: Path, ref: str, path: str) -> str:
    require_sha40(ref, "tree ref")
    line = run_git(["ls-tree", ref, "--", path], repo)
    return parse_gitlink_line(line, path)


def read_source_tree(repo: Path, ref: str, path: str) -> str:
    require_sha40(ref, "tree ref")
    line = run_git(["ls-tree", ref, "--", path], repo)
    match = TREE_RE.fullmatch(line.strip())
    if not match:
        if not line.strip():
            raise AlignmentError(f"missing source tree: {path}")
        raise AlignmentError(f"path is not a mode 040000 source tree: {path}")
    if match.group(2) != path:
        raise AlignmentError(f"source tree path mismatch for {path}")
    return require_sha40(match.group(1), f"source tree {path}")


def compare_parent_gitlinks(
    parent_repo: Path,
    parent_sha: str,
    child_parent_sha: str,
    dependencies: list[str],
) -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []
    for dependency in dependencies:
        expected = read_gitlink(parent_repo, parent_sha, dependency)
        actual = read_gitlink(parent_repo, child_parent_sha, dependency)
        checks.append(
            {
                "path": dependency,
                "status": "passed" if expected == actual else "failed",
                "expected": expected,
                "actual": actual,
            }
        )
    return checks


def compare_parent_source_trees(
    parent_repo: Path,
    parent_sha: str,
    child_parent_sha: str,
    source_roots: list[str],
) -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []
    for source_root in source_roots:
        expected = read_source_tree(parent_repo, parent_sha, source_root)
        actual = read_source_tree(parent_repo, child_parent_sha, source_root)
        checks.append(
            {
                "path": source_root,
                "kind": "source_tree",
                "status": "passed" if expected == actual else "failed",
                "expected": expected,
                "actual": actual,
            }
        )
    return checks


def clone_target(target: dict[str, Any], workspace: Path) -> tuple[Path, str, str]:
    ref = os.environ.get(target["ref_env"], "").strip() or target["default_ref"]
    if ref.startswith("-") or any(character.isspace() for character in ref):
        raise AlignmentError(f"{target['name']}: unsafe ref value")
    target_dir = workspace / target["name"]
    if target_dir.exists():
        shutil.rmtree(target_dir)
    run_git(
        [
            "clone",
            "--quiet",
            "--depth",
            "1",
            "--single-branch",
            "--branch",
            ref,
            target["repository"],
            str(target_dir),
        ],
        workspace,
        capture=False,
    )
    child_sha = require_sha40(run_git(["rev-parse", "HEAD"], target_dir), "child HEAD")
    return target_dir, ref, child_sha


def evaluate_target(
    parent_repo: Path,
    parent_sha: str,
    target: dict[str, Any],
    workspace: Path,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "name": target["name"],
        "mode": target["mode"],
        "repository": target["repository"],
        "status": "failed",
        "checks": [],
        "errors": [],
    }
    try:
        child_repo, ref, child_sha = clone_target(target, workspace)
        result["ref"] = ref
        result["commit"] = child_sha

        child_parent_sha = read_gitlink(
            child_repo,
            child_sha,
            target["iot_reference_gitlink"],
        )
        result["iot_reference_rx_commit"] = child_parent_sha
        run_git(
            ["fetch", "--quiet", "--depth", "1", "origin", child_parent_sha],
            parent_repo,
            capture=False,
        )
        result["checks"] = compare_parent_gitlinks(
            parent_repo,
            parent_sha,
            child_parent_sha,
            target["dependencies"],
        )
        result["checks"].extend(
            compare_parent_source_trees(
                parent_repo,
                parent_sha,
                child_parent_sha,
                target["source_roots"],
            )
        )

        result["status"] = (
            "passed"
            if all(check["status"] == "passed" for check in result["checks"])
            else "failed"
        )
    except (AlignmentError, OSError) as exc:
        result["errors"].append(redact_sensitive_text(str(exc)))
    return result


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_dotenv(
    path: Path,
    config: dict[str, Any] | None,
    results: list[dict[str, Any]],
) -> None:
    """Export each resolved child SHA for later immutable-SHA assertions."""

    path.parent.mkdir(parents=True, exist_ok=True)
    commits_by_name = {
        result["name"]: result.get("commit", "")
        for result in results
        if isinstance(result, dict) and isinstance(result.get("name"), str)
    }
    lines: list[str] = []
    if config is not None:
        for target in config["targets"]:
            commit = commits_by_name.get(target["name"], "")
            if commit:
                lines.append(
                    f"{target['resolved_ref_env']}="
                    f"{require_sha40(commit, target['name'] + ' resolved commit')}"
                )
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--dotenv", required=True, type=Path)
    args = parser.parse_args(argv)

    parent_repo = Path.cwd().resolve()
    report: dict[str, Any] = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "failed",
        "parent": {},
        "targets": [],
        "errors": [],
    }
    config: dict[str, Any] | None = None
    exit_code = 1
    try:
        config = load_config(args.config.resolve())
        parent_sha = require_sha40(
            run_git(["rev-parse", "HEAD"], parent_repo),
            "parent HEAD",
        )
        report["parent"] = {
            "commit": parent_sha,
            "repository": os.environ.get("CI_PROJECT_URL", "").strip(),
        }
        workspace = args.workspace.resolve()
        workspace.mkdir(parents=True, exist_ok=True)
        report["targets"] = [
            evaluate_target(parent_repo, parent_sha, target, workspace)
            for target in config["targets"]
        ]
        report["status"] = (
            "passed"
            if report["targets"]
            and all(target["status"] == "passed" for target in report["targets"])
            else "failed"
        )
        exit_code = 0 if report["status"] == "passed" else 1
    except (AlignmentError, OSError) as exc:
        report["errors"].append(redact_sensitive_text(str(exc)))
    finally:
        write_report(args.output.resolve(), report)
        write_dotenv(args.dotenv.resolve(), config, report["targets"])

    for target in report["targets"]:
        print(
            f"[{target['status'].upper()}] {target['name']} "
            f"ref={target.get('ref', '?')} commit={target.get('commit', '?')}"
        )
        for check in target["checks"]:
            print(f"  [{check['status'].upper()}] {check['path']}")
        for error in target["errors"]:
            print(f"  [ERROR] {error}")
    for error in report["errors"]:
        print(f"[ERROR] {error}")
    print(f"dependency alignment: {report['status']}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

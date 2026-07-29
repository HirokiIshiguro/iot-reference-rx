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
from urllib.parse import urlsplit, urlunsplit


SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
ENV_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
GITLINK_RE = re.compile(
    r"^160000 commit ([0-9a-f]{40})\t(.+)$"
)
TREE_ENTRY_RE = re.compile(
    r"^(?P<mode>[0-7]{6}) (?P<type>blob|tree|commit) "
    r"(?P<object>[0-9a-f]{40})\t(?P<path>.+)$"
)
SUPPORTED_MODES = {"vendored_subset", "parent_gitlinks"}


class AlignmentError(RuntimeError):
    """A deterministic dependency-alignment failure."""


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
        stderr = (completed.stderr or "").strip()
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
        ref_env = target.get("ref_env")
        if not isinstance(ref_env, str) or not ENV_NAME_RE.fullmatch(ref_env):
            raise AlignmentError(f"{name}: invalid ref_env")
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

        if target["mode"] == "parent_gitlinks":
            if target.get("allowed_patches"):
                raise AlignmentError(
                    f"{name}: allowed_patches is only valid for vendored_subset"
                )
            link = target.get("iot_reference_gitlink")
            if not isinstance(link, str):
                raise AlignmentError(f"{name}: iot_reference_gitlink is required")
            target["iot_reference_gitlink"] = safe_relative_path(
                link, f"{name} iot_reference_gitlink"
            )
        else:
            allowed_patches = target.get("allowed_patches", [])
            if not isinstance(allowed_patches, list):
                raise AlignmentError(f"{name}: allowed_patches must be a list")
            normalized_patches: list[dict[str, str]] = []
            patch_paths: set[str] = set()
            for patch in allowed_patches:
                if not isinstance(patch, dict):
                    raise AlignmentError(
                        f"{name}: each allowed patch must be an object"
                    )
                patch_path = safe_relative_path(
                    patch.get("path", ""),
                    f"{name} allowed patch",
                )
                if not any(
                    patch_path.startswith(f"{dependency}/")
                    for dependency in normalized
                ):
                    raise AlignmentError(
                        f"{name}: allowed patch is outside dependencies: "
                        f"{patch_path}"
                    )
                if patch_path in patch_paths:
                    raise AlignmentError(
                        f"{name}: duplicate allowed patch: {patch_path}"
                    )
                patch_paths.add(patch_path)
                reason = patch.get("reason")
                if not isinstance(reason, str) or not reason.strip():
                    raise AlignmentError(
                        f"{name}: allowed patch reason is required"
                    )
                normalized_patches.append(
                    {
                        "path": patch_path,
                        "parent_blob": require_sha40(
                            patch.get("parent_blob", ""),
                            f"{name} allowed patch parent blob",
                        ),
                        "child_blob": require_sha40(
                            patch.get("child_blob", ""),
                            f"{name} allowed patch child blob",
                        ),
                        "reason": reason.strip(),
                    }
                )
            target["allowed_patches"] = normalized_patches
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


def initialize_parent_submodules(parent_repo: Path, dependencies: list[str]) -> None:
    run_git(["submodule", "sync", "--", *dependencies], parent_repo, capture=False)
    update_args = [
        "submodule",
        "update",
        "--init",
        "--force",
        "--depth",
        "1",
        "--",
        *dependencies,
    ]
    last_error: AlignmentError | None = None
    for attempt in range(2):
        try:
            run_git(update_args, parent_repo, capture=False)
            return
        except AlignmentError as exc:
            last_error = exc
            if attempt == 0:
                print(
                    "[WARN] parent dependency checkout failed once; "
                    "retrying the same recorded pins",
                    file=sys.stderr,
                )
                run_git(
                    ["submodule", "sync", "--", *dependencies],
                    parent_repo,
                    capture=False,
                )
    assert last_error is not None
    raise last_error


def git_blob_manifest(
    repo: Path,
    ref: str,
    prefix: str = "",
) -> tuple[dict[str, str], list[str]]:
    """Return tracked blob IDs and nested gitlinks below prefix.

    Git object IDs are used instead of working-tree byte hashes so a Windows
    checkout's CRLF conversion cannot be misclassified as a library-version
    change.
    """

    require_sha40(ref, "tree ref")
    args = ["ls-tree", "-r", "-z", ref]
    normalized_prefix = prefix.rstrip("/")
    if normalized_prefix:
        args.extend(["--", normalized_prefix])
    output = run_git(args, repo)

    blobs: dict[str, str] = {}
    nested_gitlinks: list[str] = []
    for raw_entry in output.split("\0"):
        if not raw_entry:
            continue
        match = TREE_ENTRY_RE.fullmatch(raw_entry)
        if not match:
            raise AlignmentError(f"cannot parse git tree entry: {raw_entry!r}")
        path = match.group("path")
        if normalized_prefix:
            marker = f"{normalized_prefix}/"
            if not path.startswith(marker):
                raise AlignmentError(
                    f"git tree path escaped requested prefix: {path}"
                )
            path = path[len(marker):]
        if match.group("mode") == "160000":
            nested_gitlinks.append(path)
        elif match.group("type") == "blob":
            blobs[path] = match.group("object")
    return blobs, sorted(nested_gitlinks)


def compare_vendored_dependency(
    parent_root: Path,
    child_root: Path,
    dependency: str,
    child_ref: str = "HEAD",
    allowed_patches: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    parent_dependency = parent_root / dependency
    if not parent_dependency.is_dir():
        raise AlignmentError(
            f"parent dependency checkout is missing: {dependency}"
        )
    parent_ref = require_sha40(
        run_git(["rev-parse", "HEAD"], parent_dependency),
        f"parent dependency {dependency}",
    )
    child_ref = require_sha40(
        run_git(["rev-parse", child_ref], child_root),
        "child tree ref",
    )
    parent_manifest, parent_nested_gitlinks = git_blob_manifest(
        parent_dependency,
        parent_ref,
    )
    child_manifest, child_nested_gitlinks = git_blob_manifest(
        child_root,
        child_ref,
        dependency,
    )
    if not child_manifest:
        raise AlignmentError(f"vendored dependency is empty: {dependency}")

    # A parent library may contain a separately pinned, transitive submodule.
    # The RX671 repositories vendor those transitive files as ordinary blobs.
    # They are excluded here: this gate compares the direct libraries listed in
    # policy, while their own gitlinks remain pinned by the parent library.
    ignored_child_files = sorted(
        path
        for path in child_manifest
        if any(
            path == nested or path.startswith(f"{nested}/")
            for nested in parent_nested_gitlinks
        )
    )
    for path in ignored_child_files:
        del child_manifest[path]

    missing_in_parent = sorted(set(child_manifest) - set(parent_manifest))
    modified_candidates = sorted(
        path
        for path in set(child_manifest) & set(parent_manifest)
        if child_manifest[path] != parent_manifest[path]
    )
    allowed_by_path = {
        patch["path"]: patch
        for patch in (allowed_patches or [])
        if patch["path"].startswith(f"{dependency}/")
    }
    applied_allowed_patches: list[dict[str, str]] = []
    modified: list[str] = []
    for path in modified_candidates:
        full_path = f"{dependency}/{path}"
        patch = allowed_by_path.get(full_path)
        if (
            patch is not None
            and patch["parent_blob"] == parent_manifest[path]
            and patch["child_blob"] == child_manifest[path]
        ):
            applied_allowed_patches.append(patch)
        else:
            modified.append(path)
    parent_only = sorted(set(parent_manifest) - set(child_manifest))
    status = (
        "passed"
        if not missing_in_parent and not modified and not child_nested_gitlinks
        else "failed"
    )
    return {
        "path": dependency,
        "status": status,
        "parent_dependency_commit": parent_ref,
        "child_repository_commit": child_ref,
        "checked_files": len(child_manifest),
        "parent_only_files": len(parent_only),
        "ignored_parent_nested_gitlinks": parent_nested_gitlinks,
        "ignored_child_files_below_nested_gitlinks": len(ignored_child_files),
        "child_nested_gitlinks": child_nested_gitlinks,
        "allowed_patches": applied_allowed_patches,
        "missing_in_parent": missing_in_parent,
        "modified": modified,
    }


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

        if target["mode"] == "vendored_subset":
            result["checks"] = [
                compare_vendored_dependency(
                    parent_repo,
                    child_repo,
                    dependency,
                    child_sha,
                    target.get("allowed_patches", []),
                )
                for dependency in target["dependencies"]
            ]
        else:
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

        result["status"] = (
            "passed"
            if all(check["status"] == "passed" for check in result["checks"])
            else "failed"
        )
    except (AlignmentError, OSError) as exc:
        result["errors"].append(str(exc))
    return result


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
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
        vendored_dependencies = sorted(
            {
                dependency
                for target in config["targets"]
                if target["mode"] == "vendored_subset"
                for dependency in target["dependencies"]
            }
        )
        if vendored_dependencies:
            initialize_parent_submodules(parent_repo, vendored_dependencies)
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
        report["errors"].append(str(exc))
    finally:
        write_report(args.output.resolve(), report)

    for target in report["targets"]:
        print(
            f"[{target['status'].upper()}] {target['name']} "
            f"ref={target.get('ref', '?')} commit={target.get('commit', '?')}"
        )
        for check in target["checks"]:
            print(f"  [{check['status'].upper()}] {check['path']}")
            for patch in check.get("allowed_patches", []):
                print(
                    f"    [ALLOWED PATCH] {patch['path']}: "
                    f"{patch['reason']}"
                )
        for error in target["errors"]:
            print(f"  [ERROR] {error}")
    for error in report["errors"]:
        print(f"[ERROR] {error}")
    print(f"dependency alignment: {report['status']}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

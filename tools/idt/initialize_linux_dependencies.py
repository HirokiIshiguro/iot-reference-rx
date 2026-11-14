"""Initialize the same pinned nested dependencies as the Windows builder."""
from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
import re
import subprocess


def source_only_paths(windows_helper: Path) -> tuple[str, ...]:
    """Reuse the Windows helper's literal exclusion list; reject changed syntax."""
    source = windows_helper.read_text(encoding="utf-8-sig")
    matches = re.findall(r"(?m)^\s*\$sourceOnly\s*=\s*@\(([^\r\n)]*)\)\s*$", source)
    if len(matches) != 1 or not re.fullmatch(r"\s*'[^']+'(?:\s*,\s*'[^']+')*\s*", matches[0]):
        raise ValueError("Windows nested-dependency exclusions cannot be read")
    paths = tuple(re.findall(r"'([^']+)'", matches[0]))
    if any(PurePosixPath(p).is_absolute() or ".." in PurePosixPath(p).parts or "\\" in p for p in paths):
        raise ValueError("invalid nested-dependency exclusion")
    return paths


def git_environment(source, config):
    """Keep Runner Git authentication, never forward AWS or OIDC secrets."""
    fixed = {"GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM", "GIT_CONFIG_NOSYSTEM", "GIT_CONFIG_COUNT",
             "GIT_SSL_CAINFO"}
    env = {name: value for name, value in source.items()
           if name in fixed or re.fullmatch(r"GIT_CONFIG_(?:KEY|VALUE)_[0-9]+", name)}
    for name in ("CI_JOB_TOKEN", "LANG", "LC_ALL"):
        if name in source:
            env[name] = source[name]
    env.update(PATH=config.search_path, HOME=config.home, GIT_TERMINAL_PROMPT="0")
    return env


def initialize(source: Path, git: str, env: dict[str, str]) -> int:
    """Update nested pins and verify the resulting recursive status."""
    source = Path(source).resolve(strict=True)
    excluded = source_only_paths(source / "tools/rx_e2studio_cli.ps1")

    def git_run(args, *, allow_missing=False):
        result = subprocess.run([git, *args], cwd=source, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
        if result.returncode != 0 and not (allow_missing and result.returncode == 1):
            # Git stderr can contain credential-bearing remote URLs.
            raise RuntimeError("nested dependency initialization failed")
        return result.stdout.strip()

    def disabled_in_manifest(name):
        relative = PurePosixPath(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("invalid nested dependency path")
        path = source.joinpath(*relative.parts)
        for parent in path.parents:
            if parent == source.parent:
                break
            descriptor = parent / ".gitmodules"
            if not descriptor.is_file():
                continue
            rows = git_run(["config", "--file", str(descriptor), "--get-regexp", r"^submodule\..*\.path$"],
                           allow_missing=True)
            subpath = path.relative_to(parent).as_posix()
            for entry in rows.splitlines():
                parts = entry.split(None, 1)
                if len(parts) == 2 and parts[1] == subpath:
                    update_key = parts[0][:-len(".path")] + ".update"
                    return git_run(["config", "--file", str(descriptor), "--get", update_key],
                                   allow_missing=True).lower() == "none"
        return False

    rows = git_run(["config", "--file", ".gitmodules", "--get-regexp", r"^submodule\..*\.path$"])
    include = git_run(["config", "--get", "include.path"], allow_missing=True)
    count = 0
    for row in rows.splitlines():
        parts = row.split(None, 1)
        if len(parts) != 2:
            raise ValueError("invalid submodule path entry")
        relative = parts[1]
        if relative in excluded:
            continue
        dependency = (source / relative).resolve(strict=True)
        if source not in dependency.parents:
            raise ValueError("nested dependency escapes source")
        if not (dependency / ".gitmodules").is_file():
            continue
        args = ["-C", str(dependency)]
        if include:
            args += ["-c", "include.path=" + include]
        git_run(args + ["submodule", "update", "--init", "--recursive", "--depth", "1"])
        count += 1

    status = git_run(["submodule", "status", "--recursive"])
    for row in status.splitlines():
        if not row or row[0] not in "-+U":
            continue
        name = row[42:].split(" (", 1)[0].strip()
        if any(name.startswith(path + "/") for path in excluded):
            continue
        if row[0] == "-" and disabled_in_manifest(name):
            continue
        raise RuntimeError("nested dependency is missing or differs from its pinned revision")
    return count

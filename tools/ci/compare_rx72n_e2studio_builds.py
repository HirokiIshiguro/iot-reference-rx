"""Compare two clean e² studio/CC-RX builds of one RX72N project."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re


def normalize_path(path: str, repo_root: Path, project_name: str) -> str:
    path = re.sub(r"/+", "/", path.replace("\\", "/"))
    repo = repo_root.as_posix().rstrip("/") + "/"
    if not path.lower().startswith(repo.lower()):
        return path
    path = path[len(repo):]
    project = f"Projects/{project_name}/e2studio_ccrx/"
    if path.startswith(project):
        return path.removeprefix(project)
    if path.startswith("Middleware/Renesas/"):
        parts = path.split("/")
        if parts[2] == "rx-driver-package" and len(parts) >= 7 and parts[3] == "source":
            return "/".join(("src/smc_gen", *parts[6:]))
        if len(parts) >= 5 and parts[3].endswith("_vx.xx"):
            return "/".join(("src/smc_gen", *parts[4:]))
    return path


def snapshot(build_dir: Path, repo: Path, project: str) -> dict:
    def normalize(path: str) -> str:
        return normalize_path(path, repo, project)

    sources = Counter()
    makefile = (build_dir / "makefile").read_text(encoding="utf-8-sig")
    includes = re.findall(r"(?m)^-include[ \t]+([^\n]+subdir\.mk)[ \t]*$", makefile)
    for include in includes:
        text = (build_dir / include).read_text(encoding="utf-8-sig")
        for block in re.findall(r"(?m)^\w+_SRCS\s*\+=\s*\\\n((?:[^\n]*\\\n)*[^\n]+)", text):
            for row in block.splitlines():
                path = row.strip().removesuffix("\\").rstrip()
                if Path(path).suffix.lower() not in {".c", ".s", ".asm", ".cpp", ".cxx"}:
                    continue
                if not Path(path).is_absolute():
                    path = str((build_dir / path).resolve())
                sources[normalize(path)] += 1

    commands = json.loads((build_dir / "compile_commands.json").read_bytes())
    options = {}
    for row in commands:
        flags = []
        for match in re.finditer(r'"(-(?:include|define|undefine)=[^"]*)"|(-(?:include|define|undefine)=\S+)',
                                 row["command"]):
            option, value = (match[1] or match[2]).split("=", 1)
            flags.append((option, tuple(normalize(item) for item in value.split(","))))
        options[normalize(row["file"])] = flags

    linker = (build_dir / f"Linker{project}.tmp").read_text(encoding="utf-8", errors="replace")
    link_flags = [line.strip() for line in linker.splitlines()
                  if not line.startswith(("-input=", "-MAKEUD="))]
    link_order = [line for line in linker.splitlines() if line.startswith("-input=")]
    sections = {}
    map_data = (build_dir / f"{project}.map").read_text(encoding="utf-8", errors="replace")
    layout, separator, _ = map_data.partition("*** Total Section Size ***")
    if not separator:
        raise ValueError("The CC-RX link map has no section size table")
    for name, size in re.findall(r"(?m)^([A-Za-z_][\w.$]*)\s+(?:\r?\n\s*)?"
                                 r"[\da-fA-F]{8}\s+[\da-fA-F]{8}\s+([\da-fA-F]{1,8})\s+\d+\s*$", layout):
        sections[name] = int(size, 16)
    sections.update({name: int(size, 16) for name, size in re.findall(
        r"(?m)^(RAMDATA|ROMDATA|PROGRAM) SECTION:[ \t]+([\da-fA-F]+)", map_data)})
    if not sources or not options or not sections or not link_order:
        raise ValueError("Missing source, compiler, or linker evidence")
    return {"sources": sources, "options": options, "link_flags": link_flags, "link_order": link_order,
            "sections": sections, "mot_bytes": (build_dir / f"{project}.mot").stat().st_size}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project")
    for prefix in ("before", "after"):
        parser.add_argument(f"--{prefix}-build", required=True, type=Path)
        parser.add_argument(f"--{prefix}-repo", required=True, type=Path)
    args = parser.parse_args()

    before = snapshot(args.before_build, args.before_repo.resolve(), args.project)
    after = snapshot(args.after_build, args.after_repo.resolve(), args.project)
    removed = before["sources"] - after["sources"]
    added = after["sources"] - before["sources"]
    changed_flags = sorted(path for path in before["options"].keys() | after["options"].keys()
                           if before["options"].get(path) != after["options"].get(path))
    changed_sections = {
        name: [before["sections"].get(name), after["sections"].get(name)]
        for name in sorted(before["sections"].keys() | after["sections"].keys())
        if before["sections"].get(name) != after["sections"].get(name)
    }
    report = {
        "project": args.project,
        "source_count": [sum(before["sources"].values()), sum(after["sources"].values())],
        "c_source_count": [sum(count for path, count in build["sources"].items() if path.endswith(".c"))
                           for build in (before, after)],
        "removed_sources": list(removed.elements()),
        "added_sources": list(added.elements()),
        "sources_with_changed_includes_or_defines": changed_flags,
        "link_options_match": before["link_flags"] == after["link_flags"],
        "mot_bytes": [before["mot_bytes"], after["mot_bytes"]],
        "changed_section_sizes": changed_sections,
    }
    print(json.dumps(report, indent=2))
    return int(bool(removed or added or changed_flags or changed_sections or not report["link_options_match"]
                    or before["mot_bytes"] != after["mot_bytes"]))


if __name__ == "__main__":
    raise SystemExit(main())

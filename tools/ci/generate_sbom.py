"""Generate the source checkout SBOM. Run with --check to detect drift.

After changing submodule pins, initialize the submodules recursively at the
new pins and use --refresh to read their Git objects and locally fetched tags.
For a release, refresh tags from each declared repository before generating.
"""

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import urljoin, urlsplit


ROOT = Path(__file__).resolve().parents[2]
REPOSITORY = "https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx.git"
EVIDENCE = ROOT / "tools/ci/sbom_gitlinks.json"
OUTPUT = ROOT / "sbom.spdx"
ROOT_ID = "SPDXRef-iot-reference-rx"


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], encoding="utf-8")


def dependency_key(url, commit):
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.query or parsed.fragment or not re.fullmatch(r"[0-9a-f]{40}", commit)):
        raise ValueError(f"Invalid source location for commit {commit}")
    repo = (parsed.netloc + parsed.path.rstrip("/").removesuffix(".git")).lower()
    return f"{repo}@{commit}"


def gitlinks(repo, commit, url):
    entries = git(repo, "ls-tree", "-rz", commit).split("\0")
    links = {entry.split("\t", 1)[1]: entry.split()[2]
             for entry in entries if entry.startswith("160000 ")}
    if not links:
        return {}
    config = git(repo, "config", "--blob", f"{commit}:.gitmodules", "-z", "--list")
    settings = dict(item.split("\n", 1) for item in config.rstrip("\0").split("\0"))
    urls = {path: urljoin(url.rstrip("/") + "/", settings[key.removesuffix(".path") + ".url"])
            for key, path in settings.items() if key.startswith("submodule.") and key.endswith(".path")}
    if links.keys() != urls.keys():
        raise ValueError(f".gitmodules paths differ from gitlinks at {commit}")
    return {path: [urls[path], sha] for path, sha in sorted(links.items())}


def refresh(repo, evidence, links):
    refreshed = {}

    def visit(parent, direct):
        for path, (url, commit) in direct.items():
            key = dependency_key(url, commit)
            if key in refreshed:
                continue
            child = parent / path
            if (not child.is_dir()
                    or Path(git(child, "rev-parse", "--show-toplevel").strip()).resolve() != child):
                raise ValueError(f"Initialize submodule {path} at {commit} before refreshing")
            children = gitlinks(child, commit, url)
            metadata = {"tags": git(child, "tag", "--points-at", commit).splitlines(),
                        "children": children}
            # Retain reviewed version labels and license declarations only at their exact commit.
            for field in ("manifestVersion", "license"):
                if field in evidence.get(key, {}):
                    metadata[field] = evidence[key][field]
            refreshed[key] = metadata
            visit(child, children)

    visit(repo, links)
    return refreshed


def manifest_versions(manifest, links, evidence):
    # This accepts the manifest's quoted Git dependency records. Reject a
    # changed record shape instead of silently skipping a dependency.
    header, dependencies = manifest.split("\ndependencies:\n", 1)
    base, = re.findall(r'^version:\s*"([^"]+)"\s*$', header, re.MULTILINE)
    records = re.split(r'^  - name: "[^"]+"\s*\n', dependencies, flags=re.MULTILINE)
    if len(records) < 2 or records[0].strip():
        raise ValueError("manifest.yml has no quoted Git dependency records")
    versions = {}
    for record in records[1:]:
        fields = re.match(
            r'    version: "([^"]+)"\n    repository:\n      type: "git"\n'
            r'      url: "([^"]+)"\n      path: "/([^"]+)"(?:\n|$)', record
        )
        if fields is None:
            raise ValueError(f"Unsupported manifest.yml dependency fields: {record.splitlines()[0]}")
        version, url, path = fields.groups()
        if path not in links:
            raise ValueError(f"manifest.yml dependency has no gitlink: {path}")
        key = dependency_key(*links[path])
        if key != dependency_key(url, links[path][1]):
            raise ValueError(f"manifest.yml URL differs from .gitmodules: {path}")
        known = evidence.get(key, {})
        accepted = {*known.get("tags", []), known.get("manifestVersion")}
        if version not in accepted and f"v{version}" not in accepted:
            raise ValueError(f"manifest.yml version {version} does not match {path} at {links[path][1]}")
        if key in versions and versions[key] != version:
            raise ValueError(f"Conflicting manifest.yml versions for {path}")
        versions[key] = version
    return base, versions


def document(links, manifest, snapshot):
    evidence = snapshot["repositories"]
    base, versions = manifest_versions(manifest, links, evidence)
    packages = {}
    relationships = defaultdict(list)

    def visit(parent, children):
        for path, (url, commit) in sorted(children.items()):
            key = dependency_key(url, commit)
            identifier = "SPDXRef-" + hashlib.sha256(key.encode()).hexdigest()
            relationships[parent, identifier].append(path)
            if key in packages:
                continue
            if key not in evidence:
                raise ValueError(f"Missing pinned Git evidence for {path} at {commit}")
            metadata = evidence[key]
            tags = sorted(tag for tag in metadata["tags"] if not tag.startswith("latest-"))
            version = versions.get(key) or next((tag for tag in tags if re.match(r"[vV]\d", tag)),
                                                tags[0] if tags else commit)
            name = urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")
            packages[key] = package(name, identifier, version, f"git+{url}@{commit}",
                                    metadata.get("license", "NOASSERTION"))
            if version == metadata.get("manifestVersion"):
                packages[key] += "\nPackageSourceInfo: Version declared in README.md at the pinned commit."
            visit(identifier, metadata["children"])

    visit(ROOT_ID, links)
    if packages.keys() != evidence.keys():
        raise ValueError("Unused commits in SBOM evidence. Refresh it after updating gitlinks.")
    root_package = package("iot-reference-rx", ROOT_ID, base, "NOASSERTION", "MIT")
    root_package += "\nPackageSourceInfo: PackageVersion identifies the FreeRTOS LTS base in manifest.yml."
    content = [
        "SPDXVersion: SPDX-2.3",
        "DataLicense: CC0-1.0",
        "SPDXID: SPDXRef-DOCUMENT",
        "DocumentName: iot-reference-rx-submodules",
        "DocumentNamespace: " + REPOSITORY.removesuffix(".git") + "/spdx/{digest}",
        "Creator: Tool: tools/ci/generate_sbom.py",
        f"Created: {snapshot['created']}",
        "DocumentComment: <text>Git submodule inventory for the source checkout, including nested "
        "test and example repositories. CONTAINS follows Git links. Vendored files and "
        "dependencies selected by individual firmware builds are outside this inventory.</text>",
        f"\nRelationship: SPDXRef-DOCUMENT DESCRIBES {ROOT_ID}",
        "\n" + root_package,
    ]
    content.extend("\n" + packages[key] for key in sorted(packages))
    for (parent, child), paths in sorted(relationships.items()):
        content.append(f"\nRelationship: {parent} CONTAINS {child}")
        content.append(f"RelationshipComment: <text>{', '.join(paths)}</text>")
    text = "\n".join(content) + "\n"
    return text.replace("{digest}", hashlib.sha256(text.encode()).hexdigest(), 1)


def package(name, identifier, version, location, license_declared):
    return "\n".join([
        f"PackageName: {name}", f"SPDXID: {identifier}", f"PackageVersion: {version}",
        f"PackageDownloadLocation: {location}", "FilesAnalyzed: false",
        "PackageLicenseConcluded: NOASSERTION", f"PackageLicenseDeclared: {license_declared}",
        "PackageCopyrightText: NOASSERTION",
    ])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="fail if the committed SBOM is stale")
    mode.add_argument("--refresh", action="store_true", help="refresh evidence from local Git objects")
    args = parser.parse_args()
    try:
        links = gitlinks(ROOT, "HEAD", REPOSITORY)
        manifest = git(ROOT, "show", "HEAD:manifest.yml")
        snapshot = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        if args.refresh:
            refreshed = refresh(ROOT, snapshot["repositories"], links)
            if refreshed != snapshot["repositories"]:
                snapshot = {"created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "repositories": refreshed}
        generated = document(links, manifest, snapshot)
        if args.check:
            if OUTPUT.read_text(encoding="utf-8") != generated:
                raise ValueError("sbom.spdx is stale. Run python tools/ci/generate_sbom.py.")
        else:
            if args.refresh:
                EVIDENCE.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n",
                                    encoding="utf-8", newline="\n")
            OUTPUT.write_text(generated, encoding="utf-8", newline="\n")
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()

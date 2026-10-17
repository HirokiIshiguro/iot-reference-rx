"""Route IDT's editable PKCS11 group list to pristine private build inputs.

The source view contains product configuration only. Borrowed test definitions
remain in the fixed submodule and are copied, without editing, into a separate
private build tree. Neither the selection facade nor its group list is compiled.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import stat
import sys

try:
    from ..idt_source_manifest import verify_dependency_provenance, PKCS11_RUNNER_FILE
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from idt_source_manifest import verify_dependency_provenance, PKCS11_RUNNER_FILE


CONFIG_FILES = ("manifest.yml", "Test/include/test_execution_config.h", "Test/include/test_param_config.h")
# FRQ 2.5 uses this fixed relative selector path. In the mutable view it holds
# only our group list; in the distinct build tree it holds the original SDK.
FACADE_FILE = PKCS11_RUNNER_FILE
MARKER_FILE = ".rx-idt-pkcs11-source-view.json"
BINDING_FILE = ".rx-idt-pkcs11-build-inputs.json"
GROUPS = ("Full_PKCS11_StartFinish", "Full_PKCS11_Capabilities", "Full_PKCS11_NoObject",
          "Full_PKCS11_RSA", "Full_PKCS11_EC")
FACADE = ("/* Product-owned PKCS11 selection configuration; never compiled. */\n"
          "void RxIdt_Pkcs11GroupSelection( void )\n{\n" +
          "".join("    RUN_TEST_GROUP( " + name + " );\n" for name in GROUPS) + "}\n")


def _bytes(root: Path, relative: str) -> bytes:
    path = root / relative
    for node in (path, *path.parents):
        metadata = node.lstat()
        if stat.S_ISLNK(metadata.st_mode) or (getattr(metadata, "st_file_attributes", 0) &
                getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)):
            raise ValueError("Linked PKCS11 source-view input is unsupported")
        if node == root:
            break
    if not path.is_file():
        raise ValueError("Missing PKCS11 source-view input: " + relative)
    return path.read_bytes()


def _hashes(view: Path) -> dict[str, str]:
    return {relative: hashlib.sha256(_bytes(view, relative)).hexdigest()
            for relative in (*CONFIG_FILES, FACADE_FILE, MARKER_FILE)}


def create_source_view(source: Path, destination: Path) -> None:
    source = Path(source).resolve(strict=True)
    destination = Path(destination).resolve()
    if destination == source or source in destination.parents:
        raise ValueError("PKCS11 source view must be outside the source repository")
    destination.mkdir(parents=False, exist_ok=False)
    for relative in CONFIG_FILES:
        path = destination / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_bytes(source, relative))
    facade = destination / FACADE_FILE
    facade.parent.mkdir(parents=True, exist_ok=True)
    with facade.open("w", encoding="utf-8", newline="\n") as output:
        output.write(FACADE)
    (destination / MARKER_FILE).write_text(json.dumps({"schema_version": 1,
        "purpose": "product-owned-native-pkcs11-selection"}) + "\n", encoding="utf-8")


def selected_group(view: Path) -> dict:
    marker = json.loads(_bytes(view, MARKER_FILE))
    if marker != {"schema_version": 1, "purpose": "product-owned-native-pkcs11-selection"}:
        raise ValueError("Unknown PKCS11 source-view marker")
    original_lines = FACADE.splitlines()
    lines = _bytes(view, FACADE_FILE).decode("utf-8").splitlines()
    if len(lines) != len(original_lines):
        raise ValueError("Product PKCS11 selector has an unsupported body change")
    enabled = []
    for original, actual in zip(original_lines, lines):
        match = re.fullmatch(r"    RUN_TEST_GROUP\( (Full_PKCS11_\w+) \);", original)
        if match is None:
            if actual != original:
                raise ValueError("Product PKCS11 selector has an unsupported body change")
            continue
        if actual == original:
            enabled.append(match.group(1))
        elif not re.fullmatch(r"[ \t]*//" + re.escape(original.strip()), actual):
            raise ValueError("Product PKCS11 selector has an unsupported group edit")
    if enabled == ["Full_PKCS11_StartFinish", "Full_PKCS11_Capabilities"]:
        return {"argument": "StartFinish", "definition": 1,
                "native_test_id": "Full_PKCS11_StartFinish", "groups": enabled, "assertion_cases": 6}
    if enabled == ["Full_PKCS11_Capabilities", "Full_PKCS11_NoObject"]:
        return {"argument": "NoObject", "definition": 2,
                "native_test_id": "Full_PKCS11_NoObject", "groups": enabled, "assertion_cases": 5}
    raise ValueError("Product PKCS11 selector is not a supported native Core selection")


def build_directory(view: Path, runtime: Path) -> Path:
    view = Path(view).resolve(strict=True)
    runtime = Path(runtime).resolve(strict=True)
    if view.parent not in (runtime, runtime / "source"):
        raise ValueError("PKCS11 selection must be a direct private runtime source view")
    identity = hashlib.sha256(str(view).encode("utf-8")).hexdigest()[:24]
    return runtime / ("pkcs11-build-" + identity)


def prepare_build_tree(view: Path, source: Path, runtime: Path, target: str, provenance: dict) -> dict:
    # Enforce the ownership boundary before opening any selection input.
    output = build_directory(view, runtime)
    view, source = Path(view).resolve(strict=True), Path(source).resolve(strict=True)
    selection = selected_group(view)
    verified = verify_dependency_provenance(source, target, provenance, test_group="PKCS11")
    if output == source or source in output.parents or output in source.parents:
        raise ValueError("PKCS11 build inputs must be separate from the original source")
    # A build callback is owned once; preserve an existing tree instead of
    # overwriting, cleaning or silently reusing its inputs on a retry.
    shutil.copytree(source, output, symlinks=True,
                    ignore=shutil.ignore_patterns(".git", "__pycache__", "artifacts"))
    for relative in CONFIG_FILES:
        if relative != "manifest.yml":
            (output / relative).write_bytes(_bytes(view, relative))
        elif _bytes(view, relative) != _bytes(source, relative):
            raise ValueError("PKCS11 source-view manifest differs from original production version")
    verify_dependency_provenance(output, target, provenance, test_group="PKCS11")
    binding = {"schema_version": 1, "target_id": target,
               "source_sha": provenance.get("source_sha"), "selection": selection,
               "source_view_sha256": _hashes(view), "verified_dependency_file_count": verified,
               "original_test_runner_sha256": provenance["dependency_files_sha256"][PKCS11_RUNNER_FILE],
               "qualification": "not-established"}
    (output / BINDING_FILE).write_text(json.dumps(binding, indent=2)+"\n", encoding="utf-8")
    return {"build_source": str(output), "selection": selection}


def resolve_build_tree(view: Path, runtime: Path, target: str) -> Path:
    view = Path(view).resolve(strict=True)
    source = build_directory(view, runtime)
    binding = json.loads(_bytes(source, BINDING_FILE))
    if (binding.get("schema_version") != 1 or binding.get("target_id") != target or
            binding.get("selection") != selected_group(view) or
            binding.get("source_view_sha256") != _hashes(view)):
        raise ValueError("PKCS11 source view differs from its private build binding")
    for relative in CONFIG_FILES:
        if _bytes(source, relative) != _bytes(view, relative):
            raise ValueError("PKCS11 effective product configuration differs from native source view")
    if hashlib.sha256(_bytes(source, PKCS11_RUNNER_FILE)).hexdigest() != binding.get("original_test_runner_sha256"):
        raise ValueError("PKCS11 compiled test body differs from captured original")
    return source


def record_build_binding(view: Path, runtime: Path, target: str) -> None:
    source = resolve_build_tree(view, runtime, target)
    binding = json.loads(_bytes(source, BINDING_FILE))
    path = source / "artifacts/idt/build_transport/build_manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8-sig"))
    if manifest.get("pkcs11_selection") != binding["selection"]:
        # PowerShell metadata omits the CLI argument name; compare only the
        # actual compiler definition, native test id, group order and count.
        expected = {key: value for key, value in binding["selection"].items() if key != "argument"}
        if manifest.get("pkcs11_selection") != expected:
            raise ValueError("PKCS11 build selection differs from native source view")
    if manifest.get("source_sha") != binding["source_sha"]:
        raise ValueError("PKCS11 build source identity differs from source provenance")
    manifest["pkcs11_source_view"] = binding
    path.write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("create", "prepare", "resolve", "record"))
    parser.add_argument("--view", type=Path, required=True)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--runtime", type=Path)
    parser.add_argument("--target")
    parser.add_argument("--provenance", type=Path)
    args = parser.parse_args()
    if args.action == "create":
        create_source_view(args.source, args.view)
    elif args.action == "prepare":
        provenance = json.loads(args.provenance.read_text(encoding="utf-8-sig"))
        print(json.dumps(prepare_build_tree(args.view, args.source, args.runtime, args.target, provenance)))
    elif args.action == "record":
        record_build_binding(args.view, args.runtime, args.target)
    else:
        print(resolve_build_tree(args.view, args.runtime, args.target))


if __name__ == "__main__":
    main()

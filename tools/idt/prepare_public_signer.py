"""Prepare four reviewed public signer inputs for a signed RX boot transaction.

The source checkout must be clean. Output is a new private directory outside
the checkout; stdout contains only the four environment-variable paths as JSON.
Compiler/certificate-tool output remains in private local logs. No hardware or
cloud operation is provided by this helper.
Native IDT retains its reviewed development signer; normal CI may explicitly
select the signer used for its application package.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

try:
    from . import public_signer_provision as controller
    from .targets import get_target
    from .. import build_public_signer_provisioner as producer
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import build_public_signer_provisioner as producer
    import public_signer_provision as controller
    from targets import get_target


def _unlinked(path):
    path = Path(path)
    if any(item.is_symlink() or (hasattr(item, "is_junction") and item.is_junction())
           for item in (path, *path.parents)):
        raise RuntimeError("Public signer preparation does not accept linked paths")
    return path


def _file(path):
    path = _unlinked(path)
    if not path.is_file():
        raise RuntimeError("Missing public signer preparation input: " + path.name)
    return path


def _source_state(source):
    values = []
    environment={key:value for key,value in os.environ.items() if not key.upper().startswith("GIT_")}
    for arguments in (("status", "--porcelain=v1", "--untracked-files=all"), ("rev-parse", "HEAD")):
        result = subprocess.run(["git", "--no-optional-locks", "-c", "safe.directory="+str(source),
                                 "-C", str(source), *arguments], capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=30, env=environment)
        if result.returncode:
            raise RuntimeError("Cannot verify public signer source checkout")
        values.append(result.stdout.strip())
    if values[0] or not re.fullmatch(r"[a-f0-9]{40}", values[1]):
        raise RuntimeError("Native public signer preparation requires a clean committed source checkout")
    return values[1]


def _public_from_development_key(source, target, signing_key=None):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    path = _file(source/target["signing_key"] if signing_key is None else signing_key).resolve(strict=True)
    if signing_key is None and not path.is_relative_to(source):
        raise RuntimeError("Development signing key must remain inside its reviewed source checkout")
    try:
        key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    except Exception:
        raise RuntimeError("Cannot load the purpose-selected development signing key") from None
    if not isinstance(key, ec.EllipticCurvePrivateKey) or not isinstance(key.curve, ec.SECP256R1):
        raise RuntimeError("The reviewed development signing key must be ECDSA P-256")
    public = key.public_key()
    return path, public.public_bytes(serialization.Encoding.PEM,
                                   serialization.PublicFormat.SubjectPublicKeyInfo)


def _cleanup_public_outputs(output, build):
    # Only paths created by this helper are removed. Preserve private logs for
    # diagnosis, and preserve an unrelated sibling/workspace/source checkout.
    if _unlinked(output).resolve(strict=True) != output:
        raise RuntimeError("Public signer output ownership changed during preparation")
    for name in controller.ENVIRONMENT_INPUTS:
        path=output/name
        if path.exists() or path.is_symlink():
            path.unlink()
    if build.exists():
        if (_unlinked(build).resolve(strict=True) != output/"build" or not build.is_relative_to(output)):
            raise RuntimeError("Public signer build ownership changed during preparation")
        for name in ("build-private.log", "launcher-private.log"):
            path=build/name
            if path.is_file() and not path.is_symlink():
                shutil.copyfile(path, output/("failed-"+name))
        shutil.rmtree(build)


def prepare(source: Path, target_id: str, output: Path, workspace: Path, python: str,
            environ=None, *, signing_key=None) -> dict[str, str]:
    """Generate a complete native input set; override handling belongs to the caller."""
    environment = os.environ if environ is None else environ
    source = _unlinked(source).resolve(strict=True)
    target = get_target(target_id)
    output = _unlinked(output).resolve()
    workspace = _unlinked(workspace).resolve()
    if output.exists() or output.is_symlink():
        raise FileExistsError("Public signer output already exists; it will not be overwritten")
    if output.is_relative_to(source) or workspace.is_relative_to(source) or workspace.is_relative_to(output):
        raise RuntimeError("Public signer output/workspace must stay outside the source checkout and output directory")
    supplied = {variable: environment.get(variable, "") for variable in controller.ENVIRONMENT_INPUTS.values()}
    if any(supplied.values()):
        raise RuntimeError("Public signer preparation is generation-only; handle all four overrides in the caller")
    source_sha = _source_state(source)
    project = source/target["application_project"]
    name = ET.parse(_file(project/".project")).getroot().findtext("name")
    if not name or not re.fullmatch("[A-Za-z0-9_]+", name):
        raise RuntimeError("Invalid public signer application project name")
    output.mkdir(parents=True, mode=0o700, exist_ok=False)
    build = output/"build"
    try:
        with (output/"producer-private.log").open("w", encoding="utf-8") as log, redirect_stdout(log), redirect_stderr(log):
            metadata = producer.build(source, target_id, build, workspace, python)
        manifest_path = _file(build/"provisioner-manifest.json")
        manifest = json.loads(manifest_path.read_bytes())
        if (manifest != metadata or manifest.get("formal") is not True or
                manifest.get("source_tree_dirty") is not False or manifest.get("source_sha") != source_sha):
            raise RuntimeError("Public signer producer did not return a formal matching source manifest")
        mot = _file(build/(name+".mot"))
        # A public native input set is copied only from the just-validated
        # producer output; private compiler logs never enter that set.
        shutil.copyfile(mot, output/"public_signer_provisioner.mot")
        shutil.copyfile(manifest_path, output/"public_signer_provisioner_manifest.json")
        key_path, public = _public_from_development_key(source, target, signing_key)
        (output/"signer.pub.pem").write_bytes(public)
        command = [python, str(_file(source/"tools/generate_signer_cert.py")),
                   "--key", str(key_path), "--out", str(output/"signer.crt.pem")]
        with (output/"signer-tool-private.log").open("wb") as log:
            result = subprocess.run(command, cwd=source, stdout=log, stderr=subprocess.STDOUT,
                                    env=producer.isolated_environment(environment), timeout=90)
        if result.returncode:
            raise RuntimeError("Public signer certificate tool failed; private logs are retained")
        paths = {variable: str(_file(output/filename)) for filename, variable in controller.ENVIRONMENT_INPUTS.items()}
        checked = controller.validate_prepared_signer(source, output, target, source_sha, environ=paths)
        _, public = _public_from_development_key(source, target, signing_key)
        from cryptography.hazmat.primitives import serialization
        spki = serialization.load_pem_public_key(public).public_bytes(serialization.Encoding.DER,
                                      serialization.PublicFormat.SubjectPublicKeyInfo)
        if checked["public_signer_spki_sha256"] != hashlib.sha256(spki).hexdigest():
            raise RuntimeError("Prepared public signer differs from the initial development package signer")
        if _source_state(source) != source_sha:
            raise RuntimeError("Public signer source changed during preparation")
        return paths
    except BaseException:
        _cleanup_public_outputs(output, build)
        raise


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--target", choices=tuple(controller.LAYOUTS), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--signing-key", type=Path,
                        help="Explicit normal-CI signer; omitted for the reviewed native-IDT development key")
    args=parser.parse_args(argv)
    try:
        paths=prepare(args.source,args.target,args.output,args.workspace,args.python,
                      signing_key=args.signing_key)
    except Exception:
        print("Public signer preparation failed; inspect the requested private output directory.",file=sys.stderr)
        return 1
    print(json.dumps(paths, sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())

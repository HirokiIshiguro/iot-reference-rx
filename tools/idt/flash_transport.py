#!/usr/bin/env python3
"""Transfer the exact just-built IDT images to the selected locked bench."""
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
from prepare_transport_key import validate_source, macro
from flash_failure import record_flash_failure
from targets import get_target, target_fingerprint
from cleanup_budget import flash_remote_seconds

SSH=os.environ.get('IDT_WINDOWS_SSH','/mnt/c/Windows/System32/OpenSSH/ssh.exe')
SCP=os.environ.get('IDT_WINDOWS_SCP','/mnt/c/Windows/System32/OpenSSH/scp.exe')
def sha256(path):
    if path.is_symlink() or not path.is_file():
        raise RuntimeError('Missing or symbolic link flash input: ' + path.name)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validated_inputs(source, target):
    """Fail before SSH for stale, substituted, or other-target build outputs."""
    out = source / 'artifacts/idt/build_transport'
    manifest_path = out / 'build_manifest.json'
    sha256(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    if (manifest.get('target_id') != target['id'] or
            manifest.get('target_sha256') != target_fingerprint(target)):
        raise RuntimeError('Build manifest target mismatch')
    basename = target['artifact_basename']
    outputs = {
        'mot': out / (basename + '.mot'),
        'rsu': out / (basename + '.rsu'),
        'bootloader': out / 'bootloader.mot',
        'bootloader_bank1': out / 'bootloader_bank1.mot',
    }
    for name, path in outputs.items():
        entry = manifest.get('outputs', {}).get(name, {})
        if sha256(path) != entry.get('sha256'):
            raise RuntimeError('Firmware hash mismatch: ' + name)
    if sha256(source / 'Test/include/test_param_config.h') != manifest.get('parameter_config_sha256'):
        raise RuntimeError('Test parameter hash mismatch')
    here = Path(__file__).resolve().parent
    files = {
        'bootloader.mot': outputs['bootloader'],
        'bootloader_bank1.mot': outputs['bootloader_bank1'],
        'idt_transport.rsu': outputs['rsu'],
        'test_uart_download_rx72n.py': source / 'tools/test_uart_download_rx72n.py',
        'rpi_flash.py': here / 'rpi_flash.py',
        'targets.py': here / 'targets.py',
        'targets.json': here / 'targets.json',
        'cleanup_budget.py': here / 'cleanup_budget.py',
        'rfp_process.py': here / 'rfp_process.py',
    }
    provision_plan = None
    if target['id'] == 'rx671-wifi':
        # This is required for every bootloader-backed scope, including PKCS11
        # and OTA PAL. No application can provision trust before its first boot.
        from rx671_provision import source_inputs, validate_bundle
        runtime = Path(os.environ['IDT_RUNTIME_DIR']).resolve(strict=True)
        files.update(source_inputs(source, runtime, target, manifest.get('source_sha')))
        policy_hashes = {'rx_bootloader_config.h': sha256(files['rx671_bootloader_config.h']),
                         'rx671.h': sha256(files['rx671_target.h'])}
        if manifest.get('bootloader_policy_sha256') != policy_hashes:
            raise RuntimeError('RX671 bootloader policy differs from its effective build inputs')
        provision_plan = validate_bundle(files, target, manifest.get('source_sha'))
    flash_manifest = {
        'schema_version': 1,
        'target_id': target['id'],
        'target_sha256': target_fingerprint(target),
        'build_manifest_sha256': sha256(manifest_path),
        'source_sha': manifest.get('source_sha'),
        'files': {name: {'sha256': sha256(path), 'size_bytes': path.stat().st_size}
                  for name, path in files.items()},
    }
    if provision_plan is not None:
        flash_manifest['rx671_provision_plan'] = provision_plan
        flash_manifest['bootloader_policy_sha256'] = policy_hashes
    return files, flash_manifest


def main():
    token=os.environ.get('IDT_BENCH_TOKEN','')
    if not re.fullmatch('[a-f0-9]{32}',token):raise RuntimeError('No valid bench token')
    if len(sys.argv)!=2:raise RuntimeError('One IDT source path is required')
    target=get_target()
    source=validate_source(sys.argv[1])
    runtime=Path(os.environ['IDT_RUNTIME_DIR']).resolve(strict=True)
    if source.parent not in (runtime,runtime/'source'):
        raise RuntimeError('Flashed images must come from the private IDT runtime')
    files,flash_manifest=validated_inputs(source,target)
    if os.environ.get('IDT_SCOPE','transport') not in {'pkcs11','ota-pal'}:
        params=(source/'Test/include/test_param_config.h').read_text().splitlines(keepends=True)
        prefix='TRANSPORT' if os.environ.get('IDT_SCOPE','transport') == 'transport' else 'MQTT'
        certificate=macro(params,prefix+'_CLIENT_CERTIFICATE')[2]
        key=macro(params,prefix+'_CLIENT_PRIVATE_KEY')[2]
        if not certificate or not certificate.startswith('-----BEGIN CERTIFICATE-----') or not key or 'PRIVATE KEY-----' not in key:
            raise RuntimeError('No IDT-generated TLS credentials')
    remote='/tmp/codex-idt-155-flash-'+token
    alias=target['ssh_alias']
    env={k:v for k,v in os.environ.items() if not k.startswith('AWS_')}
    def run(cmd,**kwargs):return subprocess.run(cmd,env=env,check=True,**kwargs)
    # mkdir fails for an existing run: concurrent callbacks cannot share staging.
    with tempfile.TemporaryDirectory(prefix='flash-manifest-',dir=runtime) as temporary:
        staged_manifest=Path(temporary)/'flash_manifest.json'
        staged_manifest.write_text(json.dumps(flash_manifest,sort_keys=True)+'\n',encoding='utf-8')
        manifest_sha256=sha256(staged_manifest)
        files['flash_manifest.json']=staged_manifest
        run([SSH,'-T','-o','BatchMode=yes',alias,'umask 077; mkdir '+shlex.quote(remote)],timeout=30)
        completed = False
        try:
            for name,path in files.items():
                windows=subprocess.check_output(['wslpath','-w',str(path)],text=True).strip()
                run([SCP,'-q','-o','BatchMode=yes',windows,alias+':'+remote+'/'+name],timeout=60)
            command=shlex.join(['python3',remote+'/rpi_flash.py',token,remote,target['id'],manifest_sha256])
            run([SSH,'-T','-o','BatchMode=yes',alias,command],timeout=flash_remote_seconds(target['id']))
            completed = True
        finally:
            # SSH timeout/interruption does not prove the remote process exited.
            # Keep failed private staging for owned-bench inspection/recovery.
            # Delete only confirmed-complete staging, entirely on Linux.
            cleanup = "\n".join([
                "from pathlib import Path",
                "import shutil",
                "p=Path("+repr(remote)+")",
                "expected='codex-idt-155-flash-' + "+repr(token),
                "if p.parent != Path('/tmp') or p.name != expected or p.is_symlink(): raise RuntimeError('Unsafe staging path')",
                "resolved=p.resolve()",
                "if resolved.parent != Path('/tmp') or resolved.name != expected: raise RuntimeError('Staging path escaped /tmp')",
                "if resolved.exists(): shutil.rmtree(resolved)"])
            if completed:
                run([SSH,'-T','-o','BatchMode=yes',alias,'python3 -c '+shlex.quote(cleanup)],timeout=30)
def run_callback():
    try:
        main()
    except BaseException as error:
        record_flash_failure(os.environ['IDT_RUNTIME_DIR'], error)
        raise


if __name__=='__main__':run_callback()

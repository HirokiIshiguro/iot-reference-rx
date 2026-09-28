#!/usr/bin/env python3
"""Transfer the exact just-built IDT image to the locked RX72N bench."""
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
from prepare_transport_key import validate_source, macro
from flash_failure import record_flash_failure

SSH=os.environ.get('IDT_WINDOWS_SSH','/mnt/c/Windows/System32/OpenSSH/ssh.exe')
SCP=os.environ.get('IDT_WINDOWS_SCP','/mnt/c/Windows/System32/OpenSSH/scp.exe')
def main():
    token=os.environ.get('IDT_BENCH_TOKEN','')
    if not re.fullmatch('[a-f0-9]{32}',token):raise RuntimeError('No valid bench token')
    if len(sys.argv)!=2:raise RuntimeError('One IDT source path is required')
    source=validate_source(sys.argv[1])
    runtime=Path(os.environ['IDT_RUNTIME_DIR']).resolve(strict=True)
    if source.parent not in (runtime,runtime/'source'):
        raise RuntimeError('Flashed images must come from the private IDT runtime')
    out=source/'artifacts/idt/build_transport'
    manifest=json.loads((out/'build_manifest.json').read_text(encoding='utf-8-sig'))
    if hashlib.sha256((out/'rx72n_idt_transport.mot').read_bytes()).hexdigest()!=manifest['outputs']['mot']['sha256']:
        raise RuntimeError('Firmware hash mismatch')
    if hashlib.sha256((source/'Test/include/test_param_config.h').read_bytes()).hexdigest()!=manifest['parameter_config_sha256']:
        raise RuntimeError('Test parameter hash mismatch')
    if os.environ.get('IDT_SCOPE','transport') not in {'pkcs11','ota-pal'}:
        params=(source/'Test/include/test_param_config.h').read_text().splitlines(keepends=True)
        prefix='TRANSPORT' if os.environ.get('IDT_SCOPE','transport') == 'transport' else 'MQTT'
        certificate=macro(params,prefix+'_CLIENT_CERTIFICATE')[2]
        key=macro(params,prefix+'_CLIENT_PRIVATE_KEY')[2]
        if not certificate or not certificate.startswith('-----BEGIN CERTIFICATE-----') or not key or 'PRIVATE KEY-----' not in key:
            raise RuntimeError('No IDT-generated TLS credentials')
    files={'bootloader.mot':source/'Projects/boot_loader_rx72n_envision_kit/e2studio_ccrx/HardwareDebug/boot_loader_rx72n_envision_kit.mot','bootloader_bank1.mot':out/'bootloader_bank1.mot','rx72n_idt_transport.rsu':out/'rx72n_idt_transport.rsu','test_uart_download_rx72n.py':source/'tools/test_uart_download_rx72n.py','rpi_flash.py':Path(__file__).with_name('rpi_flash.py')}
    remote='/tmp/codex-idt-155-flash-'+token
    env={k:v for k,v in os.environ.items() if not k.startswith('AWS_')}
    def run(cmd,**kwargs):return subprocess.run(cmd,env=env,check=True,**kwargs)
    run([SSH,'-T','-o','BatchMode=yes','rpi1','umask 077; mkdir '+shlex.quote(remote)],timeout=30)
    try:
        for name,path in files.items():
            if not path.is_file():raise RuntimeError('Missing input: '+name)
            windows=subprocess.check_output(['wslpath','-w',str(path)],text=True).strip()
            run([SCP,'-q','-o','BatchMode=yes',windows,'rpi1:'+remote+'/'+name],timeout=60)
        run([SSH,'-T','-o','BatchMode=yes','rpi1','python3 '+shlex.quote(remote+'/rpi_flash.py')+' '+shlex.quote(token)+' '+shlex.quote(remote)],timeout=900)
    finally:
        # Delete only this run's private staging directory, entirely on Linux.
        cleanup = "\n".join([
            "from pathlib import Path",
            "import shutil",
            "p=Path("+repr(remote)+")",
            "expected='codex-idt-155-flash-' + "+repr(token),
            "if p.parent != Path('/tmp') or p.name != expected or p.is_symlink(): raise RuntimeError('Unsafe staging path')",
            "resolved=p.resolve()",
            "if resolved.parent != Path('/tmp') or resolved.name != expected: raise RuntimeError('Staging path escaped /tmp')",
            "if resolved.exists(): shutil.rmtree(resolved)"])
        run([SSH,'-T','-o','BatchMode=yes','rpi1','python3 -c '+shlex.quote(cleanup)],timeout=30)
def run_callback():
    try:
        main()
    except BaseException as error:
        record_flash_failure(os.environ['IDT_RUNTIME_DIR'], error)
        raise


if __name__=='__main__':run_callback()

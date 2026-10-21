"""One RX671 historical-code control with a current signed normal restoration.

LOCALUNREADY. No command is enabled until the concrete input/transaction review.
Firmware remains inside ordinary CI artifact staging. UART is projected in RAM.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import signal
import stat
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools import install_normal_boot as normal, normal_boot
from tools import build_rx671_fwup_v2_rsu as srec, shift_srec_addresses as shift
from tools.idt import cleanup_budget as budget, public_signer_provision as trust, rfp_process
from tools.idt.targets import get_target

OLD = '666d97f64eecc2451ec3b54ee101b5b53a603c51'
BASE = '5d4b4a62e6e1def5e9bcedd26ff5502fb32caf0a'
PROFILE = 'rx671-known-good-control-v1'
CF = (0xFFE00000, 0xFFFFFFFF)
EXECUTION_REVIEWED = True
CAPTURE_SECONDS = 300
TRANSACTION_SECONDS = (budget.FLASH_LOCK_WAIT_SECONDS + 6*budget.FLASH_RFP_COMMAND_SECONDS +
                       CAPTURE_SECONDS + budget.FLASH_DOWNLOAD_SECONDS +
                       budget.FLASH_ABORT_RESET_SECONDS + budget.END_STATE_QUIET_SECONDS)


def digest(path):
    return hashlib.sha256(trust._bytes(Path(path))).hexdigest()


def document(path, expected):
    data = trust._bytes(Path(path))
    if len(data) > 512*1024 or not re.fullmatch('[0-9a-f]{64}', expected) or hashlib.sha256(data).hexdigest() != expected:
        raise RuntimeError('Reviewed public manifest hash mismatch')
    return json.loads(data)


def decode_image(path, require_reset=True):
    data = trust._bytes(Path(path))
    if len(data) > 8*1024*1024:
        raise RuntimeError('Historical MOT exceeds bounded input size')
    memory = {}
    for number, line in enumerate(data.decode('ascii').splitlines(), 1):
        if not line.strip():
            continue
        kind, address, payload = srec._decode_srecord(line.strip(), number)
        if kind not in {'S1', 'S2', 'S3'}:
            continue
        if not payload or not any(a <= address <= address+len(payload)-1 <= b for a,b in (CF, *trust.OPTIONS)):
            raise RuntimeError('Historical MOT data is outside CF/options')
        for offset, value in enumerate(payload):
            position = address+offset
            if position in memory and memory[position] != value:
                raise RuntimeError('Conflicting historical S-record bytes')
            memory[position] = value
    if not memory:
        raise RuntimeError('Empty firmware image')
    if not require_reset:
        return memory
    if any(p not in memory for p in range(0xFFFFFFFC, 0x100000000)):
        raise RuntimeError('Historical reset vector is absent')
    reset = int.from_bytes(bytes(memory[p] for p in range(0xFFFFFFFC, 0x100000000)), 'little')
    if not CF[0] <= reset <= CF[1] or reset not in memory:
        raise RuntimeError('Historical reset vector is outside its code')
    return memory


def cf_view(original, output, require_reset=True):
    memory = decode_image(original, require_reset)
    lines = []
    for line in trust._bytes(Path(original)).decode('ascii').splitlines():
        if line.strip():
            transformed = shift.rewrite_record(line.strip(), 0, *CF, True)
            if transformed is not None:
                lines.append(transformed)
    with Path(output).open('x', encoding='ascii') as stream:
        stream.write('\n'.join(lines)+'\n')
    view = decode_image(output, require_reset)
    expected = {p:v for p,v in memory.items() if CF[0] <= p <= CF[1]}
    if view != expected or not view:
        raise RuntimeError('Derived CF view differs from original CF bytes')
    return hashlib.sha256(Path(output).read_bytes()).hexdigest()


def validate_inputs(args, target):
    if not re.fullmatch('[0-9a-f]{40}', args.restore_source) or args.runtime_source != OLD:
        raise RuntimeError('Fixed source binding mismatch')
    if (os.environ.get('CI_COMMIT_SHA') != args.restore_source or
            os.environ.get('CI_PIPELINE_ID') != str(args.pipeline_id) or
            os.environ.get('CI_JOB_ID') != str(args.job_id)):
        raise RuntimeError('Live consumer CI identity differs from reviewed binding')
    old = document(args.old_root/'control_manifest.json', args.old_manifest_sha256)
    restore = document(args.restore_bundle/'restore_producer_manifest.json', args.restore_producer_sha256)
    if (old.get('profile') != 'rx671-known-good-control-input-v1' or old.get('schema_version') != 1 or
            old.get('product_source_sha') != OLD or old.get('delivery_source_sha') != args.restore_source or
            old.get('pipeline_id') != args.pipeline_id or old.get('producer_job_id') != args.old_job_id or
            old.get('target_id') != target['id'] or old.get('artifact_file') != 'aws_wifi_rx671_ek.mot' or
            old.get('embedded_credentials') is not True or old.get('build_mode') != 'normal-mqtt' or
            old.get('e2studio_timeout_seconds') != 180):
        raise RuntimeError('Historical producer identity/profile mismatch')
    flags = {'ota_runtime':False,'ota_provisioner':False,'fleet':False,'wifi_kvs':False,
             'throughput':False,'tsip_entropy':False}
    if old.get('profile_flags') != flags or not isinstance(old.get('submodule_pins'), dict) or len(old['submodule_pins']) != 31:
        raise RuntimeError('Historical coherent normal profile is absent')
    if (restore.get('schema_version') != 1 or restore.get('profile') != 'rx671-known-good-restore-input-v1' or
            restore.get('delivery_source_sha') != args.restore_source or restore.get('product_base_source_sha') != BASE or
            restore.get('pipeline_id') != args.pipeline_id or restore.get('producer_job_id') != args.restore_job_id or
            restore.get('normal_manifest_sha256') != args.normal_manifest_sha256):
        raise RuntimeError('Current restore producer identity mismatch')
    manifest = document(args.restore_bundle/'normal_install_manifest.json', args.normal_manifest_sha256)
    if normal_boot.validate(args.restore_bundle, target, args.restore_source) != manifest:
        raise RuntimeError('Normal restore bundle did not validate')
    old_mot = args.old_root/'aws_wifi_rx671_ek.mot'
    if digest(old_mot) != old.get('artifact_sha256'):
        raise RuntimeError('Historical firmware hash mismatch')
    decode_image(old_mot)
    return old_mot, manifest


class Projection:
    """Only full matched constants/numeric tokens survive a received line."""
    def __init__(self):
        self.pending=bytearray();self.bytes_seen=0;self.lines_seen=0;self.overflow=False;self.discard_line=False
        self.network_ready=False;self.tls=None;self.mqtt=None;self.boot_observed=False
        self.join_ok=False;self.bringup_done=False;self.tcp_up=False;self.failure_seen=False;self.order_valid=True
        self.application_observed=False
    def feed(self, chunk):
        self.bytes_seen += len(chunk)
        if self.bytes_seen > 4*1024*1024:
            self.overflow=True;return
        for value in chunk:
            if value == 10:
                line=bytes(self.pending).rstrip(b'\r');self.pending.clear();self.lines_seen+=1
                if self.discard_line:self.discard_line=False;continue
                if line == b'=== aws_wifi_rx671_ek boot ===':self.boot_observed=True
                if line == b'WHD bring-up done':self.bringup_done=True;self.application_observed=True
                if line == b'FreeRTOS+TCP network up':self.tcp_up=True;self.application_observed=True
                join=re.fullmatch(br'whd_wifi_join=([0-9A-Fa-f]{8})',line)
                if join:
                    self.application_observed=True
                    if join[1]==b'00000000':self.join_ok=True
                    else:self.failure_seen=True
                if line == b'AWS MQTT smoke: network ready':self.network_ready=True;self.application_observed=True
                found=re.fullmatch(br'AWS (TLS|MQTT)=(0|[1-9][0-9]{0,9}|-[0-9A-Fa-f]{8})',line)
                if found:
                    token=found[2].decode('ascii')
                    if token[0]!='-' and int(token)>0x7fffffff:continue
                    if token[0]=='-' and not 1 <= int(token[1:],16) <= 0x80000000:continue
                    name='tls' if found[1]==b'TLS' else 'mqtt'
                    if getattr(self,name) is not None or not self.network_ready or (name=='mqtt' and self.tls!='0'):
                        self.order_valid=False
                    else:setattr(self,name,token)
                    if token!='0':self.failure_seen=True
                    self.application_observed=True
            elif self.discard_line:continue
            elif len(self.pending)<640:self.pending.append(value)
            else:self.overflow=True;self.pending.clear();self.discard_line=True
    def result(self):
        success=(not self.overflow and not self.failure_seen and self.order_valid and self.join_ok and
                 self.bringup_done and self.tcp_up and self.network_ready and self.tls=='0' and self.mqtt=='0')
        return {'boot_observed':self.boot_observed,'network_ready':self.network_ready,
                'historical_network_gates':{'whd_join_zero':self.join_ok,'whd_bringup_done':self.bringup_done,'tcp_up':self.tcp_up},
                'tls_status_token':self.tls,'mqtt_status_token':self.mqtt,
                'bounded_capture_integrity':not self.overflow,'status_order_valid':self.order_valid,
                'nonzero_status_seen':self.failure_seen,'bytes_seen':self.bytes_seen,
                'control_result':'PASS_TLS_MQTT_PUBLISH' if success else
                    ('INCONCLUSIVE_BOOT_NOT_OBSERVED' if not self.boot_observed and not self.application_observed else 'FAIL_OR_NOT_COMPLETED')}


def capture(target, call, check_owner):
    import serial
    projection=Projection();stop=threading.Event();errors=[]
    with serial.Serial(target['uart'],target['baud'],timeout=0.1,exclusive=True) as port:
        port.reset_input_buffer()
        def receive():
            try:
                while not stop.is_set():projection.feed(port.read(4096))
            except BaseException as error:errors.append(type(error).__name__)
        thread=threading.Thread(target=receive,daemon=True);thread.start()
        try:
            trust._checked_call(call,check_owner,[*normal.rfp_command(target),'-sig','-run','-noquery'],budget.FLASH_RFP_COMMAND_SECONDS)
            end=time.monotonic()+CAPTURE_SECONDS
            while time.monotonic()<end:
                check_owner()
                if errors or projection.overflow or projection.mqtt is not None or (projection.tls is not None and projection.tls!='0'):break
                time.sleep(0.1)
        finally:
            stop.set();thread.join(timeout=1)
            if thread.is_alive():raise RuntimeError('UART capture thread did not stop')
    if errors:raise RuntimeError('Bounded UART capture failed')
    return projection.result()


def transaction(args,target,cf_path,manifest,receipt):
    import fcntl
    owner=None;owned=False;touched=False
    check=lambda:normal.check_bench_lease(target,owner=owner)
    normal.check_ci_identity(target);check();normal.check_devices(target)
    lock=Path(target['rfp_lock'])
    if any(p.is_symlink() for p in (lock,*lock.parents)):raise RuntimeError('Linked global programmer lock')
    try:
        lock.parent.mkdir(mode=0o1777,parents=True);os.chmod(lock.parent,0o1777)
    except FileExistsError:pass
    try:
        fd=os.open(lock,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o666);os.fchmod(fd,0o666)
    except FileExistsError:fd=os.open(lock,os.O_RDWR|os.O_NOFOLLOW)
    if not stat.S_ISREG(os.fstat(fd).st_mode):os.close(fd);raise RuntimeError('Nonregular global programmer lock')
    deadline=time.monotonic()+TRANSACTION_SECONDS
    def call(command,timeout=budget.FLASH_RFP_COMMAND_SECONDS,*,abort=False):
        check();remaining=budget.FLASH_ABORT_RESET_SECONDS if abort else deadline-time.monotonic()
        if remaining<=0:raise RuntimeError('Reviewed transaction deadline exhausted')
        result=rfp_process.run_guarded(command,target=target,timeout=min(timeout,remaining),quiet=True)
        check();return result
    def checked(command,timeout=budget.FLASH_RFP_COMMAND_SECONDS):
        return trust._checked_call(call,check,command,timeout)
    def erase_cf():checked([*normal.rfp_command(target),'-range','FFE00000,FFFFFFFF','-erase','-noquery'])
    def program(path):checked([*normal.rfp_command(target),'-p','-v','-noquery',str(path)])
    try:
        lock_end=time.monotonic()+budget.FLASH_LOCK_WAIT_SECONDS
        while True:
            check()
            try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);break
            except BlockingIOError:
                if time.monotonic()>=lock_end:raise RuntimeError('Global programmer lock timeout')
                time.sleep(0.1)
        check()
        owner={'profile':PROFILE,'pid':os.getpid(),'token':secrets.token_hex(16),'target_id':target['id'],
               'source_sha':args.restore_source,'runtime_source_sha':OLD,'pipeline_id':args.pipeline_id,'job_id':args.job_id}
        owner_fd=os.open(target['owner_file'],os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        owned=True
        with os.fdopen(owner_fd,'w',encoding='utf-8') as stream:
            json.dump(owner,stream);stream.flush();os.fsync(stream.fileno())
        check()
        try:
            touched=True;receipt['stage']='historical_cf_erase'
            erase_cf();receipt['stage']='historical_cf_program';program(cf_path)
            receipt['stage']='historical_capture';receipt['observation']=capture(target,call,check)
        finally:
            if touched:
                # An unsafe sentinel stops all commands; ownership remains retained.
                check();receipt['stage']='restore_validation'
                if normal_boot.validate(args.restore_bundle,target,args.restore_source)!=manifest:
                    raise RuntimeError('Restore bundle changed during control')
                receipt['stage']='restore_cf_erase';erase_cf()
                receipt['stage']='restore_boot0';program(cf_path.parent/'restore-boot0-cf-only.mot')
                receipt['stage']='restore_boot1';program(cf_path.parent/'restore-boot1-cf-only.mot')
                receipt['stage']='restore_signed_download'
                checked(normal.download_command(args.restore_bundle,target),budget.FLASH_DOWNLOAD_SECONDS)
                receipt['signed_normal_restore_and_handoff']=True
                receipt['stage']='reset_and_quiet'
                receipt['end_state']=normal.reset_and_quiet(target,call,check)
                check();Path(target['owner_file']).unlink();owned=False
                receipt['owner_finished']=True;receipt['stage']='closed'
    except BaseException:
        # A failed restoration gets one canonical bounded abort reset. A failed
        # quiet/reset attempt is retained for a later exact-owner continuation,
        # never silently reset a second time here. Unsafe/lost ownership blocks
        # this abort through the unchanged current guard.
        if owned and touched and receipt.get('stage') not in {'reset_and_quiet','closed'}:
            try:
                receipt['abort_end_state']=normal.reset_and_quiet(target,
                    lambda command,timeout:call(command,timeout,abort=True),check)
            except BaseException as error:
                receipt['abort_error_class']=type(error).__name__
        raise
    finally:
        receipt['owner_retained']=owned
        os.close(fd)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('old-root','restore-bundle','receipt'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--runtime-source',required=True)
    parser.add_argument('--restore-source',required=True)
    for name in ('pipeline-id','job-id','old-job-id','restore-job-id'):
        parser.add_argument('--'+name,type=int,required=True)
    for name in ('old-manifest-sha256','restore-producer-sha256','normal-manifest-sha256'):
        parser.add_argument('--'+name,required=True)
    parser.add_argument('--execute-reviewed-candidate',action='store_true')
    args=parser.parse_args(argv)
    if min(args.pipeline_id,args.job_id,args.old_job_id,args.restore_job_id)<=0:raise RuntimeError('Invalid positive CI identity')
    target=get_target('rx671-wifi');old_mot,manifest=validate_inputs(args,target)
    if not args.execute_reviewed_candidate or not EXECUTION_REVIEWED:
        raise RuntimeError('LOCALUNREADY: transaction review has not enabled hardware')
    if not sys.platform.startswith('linux'):raise RuntimeError('Reviewed Linux bench is required')
    if args.receipt.exists():raise RuntimeError('One-use receipt already exists')
    args.receipt.parent.mkdir(parents=True,exist_ok=True)
    receipt={'schema_version':1,'profile':PROFILE,'runtime_source_sha':OLD,'restore_source_sha':args.restore_source,
             'pipeline_id':args.pipeline_id,'job_id':args.job_id,'stage':'validated',
             'signed_normal_restore_and_handoff':False,'owner_finished':False,
             'data_flash_or_options_write_requested':False,'historical_full_option_envelope_reproduced':False,
             'success_scope':'Historical normal MQTT six markers; device-side QoS0 Publish API success, not cloud receipt',
             'retained_dual_boot_compatibility':'bounded_hardware_observation_required'}
    def interrupted(*_):raise KeyboardInterrupt
    signal.signal(signal.SIGTERM,interrupted)
    try:
        with tempfile.TemporaryDirectory(prefix='rx671-kg-cf-') as temporary:
            cf=Path(temporary)/'historical-cf-only.mot';receipt['cf_view_sha256']=cf_view(old_mot,cf)
            receipt['restore_boot_cf_view_sha256']={
                'bank0':cf_view(args.restore_bundle/'bootloader.mot',cf.parent/'restore-boot0-cf-only.mot'),
                'bank1':cf_view(args.restore_bundle/'bootloader_bank1.mot',cf.parent/'restore-boot1-cf-only.mot',False)}
            transaction(args,target,cf,manifest,receipt)
    except BaseException as error:
        receipt['error_class']=type(error).__name__
    finally:
        with args.receipt.open('x',encoding='utf-8') as stream:json.dump(receipt,stream,sort_keys=True,indent=2);stream.write('\n')
    print(json.dumps({'stage':receipt['stage'],'owner_finished':receipt['owner_finished'],
                      'signed_normal_restore_and_handoff':receipt['signed_normal_restore_and_handoff'],
                      'control_result':receipt.get('observation',{}).get('control_result','NOT_OBSERVED')}))
    return 0 if receipt['owner_finished'] and receipt.get('observation',{}).get('control_result')=='PASS_TLS_MQTT_PUBLISH' else 1

if __name__=='__main__':raise SystemExit(main())

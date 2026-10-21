"""Prepare-only by default. Fixed CI-owner metadata audit; never print private text."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

STAGING = Path('C:/ai/codex/tmp/kg-rx671-11721-72613')
FAILED_SOURCE = '0bd79dd49faccdc1b8a7f2b047405da89fe6f4b9'
# LF-canonical SHA256 of Git666d:tools/build_headless_rx671_wifi.ps1.
# Pin verified during preparation from public Git; no runtime Git fallback.
HELPER_SHA = 'be65f1f266451b6fc64eb67e5306b525ae4647fb8016e598832413cefba3bdf2'
PINS_SHA = 'c6a2265cf8a51960b8700f88be3f3a3ec2283a6ef27dac314b76867140012657'
TREE = 'e06c6a7f644186e2cc85986d376c36924f1eebe2'
CPROJECT = 'c591238a57d5f11fe49efdc5750a045a0f19985b65b75048f2858373b5528ca0'
APP = 'old/Projects/aws_wifi_rx671_ek/e2studio_ccrx/HardwareDebug/aws_wifi_rx671_ek.mot'
FIXED = {'old':'old','prebuild_proof':'public-prebuild-proof.json','build_log':'build-private.log',
         'console_log':'console-private.log','control_manifest':'control_manifest.json','application_mot':APP,
         'historical_public_helper':'old/tools/build_headless_rx671_wifi.ps1'}
STAGES = {'patch_already_applied':'WHD patch is already applied.', 'patch_applying':'Applying WHD patch...',
          'blob_staging':'Staging Type 1YN WHD blobs...', 'import_build_banner':'=== RX671 Wi-Fi import + build ===',
          'local_join_generated':'Generated ignored local JOIN header', 'local_aws_generated':'Generated ignored local AWS IoT header',
          'build_finished':'RX671 Wi-Fi build completed successfully.'}
# Whole diagnostic lines only; retain a bounded code/count, never message/path.
DIAGNOSTIC = re.compile(r'^(?:(?:"[^"\r\n]{1,2048}"|[^\r\n]{1,2048})\([0-9]+(?:,[0-9]+)?\)\s*:\s*)?([CFEWL][0-9]{4,7}):[^\r\n]*$')

class ClosedStop(Exception):
    pass

def stop(code):
    raise ClosedStop(code)

def checked(path):
    for item in (path,*path.parents):
        info = item.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0) & 0x400:
            stop('REPARSE_POINT_REJECTED')
    return path.stat()

def metadata(path,directory=False):
    try:
        info = checked(path)
        if not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)):
            stop('UNEXPECTED_FILE_TYPE')
        return {'present':True,'bytes':None if directory else info.st_size}
    except FileNotFoundError:
        return {'present':False,'bytes':None}

def bounded(path,limit):
    info = checked(path)
    if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
        stop('FILE_SIZE_BOUND_EXCEEDED')
    with path.open('rb') as stream:
        data = stream.read(limit+1)
    if len(data)>limit:
        stop('FILE_SIZE_BOUND_EXCEEDED')
    return data

def text(data):
    try:
        return data.decode('utf-16' if data.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8-sig')
    except UnicodeError:
        stop('TEXT_ENCODING_REJECTED')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true')
    if not parser.parse_args().execute:
        print(json.dumps({'LOCALUNREADY':True,'staging_reads':0,'API_native_HIL_actions':0})); return 0
    if (sys.platform!='win32' or os.environ.get('CI_PROJECT_ID')!='38' or
        os.environ.get('CI_PIPELINE_SOURCE')!='api' or os.environ.get('RUN_RX671_FAILED_BUILD_DIAGNOSTIC')!='true'):
        print(json.dumps({'status':'CONTEXT_REJECTED','staging_reads':0})); return 2
    source = os.environ.get('CI_COMMIT_SHA','')
    if not re.fullmatch('[a-f0-9]{40}',source) or not os.environ.get('CI_PROJECT_DIR'):
        print(json.dumps({'status':'CI_SOURCE_OR_PROJECT_REJECTED','staging_reads':0})); return 2
    project = Path(os.environ['CI_PROJECT_DIR']).absolute()
    result = {'schema_version':1,'profile':'rx671-failed72613-metadata-only-v1','failed_pipeline_id':11721,
              'failed_job_id':72613,'failed_source_sha':FAILED_SOURCE,'diagnostic_source_sha':source,
              'status':'METADATA_ONLY_COMPLETE','file_metadata':{},'stage_presence':{k:False for k in STAGES},
              'build_failed_presence':False,'historical_helper_verified':False,'public_throw_source_lines':[],
              'public_write_host_source_lines':[],'prebuild_proof_present':False,'prebuild_pin_tree_cproject_claims_match':False,
              'compiler_diagnostic_codes':{},'line_bound_exceeded':False,'raw_or_log_hash_saved':False,
              'boundary':'Presence and public diagnostic candidates only; no root-cause, build, firmware, or hardware success claim'}
    try:
        checked(project)
        live = subprocess.run(['git','-C',str(project),'rev-parse','HEAD'],capture_output=True)
        if live.returncode or live.stdout.decode().strip()!=source: stop('LIVE_CHECKOUT_SOURCE_MISMATCH')
        if not metadata(STAGING,True)['present']: stop('STAGING_MISSING')
        for label,relative in FIXED.items(): result['file_metadata'][label] = metadata(STAGING/relative,label=='old')
        prefixes = {'throw':{},'Write-Host':{}}
        if result['file_metadata']['historical_public_helper']['present']:
            raw = bounded(STAGING/FIXED['historical_public_helper'],512*1024).replace(b'\r\n',b'\n')
            if hashlib.sha256(raw).hexdigest()!=HELPER_SHA: stop('HISTORICAL_PUBLIC_HELPER_IDENTITY_MISMATCH')
            result['historical_helper_verified'] = True
            for number,line in enumerate(text(raw).splitlines(),1):
                match = re.search(r'\b(throw|Write-Host)\s+\(?\s*"([^"\r\n]+)',line)
                if match:
                    prefix = re.split(r'[$`]',match[2],maxsplit=1)[0]
                    if len(prefix)>=12: prefixes[match[1]][number] = prefix
        if result['file_metadata']['prebuild_proof']['present']:
            result['prebuild_proof_present'] = True
            proof = json.loads(bounded(STAGING/FIXED['prebuild_proof'],512*1024)); pins = proof.get('submodule_pins',{})
            pin_hash = hashlib.sha256(json.dumps(pins,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()).hexdigest()
            result['prebuild_pin_tree_cproject_claims_match'] = (isinstance(pins,dict) and len(pins)==31 and pin_hash==PINS_SHA and
                proof.get('product_project_git_tree_oid')==TREE and proof.get('cproject_sha256')==CPROJECT)
        matched = {'throw':set(),'Write-Host':set()}
        for label in ('build_log','console_log'):
            if not result['file_metadata'][label]['present']: continue
            for line in text(bounded(STAGING/FIXED[label],4*1024*1024)).splitlines():
                if len(line.encode('utf-8'))>4096: result['line_bound_exceeded']=True; continue
                line = re.sub(r'\x1b\[[0-9;]*[A-Za-z]','',line).strip()
                for name,prefix in STAGES.items():
                    if line.startswith(prefix): result['stage_presence'][name]=True
                if line.startswith(('make: ***','make.exe: ***','BUILD FAILED','Build Failed')): result['build_failed_presence']=True
                match = DIAGNOSTIC.fullmatch(line)
                if match and len(result['compiler_diagnostic_codes'])<64:
                    code=match[1]; result['compiler_diagnostic_codes'][code]=result['compiler_diagnostic_codes'].get(code,0)+1
                for kind,items in prefixes.items():
                    matched[kind].update(number for number,prefix in items.items() if prefix in line)
        result['public_throw_source_lines']=sorted(matched['throw'])
        result['public_write_host_source_lines']=sorted(matched['Write-Host'])
    except PermissionError: result['status']='PERMISSION_DENIED_STOP'
    except FileNotFoundError: result['status']='STAGING_COMPONENT_MISSING_STOP'
    except ClosedStop as error: result['status']=str(error)
    except (UnicodeError,json.JSONDecodeError): result['status']='BOUNDED_TEXT_OR_JSON_REJECTED'
    except Exception: result['status']='AUDIT_REJECTED_CLOSED'
    try:
        checked(project)
        output = project/'artifacts/kg_failed72613_diagnostic'
        for parent in (project/'artifacts',output):
            parent.mkdir(exist_ok=True); checked(parent)
        with (output/'public_result.json').open('x',encoding='utf-8') as stream:
            json.dump(result,stream,sort_keys=True,indent=2); stream.write('\n')
    except Exception:
        print(json.dumps({'status':'OUTPUT_UNAVAILABLE_OR_ALREADY_CONSUMED','raw_saved_or_printed':False})); return 3
    print(json.dumps({'status':result['status'],'raw_saved_or_printed':False}))
    return 0 if result['status']=='METADATA_ONLY_COMPLETE' else 2

if __name__=='__main__': raise SystemExit(main())

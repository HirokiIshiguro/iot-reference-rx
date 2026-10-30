"""Incident-only normal dependency diagnostic; no SDK, AWS, WSL or device access."""
from __future__ import annotations
import argparse,hashlib,json,os,re,shutil,stat,subprocess
from pathlib import Path

SOURCE='83489f135c0382ef7879612b5cde03844f2d399c'
CALLER='77805a37506378922c472d6e108516db98d846ed4387883bf31237fd82bf744d'
ADAPTER='0f6dd989673cc7ce770f5760f63f01ac3b0c55fb1ae237de06f2d8f763972ca0'
ADAPTER_CODES=frozenset('SOURCE_BOM SOURCE_LONE_CR LINKED_SOURCE OWNED_CHILD_START OWNED_CHILD_STOP_UNKNOWN OWNED_CHILD_TIME_BUDGET OWNED_CHILD_OUTPUT_BOUND POWERSHELL7_REQUIRED CI_IDENTITY CI_SELECTOR NORMAL_CLONE_REQUIRED CI_CHECKOUT_ROOT ORIGINAL_SOURCE_HASH ROOT_TOPLEVEL_MISMATCH ROOT_DEPENDENCY_METADATA DEPENDENCY_PATH_SCHEMA DEPENDENCY_COUNT INITIALIZER_COMPLETED NESTED_INITIALIZATION_FAILED INITIALIZER_UNCLASSIFIED_FAILURE CI_SOURCE_HEAD SOURCE_DIFF_UNAVAILABLE UNREVIEWED_SOURCE_DELTA TRACKED_SOURCE_DIRTY GITLINK_METADATA ORIGINAL_GITLINKS_CHANGED ROOT_DEPENDENCY_NOT_INITIALIZED DEPENDENCY_METADATA_FAILED ROOT_PIN_MISMATCH INITIALIZER_NOT_EXERCISED INITIALIZER_LAUNCHER_HOLD INITIALIZER_RESULT_SCHEMA DEPENDENCY_DIAGNOSTIC_OBSERVED DEPENDENCY_DIAGNOSTIC_HOLD'.split())
REQUEST={'kind':'NORMAL_DEPENDENCY_INITIALIZER_DIAGNOSTIC','project_id':38,'prior_pipeline_id':11896,
         'prior_job_id':73293,'original_source':SOURCE,'caller_sha256':CALLER,'initialize_once':True}
class Hold(RuntimeError):pass
def need(value,code):
    if not value:raise Hold(code)
def strict(raw):
    def pairs(items):
        out={}
        for key,value in items:need(key not in out,'DUPLICATE_KEY');out[key]=value
        return out
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:need(False,'NONFINITE_JSON'))
def admit(request,environ,caller_hash):
    need(type(request)is dict and set(request)==set(REQUEST),'REQUEST_SCHEMA')
    need(all(type(request[k])is type(v)and request[k]==v for k,v in REQUEST.items()),'REQUEST_BINDING')
    need(caller_hash==CALLER,'CALLER_HASH')
    need(environ.get('CI_PROJECT_ID')=='38'and environ.get('CI_PIPELINE_SOURCE')=='api'and environ.get('GITLAB_USER_ID')=='38','CI_IDENTITY')
    need(environ.get('CI_JOB_NAME')=='test_rx65n_bg96_idt'and environ.get('IDT_TARGET')=='rx65n-bg96'and environ.get('IDT_SCOPE')=='transport','CI_SELECTOR')
    need(environ.get('GIT_SUBMODULE_STRATEGY')=='normal'and environ.get('GIT_STRATEGY')=='clone','NORMAL_CLONE_REQUIRED')
    need(all(re.fullmatch('[1-9][0-9]{0,11}',environ.get(k,''))for k in('CI_PIPELINE_ID','CI_JOB_ID')),'CI_IDS')
    need(environ.get('CI_PIPELINE_ID')!='11896'and environ.get('CI_JOB_ID')!='73293','NEW_DIAGNOSTIC_REQUIRED')
    need(re.fullmatch('[0-9a-f]{40}',environ.get('CI_COMMIT_SHA',''))is not None,'CURRENT_SOURCE')
def unlinked(path):
    for value in(path,*path.parents):
        info=value.lstat()
        need(not stat.S_ISLNK(info.st_mode)and not(getattr(info,'st_file_attributes',0)&0x400),'LINKED_SOURCE')
def project(value):
    need(type(value)is dict,'ADAPTER_SCHEMA')
    allowed={'schema_version','result','reasonCode','initializer_invoked','initializer_succeeded','raw_git_output_saved','hardware_actions','sdk_aws_actions','dependencies','expected_nested_update_attempts','initializer','metadata_failed_dependency_id'}
    need(not(set(value)-allowed),'ADAPTER_KEYS')
    need(type(value.get('schema_version'))is int and value['schema_version']==1 and value.get('raw_git_output_saved')is False and all(type(value.get(k))is int and value[k]==0 for k in('hardware_actions','sdk_aws_actions')),'ADAPTER_INVARIANTS')
    need(value.get('result')in('HOLD','DEPENDENCY_DIAGNOSTIC_OBSERVED')and value.get('reasonCode')in ADAPTER_CODES,'ADAPTER_RESULT')
    need(all(type(value.get(k))is bool for k in('initializer_invoked','initializer_succeeded')),'ADAPTER_FLAGS')
    rows=value.get('dependencies',[])
    need(type(rows)is list and len(rows)<=41,'DEPENDENCY_ROWS')
    if 'metadata_failed_dependency_id'in value:need(type(value['metadata_failed_dependency_id'])is str and re.fullmatch('DEP_(?:0[1-9]|[1-3][0-9]|4[01])',value['metadata_failed_dependency_id'])is not None,'METADATA_DEPENDENCY_ID')
    seen=set()
    for row in rows:
        need(type(row)is dict and set(row)=={'dependency_id','initialized','head_matches_source_pin','dirty','shallow','nested_descriptor_present','source_only_excluded'},'DEPENDENCY_SCHEMA')
        dep=row['dependency_id'];need(type(dep)is str and re.fullmatch('DEP_(?:0[1-9]|[1-3][0-9]|4[01])',dep)is not None and dep not in seen,'DEPENDENCY_ID');seen.add(dep)
        need(all(type(v)is bool for k,v in row.items()if k!='dependency_id'),'DEPENDENCY_FLAGS')
    if 'expected_nested_update_attempts'in value:need(type(value['expected_nested_update_attempts'])is int and 0<=value['expected_nested_update_attempts']<=41,'UPDATE_COUNT')
    if 'initializer'in value:
        inner=value['initializer']
        need(type(inner)is dict and not(set(inner)-{'schema_version','result','reasonCode','initializer_invoked','initializer_succeeded','raw_git_output_saved','hardware_actions','sdk_aws_actions','git_exit_code','failed_dependency_id'}),'INNER_SCHEMA')
        need(inner.get('result')in('HOLD','INITIALIZER_COMPLETED')and inner.get('reasonCode')in ADAPTER_CODES,'INNER_RESULT')
        need(type(inner.get('schema_version'))is int and inner['schema_version']==1 and inner.get('initializer_invoked')is True and type(inner.get('initializer_succeeded'))is bool and inner.get('raw_git_output_saved')is False and all(type(inner.get(k))is int and inner[k]==0 for k in('hardware_actions','sdk_aws_actions')),'INNER_FLAGS')
        if 'failed_dependency_id'in inner:need(inner['failed_dependency_id']in seen,'FAILED_DEPENDENCY_ID')
        code=inner.get('git_exit_code');need(code is None or(type(code)is int and -2147483648<=code<=4294967295),'EXIT_CODE')
    if value['result']=='DEPENDENCY_DIAGNOSTIC_OBSERVED':
        need(len(rows)==41 and value.get('expected_nested_update_attempts',0)>0 and value.get('initializer_invoked')is True and 'initializer'in value,'NO_SKIPPED_ALL_SUCCESS')
    return value
def run_requested(caller):
    output={'schema_version':1,'diagnostic_only':True,'native_tests_run':False,'qualification':False,
            'result':'HOLD','reasonCode':'DEPENDENCY_DIAGNOSTIC_HOLD','functional_PASS_claimed':False,
            'RPi_actions':0,'SDK_executions':0,'AWS_operations':0,'WSL_executions':0,
            'private_runtime_reads':0,'raw_git_output_saved':False,'prior_run_host_stopped':'UNKNOWN'}
    destination=None
    try:
        raw=os.environ.get('RX_IDT_PRIOR_RUN_DIAGNOSTIC','');need(len(raw)<=4096,'REQUEST_BOUND')
        caller=Path(caller).resolve();body=caller.read_bytes().replace(b'\r\n',b'\n')
        need(b'\r'not in body and not body.startswith(b'\xef\xbb\xbf'),'CALLER_ENCODING');body.decode('utf-8','strict')
        admit(strict(raw),os.environ,hashlib.sha256(body).hexdigest());need(os.name=='nt','WINDOWS_CI_REQUIRED')
        parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path);args=parser.parse_args()
        source=caller.parents[2];desired=source/'artifacts/idt'
        need(Path(os.environ.get('CI_PROJECT_DIR','')).resolve()==source and args.output.resolve()==desired,'PUBLIC_OUTPUT_SCOPE')
        unlinked(source)
        for path in(source/'artifacts',desired):
            if not path.exists():path.mkdir()
            unlinked(path)
        need(not(desired/'prior-run-diagnostic.json').exists(),'ALREADY_WRITTEN')
        destination=desired/'prior-run-diagnostic.json'
        # Exclusive marker prevents executing twice within this disposable CI job.
        with(desired/'normal-dependency-once.json').open('x',encoding='utf-8')as stream:json.dump({'kind':REQUEST['kind'],'original_source':SOURCE},stream)
        adapter=caller.with_name('normal_dependency_diagnostic.ps1');unlinked(adapter)
        adapter_bytes=adapter.read_bytes().replace(b'\r\n',b'\n')
        need(b'\r'not in adapter_bytes and not adapter_bytes.startswith(b'\xef\xbb\xbf'),'ADAPTER_ENCODING')
        adapter_bytes.decode('utf-8','strict');need(hashlib.sha256(adapter_bytes).hexdigest()==ADAPTER,'ADAPTER_HASH')
        pwsh=shutil.which('pwsh.exe')or shutil.which('pwsh');need(pwsh is not None,'POWERSHELL7_REQUIRED')
        completed=subprocess.run([pwsh,'-NoProfile','-NonInteractive','-File',str(adapter),'-ProjectRoot',str(source)],capture_output=True)
        need(completed.returncode==0 and len(completed.stdout)<=131072 and not completed.stderr.strip(),'ADAPTER_HOLD')
        value=project(strict(completed.stdout));output['dependency_diagnostic']=value
        if value['result']=='DEPENDENCY_DIAGNOSTIC_OBSERVED':output.update(result='DIAGNOSTIC_OBSERVED',reasonCode='DIAGNOSTIC_OBSERVED')
        else:output['reasonCode']=value['reasonCode']
        output['current_ci']={'pipeline_id':int(os.environ['CI_PIPELINE_ID']),'job_id':int(os.environ['CI_JOB_ID']),'source_sha':os.environ['CI_COMMIT_SHA']}
        output['prior_failed_build']={'pipeline_id':11896,'job_id':73293,'source_sha':SOURCE}
    except BaseException as error:
        output['reasonCode']=str(error)if type(error)is Hold and re.fullmatch('[A-Z_]{1,80}',str(error))else'DEPENDENCY_DIAGNOSTIC_HOLD'
    if destination is not None:
        try:
            with destination.open('x',encoding='utf-8')as stream:json.dump(output,stream,indent=2,sort_keys=True);stream.write('\n')
        except BaseException:output.update(result='HOLD',reasonCode='PUBLIC_DIAGNOSTIC_WRITE_HOLD')
    print(json.dumps(output,sort_keys=True));return 0 if output['result']=='DIAGNOSTIC_OBSERVED'else 2

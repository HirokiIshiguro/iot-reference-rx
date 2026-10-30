"""Original CI account, configured WSL namespace process metadata only."""
import argparse,hashlib,json,os,re,subprocess
from pathlib import Path

CALLER_SHA256='77805a37506378922c472d6e108516db98d846ed4387883bf31237fd82bf744d'
PRIOR={'project_id':38,'pipeline_id':11883,'job_id':73265,
 'source_sha':'83489f135c0382ef7879612b5cde03844f2d399c','target_id':'rx65n-bg96',
 'target_sha256':'7fd421681eede85a1d668bf76966e10471b5640058f4ce82dc10685f111f3bc2',
 'group':'FullTransportInterfaceTLS','job_started_at':'2026-10-30T17:24:16.976+09:00',
 'job_finished_at':'2026-10-30T18:22:59.075+09:00'}
KIND='HOST_PROCESS_METADATA_ONLY'
class Hold(RuntimeError):pass
def need(ok,code):
    if not ok:raise Hold(code)
def strict(raw):
    def pairs(items):
        value={}
        for key,item in items:need(key not in value,'DUPLICATE_JSON_KEY');value[key]=item
        return value
    def bad(_):raise Hold('NONFINITE_JSON')
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=bad)

# Root must bind the separately frozen inner probe and its exact schema.
EXECUTION_READY=True
INNER_FILENAME='native_host_metadata_proc.py'
INNER_SHA256='776d4ab21e77528eca2f1cfe3d2f81f8ced25d9d8c209df8d3ff148ff2e017a8'
INNER_SCOPE='CURRENT_NORMAL_WSL_UID_LAUNCH_NAME_METADATA'
INNER_FIELDS={'current_uid_relevant_processes_absent', 'SDK_count', 'FRQ_count', 'scan_error_stage', 'scan_error_class', 'unparsed_python_count', 'all_UID_processes_absent', 'prior_run_host_stopped', 'scope', 'scan_error_errno', 'python_version', 'scan_complete', 'supervisor_count'}

def load_inner():
    need(EXECUTION_READY,'HOST_METADATA_SOURCE_UNREADY')
    need(type(INNER_SHA256)is str and re.fullmatch('[0-9a-f]{64}',INNER_SHA256),'INNER_HASH_UNBOUND')
    path=Path(__file__).resolve().with_name(INNER_FILENAME)
    need(path.is_file()and not any(p.is_symlink()or(getattr(p.lstat(),'st_file_attributes',0)&0x400)for p in(path,*path.parents)),'LINKED_INNER')
    raw=path.read_bytes().replace(b'\r\n',b'\n')
    need(b'\r'not in raw and not raw.startswith(b'\xef\xbb\xbf'),'INNER_ENCODING')
    need(len(raw)<=65536 and hashlib.sha256(raw).hexdigest()==INNER_SHA256,'INNER_SOURCE_HASH')
    return raw.decode('utf-8','strict')


def observe(profile):
    result={'scope':INNER_SCOPE,'scan_complete':False,'current_uid_relevant_processes_absent':'UNKNOWN',
        'prior_run_host_stopped':'UNKNOWN','all_UID_processes_absent':'UNKNOWN',
        'launcher_error_stage':'NONE','launcher_error_class':'NONE','launcher_error_errno':None,'launcher_exited':False}
    stage='WSL_LAUNCH'
    try:
        binary=Path(os.environ.get('WINDIR',r'C:\Windows'))/'System32/wsl.exe'
        process=subprocess.Popen([str(binary),'-d',profile['wsl_distribution'],'--exec',profile['wsl_python'],'-I','-B','-c',load_inner()],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        stage='WSL_COMMUNICATE'
        try:stdout,stderr=process.communicate(timeout=20)
        except subprocess.TimeoutExpired:
            result.update(launcher_error_stage='WSL_TIMEOUT',launcher_error_class='TimeoutExpired')
            return result
        result['launcher_exited']=True
        need(process.returncode==0 and len(stdout)<=16384 and len(stderr)<=16384 and not stderr.strip(),'WSL_OUTPUT_UNCONFIRMED')
        stage='WSL_SCHEMA';value=strict(stdout)
        need(type(value)is dict and set(value)==INNER_FIELDS,'WSL_SCHEMA')
        need(value['scope']==INNER_SCOPE and type(value['scan_complete'])is bool,'WSL_SCOPE')
        for key in('SDK_count','FRQ_count','supervisor_count','unparsed_python_count'):
            need(type(value[key])is int and 0<=value[key]<=65536,'WSL_COUNT')
        need(type(value['python_version'])is list and len(value['python_version'])==3 and all(type(n)is int and 0<=n<=65535 for n in value['python_version']),'WSL_VERSION')
        need(value['prior_run_host_stopped']==value['all_UID_processes_absent']=='UNKNOWN','WSL_OVERCLAIM')
        need(value['scan_error_errno']is None or type(value['scan_error_errno'])is int and -65535<=value['scan_error_errno']<=65535,'WSL_ERRNO')
        stages={'NONE','IDENTITY','SELF_EXE','ENUMERATE_PROC','PROCESS_STAT','PROCESS_COMM','PROCESS_EXE','PYTHON_CMDLINE','PYTHON_ARGUMENTS'}
        classes={'NONE','PermissionError','FileNotFoundError','ProcessLookupError','OSError','ValueError','TypeError','AttributeError','RuntimeError','AssertionError','UnicodeDecodeError','OTHER_EXCEPTION'}
        need(value['scan_error_stage']in stages and value['scan_error_class']in classes,'WSL_ERROR_ENUM')
        absent=value['current_uid_relevant_processes_absent']
        if value['scan_complete']:
            need(value['unparsed_python_count']==0 and value['scan_error_stage']==value['scan_error_class']=='NONE','WSL_COMPLETE')
            need(type(absent)is bool and absent is(not any(value[k]for k in('SDK_count','FRQ_count','supervisor_count'))),'WSL_ABSENCE')
        else:need(absent=='UNKNOWN','WSL_INCOMPLETE_ABSENCE')
        result.update(observation=value,scan_complete=value['scan_complete'],current_uid_relevant_processes_absent=absent)
    except BaseException as error:
        result['launcher_error_stage']=stage
        name=type(error).__name__
        result['launcher_error_class']=str(error)if type(error)is Hold and re.fullmatch('[A-Z_]{1,80}',str(error))else name if name in('OSError','PermissionError','ValueError','TypeError','FileNotFoundError','UnicodeDecodeError')else'OTHER_EXCEPTION'
        number=getattr(error,'errno',None);result['launcher_error_errno']=number if type(number)is int and -65535<=number<=65535 else None
    return result


def run_requested(caller):
    output={'schema_version':1,'kind':KIND,'diagnostic_only':True,'native_tests_run':False,
        'qualification':False,'functional_PASS_claimed':False,'prior_run_host_stopped':'UNKNOWN',
        'private_runtime_reads':0,'raw_UART_reads':0,'SDK_executions':0,'AWS_operations':0,
        'RPi_actions':0,'native_process_signals_sent':0,'identity_changed':False,
        'historical_creator_identity_proven':'UNKNOWN','result':'HOLD','reasonCode':'HOST_METADATA_HOLD'}
    destination=None
    try:
        need(EXECUTION_READY,'HOST_METADATA_SOURCE_UNREADY')
        raw=os.environ.get('RX_IDT_PRIOR_RUN_DIAGNOSTIC','');need(len(raw)<=4096,'REQUEST_BOUND');request=strict(raw)
        need(type(request)is dict and set(request)==set(PRIOR)|{'caller_sha256','kind'},'REQUEST_SCHEMA')
        need(all(type(request[k])is type(v)and request[k]==v for k,v in PRIOR.items())and request['kind']==KIND,'REQUEST_IDENTITY')
        caller=Path(caller).resolve();data=caller.read_bytes().replace(b'\r\n',b'\n');need(b'\r'not in data and not data.startswith(b'\xef\xbb\xbf'),'CALLER_ENCODING')
        need(hashlib.sha256(data).hexdigest()==request['caller_sha256']==CALLER_SHA256,'CALLER_HASH')
        need(os.name=='nt'and os.environ.get('CI_PROJECT_ID')=='38'and os.environ.get('GITLAB_USER_ID')=='38'and os.environ.get('CI_PIPELINE_SOURCE')=='api','OWN_NORMAL_CI_REQUIRED')
        need(os.environ.get('CI_JOB_NAME')=='test_rx65n_bg96_idt'and os.environ.get('IDT_TARGET')=='rx65n-bg96'and os.environ.get('IDT_SCOPE')=='transport','CI_SCOPE')
        for key,old in(('CI_PIPELINE_ID',11883),('CI_JOB_ID',73265)):
            need(re.fullmatch('[1-9][0-9]{0,11}',os.environ.get(key,''))and int(os.environ[key])!=old,'NEW_CI_REQUIRED')
        need(re.fullmatch('[0-9a-f]{40}',os.environ.get('CI_COMMIT_SHA',''))is not None,'CURRENT_SOURCE')
        parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path);args=parser.parse_args()
        source=caller.parents[2];destination=source/'artifacts/idt'
        need(Path(os.environ.get('CI_PROJECT_DIR','')).resolve()==source and args.output.resolve()==destination,'OUTPUT_SCOPE')
        for path in(source,source/'artifacts',destination):
            if not path.exists():path.mkdir()
            need(not any(p.is_symlink()or(getattr(p.lstat(),'st_file_attributes',0)&0x400)for p in(path,*path.parents)),'LINKED_OUTPUT')
        need(not(destination/'prior-run-diagnostic.json').exists(),'ALREADY_WRITTEN')
        try:from .host_profile import load_host_profile
        except ImportError:from host_profile import load_host_profile
        output['process_metadata']=observe(load_host_profile())
        output.update(current_ci={'project_id':38,'pipeline_id':int(os.environ['CI_PIPELINE_ID']),'job_id':int(os.environ['CI_JOB_ID']),'source_sha':os.environ['CI_COMMIT_SHA']},prior_context=PRIOR,result='HOST_PROCESS_METADATA_OBSERVED',reasonCode='HOST_PROCESS_METADATA_OBSERVED')
    except BaseException as error:
        output['reasonCode']=str(error)if type(error)is Hold and re.fullmatch('[A-Z_]{1,80}',str(error))else'HOST_METADATA_HOLD'
    if destination is not None:
        try:
            with(destination/'prior-run-diagnostic.json').open('x',encoding='utf-8')as stream:json.dump(output,stream,sort_keys=True,indent=2);stream.write('\n')
        except BaseException:output.update(result='HOLD',reasonCode='PUBLIC_WRITE_HOLD')
    print(json.dumps(output,sort_keys=True));return 0 if output['result']=='HOST_PROCESS_METADATA_OBSERVED'else 2

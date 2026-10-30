"""Read one prior runtime as its original normal CI owner; never run a suite or touch a board."""
from __future__ import annotations
import argparse,ctypes,hashlib,json,os,re,stat,subprocess
from datetime import datetime,timezone
from pathlib import Path

PRIOR={'project_id':38,'pipeline_id':11883,'job_id':73265,
       'source_sha':'83489f135c0382ef7879612b5cde03844f2d399c','target_id':'rx65n-bg96',
       'target_sha256':'7fd421681eede85a1d668bf76966e10471b5640058f4ce82dc10685f111f3bc2',
       'group':'FullTransportInterfaceTLS','job_started_at':'2026-10-30T17:24:16.976+09:00',
       'job_finished_at':'2026-10-30T18:22:59.075+09:00'}
REASONS={
 'RPi UART bridge did not become ready':'UART_BRIDGE_NOT_READY',
 'UART bridge exited during IDT execution':'UART_BRIDGE_EXITED',
 'IDT run exceeded its time budget':'NATIVE_TIME_BUDGET',
 'signal received':'INTERRUPTED_SIGNAL',
 'private UART capture failed':'PRIVATE_CAPTURE_FAILED',
 'device reported a fatal IDT port error':'DEVICE_FATAL_PORT_ERROR',
 'UART RX stream failed':'UART_RX_STREAM_FAILED',
 'Firmware flash callback failed; remaining native results are invalid':'FLASH_CALLBACK_FAILED',
 'Owned native IDT process did not stop within its cleanup budget':'NATIVE_CLEANUP_BUDGET',
 'RPi bridge exceeded its end-state cleanup budget; inspect the owned bench':'BRIDGE_END_STATE_BUDGET',
 'Owned SSH process did not stop; inspect the private runtime and bench':'OWNED_SSH_NOT_STOPPED',
 'UART capture did not drain before closing':'CAPTURE_NOT_DRAINED',
 'UART capture did not complete':'CAPTURE_INCOMPLETE'}

class Hold(RuntimeError):pass
def need(ok,code):
    if not ok:raise Hold(code)
def strict(raw):
    def pairs(items):
        out={}
        for k,v in items:need(k not in out,'DUPLICATE_JSON_KEY');out[k]=v
        return out
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:need(False,'NONFINITE_JSON'))
def moment(value):
    need(type(value)is str,'INVALID_TIME');at=datetime.fromisoformat(value.replace('Z','+00:00'))
    need(at.tzinfo is not None,'TIMEZONE_REQUIRED');return at
def admit(request,caller_hash,environ):
    need(type(request)is dict and set(request)==set(PRIOR)|{'caller_sha256','include_console_enums'},'REQUEST_SCHEMA')
    need(all(type(request[k])is type(v)and request[k]==v for k,v in PRIOR.items()),'PRIOR_RUN_BINDING')
    need(request['caller_sha256']==caller_hash and re.fullmatch('[0-9a-f]{64}',caller_hash)is not None,'CALLER_HASH')
    need(type(request['include_console_enums'])is bool,'CONSOLE_SELECTOR')
    need(environ.get('CI_PROJECT_ID')=='38'and environ.get('CI_PIPELINE_SOURCE')=='api','NORMAL_CI_REQUIRED')
    need(environ.get('GITLAB_USER_ID')=='38','OWN_CODEX_API_ACTOR_REQUIRED')
    need(environ.get('CI_JOB_NAME')=='test_rx65n_bg96_idt'and environ.get('IDT_TARGET')=='rx65n-bg96'and environ.get('IDT_SCOPE')=='transport','CURRENT_NATIVE_SELECTOR')
    need(all(re.fullmatch('[1-9][0-9]{0,11}',environ.get(k,''))for k in('CI_PIPELINE_ID','CI_JOB_ID')),'CURRENT_CI_IDS')
    need(int(environ['CI_PIPELINE_ID'])!=PRIOR['pipeline_id']and int(environ['CI_JOB_ID'])!=PRIOR['job_id'],'NEW_DIAGNOSTIC_JOB_REQUIRED')
    need(re.fullmatch('[0-9a-f]{40}',environ.get('CI_COMMIT_SHA',''))is not None,'CURRENT_SOURCE_REQUIRED')
    need(moment(request['job_started_at'])<moment(request['job_finished_at']),'PRIOR_TIME_ORDER')

def unlinked(path):
    for p in(path,*path.parents):
        info=p.lstat()
        need(not stat.S_ISLNK(info.st_mode)and not(getattr(info,'st_file_attributes',0)&0x400),'LINKED_PATH_REJECTED')

def owner_relation(token_user_matches,token_default_owner_matches):
    need(type(token_user_matches)is bool and type(token_default_owner_matches)is bool,'OWNER_RELATION_FLAGS')
    return 'TOKEN_USER'if token_user_matches else'TOKEN_DEFAULT_OWNER'if token_default_owner_matches else'OTHER'

def windows_owner_relation(path):
    """Compare owner to effective TokenUser/TokenOwner; never stringify a SID."""
    need(os.name=='nt','NORMAL_WINDOWS_OWNER_REQUIRED')
    from ctypes import wintypes as w
    a=ctypes.WinDLL('advapi32',use_last_error=True);k=ctypes.WinDLL('kernel32',use_last_error=True)
    a.GetNamedSecurityInfoW.argtypes=[w.LPWSTR,w.DWORD,w.DWORD,ctypes.POINTER(ctypes.c_void_p),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.POINTER(ctypes.c_void_p)]
    a.GetNamedSecurityInfoW.restype=w.DWORD
    a.OpenThreadToken.argtypes=[w.HANDLE,w.DWORD,w.BOOL,ctypes.POINTER(w.HANDLE)];a.OpenThreadToken.restype=w.BOOL
    a.OpenProcessToken.argtypes=[w.HANDLE,w.DWORD,ctypes.POINTER(w.HANDLE)];a.OpenProcessToken.restype=w.BOOL
    a.GetTokenInformation.argtypes=[w.HANDLE,w.DWORD,ctypes.c_void_p,w.DWORD,ctypes.POINTER(w.DWORD)];a.GetTokenInformation.restype=w.BOOL
    a.EqualSid.argtypes=[ctypes.c_void_p,ctypes.c_void_p];a.EqualSid.restype=w.BOOL
    k.GetCurrentProcess.restype=w.HANDLE;k.GetCurrentThread.restype=w.HANDLE
    k.CloseHandle.argtypes=[w.HANDLE];k.LocalFree.argtypes=[ctypes.c_void_p]
    owner=ctypes.c_void_p();descriptor=ctypes.c_void_p();token=w.HANDLE()
    need(a.GetNamedSecurityInfoW(str(path),1,1,ctypes.byref(owner),None,None,None,ctypes.byref(descriptor))==0,'OWNER_METADATA_DENIED')
    try:
        if not a.OpenThreadToken(k.GetCurrentThread(),8,True,ctypes.byref(token)):
            need(ctypes.get_last_error()==1008 and a.OpenProcessToken(k.GetCurrentProcess(),8,ctypes.byref(token)),'EFFECTIVE_TOKEN_UNAVAILABLE')
        matches=[]
        for information_class in(1,4):  # TokenUser and TokenOwner/default creator owner.
            size=w.DWORD();a.GetTokenInformation(token,information_class,None,0,ctypes.byref(size));need(0<size.value<=65536,'TOKEN_METADATA_BOUND')
            data=ctypes.create_string_buffer(size.value)
            need(a.GetTokenInformation(token,information_class,data,size.value,ctypes.byref(size)),'TOKEN_METADATA_DENIED')
            sid=ctypes.cast(data,ctypes.POINTER(ctypes.c_void_p))[0]
            matches.append(bool(a.EqualSid(owner,sid)))
        return owner_relation(*matches)
    finally:
        if token:k.CloseHandle(token)
        if descriptor:k.LocalFree(descriptor)

def read_owned(path,limit,diagnostic=None,kind=None):
    unlinked(path);relation=windows_owner_relation(path)
    need(relation in('TOKEN_USER','TOKEN_DEFAULT_OWNER'),'ORIGINAL_OWNER_MISMATCH');before=path.stat()
    if diagnostic is not None:
        limits={'SOURCE_PROVENANCE':2*1024*1024,'TRANSPORT_RESULT':512*1024,'CONSOLE':4*1024*1024}
        need(type(diagnostic)is dict and kind in limits and limit==limits[kind],'FILE_SHAPE_DIAGNOSTIC_SCOPE')
        need(type(before.st_nlink)is int and 0<=before.st_nlink<=2147483647 and
             type(before.st_size)is int and 0<=before.st_size<=9223372036854775807,'FILE_SHAPE_METADATA_BOUNDS')
        diagnostic['last_file_shape']={'kind':kind,'owner_relation':relation,'regular':bool(stat.S_ISREG(before.st_mode)),
            'link_count':before.st_nlink,'size_bytes':before.st_size,'limit_bytes':limit}
    need(stat.S_ISREG(before.st_mode)and before.st_nlink==1 and before.st_size<=limit,'OWNED_FILE_SHAPE')
    with path.open('rb')as f:raw=f.read(limit+1)
    after=path.stat()
    need(len(raw)<=limit and(before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_ino,after.st_size,after.st_mtime_ns),'OWNED_FILE_CHANGED')
    return raw

def select_runtime(root,request,metadata,diagnostic=None):
    # This canonical parent is a shared container: inspect only directory
    # metadata using the normal account's existing permissions. Its owner can
    # differ; every candidate private run and allowed file must match our token.
    unlinked(root);need(root.is_dir(),'RUNTIME_ROOT_MISSING')
    start,end=(moment(request[k]).timestamp()for k in('job_started_at','job_finished_at'));matches=[];accepted_owner_count=0
    entries=list(root.iterdir());need(len(entries)<=4096,'RUNTIME_ENTRY_BOUND')
    for path in entries:
        if not re.fullmatch('run-[a-z0-9_]{8}',path.name):continue
        info=path.lstat();created=getattr(info,'st_birthtime',info.st_ctime)
        if not start<=created<=end:continue
        need(stat.S_ISDIR(info.st_mode),'RUNTIME_DIRECTORY_REQUIRED');unlinked(path)
        metadata['candidate_count']+=1;relation=windows_owner_relation(path)
        if relation=='OTHER':continue  # Unrelated owner: metadata only, no body read.
        accepted_owner_count+=1
        provenance=strict(read_owned(path/'source-provenance.json',2*1024*1024,diagnostic,'SOURCE_PROVENANCE'))
        if type(provenance)is dict and all(provenance.get(k)==request[k]for k in('source_sha','target_id','target_sha256'))and provenance.get('source_tree_dirty')is False:
            matches.append((path,relation))
    metadata['owner_relation']=matches[0][1]if len(matches)==1 else'OTHER'
    need(not metadata['candidate_count']or accepted_owner_count>0,'ORIGINAL_OWNER_MISMATCH')
    need(len(matches)==1,'PRIOR_RUNTIME_MISSING_OR_AMBIGUOUS');return matches[0][0]

def reason_code(value):
    if type(value)is not str:return 'NONE'if value is None else'UNKNOWN'
    if value in REASONS:return REASONS[value]
    if re.fullmatch(r'expected one current JUnit report, found [0-9]{1,6}',value):return 'JUNIT_REPORT_COUNT'
    if re.fullmatch(r'RPi bridge/end-state cleanup failed, exit -?[0-9]{1,10}',value):return 'BRIDGE_END_STATE_EXIT'
    return 'UNKNOWN'
def project_result(value,request):
    need(type(value)is dict and all(value.get(k)==request[k]for k in('target_id','target_sha256','group')),'TRANSPORT_RESULT_IDENTITY')
    start,finish=moment(value.get('startedUtc')),moment(value.get('finishedUtc'))
    need(moment(request['job_started_at'])<=start<=moment(request['job_finished_at'])and start<finish<=datetime.now(timezone.utc),'TRANSPORT_RESULT_TIME')
    exit_code=value.get('idtExitCode')
    return {'reasonCode':reason_code(value.get('reason')),'reason_field_present':'reason'in value,
            'cleanupError_present':'cleanupError'in value,'cleanupReasonCode':reason_code(value.get('cleanupError')),
            'idt_exit_code':exit_code if type(exit_code)is int and -2147483648<=exit_code<=2147483647 else None,
            'prior_verdict':value.get('verdict')if value.get('verdict')in('FAIL','INTERRUPTED','SELECTED_GROUP_PASS','SINGLE_CASE_PASS','SELECTED_CASES_PASS')else'UNKNOWN',
            'source_target_time_bound':True,'prior_result_started_at':start.isoformat(),'prior_result_finished_at':finish.isoformat(),
            'result_finish_relative_to_job':'AFTER_JOB_TERMINAL'if finish>moment(request['job_finished_at'])else'BY_JOB_TERMINAL','functional_PASS_claimed':False}

PROC_CODE=r'''
import json,os,re,sys
from pathlib import Path
def first_script(parts):
 i=1
 while i<len(parts)and i<=64:
  arg=parts[i]
  if arg==b'--':return parts[i+1]if i+1<len(parts)and parts[i+1]!=b'-'else None
  if not arg.startswith(b'-'):return arg
  if arg in(b'-c',b'-m',b'-'):return None
  if arg in(b'-W',b'-X',b'--check-hash-based-pycs'):
   if i+1>=len(parts):return None
   i+=2;continue
  if re.fullmatch(rb'-[BEIOPqsuSvVxibdR]+',arg):i+=1;continue
  if arg.startswith((b'-W',b'-X'))and len(arg)>2:i+=1;continue
  return None
 return None
out={'scope':'CURRENT_NORMAL_WSL_UID_ONLY','scan_complete':False,'SDK_count':0,'FRQ_count':0,'supervisor_count':0,'unparsed_python_count':0,'current_uid_relevant_processes_absent':'UNKNOWN','prior_run_host_stopped':'UNKNOWN','all_UID_processes_absent':'UNKNOWN'}
try:
 uid=os.geteuid();assert os.getuid()==uid
 own_python=Path(os.readlink('/proc/self/exe')).name.removesuffix(' (deleted)')
 entries=list(Path('/proc').iterdir());assert len(entries)<=65536
 for p in entries:
  if not p.name.isdecimal()or int(p.name)==os.getpid():continue
  try:
   if p.stat().st_uid!=uid:continue
   executable=Path(os.readlink(p/'exe')).name.removesuffix(' (deleted)')
   if executable=='devicetester_linux_x86-64':out['SDK_count']+=1;continue
   if executable=='frq_linux_x86-64':out['FRQ_count']+=1;continue
   if executable!=own_python and re.fullmatch(r'python(?:[0-9]+(?:\.[0-9]+)*)?',executable)is None:continue
   with(p/'cmdline').open('rb')as stream:args=stream.read(65537)
   if len(args)>65536:out['unparsed_python_count']+=1;continue
   script=first_script([v for v in args.split(b'\0')if v])
   if script is None:out['unparsed_python_count']+=1;continue
   if Path(os.fsdecode(script)).name=='run_transport.py':out['supervisor_count']+=1
  except(FileNotFoundError,ProcessLookupError):continue
 out['scan_complete']=out['unparsed_python_count']==0
 if out['scan_complete']:out['current_uid_relevant_processes_absent']=not any(out[k]for k in('SDK_count','FRQ_count','supervisor_count'))
except BaseException:pass
print(json.dumps(out))
'''
def observe_processes(profile):
    unknown={'scope':'CURRENT_NORMAL_WSL_UID_ONLY','scan_complete':False,'current_uid_relevant_processes_absent':'UNKNOWN','prior_run_host_stopped':'UNKNOWN','all_UID_processes_absent':'UNKNOWN'}
    try:
        wsl=Path(os.environ.get('WINDIR',r'C:\Windows'))/'System32/wsl.exe'
        result=subprocess.run([str(wsl),'-d',profile['wsl_distribution'],'--exec',profile['wsl_python'],'-I','-B','-c',PROC_CODE],capture_output=True,timeout=20)
        need(result.returncode==0 and len(result.stdout)<=8192 and not result.stderr.strip(),'WSL_METADATA_UNCONFIRMED')
        value=strict(result.stdout)
        expected={'scope','scan_complete','SDK_count','FRQ_count','supervisor_count','unparsed_python_count','current_uid_relevant_processes_absent','prior_run_host_stopped','all_UID_processes_absent'}
        need(type(value)is dict and set(value)==expected and value['scope']=='CURRENT_NORMAL_WSL_UID_ONLY','WSL_PROJECTION_SCHEMA')
        need(type(value['scan_complete'])is bool and all(type(value[k])is int and 0<=value[k]<=65536 for k in('SDK_count','FRQ_count','supervisor_count','unparsed_python_count'))and(not value['scan_complete']or value['unparsed_python_count']==0),'WSL_PROJECTION_TYPES')
        need(value['prior_run_host_stopped']==value['all_UID_processes_absent']=='UNKNOWN','WSL_SCOPE_OVERCLAIM')
        absent=value['current_uid_relevant_processes_absent']
        need((type(absent)is bool or absent=='UNKNOWN')and(absent is(not any(value[k]for k in('SDK_count','FRQ_count','supervisor_count')))if value['scan_complete']else absent=='UNKNOWN'),'WSL_PROJECTION_TYPES')
        return value
    except BaseException:return unknown

def run_requested(caller):
    """Only this entry reads the restricted original-owner files, after closed admission."""
    output={'schema_version':1,'diagnostic_only':True,'native_tests_run':False,'qualification':False,
            'result':'HOLD','reasonCode':'DIAGNOSTIC_HOLD','functional_PASS_claimed':False,
            'RPi_actions':0,'SDK_executions':0,'AWS_operations':0,'native_process_signals_sent':0,
            'WSL_metadata_launcher_terminations':'UNKNOWN',
            'raw_private_content_saved':False,'prior_run_host_stopped':'UNKNOWN'}
    destination=None
    try:
        request_raw=os.environ.get('RX_IDT_PRIOR_RUN_DIAGNOSTIC','');need(len(request_raw)<=4096,'REQUEST_BOUND')
        request=strict(request_raw);caller=Path(caller).resolve()
        caller_bytes=caller.read_bytes().replace(b'\r\n',b'\n')
        need(b'\r'not in caller_bytes and not caller_bytes.startswith(b'\xef\xbb\xbf'),'CALLER_NEWLINE_ENCODING')
        caller_bytes.decode('utf-8','strict');admit(request,hashlib.sha256(caller_bytes).hexdigest(),os.environ)
        need(os.name=='nt','NORMAL_WINDOWS_CI_REQUIRED')
        parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path);args=parser.parse_args()
        source=caller.parents[2];desired=source/'artifacts/idt'
        need(Path(os.environ.get('CI_PROJECT_DIR','')).resolve()==source and args.output.resolve()==desired,'PUBLIC_OUTPUT_SCOPE')
        unlinked(source)
        for directory in(source/'artifacts',desired):
            if not directory.exists():directory.mkdir()
            unlinked(directory)
        need(not(desired/'prior-run-diagnostic.json').exists(),'DIAGNOSTIC_ALREADY_WRITTEN')
        destination=desired
        try:from .host_profile import load_host_profile
        except ImportError:from host_profile import load_host_profile
        profile=load_host_profile();output['process_observation']=observe_processes(profile)
        metadata={'owner_relation':'OTHER','candidate_count':0};output['runtime_metadata']=metadata
        runtime=select_runtime(Path(profile['runtime_root']),request,metadata,output)
        output.update(prior_run={k:request[k]for k in PRIOR},
                      current_ci={'project_id':38,'pipeline_id':int(os.environ['CI_PIPELINE_ID']),'job_id':int(os.environ['CI_JOB_ID']),'source_sha':os.environ['CI_COMMIT_SHA']},
                      normal_creator_owner_class_accepted=True,uniquely_matched_runtime=True)
        try:value=strict(read_owned(runtime/'execution/transport-result.json',512*1024,output,'TRANSPORT_RESULT'))
        except FileNotFoundError:raise Hold('TRANSPORT_RESULT_MISSING')from None
        output['prior_result']=project_result(value,request)
        if request['include_console_enums']:
            raw=read_owned(runtime/'console.log',4*1024*1024,output,'CONSOLE')
            output['console_fixed_enum_counts']={code:min(65535,raw.count(text.encode()))for text,code in REASONS.items()}
        output.update(result='DIAGNOSTIC_OBSERVED',reasonCode='DIAGNOSTIC_OBSERVED',observed_at=datetime.now(timezone.utc).isoformat())
    except BaseException as error:
        output.update(result='HOLD',reasonCode=str(error)if type(error)is Hold and re.fullmatch('[A-Z_]{1,80}',str(error))else'DIAGNOSTIC_HOLD')
    if destination is not None:
        try:
            with(destination/'prior-run-diagnostic.json').open('x',encoding='utf-8')as stream:json.dump(output,stream,sort_keys=True,indent=2);stream.write('\n')
        except BaseException:output.update(result='HOLD',reasonCode='PUBLIC_DIAGNOSTIC_WRITE_HOLD')
    print(json.dumps(output,sort_keys=True));return 0 if output['result']=='DIAGNOSTIC_OBSERVED'else 2

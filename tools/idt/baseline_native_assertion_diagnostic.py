"""One current11947 raw-XML assertion projection by its normal Windows CI owner. UNREADY."""
from __future__ import annotations
import argparse,ctypes,hashlib,json,os,re,stat,sys
from datetime import datetime,timezone
from pathlib import Path
import xml.etree.ElementTree as ET
EXECUTION_READY=True
SOURCE='fab661c7a1249bd3f0b4e6411b3b095d81606c54'
TARGET='rx65n-bg96'
TARGET_SHA='7fd421681eede85a1d668bf76966e10471b5640058f4ce82dc10685f111f3bc2'
GROUP='FullTransportInterfaceTLS'
JOB_START='2026-10-31T01:17:29.440+09:00'
JOB_FINISH='2026-10-31T02:10:13.705+09:00'
HOST_PROFILE_SHA='aa63af1c1d100e577a0bc6413e92b822be247dcc6cc362f6d9ccd348dc992792'
XML_LIMIT=2*1024*1024
PROVENANCE_BYTES=6063777
RESULT_NAME='baseline11928-assertion-diagnostic.json'
CASE='TransportSend_RemoteDisconnect'
MESSAGES={'COMMAND_SEND_LENGTH':'Transport send should not have any error.','POST_DISCONNECT_NEGATIVE':'Transport send should return negative value when disconnected.'}
class Hold(RuntimeError):pass
DEPENDENCIES={'Middleware/3rdparty/TraceRecorderSource': '2f888cb9e6240c88e33eacd5acd50555fb13fbf5', 'Middleware/3rdparty/littlefs': '6cb4e86540eca0d9ba62500a298385c9d863c8be', 'Middleware/3rdparty/mbedtls': 'c765c831e5c2a0971410692f92f7a81d6ec65ec2', 'Middleware/3rdparty/tinycbor': 'd94ca09aa91f5b3c581527aa8bca179a82b79874', 'Middleware/3rdparty/tinycrypt': 'cf24c907a61c01bc2c4e1ee0ae24457c27a840a2', 'Middleware/AWS/Fleet-Provisioning-for-AWS-IoT-embedded-sdk': '7691e8af27bd0a42b7fe2f21c8b3289fa037df17', 'Middleware/AWS/Jobs-for-AWS-IoT-embedded-sdk': 'f09232966a558916253537fed68c07e529cd8f39', 'Middleware/AWS/aws-iot-core-mqtt-file-streams-embedded-c': '383ffeff43a80123e07cf8ca613d12ce680527b0', 'Middleware/FreeRTOS-Plus-CLI': '152cf36d6775bce6026a791845af12201aae703d', 'Middleware/FreeRTOS/FreeRTOS-Kernel': '9b777ae5c5b8e9e456065a00294d1e5f5f9facf5', 'Middleware/FreeRTOS/FreeRTOS-Plus-TCP': 'c12361095aca68aeed858f45d14395fbffa92c0d', 'Middleware/FreeRTOS/backoffAlgorithm': '14f4c88b33dd554be30a00a312c88d3986d457d0', 'Middleware/FreeRTOS/coreJSON': 'cffa492da18c890181d64462f8af63992a69d3b0', 'Middleware/FreeRTOS/coreMQTT': '04845c6a8e5f9cf2d232f1c6e80baeb81302e690', 'Middleware/FreeRTOS/coreMQTT-Agent': '2338d00db41196e4a1fce4bc3ab32f907e77f871', 'Middleware/FreeRTOS/corePKCS11': 'ccc78afee1716436cca832dd3d9388ead2ba05b0', 'Middleware/Renesas/r_cellular': 'e129c6dd730e1029440fd4b977862b0a9c6ed1f3', 'Middleware/Renesas/r_flash_rx': '5304d35e22002d0b0b0d24ae7773c64788ede5b3', 'Middleware/Renesas/r_sdio_rx': 'cc94efa0a37db72a6fede1bc651a891a0a6e8bec', 'Middleware/Renesas/r_simple_glcdc_config_rx': 'ade52ca9b3869c4d80855ee41a1bf63db70695db', 'Middleware/Renesas/r_simple_graphic_rx': 'a7c3d736eab56aa622caabe0715ba290e1136f49', 'Middleware/Renesas/rm_littlefs_rx': '60f93c8427ce88f70ea26aae7abc641f577a7765', 'Middleware/Renesas/rm_rtos_abstraction_rx': '5818cdfbda661d098fd028bf6975847d5af2c491', 'Middleware/Renesas/rx-driver-package': 'bcc409d331b0bff68d4b09bf6fc41376f75d42bc', 'Middleware/freertos_plus': 'a038063c3b0216e0b4d46d72425388a0c2938b13', 'Projects/boot_loader_ck_rx65n/e2studio_ccrx/lib/rx_bootloader': '8e19b0cdeeaab06f22fa0636f4cd469218edc6c1', 'Test/FreeRTOS-Libraries-Integration-Tests': '0a0a92160a81c5cba008e472203513bd0cfb4c7a', 'Test/Unity': '22777c4810de3e3a4cb521a05eca2752fccd00ea'}
REQUIRED_CASES=('TransportSend_NetworkContextNullPtr', 'TransportSend_BufferNullPtr', 'TransportSend_ZeroByteToSend', 'TransportRecv_NetworkContextNullPtr', 'TransportRecv_BufferNullPtr', 'TransportRecv_ZeroByteToRecv', 'Transport_SendOneByteRecvCompare', 'Transport_SendRecvOneByteCompare', 'Transport_SendRecvCompare', 'Transport_SendRecvCompareMultithreaded', 'TransportSend_RemoteDisconnect', 'TransportRecv_RemoteDisconnect', 'TransportRecv_NoDataToReceive', 'TransportRecv_ReturnZeroRetry')

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

def read_owned(path,limit):
    unlinked(path);need(windows_owner_relation(path)in('TOKEN_USER','TOKEN_DEFAULT_OWNER'),'ORIGINAL_OWNER_MISMATCH');before=path.stat()
    need(stat.S_ISREG(before.st_mode)and before.st_nlink==1 and before.st_size<=limit,'OWNED_FILE_SHAPE')
    with path.open('rb')as f:raw=f.read(limit+1)
    after=path.stat()
    need(len(raw)<=limit and(before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_ino,after.st_size,after.st_mtime_ns),'OWNED_FILE_CHANGED')
    return raw

def canonical_code(raw):
    value=raw.replace(b'\r\n',b'\n')
    need(b'\r' not in value and not value.startswith(b'\xef\xbb\xbf'),'CODE_ENCODING')
    value.decode('utf-8','strict');return value

def file_time_bound(path):
    unlinked(path);info=path.stat();created=getattr(info,'st_birthtime',info.st_ctime)
    need(moment(JOB_START).timestamp()<=created<=moment(JOB_FINISH).timestamp() and moment(JOB_START).timestamp()<=info.st_mtime<=moment(JOB_FINISH).timestamp(),'ORIGINAL_FILE_TIME_WINDOW')

def select_runtime(root,audit):
    unlinked(root);need(root.is_dir(),'RUNTIME_ROOT_UNAVAILABLE')
    entries=list(root.iterdir());need(len(entries)<=4096,'RUNTIME_DIRECTORY_BOUND')
    candidates=[]
    for path in entries:
        if re.fullmatch(r'run-[a-z0-9_]{8}',path.name) is None:continue
        info=path.lstat();created=getattr(info,'st_birthtime',info.st_ctime)
        if not moment(JOB_START).timestamp()<=created<=moment(JOB_FINISH).timestamp():continue
        need(stat.S_ISDIR(info.st_mode),'RUNTIME_DIRECTORY_SHAPE');unlinked(path)
        if windows_owner_relation(path) in ('TOKEN_USER','TOKEN_DEFAULT_OWNER'):candidates.append(path)
    # Metadata-only uniqueness precedes all private body reads.
    need(len(candidates)==1,'ORIGINAL_RUNTIME_MISSING_OR_AMBIGUOUS')
    runtime=candidates[0]
    provenance_path=runtime/'source-provenance.json';file_time_bound(provenance_path)
    need(windows_owner_relation(provenance_path) in ('TOKEN_USER','TOKEN_DEFAULT_OWNER'),'ORIGINAL_OWNER_MISMATCH')
    audit.update(provenance_size_observed=True,provenance_size_bytes=provenance_path.stat().st_size)
    provenance=strict(read_owned(provenance_path,PROVENANCE_BYTES))
    need(type(provenance)is dict and provenance.get('source_sha')==SOURCE and provenance.get('source_tree_dirty') is False and provenance.get('target_id')==TARGET and provenance.get('target_sha256')==TARGET_SHA,'ORIGINAL_SOURCE_TARGET_PROVENANCE')
    need(provenance.get('test_library_sha')==DEPENDENCIES['Test/FreeRTOS-Libraries-Integration-Tests'] and provenance.get('submodule_shas')==DEPENDENCIES and provenance.get('dependency_target_id')==TARGET and provenance.get('dependency_manifest_schema_version')==1,'ORIGINAL_DEPENDENCY_PROVENANCE')
    result_path=runtime/'execution/transport-result.json';file_time_bound(result_path)
    result=strict(read_owned(result_path,512*1024))
    need(type(result)is dict and result.get('target_id')==TARGET and result.get('target_sha256')==TARGET_SHA and result.get('group')==GROUP and result.get('testId') is None and result.get('suite')=='FRQ_2.5.0','ORIGINAL_EXECUTION_SCHEMA')
    need(moment(JOB_START)<=moment(result['startedUtc'])<moment(result['finishedUtc'])<=moment(JOB_FINISH),'ORIGINAL_EXECUTION_TIME')
    need(type(result.get('idtExitCode'))is int and result['idtExitCode']==0,'ORIGINAL_IDT_EXIT')
    return runtime,result

def select_xml(runtime,execution):
    # The original pinned inspect_junit required one report and stored its path.
    # This is descriptor selection, not a new recursive global uniqueness claim.
    need(all(type(execution.get(k))is int and execution[k]==v for k,v in (('tests',14),('failures',1),('errors',0),('skipped',0))),'ORIGINAL_REPORT_DESCRIPTOR_COUNTS')
    report=execution.get('report')
    need(type(report)is str and 0<len(report)<=4096 and not any(ord(c) in (0,10,13) for c in report),'ORIGINAL_REPORT_DESCRIPTOR_SHAPE')
    normalized=report.replace(chr(92),'/')
    need(all(part not in ('.','..') for part in normalized.split('/')),'ORIGINAL_REPORT_DESCRIPTOR_TRAVERSAL')
    if normalized.startswith('/mnt/c/'):
        candidate=Path('C:/'+normalized[len('/mnt/c/'):])
    elif normalized[:3].lower()=='c:/':
        candidate=Path(normalized)
    else:
        raise Hold('ORIGINAL_REPORT_DESCRIPTOR_FORMAT')
    root=(runtime/'execution/results').absolute()
    candidate=candidate.absolute()
    need(candidate.name=='FRQ_Report.xml' and candidate.is_relative_to(root) and candidate!=root,'ORIGINAL_REPORT_DESCRIPTOR_SUBTREE')
    unlinked(candidate);file_time_bound(candidate)
    return candidate

def classify_xml(raw):
    text=raw.decode('utf-8-sig','strict')
    need('\0' not in text and '<!DOCTYPE' not in text.upper() and '<!ENTITY' not in text.upper(),'XML_ENCODING_OR_DECLARATION')
    root=ET.fromstring(text);tag=lambda n:n.tag.rsplit('}',1)[-1]
    try:
        nodes=list(root.iter());need(len(nodes)<=4096 and tag(root)in('testsuites','testsuite'),'XML_SCHEMA_BOUND')
        suites=[n for n in nodes if tag(n)=='testsuite' and n.get('name')==GROUP];need(len(suites)==1,'EXACT_GROUP_REQUIRED')
        all_cases=[n for n in nodes if tag(n)=='testcase'];cases=[n for n in suites[0].iter() if tag(n)=='testcase']
        need(len(all_cases)==len(cases)==14 and sorted(n.get('name','') for n in cases)==sorted(REQUIRED_CASES),'EXACT_REQUIRED14_REPORT')
        failures=[(case,child)for case in cases for child in case if tag(child)=='failure']
        need(len(failures)==1 and failures[0][0].get('name')==CASE and not any(tag(n)in('error','skipped') for n in nodes),'SAME_PUBLIC_13PASS1FAIL_REPORT')
        failure=failures[0][1]
        # Only the failed selected testcase text/message is searched; no text is returned.
        value=''.join(failure.itertext())+'\n'+failure.get('message','')
        present={name:message in value for name,message in MESSAGES.items()}
        code='AMBIGUOUS' if all(present.values()) else next((name for name,yes in present.items() if yes),'UNKNOWN')
        return {'assertion':code,'command_send_literal_present':present['COMMAND_SEND_LENGTH'],'post_disconnect_literal_present':present['POST_DISCONNECT_NEGATIVE'],'case_count':14,'failure_count':1,'error_count':0,'skipped_count':0,'public_report_shape_matches':True}
    finally:root.clear()

def save(path,value):
    with path.open('x',encoding='utf-8')as stream:json.dump(value,stream,sort_keys=True,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true');parser.add_argument('--reviewed-code-sha256');parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    result={'schema_version':1,'diagnostic_only':True,'original_project':38,'original_pipeline':11928,'original_job':73341,'result':'HOLD','reason':'ADMISSION_HOLD','assertion':'UNOBSERVED','private_XML_read_attempts':0,'provenance_size_observed':False,'provenance_size_bytes':0,'provenance_limit_bytes':PROVENANCE_BYTES,'raw_private_content_saved':False,'private_body_or_path_or_hash_exported':False,'native_tests_run':False,'RPi_actions':0,'SDK_executions':0,'WSL_executions':0,'AWS_operations':0,'functional_PASS_claimed':False,'root_cause_identified':False}
    destination=None;raw=bytearray()
    try:
        need(args.execute and EXECUTION_READY and sys.flags.isolated and sys.dont_write_bytecode and __debug__,'UNREADY_OR_NOT_ISOLATED')
        own=Path(__file__).absolute();source=Path(os.environ.get('CI_PROJECT_DIR','')).absolute()
        need(os.name=='nt' and os.environ.get('CI_PROJECT_ID')=='38' and os.environ.get('CI_PIPELINE_SOURCE')=='api' and os.environ.get('GITLAB_USER_ID')=='38','NORMAL_OWN_WINDOWS_CI_REQUIRED')
        need(os.environ.get('CI_JOB_NAME')=='inspect_rx65n_baseline11928_assertion' and os.environ.get('READ_BASELINE11928_ASSERTION')=='true' and os.environ.get('CI_COMMIT_REF_NAME')=='codex/184-baseline11928-assertion-readonly','EXACT_DIAGNOSTIC_SELECTOR')
        need(all(re.fullmatch('[1-9][0-9]{0,11}',os.environ.get(k,'')) for k in ('CI_PIPELINE_ID','CI_JOB_ID')) and int(os.environ['CI_PIPELINE_ID']) not in (11928,11947,11954,11956,11958,11960) and int(os.environ['CI_JOB_ID']) not in (73341,73384,73390,73391,73392,73393),'NEW_DIAGNOSTIC_IDS')
        need(re.fullmatch('[0-9a-f]{40}',os.environ.get('CI_COMMIT_SHA',''))is not None,'DIAGNOSTIC_SOURCE_REQUIRED')
        need(own==source/'tools/idt/baseline_native_assertion_diagnostic.py','DIAGNOSTIC_CODE_LOCATION');unlinked(own)
        need(re.fullmatch('[0-9a-f]{64}',args.reviewed_code_sha256 or '')is not None and hashlib.sha256(canonical_code(own.read_bytes())).hexdigest()==args.reviewed_code_sha256,'ACTUAL_REVIEWED_CODE')
        desired=source/'artifacts/idt'/RESULT_NAME
        need(args.output.absolute()==desired,'PUBLIC_OUTPUT_SCOPE');unlinked(source)
        for directory in (source/'artifacts',desired.parent):
            if not directory.exists():directory.mkdir()
            unlinked(directory)
        need(not desired.exists(),'PUBLIC_RESULT_ALREADY_EXISTS');destination=desired
        save(desired.with_name('baseline11928-assertion-intent.json'),{'schema_version':1,'diagnostic_only':True,'original_pipeline':11928,'original_job':73341,'maximum_private_XML_read_attempts':1,'native_tests_run':False,'RPi_actions':0,'SDK_executions':0,'WSL_executions':0,'AWS_operations':0})
        helper=source/'tools/idt/host_profile.py';unlinked(helper);data=canonical_code(helper.read_bytes());need(len(data)<=512*1024 and hashlib.sha256(data).hexdigest()==HOST_PROFILE_SHA,'CURRENT_PROFILE_HELPER_SOURCE')
        ns={'__name__':'reviewed_normal_host_profile','__file__':str(helper)};exec(compile(data,str(helper),'exec'),ns)
        profile=ns['load_host_profile']();runtime,original_execution=select_runtime(Path(profile['runtime_root']),result)
        xml=select_xml(runtime,original_execution);result['private_XML_read_attempts']=1;raw=bytearray(read_owned(xml,XML_LIMIT));projection=classify_xml(raw);raw.clear()
        result.update(projection,result='ASSERTION_DIAGNOSTIC_OBSERVED',reason='OBSERVED',normal_creator_owner_checks_passed=True,unique_time_source_target_runtime=True,reference_method='OWNER_SOURCE_TARGET_TIME_AND_REPORT',source_helper_checked=True)
    except BaseException as error:
        code=str(error) if type(error)is Hold and re.fullmatch('[A-Z][A-Z0-9_]{0,80}',str(error)) else 'DIAGNOSTIC_HOLD'
        result.update(result='HOLD',reason=code)
    finally:raw.clear()
    if destination is not None:
        try:save(destination,result)
        except BaseException:result.update(result='HOLD',reason='PUBLIC_RESULT_WRITE_HOLD')
    print(json.dumps(result,sort_keys=True));return 0 if result['result']=='ASSERTION_DIAGNOSTIC_OBSERVED'else 2
if __name__=='__main__':raise SystemExit(main())

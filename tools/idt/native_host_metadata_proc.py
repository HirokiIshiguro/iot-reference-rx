
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
out={'scope':'CURRENT_NORMAL_WSL_UID_LAUNCH_NAME_METADATA','scan_complete':False,'SDK_count':0,'FRQ_count':0,'supervisor_count':0,'unparsed_python_count':0,'current_uid_relevant_processes_absent':'UNKNOWN','prior_run_host_stopped':'UNKNOWN','all_UID_processes_absent':'UNKNOWN'}
out.update(python_version=list(sys.version_info[:3]),scan_error_stage='NONE',scan_error_class='NONE',scan_error_errno=None)
stage='IDENTITY'
def undeleted(value):
 suffix=' (deleted)'
 return value[:-len(suffix)]if value.endswith(suffix)else value

try:
 uid=os.geteuid();assert os.getuid()==uid
 stage='SELF_EXE'
 own_python=undeleted(Path(os.readlink('/proc/self/exe')).name)
 stage='ENUMERATE_PROC'
 entries=list(Path('/proc').iterdir());assert len(entries)<=65536
 for p in entries:
  if not p.name.isdecimal()or int(p.name)==os.getpid():continue
  try:
   stage='PROCESS_STAT'
   if p.stat().st_uid!=uid:continue
   stage='PROCESS_COMM'
   with(p/'comm').open('rb')as stream:comm_raw=stream.read(257)
   if len(comm_raw)>256:raise RuntimeError('COMM_METADATA_BOUND')
   comm=comm_raw.rstrip(b'\n').decode('utf-8','strict')
   # Kernel comm has at most 15 visible bytes. Classify expected launch names;
   # this is observation, not proof of historical ownership or no other users.
   sdk_comm='devicetester_linux_x86-64'[:15]
   frq_comm='frq_linux_x86-64'[:15]
   python_comm=comm in(own_python,'run_transport.py'[:15])or re.fullmatch(r'python(?:[0-9]+(?:\.[0-9]+)*)?',comm)is not None
   if comm not in(sdk_comm,frq_comm)and not python_comm:continue
   stage='PROCESS_EXE'
   executable=undeleted(Path(os.readlink(p/'exe')).name)
   if executable=='devicetester_linux_x86-64':out['SDK_count']+=1;continue
   if executable=='frq_linux_x86-64':out['FRQ_count']+=1;continue
   if executable!=own_python and re.fullmatch(r'python(?:[0-9]+(?:\.[0-9]+)*)?',executable)is None:continue
   stage='PYTHON_CMDLINE'
   with(p/'cmdline').open('rb')as stream:args=stream.read(65537)
   if len(args)>65536:out['unparsed_python_count']+=1;continue
   stage='PYTHON_ARGUMENTS'
   script=first_script([v for v in args.split(b'\0')if v])
   if script is None:out['unparsed_python_count']+=1;continue
   if Path(os.fsdecode(script)).name=='run_transport.py':out['supervisor_count']+=1
  except(FileNotFoundError,ProcessLookupError):continue
 out['scan_complete']=out['unparsed_python_count']==0
 if out['scan_complete']:out['current_uid_relevant_processes_absent']=not any(out[k]for k in('SDK_count','FRQ_count','supervisor_count'))
except BaseException as error:
 out['scan_error_stage']=stage
 name=type(error).__name__
 out['scan_error_class']=name if name in('PermissionError','FileNotFoundError','ProcessLookupError','OSError','ValueError','TypeError','AttributeError','RuntimeError','AssertionError','UnicodeDecodeError')else'OTHER_EXCEPTION'
 number=getattr(error,'errno',None)
 out['scan_error_errno']=number if type(number)is int and -65535<=number<=65535 else None
print(json.dumps(out))

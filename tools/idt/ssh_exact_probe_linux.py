"""Run real Bridge with only its remote command replaced; no UART or AWS."""
import os,sys,tempfile,time,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root));sys.path.insert(0,str(Path(__file__).resolve().parent))
from tools.aws.oidc_session import wsl_child_environment
from tools.idt.oidc_job import IDT_WSL_INPUTS
import run_transport as rt
from targets import get_target
original=dict(os.environ); interop=original.get("WSL_INTEROP")
base=wsl_child_environment(original,allow_names=IDT_WSL_INPUTS)
base["PATH"]=base.pop("RX_OIDC_IDT_WSL_PATH");base["HOME"]=base.pop("RX_OIDC_IDT_WSL_HOME")
os.environ.clear();os.environ.update(base)
probe=subprocess.run([rt.SSH,"-T","-o","BatchMode=yes","-o","ServerAliveInterval=10","-o","ServerAliveCountMax=3",get_target("rx72n-ethernet")["ssh_alias"],"printf idt_probe_ok"],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15)
print("PROBE short_code="+str(probe.returncode)+" marker="+str(int(probe.stdout==b"idt_probe_ok"))+" stderr="+str(int(bool(probe.stderr))),flush=True)
seen=[]
original_classifier=rt.ssh_failure_category
def classify(line):
 seen.append(line)
 return original_classifier(line)
rt.ssh_failure_category=classify
rt.bridge_command=lambda token,target: "python3 -u -c \"import sys;sys.stderr.write('IDT_UART_READY\\n');sys.stderr.flush();sys.stdin.buffer.read()\""
for label,restore in (("isolated",0),("interop",1),("inherited",2),("wslenv_empty",3)):
 os.environ.clear();os.environ.update(base)
 if restore == 1 and interop:os.environ["WSL_INTEROP"]=interop
 if restore == 2:os.environ.update({k:v for k,v in original.items() if not k.startswith("AWS_")})
 if restore == 3:os.environ["WSLENV"]=""
 with tempfile.TemporaryDirectory(prefix="idt-probe-") as d:
  try:
   seen.clear()
   b=rt.Bridge("0"*32,Path(d)/"capture",get_target("rx72n-ethernet"))
   for _ in range(100):
    if b.ready.is_set() or b.remote.poll() is not None:break
    time.sleep(0.05)
   ready=b.ready.is_set()
   try:b.close();closed=True
   except Exception:closed=False
   print("PROBE case="+label+" ready="+str(int(ready))+" close="+str(int(closed))+" code="+str(b.remote.returncode)+" classified="+str(int(b.ssh_failure is not None))+" stderr="+str(int(bool(seen)))+" syntax="+str(int(any("syntaxerror" in x.lower() for x in seen))),flush=True)
  except Exception as e: print("PROBE case="+label+" exception="+type(e).__name__,flush=True)
print("PROBE interop_present="+str(int(bool(interop))),flush=True)

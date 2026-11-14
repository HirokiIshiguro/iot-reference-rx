"""Synthetic read-only bridge probe; publishes fixed labels only."""
import os, subprocess, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
from tools.aws.oidc_session import FixedSession, wsl_bridge_environment
from tools.idt.host_profile import load_host_profile
import tools.idt.run_idt as run_idt
profile=load_host_profile(profile_path="C:/ai/codex/tools/venvs/rx72n-idt-windows/host-profile.json", environ={"WINDIR":"C:/Windows","ProgramFiles":"C:/Program Files"})
run_idt.HOST=profile
wsl_path=run_idt.wsl_path
base={k:os.environ[k] for k in ("SYSTEMROOT","WINDIR","USERPROFILE","HOME","TEMP","TMP","PATH","USERNAME","PROGRAMFILES","PROGRAMFILES(X86)","PROGRAMDATA","APPDATA","LOCALAPPDATA","COMSPEC","PATHEXT","SYSTEMDRIVE") if k in os.environ}
base.update({"HOME":os.environ["USERPROFILE"],"USERNAME":os.environ["USERNAME"],"COMSPEC":os.path.join(os.environ["WINDIR"],"System32","cmd.exe"),"SYSTEMDRIVE":"C:","PATHEXT":".COM;.EXE;.BAT;.CMD"})
base.update({"WSLENV":"", "CI":"true", "IDT_TARGET":"rx72n-ethernet", "IDT_WINDOWS_SSH":wsl_path(Path(profile["windows_ssh"])), "RX_OIDC_IDT_WSL_PATH":"/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin", "RX_OIDC_IDT_WSL_HOME":"/home/ishig"})
session=FixedSession("DUMMYACCESS", "DUMMYSECRET", "DUMMYSESSION", datetime.now(timezone.utc)+timedelta(hours=2))
allowed={"CI","IDT_TARGET","IDT_WINDOWS_SSH","RX_OIDC_IDT_WSL_PATH","RX_OIDC_IDT_WSL_HOME"}
env=wsl_bridge_environment(base,session,allow_names=allowed)
cmd=[str(Path("C:/Windows/System32/wsl.exe")),"-d",profile["wsl_distribution"],"--exec",profile["wsl_python"],wsl_path(Path(__file__).with_name("ssh_exact_probe_linux.py"))]
for label, keys in (("baseline",()), ("programdata",("PROGRAMDATA",))):
 launch_env=env.copy()
 for key in keys:
  if key in base: launch_env[key]=base[key]
 proc=subprocess.Popen(cmd,env=launch_env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 out,_=proc.communicate(timeout=90)
 print("PROBE launch="+label,flush=True)
 for line in out.decode("utf-8","replace").splitlines():
  if line.startswith("PROBE ") and len(line)<160 and all(c.isalnum() or c in " _=-" for c in line): print(line,flush=True)
 print("PROBE wsl_return="+str(proc.returncode),flush=True)
 if proc.returncode: raise SystemExit(1)

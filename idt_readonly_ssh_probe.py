"""Runner #3 read-only SSH comparison for IDT job 84552."""

from datetime import datetime, timedelta, timezone
import ntpath
import os
from pathlib import Path
import shlex
import subprocess
import sys

MARKER = b"idt-readonly-ssh-ok"
ALIAS = "rpi1"
OPTIONS = ["-T", "-o", "BatchMode=yes", "-o", "ServerAliveInterval=10", "-o", "ServerAliveCountMax=3"]
SSH_LINUX = "/mnt/c/Windows/System32/OpenSSH/ssh.exe"
WSL_HOME = "/home/ishig"
WSL_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"


def fixed_flags(stderr):
    lower = stderr.lower()
    flags = {
        "host_key": b"host key verification failed",
        "authentication": b"permission denied",
        "not_resolved": b"could not resolve hostname",
        "network_timeout": b"connection timed out",
        "network_refused": b"connection refused",
        "connection_closed": b"connection closed",
        "bad_config": b"bad configuration option",
        "invalid_argument": b"invalid argument",
        "interop": b"interop",
        "command_not_found": b"not found",
        "syntax": b"syntaxerror",
    }
    return ",".join(name for name, pattern in flags.items() if pattern in lower) or "none"


def probe(label, executable, remote_command, env):
    try:
        with subprocess.Popen(
            [executable, *OPTIONS, ALIAS, remote_command],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            bufsize=0, env=env,
        ) as process:
            # Bridge passes a live stdin pipe. The command exits by itself.
            try:
                process.wait(timeout=12)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
                print(f"{label} timeout", flush=True)
                return
            output, diagnostic = process.communicate()
    except OSError as error:
        print(f"{label} spawn_error errno={error.errno}", flush=True)
        return
    print(f"{label} exit={process.returncode} marker={output.strip() == MARKER} "
          f"stderr_present={bool(diagnostic)} flags={fixed_flags(diagnostic)}", flush=True)


def linux():
    sys.path.insert(0, str(Path(__file__).resolve().parent / "tools" / "idt"))
    from run_transport import bridge_command
    from targets import get_target
    from tools.aws.oidc_session import wsl_child_environment
    from tools.idt.oidc_job import IDT_WSL_INPUTS

    original = {key: value for key, value in os.environ.items()
                if not key.startswith("AWS_")}
    synthetic = dict(original,
                     AWS_ACCESS_KEY_ID="unused",
                     AWS_SECRET_ACCESS_KEY="unused",
                     AWS_SESSION_TOKEN="unused",
                     RX_OIDC_EXPIRATION_UTC=(datetime.now(timezone.utc) + timedelta(hours=2)).isoformat())
    isolated = wsl_child_environment(synthetic, allow_names=IDT_WSL_INPUTS)
    isolated.update(HOME=WSL_HOME, PATH=WSL_PATH)
    isolated = {key: value for key, value in isolated.items() if not key.startswith("AWS_")}
    with_interop = isolated.copy()
    if "WSL_INTEROP" in original:
        with_interop["WSL_INTEROP"] = original["WSL_INTEROP"]
    simple = "printf '%s\\n' idt-readonly-ssh-ok"

    # Carry the same quoted compressed payload, replacing its execution tail
    # with a read-only parse. No bridge code or helper modules are executed.
    command = bridge_command("probe", get_target("rx72n-ethernet"))
    python, unbuffered, flag, bootstrap, token, target = shlex.split(command)
    parse_only, tail = bootstrap.split("; mods=[", 1)
    assert "exec(p['bridge'])" in tail
    parse_only += ("; import ast; ast.parse(p['bridge']); "
                   "[ast.parse(source) for source in p['modules'].values()]; "
                   "print('idt-readonly-ssh-ok')")
    long_command = shlex.join([python, unbuffered, flag, parse_only, token, target])
    print(f"linux_interop_present={'WSL_INTEROP' in original} long_command_bytes={len(long_command)}", flush=True)
    probe("wsl_original_short", SSH_LINUX, simple, original)
    probe("wsl_isolated_short", SSH_LINUX, simple, isolated)
    probe("wsl_isolated_long", SSH_LINUX, long_command, isolated)
    if "WSL_INTEROP" in original:
        probe("wsl_isolated_plus_interop_long", SSH_LINUX, long_command, with_interop)
    probe("wsl_original_long", SSH_LINUX, long_command, original)


def windows():
    win = os.environ["WINDIR"]
    ssh = ntpath.join(win, "System32", "OpenSSH", "ssh.exe")
    wsl = ntpath.join(win, "System32", "wsl.exe")
    # Same host profile as the pilot, with no credentials or token variables.
    profile = r"C:\Users\ishig"
    env = {
        "SYSTEMROOT": win, "WINDIR": win, "USERPROFILE": profile, "HOME": profile,
        "USERNAME": "ishig",
        "TEMP": ntpath.join(profile, "AppData", "Local", "Temp"),
        "TMP": ntpath.join(profile, "AppData", "Local", "Temp"),
        "PROGRAMFILES": r"C:\Program Files", "PROGRAMFILES(X86)": r"C:\Program Files (x86)",
        "PROGRAMDATA": r"C:\ProgramData",
        "APPDATA": ntpath.join(profile, "AppData", "Roaming"),
        "LOCALAPPDATA": ntpath.join(profile, "AppData", "Local"),
        "COMSPEC": ntpath.join(win, "System32", "cmd.exe"),
        "PATHEXT": ".COM;.EXE;.BAT;.CMD", "SYSTEMDRIVE": "C:",
        "PATH": r"C:\Windows\System32;C:\Windows;C:\Windows\System32\OpenSSH",
        "WSLENV": "",
    }
    probe("windows_direct", ssh, "printf '%s\\n' idt-readonly-ssh-ok", env)
    wsl_script = subprocess.check_output(
        [wsl, "-d", "Ubuntu", "--exec", "wslpath", "-a", "-u", str(Path(__file__).resolve())],
        text=True, timeout=10,
    ).strip()
    result = subprocess.run(
        [wsl, "-d", "Ubuntu", "--exec", "python3", wsl_script],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=85, check=False,
    )
    # Only lines generated by this script are forwarded.
    for line in result.stdout.decode("utf-8", "replace").splitlines():
        if line.startswith(("linux_interop_present=", "wsl_original_", "wsl_isolated_")):
            print(line, flush=True)
    print(f"wsl_launcher_exit={result.returncode}", flush=True)
    return result.returncode


if __name__ == "__main__":
    if os.name == "nt":
        raise SystemExit(windows())
    linux()

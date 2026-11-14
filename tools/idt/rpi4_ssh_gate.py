#!/usr/bin/python3 -I
"""Proposed forced SSH command for a dedicated RPi paired-build account.

Installation and key authorization are separate host-administration actions.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import stat
import sys


COMMAND = re.compile(r'python3 -u "\$HOME/\.cache/idt-rx72n-pair/([0-9]{1,20})/rpi4_pair_agent\.py" attach \1', re.ASCII)


def checked_agent(command, home, uid):
    match = COMMAND.fullmatch(command)
    if match is None:
        raise ValueError("unexpected paired SSH command")
    root = Path(home).resolve(strict=True)
    parent = root / ".cache/idt-rx72n-pair"
    session = parent / match.group(1)
    for directory in (parent, session):
        info = directory.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != uid or stat.S_IMODE(info.st_mode) & 0o077
                or root not in directory.resolve(strict=True).parents):
            raise ValueError("invalid paired SSH session")
    for name in ("rpi4_pair_agent.py", "rpi4_pair.py"):
        path = session / name
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != uid or stat.S_IMODE(info.st_mode) != 0o600
                or path.resolve(strict=True).parent != session.resolve(strict=True)):
            raise ValueError("invalid paired SSH executable")
    return session / "rpi4_pair_agent.py", match.group(1)


def main():
    import pwd
    uid = os.geteuid()
    account = pwd.getpwuid(uid)
    if account.pw_name != "gitlab-runner-idt-rx":
        raise ValueError("unexpected paired SSH account")
    path, session = checked_agent(os.environ.get("SSH_ORIGINAL_COMMAND", ""), account.pw_dir, uid)
    os.execv("/usr/bin/python3", ["python3", "-E", "-s", "-u", str(path), "attach", session])


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("Paired SSH command rejected", file=sys.stderr)
        raise SystemExit(1) from None

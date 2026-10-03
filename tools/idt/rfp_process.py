"""Bounded Linux RFP supervision; caller must already own bench and RFP locks.

An unsafe sentinel is deliberately persistent. Only a human recovery procedure
may remove it after proving that no programmer process can still access a board.
No command arguments or process command lines are recorded in the sentinel.
"""
import json
import math
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass


class UnsafeRfpError(RuntimeError):
    """Hardware ownership cannot safely be released or reused."""


def _sentinel(target):
    return Path(str(target['rfp_lock']) + '.unsafe.json')


def raise_if_rfp_unsafe(target):
    """Fail closed for every existing sentinel, including a dangling symlink."""
    try:
        os.lstat(_sentinel(target))
    except FileNotFoundError:
        return
    except OSError:
        raise UnsafeRfpError('Cannot inspect the persistent RFP unsafe sentinel') from None
    raise UnsafeRfpError('Persistent RFP unsafe sentinel requires manual recovery')


def _mark_unsafe(target, pgid, reason):
    """Create without following/replacing files; sync both file and directory."""
    path = _sentinel(target)
    parent_fd = None
    descriptor = None
    try:
        if not stat.S_ISDIR(os.lstat(path.parent).st_mode):
            raise OSError('Unsafe sentinel directory')
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0)
        if os.open in os.supports_dir_fd:
            parent_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            descriptor = os.open(path.name, flags, 0o600, dir_fd=parent_fd)
        else:  # Allows filesystem-only unit tests on Windows; supervision is Linux-only.
            descriptor = os.open(path, flags, 0o600)
        raw = json.dumps({'schema_version': 1, 'target_id': target['id'],
                          'process_group': pgid, 'reason': reason}, sort_keys=True).encode() + b'\n'
        with os.fdopen(descriptor, 'wb') as output:
            descriptor = None
            output.write(raw)
            output.flush()
            os.fsync(output.fileno())
        if parent_fd is not None:
            os.fsync(parent_fd)
    except FileExistsError:
        # Any pre-existing file, directory or symlink already blocks reuse.
        return
    except OSError:
        raise UnsafeRfpError('RFP termination is unproved; unsafe sentinel could not be persisted') from None
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if parent_fd is not None:
            os.close(parent_fd)


@dataclass(frozen=True)
class _Process:
    pid: int
    ppid: int
    pgrp: int
    session: int
    starttime: int
    uids: tuple


def _proc_visible():
    # hidepid can omit other users' processes entirely: enumeration alone then
    # cannot establish that a sudo monitor/root programmer has terminated.
    mounts = Path('/proc/self/mountinfo').read_text().splitlines()
    for line in mounts:
        fields = line.split()
        separator = fields.index('-')
        if fields[4] == '/proc' and fields[separator + 1] == 'proc':
            options = fields[5].split(',') + fields[separator + 3].split(',')
            if any(option.startswith('hidepid=') and option != 'hidepid=0' for option in options):
                raise OSError('Restricted process visibility')
            return
    raise OSError('Process visibility is unknown')


def _proc_snapshot():
    _proc_visible()
    result = {}
    for path in Path('/proc').iterdir():
        if not path.name.isdecimal():
            continue
        try:
            raw = (path / 'stat').read_text()
            # comm may contain spaces and parentheses; subsequent fields begin
            # after the final closing parenthesis (proc_pid_stat(5)).
            fields = raw[raw.rindex(')') + 2:].split()
            pid = int(path.name)
            uids = next(line.split()[1:] for line in (path / 'status').read_text().splitlines()
                        if line.startswith('Uid:'))
            if len(uids) != 4:
                raise ValueError('Unknown process credentials')
            result[pid] = _Process(pid, int(fields[1]), int(fields[2]), int(fields[3]),
                                   int(fields[19]), tuple(map(int, uids)))
        except FileNotFoundError:
            pass  # Process exited during enumeration.
    return result


def _members(pgid, known):
    snapshot = _proc_snapshot()
    for pid in set(known).intersection(snapshot):
        process = snapshot[pid]
        if known[pid] != process.starttime:
            if pid == pgid or process.pgrp == pgid or process.session == pgid:
                raise OSError('Owned process identity changed')
            del known[pid]  # The tracked child ended and its PID was reused elsewhere.
    selected = {pid: process for pid, process in snapshot.items()
                if process.pgrp == pgid or process.session == pgid or
                known.get(pid) == process.starttime}
    # sudo with a pty may put its monitor/command in a different group/session.
    # Retain observed descendants by PID plus starttime even after reparenting.
    while True:
        children = {pid: process for pid, process in snapshot.items()
                    if pid not in selected and process.ppid in selected}
        if not children:
            break
        selected.update(children)
    known.update({pid: process.starttime for pid, process in selected.items()})
    return selected


def _unsafe(target, pgid, reason):
    _mark_unsafe(target, pgid, reason)
    raise UnsafeRfpError('RFP termination is unproved; persistent unsafe sentinel blocks reuse')


def _wait_empty(process, known, deadline):
    while True:
        process.poll()  # Reap the direct child as well as checking descendants.
        members = _members(process.pid, known)
        if process.returncode is not None and not members:
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        time.sleep(min(0.05, remaining))


@contextmanager
def _cleanup_signals():
    handlers = []
    try:
        if threading.current_thread() is threading.main_thread():
            for number in (signal.SIGINT, signal.SIGTERM):
                handlers.append((number, signal.signal(number, signal.SIG_IGN)))
        yield
    finally:
        for number, handler in reversed(handlers):
            signal.signal(number, handler)


def _stop_owned(process, known, target, deadline, reserve):
    try:
        _members(process.pid, known)  # Refuse signaling a reused/unknown group.
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except PermissionError:
            # A mixed-UID group can still receive TERM at its owned sudo parent,
            # which forwards it. The final visibility check remains mandatory.
            pass
        if _wait_empty(process, known, deadline - reserve):
            return
        members = _members(process.pid, known)
        own_uid = os.geteuid()
        if any(member.uids != (own_uid,) * 4 for member in members.values()):
            # Killing the unprivileged sudo monitor can strand its privileged
            # command. Never send a blind group SIGKILL or use sudo to kill it.
            _unsafe(target, process.pid, 'privileged-process-remains')
        for pid, member in members.items():
            # Recheck identity/credentials immediately before an individual kill.
            current = _members(process.pid, known).get(pid)
            if current is None:
                continue
            if current != member or current.uids != (own_uid,) * 4:
                _unsafe(target, process.pid, 'process-identity-changed')
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if not _wait_empty(process, known, deadline):
            _unsafe(target, process.pid, 'process-remains-after-kill')
    except UnsafeRfpError:
        raise
    except (OSError, ValueError, IndexError, StopIteration):
        _unsafe(target, process.pid, 'process-visibility-unknown')
    except BaseException:
        _unsafe(target, process.pid, 'process-termination-interrupted')


def _stop(process, known, target, deadline, reserve):
    try:
        with _cleanup_signals():
            _stop_owned(process, known, target, deadline, reserve)
    except UnsafeRfpError:
        raise
    except BaseException:
        _unsafe(target, process.pid, 'process-termination-interrupted')


def run_guarded(command, *, target, timeout, quiet=False, privileged=True):
    """Run argv with inherited stdio and check=True semantics under owned locks.

    timeout covers the entire command and cleanup. A portion (up to five seconds)
    is reserved for TERM, same-UID KILL, and reaping. An unsafe exception means
    callers must preserve their unsafe ownership state instead of reporting a
    normal release/reset. A privileged command interrupted before normal exit
    always leaves a sentinel, even if all observed processes terminated: a sudo
    child could have changed sessions and reparented before the first snapshot.
    Success assumes the normally exiting sudo parent waited for its command.
    This helper neither acquires nor releases either lock. quiet uses DEVNULL,
    never PIPE, so output cannot block termination or persist command secrets.
    """
    if isinstance(command, (str, bytes)) or not command:
        raise ValueError('RFP supervision requires a nonempty argv sequence')
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('RFP supervision requires a positive finite timeout')
    if not isinstance(quiet, bool) or not isinstance(privileged, bool):
        raise ValueError('RFP supervision flags must be boolean')
    raise_if_rfp_unsafe(target)
    if not sys.platform.startswith('linux'):
        raise RuntimeError('RFP process supervision requires Linux /proc')
    started = time.monotonic()
    deadline = started + timeout
    cleanup = min(5.0, timeout / 2)
    reserve = min(1.0, cleanup / 3)
    try:
        _proc_snapshot()  # Verify visibility before starting a hardware command.
    except (OSError, ValueError, IndexError, StopIteration):
        _unsafe(target, None, 'process-visibility-unknown')
    output = {'stdin': subprocess.DEVNULL, 'stdout': subprocess.DEVNULL,
              'stderr': subprocess.DEVNULL} if quiet else {}
    try:
        process = subprocess.Popen(command, start_new_session=True, **output)
    except KeyboardInterrupt:
        _unsafe(target, None, 'process-launch-interrupted')
    known = {}
    try:
        if not _wait_empty(process, known, deadline - cleanup):
            raise subprocess.TimeoutExpired(command, timeout)
    except BaseException:
        _stop(process, known, target, deadline, reserve)
        if privileged:
            _unsafe(target, process.pid, 'privileged-command-interrupted')
        raise
    result = subprocess.CompletedProcess(command, process.returncode)
    result.check_returncode()
    return result

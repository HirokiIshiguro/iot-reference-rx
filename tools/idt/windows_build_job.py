"""Contain an owned Windows build subprocess and its descendants in a Job.

The child must wait for ``go`` on stdin before starting build work. On failure
this module reports whether the job became empty; callers must retain private
files whenever termination cannot be established.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
import subprocess
import time


class UnconfirmedStop(RuntimeError):
    """The owned process tree could not be confirmed stopped."""


class BasicLimits(ctypes.Structure):
    _fields_ = [("process_time", ctypes.c_longlong), ("job_time", ctypes.c_longlong),
                ("flags", wintypes.DWORD), ("min_working_set", ctypes.c_size_t),
                ("max_working_set", ctypes.c_size_t), ("active_limit", wintypes.DWORD),
                ("affinity", ctypes.c_size_t), ("priority", wintypes.DWORD), ("scheduling", wintypes.DWORD)]


class IoCounters(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ulonglong) for name in
                ("read_ops", "write_ops", "other_ops", "read_bytes", "write_bytes", "other_bytes")]


class ExtendedLimits(ctypes.Structure):
    _fields_ = [("basic", BasicLimits), ("io", IoCounters), ("process_memory", ctypes.c_size_t),
                ("job_memory", ctypes.c_size_t), ("peak_process_memory", ctypes.c_size_t),
                ("peak_job_memory", ctypes.c_size_t)]


class Accounting(ctypes.Structure):
    _fields_ = [("total_user", ctypes.c_longlong), ("total_kernel", ctypes.c_longlong),
                ("period_user", ctypes.c_longlong), ("period_kernel", ctypes.c_longlong),
                ("page_faults", wintypes.DWORD), ("total_processes", wintypes.DWORD),
                ("active_processes", wintypes.DWORD), ("terminated_processes", wintypes.DWORD)]


def _kernel():
    if os.name != "nt":
        raise RuntimeError("Windows Job Objects require Windows")
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.CreateJobObjectW.argtypes = (ctypes.c_void_p, wintypes.LPCWSTR)
    k.CreateJobObjectW.restype = wintypes.HANDLE
    k.SetInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD)
    k.SetInformationJobObject.restype = wintypes.BOOL
    k.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
    k.AssignProcessToJobObject.restype = wintypes.BOOL
    k.QueryInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p)
    k.QueryInformationJobObject.restype = wintypes.BOOL
    k.TerminateJobObject.argtypes = (wintypes.HANDLE, wintypes.UINT)
    k.TerminateJobObject.restype = wintypes.BOOL
    k.CloseHandle.argtypes = (wintypes.HANDLE,)
    k.CloseHandle.restype = wintypes.BOOL
    return k


def _checked(value):
    if not value:
        raise ctypes.WinError(ctypes.get_last_error())
    return value


def _active(kernel, job):
    info = Accounting()
    _checked(kernel.QueryInformationJobObject(job, 1, ctypes.byref(info), ctypes.sizeof(info), None))
    return info.active_processes


def _wait_idle(kernel, job, seconds=10):
    deadline = time.monotonic() + seconds
    while _active(kernel, job):
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.05)
    return True


def _stop_and_confirm(kernel, job, seconds=10):
    _checked(kernel.TerminateJobObject(job, 1))
    if not _wait_idle(kernel, job, seconds):
        raise UnconfirmedStop("Windows build descendants did not stop")


def run_managed(command, *, timeout, env):
    if not isinstance(timeout, int) or isinstance(timeout, bool) or not 0 < timeout <= 10800:
        raise ValueError("invalid reviewed Windows build budget")
    kernel = _kernel()
    job = _checked(kernel.CreateJobObjectW(None, None))
    limits = ExtendedLimits()
    limits.basic.flags = 0x00002000  # KILL_ON_JOB_CLOSE, no breakaway flags.
    process = None
    assigned = False
    try:
        _checked(kernel.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)))
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, env=env,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        # The child waits on stdin before taking the lease or invoking a tool.
        _checked(kernel.AssignProcessToJobObject(job, wintypes.HANDLE(int(process._handle))))
        assigned = True
        process.stdin.write(b"go\n")
        process.stdin.close()
        code = process.wait(timeout=timeout)
        if code != 0:
            raise subprocess.CalledProcessError(code, command)
        if not _wait_idle(kernel, job):
            raise RuntimeError("Windows build left active descendants")
    except BaseException as error:
        if assigned:
            try:
                _stop_and_confirm(kernel, job)
                process.wait(timeout=10)
            except BaseException:
                raise UnconfirmedStop("Windows build termination is unconfirmed") from None
        elif process is not None and process.poll() is None:
            # The unassigned child has not received the go signal.
            process.kill()
            process.wait()
        raise error
    finally:
        if process is not None and process.stdin is not None and not process.stdin.closed:
            process.stdin.close()
        kernel.CloseHandle(job)

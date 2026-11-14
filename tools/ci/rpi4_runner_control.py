#!/usr/bin/env python3
"""Fixed CPU control for before/overlap/after Runner #28 checks."""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import select
import stat
import time


def marker_ready(path):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 995:
        raise RuntimeError('unexpected overlap marker')
    return True


def wait_for_sample(path):
    libc = ctypes.CDLL(None, use_errno=True)
    fd = libc.inotify_init1(os.O_CLOEXEC | os.O_NONBLOCK)
    if fd < 0:
        raise OSError(ctypes.get_errno(), 'inotify_init1')
    try:
        if libc.inotify_add_watch(fd, b'/tmp', 0x00000100 | 0x00000080) < 0:
            raise OSError(ctypes.get_errno(), 'inotify_add_watch')
        deadline = time.monotonic() + 120
        while not marker_ready(path):
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([fd], [], [], remaining)[0]:
                raise RuntimeError('sample start marker not observed')
            os.read(fd, 65536)
    finally:
        os.close(fd)


def snapshot():
    with open('/proc/stat', encoding='ascii') as f:
        values = [int(x) for x in f.readline().split()[1:]]
    memory = {}
    with open('/proc/meminfo', encoding='ascii') as f:
        for line in f:
            key, _, value = line.partition(':')
            if key in ('MemAvailable', 'SwapTotal', 'SwapFree'):
                memory[key + '_KiB'] = int(value.split()[0])
    return {'total': sum(values), 'idle': values[3] + values[4], **memory}


def main():
    phase = os.environ.get('MEASUREMENT_PHASE')
    if (os.environ.get('CI_PROJECT_ID') != '38' or os.environ.get('CI_RUNNER_ID') != '26'
            or os.environ.get('CI_COMMIT_REF_PROTECTED') != 'true'
            or phase not in ('before', 'overlap', 'after') or os.getuid() != 999):
        raise RuntimeError('unexpected fixed-control context')
    pipeline_id = os.environ.get('CI_PIPELINE_ID', '')
    if not pipeline_id.isdecimal():
        raise RuntimeError('invalid pipeline id')
    if phase == 'overlap':
        wait_for_sample(Path('/tmp') / ('idt-runner28-overlap-' + pipeline_id + '.ready'))
    before = snapshot()
    start_wall, start_cpu, start_epoch = time.monotonic(), time.process_time(), time.time()
    for _ in range(100):
        result = hashlib.pbkdf2_hmac('sha256', b'fixed-control', b'fixed-salt', 200000)
    end_epoch = time.time()
    elapsed, cpu = time.monotonic() - start_wall, time.process_time() - start_cpu
    after = snapshot()
    total = after['total'] - before['total']
    busy = total - (after['idle'] - before['idle'])
    print('FIXED_CONTROL=' + json.dumps({'phase': phase, 'start_epoch': start_epoch,
          'end_epoch': end_epoch, 'elapsed_seconds': round(elapsed, 3), 'cpu_seconds': round(cpu, 3),
          'host_busy_percent': round(100 * busy / total, 2) if total > 0 else None,
          'memory_before': {k: v for k, v in before.items() if k.endswith('_KiB')},
          'memory_after': {k: v for k, v in after.items() if k.endswith('_KiB')},
          'result_sha256': hashlib.sha256(result).hexdigest()}), flush=True)


if __name__ == '__main__':
    main()

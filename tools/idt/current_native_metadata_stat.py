"""UNREADY: metadata only for the normal owner's original 11947 run, never private bodies."""
from __future__ import annotations
import argparse, ctypes, hashlib, json, os, re, stat, sys
from datetime import datetime
from pathlib import Path

EXECUTION_READY = True
HOST_PROFILE_SHA = 'aa63af1c1d100e577a0bc6413e92b822be247dcc6cc362f6d9ccd348dc992792'
JOB_START = '2026-10-31T05:13:07.504+09:00'
JOB_FINISH = '2026-10-31T06:02:28.300+09:00'
RESULT_NAME = 'current11947-file-stat.json'
INTENT_NAME = 'current11947-file-stat-intent.json'
ACCEPTED_OWNERS = ('TOKEN_USER', 'TOKEN_DEFAULT_OWNER')

class Hold(RuntimeError):
    pass

def need(ok, code):
    if not ok:
        raise Hold(code)

def canonical_code(raw):
    value = raw.replace(b'\r\n', b'\n')
    need(b'\r' not in value and not value.startswith(b'\xef\xbb\xbf'), 'CODE_ENCODING')
    value.decode('utf-8', 'strict')
    return value

def reparse(info):
    return bool(stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400)

def unlinked(path):
    for item in (path, *path.parents):
        need(not reparse(item.lstat()), 'LINKED_PATH_REJECTED')

def within_window(value):
    return datetime.fromisoformat(JOB_START).timestamp() <= value <= datetime.fromisoformat(JOB_FINISH).timestamp()

def windows_owner_relation(path):
    """Compare owner to effective TokenUser/TokenOwner; never stringify or export a SID."""
    need(os.name == 'nt', 'NORMAL_WINDOWS_OWNER_REQUIRED')
    from ctypes import wintypes as w
    a = ctypes.WinDLL('advapi32', use_last_error=True)
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    a.GetNamedSecurityInfoW.argtypes = [w.LPWSTR, w.DWORD, w.DWORD, ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
    a.GetNamedSecurityInfoW.restype = w.DWORD
    a.OpenThreadToken.argtypes = [w.HANDLE, w.DWORD, w.BOOL, ctypes.POINTER(w.HANDLE)]
    a.OpenThreadToken.restype = w.BOOL
    a.OpenProcessToken.argtypes = [w.HANDLE, w.DWORD, ctypes.POINTER(w.HANDLE)]
    a.OpenProcessToken.restype = w.BOOL
    a.GetTokenInformation.argtypes = [w.HANDLE, w.DWORD, ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.DWORD)]
    a.GetTokenInformation.restype = w.BOOL
    a.EqualSid.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    a.EqualSid.restype = w.BOOL
    k.GetCurrentProcess.restype = w.HANDLE
    k.GetCurrentThread.restype = w.HANDLE
    k.CloseHandle.argtypes = [w.HANDLE]
    k.LocalFree.argtypes = [ctypes.c_void_p]
    owner, descriptor, token = ctypes.c_void_p(), ctypes.c_void_p(), w.HANDLE()
    need(a.GetNamedSecurityInfoW(str(path), 1, 1, ctypes.byref(owner), None, None, None, ctypes.byref(descriptor)) == 0, 'OWNER_METADATA_DENIED')
    try:
        if not a.OpenThreadToken(k.GetCurrentThread(), 8, True, ctypes.byref(token)):
            need(ctypes.get_last_error() == 1008 and a.OpenProcessToken(k.GetCurrentProcess(), 8, ctypes.byref(token)), 'EFFECTIVE_TOKEN_UNAVAILABLE')
        matches = []
        for information_class in (1, 4):
            size = w.DWORD()
            a.GetTokenInformation(token, information_class, None, 0, ctypes.byref(size))
            need(0 < size.value <= 65536, 'TOKEN_METADATA_BOUND')
            data = ctypes.create_string_buffer(size.value)
            need(a.GetTokenInformation(token, information_class, data, size.value, ctypes.byref(size)), 'TOKEN_METADATA_DENIED')
            sid = ctypes.cast(data, ctypes.POINTER(ctypes.c_void_p))[0]
            matches.append(bool(a.EqualSid(owner, sid)))
        return 'TOKEN_USER' if matches[0] else 'TOKEN_DEFAULT_OWNER' if matches[1] else 'OTHER'
    finally:
        if token:
            k.CloseHandle(token)
        if descriptor:
            k.LocalFree(descriptor)

def select_runtime(root):
    unlinked(root)
    need(root.is_dir(), 'RUNTIME_ROOT_UNAVAILABLE')
    entries = list(root.iterdir())
    need(len(entries) <= 4096, 'RUNTIME_DIRECTORY_BOUND')
    candidates = []
    for path in entries:
        if re.fullmatch(r'run-[a-z0-9_]{8}', path.name) is None:
            continue
        info = path.lstat()
        if not within_window(getattr(info, 'st_birthtime', info.st_ctime)):
            continue
        need(stat.S_ISDIR(info.st_mode), 'RUNTIME_DIRECTORY_SHAPE')
        unlinked(path)
        if windows_owner_relation(path) in ACCEPTED_OWNERS:
            candidates.append(path)
    need(len(candidates) == 1, 'ORIGINAL_RUNTIME_MISSING_OR_AMBIGUOUS')
    return candidates[0]

def metadata(path, limit):
    # Inspect fixed path metadata only; the file itself is never opened by Python.
    unlinked(path.parent)
    info = path.lstat()
    out = {
        'status': 'OBSERVED', 'regular': bool(stat.S_ISREG(info.st_mode)),
        'reparse': reparse(info), 'python_link_count': int(info.st_nlink),
        'size_bytes': int(info.st_size), 'size_limit_bytes': limit,
        'creation_in_original_job_window': bool(within_window(getattr(info, 'st_birthtime', info.st_ctime))),
        'mtime_in_original_job_window': bool(within_window(info.st_mtime)),
        'python_link_count_is_one': bool(info.st_nlink == 1),
        'size_within_existing_limit': bool(info.st_size <= limit),
        'owner_relation': 'UNOBSERVED', 'owner_accepted': False,
    }
    out['original_owned_file_shape_passes'] = bool(out['regular'] and out['python_link_count_is_one'] and out['size_within_existing_limit'])
    if out['regular'] and not out['reparse']:
        out['owner_relation'] = windows_owner_relation(path)
        out['owner_accepted'] = out['owner_relation'] in ACCEPTED_OWNERS
    after = path.lstat()
    fields = ('st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_file_attributes')
    need(all(getattr(info, key, None) == getattr(after, key, None) for key in fields), 'FILE_METADATA_CHANGED')
    unlinked(path.parent)
    return out

def save(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--reviewed-code-sha256')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = {'schema_version': 1, 'diagnostic_only': True, 'original_project': 38, 'original_pipeline': 11947, 'original_job': 73384, 'result': 'HOLD', 'reason': 'ADMISSION_HOLD', 'reference_method': 'OWNER_AND_JOB_TIME_ONLY', 'private_source_target_dependency_provenance_verified': False, 'private_file_data_handles_opened': 0, 'private_body_read_attempts': 0, 'private_XML_read_attempts': 0, 'raw_private_content_saved': False, 'private_body_or_path_or_hash_exported': False, 'native_tests_run': False, 'RPi_actions': 0, 'SDK_executions': 0, 'WSL_executions': 0, 'AWS_operations': 0, 'functional_PASS_claimed': False, 'root_cause_identified': False, 'provenance': {'status': 'UNOBSERVED'}, 'transport_result': {'status': 'UNOBSERVED'}}
    destination = None
    try:
        need(args.execute and EXECUTION_READY and sys.flags.isolated and sys.dont_write_bytecode and __debug__, 'UNREADY_OR_NOT_ISOLATED')
        own = Path(__file__).absolute()
        source = Path(os.environ.get('CI_PROJECT_DIR', '')).absolute()
        need(os.name == 'nt' and os.environ.get('CI_PROJECT_ID') == '38' and os.environ.get('CI_PIPELINE_SOURCE') == 'api' and os.environ.get('GITLAB_USER_ID') == '38', 'NORMAL_OWN_WINDOWS_CI_REQUIRED')
        need(os.environ.get('CI_JOB_NAME') == 'inspect_rx65n_native11947_file_stat' and os.environ.get('READ_CURRENT_NATIVE11947_FILE_STAT') == 'true' and os.environ.get('CI_COMMIT_REF_NAME') == 'codex/184-ci11947-file-stat-readonly', 'EXACT_DIAGNOSTIC_SELECTOR')
        need(all(re.fullmatch('[1-9][0-9]{0,11}', os.environ.get(key, '')) for key in ('CI_PIPELINE_ID', 'CI_JOB_ID')) and int(os.environ['CI_PIPELINE_ID']) not in (11947, 11954) and int(os.environ['CI_JOB_ID']) not in (73384, 73390), 'NEW_DIAGNOSTIC_IDS')
        need(re.fullmatch('[0-9a-f]{40}', os.environ.get('CI_COMMIT_SHA', '')) is not None, 'DIAGNOSTIC_SOURCE_REQUIRED')
        need(own == source / 'tools/idt/current_native_metadata_stat.py', 'DIAGNOSTIC_CODE_LOCATION')
        unlinked(own)
        need(re.fullmatch('[0-9a-f]{64}', args.reviewed_code_sha256 or '') is not None and hashlib.sha256(canonical_code(own.read_bytes())).hexdigest() == args.reviewed_code_sha256, 'ACTUAL_REVIEWED_CODE')
        desired = source / 'artifacts/idt' / RESULT_NAME
        need(args.output.absolute() == desired, 'PUBLIC_OUTPUT_SCOPE')
        unlinked(source)
        for directory in (source / 'artifacts', desired.parent):
            if not directory.exists():
                directory.mkdir()
            unlinked(directory)
        need(not desired.exists(), 'PUBLIC_RESULT_ALREADY_EXISTS')
        destination = desired
        save(desired.with_name(INTENT_NAME), {'schema_version': 1, 'diagnostic_only': True, 'original_pipeline': 11947, 'original_job': 73384, 'maximum_private_body_read_attempts': 0, 'maximum_private_XML_read_attempts': 0, 'private_file_data_handles_opened': 0, 'native_tests_run': False, 'RPi_actions': 0, 'SDK_executions': 0, 'WSL_executions': 0, 'AWS_operations': 0})
        helper = source / 'tools/idt/host_profile.py'
        unlinked(helper)
        data = canonical_code(helper.read_bytes())
        need(len(data) <= 512 * 1024 and hashlib.sha256(data).hexdigest() == HOST_PROFILE_SHA, 'CURRENT_PROFILE_HELPER_SOURCE')
        ns = {'__name__': 'reviewed_normal_host_profile', '__file__': str(helper)}
        exec(compile(data, str(helper), 'exec'), ns)
        profile = ns['load_host_profile']()
        runtime = select_runtime(Path(profile['runtime_root']))
        result['provenance'] = metadata(runtime / 'source-provenance.json', 2 * 1024 * 1024)
        result['transport_result'] = metadata(runtime / 'execution/transport-result.json', 512 * 1024)
        need(all(not item['reparse'] for item in (result['provenance'], result['transport_result'])), 'FIXED_FILE_REPARSE_HOLD')
        need(all(item['owner_accepted'] for item in (result['provenance'], result['transport_result'])), 'FIXED_FILE_OWNER_HOLD')
        result.update(result='METADATA_STAT_OBSERVED', reason='OBSERVED', normal_creator_owner_runtime=True, unique_original_time_runtime=True, source_helper_checked=True)
    except BaseException as error:
        code = str(error) if type(error) is Hold and re.fullmatch('[A-Z][A-Z0-9_]{0,80}', str(error)) else 'DIAGNOSTIC_HOLD'
        result.update(result='HOLD', reason=code)
    if destination is not None:
        try:
            save(destination, result)
        except BaseException:
            result.update(result='HOLD', reason='PUBLIC_RESULT_WRITE_HOLD')
    print(json.dumps(result, sort_keys=True))
    return 0 if result['result'] == 'METADATA_STAT_OBSERVED' else 2

if __name__ == '__main__':
    raise SystemExit(main())

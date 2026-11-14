#!/usr/bin/env python3
"""Run the official device-free IDT sample on ARM64; this is not Transport."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.idt.idt_bundle import verify_archive_digest, verify_install

ARCHIVE_ENV = 'IDT_RPI4_SAMPLE_ARCHIVE'
EXPECTED_CI_SHA256 = '9734f15e5cb858dd22178d5e9d22e689b2e2e6e25e3392c93a7c17183e656b1a'
ALLOWED_CHANGES = {'.gitlab-ci.yml', 'tools/idt/rpi4_sample_smoke.py', 'docs/idt-rpi4-sample.md'}
PACKAGES = {
    'qemu-user-static=1:8.2.2+ds-0ubuntu1.18': '0565144632acc09b92da93e5ef9a2f44fa092797c5b0949744351b184ad948a8',
    'libc6-amd64-cross=2.39-0ubuntu8cross1': 'db98738caedbc18b257f59c0d5485023ff6eee7232a7682f8ece02f277bb521a',
}


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def stop(signum, _frame):
    raise InterruptedError('job interrupted: ' + str(signum))


def main():
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, stop)
    # This dedicated MR profile suppresses normal lanes only for this narrow diff.
    default_branch = os.environ.get('CI_DEFAULT_BRANCH', '')
    if not default_branch:
        raise RuntimeError('default branch is unavailable')
    fetch = subprocess.run(['git', 'fetch', '--no-tags', 'origin', default_branch], cwd=ROOT,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
    if fetch.returncode:
        raise RuntimeError('could not obtain the default-branch comparison point')
    merge_base = subprocess.check_output(['git', 'merge-base', 'HEAD', 'FETCH_HEAD'], cwd=ROOT, text=True).strip()
    changed = subprocess.check_output(['git', 'diff', '--name-only', '-z', merge_base, 'HEAD'], cwd=ROOT)
    source = os.environ.get('CI_PIPELINE_SOURCE', '')
    branch = os.environ.get('CI_MERGE_REQUEST_SOURCE_BRANCH_NAME', '') if source == 'merge_request_event' else os.environ.get('CI_COMMIT_BRANCH', '')
    if branch == '207-rpi4-idt-sample' and source in ('merge_request_event', 'api', 'web'):
        if not set(changed.decode('utf-8').split('\0')) - {''} <= ALLOWED_CHANGES:
            raise RuntimeError('sample profile cannot cover unrelated changes')
        if digest(ROOT / '.gitlab-ci.yml') != EXPECTED_CI_SHA256:
            raise RuntimeError('sample profile requires the reviewed CI configuration')
    elif (branch == default_branch and source in ('api', 'web')
          and os.environ.get('RUN_RPI4_IDT_SAMPLE') == 'true'):
        head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        fetched = subprocess.check_output(['git', 'rev-parse', 'FETCH_HEAD'], cwd=ROOT, text=True).strip()
        if head != fetched:
            raise RuntimeError('main sample requires current default-branch HEAD')
    else:
        raise RuntimeError('sample profile is not authorized for this pipeline')
    if os.uname().machine != 'aarch64':
        raise RuntimeError('sample must run on ARM64')
    archive_setting = os.environ.get(ARCHIVE_ENV, '')
    if not archive_setting or not Path(archive_setting).is_absolute():
        raise RuntimeError('IDT_RPI4_SAMPLE_ARCHIVE must be an absolute path to the pinned official ZIP')
    archive_path = Path(archive_setting)
    verify_archive_digest('linux', digest(archive_path))
    output = ROOT / 'artifacts/idt-rpi4-sample'
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='idt-rpi4-sample-') as directory:
        work = Path(directory)
        env = {'PATH': '/usr/bin:/bin', 'HOME': str(work), 'LANG': 'C.UTF-8',
               'AWS_EC2_METADATA_DISABLED': 'true', 'AWS_CONFIG_FILE': '/dev/null',
               'AWS_SHARED_CREDENTIALS_FILE': '/dev/null',
               'HTTP_PROXY': 'http://127.0.0.1:9', 'HTTPS_PROXY': 'http://127.0.0.1:9',
               'NO_PROXY': '127.0.0.1,localhost'}
        subprocess.run(['apt-get', 'download', *PACKAGES], cwd=work, env=env, check=True, timeout=120)
        for package, expected in PACKAGES.items():
            files = list(work.glob(package.split('=')[0] + '_*.deb'))
            if len(files) != 1 or digest(files[0]) != expected:
                raise RuntimeError('Ubuntu package hash mismatch')
            subprocess.run(['dpkg-deb', '-x', str(files[0]), str(work / 'packages')], check=True)
        with zipfile.ZipFile(archive_path) as archive:
            for entry in archive.infolist():
                destination = (work / entry.filename).resolve()
                if work.resolve() not in destination.parents or (entry.external_attr >> 16) & 0o170000 == 0o120000:
                    raise RuntimeError('unsafe archive member')
            archive.extractall(work)
        idt = work / 'devicetester_freertos_linux'
        verify_install(idt, 'linux')
        for path in (idt / 'bin/devicetester_linux_x86-64',):
            path.chmod(0o700)
        sample = idt / 'samples/python'
        suite = idt / 'tests/IDTSampleSuitePython_1.0.1'
        shutil.copytree(sample / 'configuration/IDTSampleSuitePython_1.0.1', suite)
        shutil.copytree(sample / 'src/suite', suite / 'suite', dirs_exist_ok=True)
        shutil.copytree(idt / 'sdks/python/idt_client', suite / 'suite/sample_group/idt_client')
        subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(work / 'dummy_key')],
                       env=env, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        config = idt / 'configs'
        device = [{'id': 'LocalPool', 'sku': 'LocalSku', 'devices': [{'id': 'LocalDevice',
                   'connectivity': {'protocol': 'ssh', 'ip': '127.0.0.1', 'port': 65022,
                   'auth': {'method': 'pki', 'credentials': {'user': 'nobody', 'privKeyPath': str(work / 'dummy_key')}}}}]}]
        (config / 'device.json').write_text(json.dumps(device))
        (config / 'userdata.json').write_text('{}')
        runtime = work / 'runtime'
        runtime.mkdir()
        cfg = {'log': {'location': str(runtime / 'logs')},
               'configFiles': {'root': str(config), 'device': str(config / 'device.json')},
               'testPath': str(idt / 'tests'), 'reportPath': str(runtime / 'results'),
               'certificatePath': str(runtime / 'certificates'), 'awsRegion': 'ap-northeast-1',
               'auth': {'method': 'environment'}}
        (config / 'config.json').write_text(json.dumps(cfg))
        qemu = work / 'packages/usr/bin/qemu-x86_64-static'
        sysroot = work / 'packages/usr/x86_64-linux-gnu'
        command = [str(qemu), '-L', str(sysroot), str(idt / 'bin/devicetester_linux_x86-64'),
                   'run-suite', '--suite-id', 'IDTSampleSuitePython_1.0.1', '--pool-id', 'LocalPool',
                   '--group-id', 'sample_group', '--test-id', 'test_log',
                   '--update-idt', 'n', '--upgrade-test-suite', 'n', '--update-managed-policy', 'n']
        proc = subprocess.Popen(command, cwd=idt / 'bin', env=env, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            stdout, _ = proc.communicate(timeout=90)
        finally:
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
        reports = list((runtime / 'results').rglob('IDTSampleSuitePython_Report.xml'))
        if proc.returncode or len(reports) != 1:
            raise RuntimeError('official sample did not finish with one report')
        report = ET.parse(reports[0]).getroot()
        cases = report.findall('.//testcase')
        if (report.get('tests') != '1' or any(report.get(k, '0') != '0' for k in ('failures', 'errors', 'skipped'))
                or len(cases) != 1 or cases[0].get('name') != 'test_log'
                or any(cases[0].find(k) is not None for k in ('failure', 'error', 'skipped'))
                or b'Finished running test case' not in stdout):
            raise RuntimeError('official sample JUnit or SDK result is not a single pass')
        shutil.copyfile(reports[0], output / 'official-junit.xml')
        print('Official sample test_log: 1 PASS; IDT 4.9.0; FRQ 2.5.0 bundle verified', flush=True)
        print('This is an ARM64 QEMU sample smoke, not a Transport or hardware test.', flush=True)


if __name__ == '__main__':
    main()

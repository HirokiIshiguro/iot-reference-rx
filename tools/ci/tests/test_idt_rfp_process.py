"""RFP shutdown proofs use mocked processes only; never touch hardware or /proc."""
from contextlib import ExitStack, contextmanager
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, call, patch

from tools.idt import rfp_process as rfp


class Clock:
    now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class Process:
    pid = 4321
    returncode = None

    def __init__(self, polls):
        self.polls = iter(polls)

    def poll(self):
        outcome = next(self.polls, self.returncode)
        if isinstance(outcome, BaseException):
            raise outcome
        self.returncode = outcome
        return outcome


def member(pid=4321, uid=1000, pgrp=4321, ppid=1, session=4321, starttime=123):
    return rfp._Process(pid, ppid, pgrp, session, starttime, (uid,) * 4)


@contextmanager
def supervision(process, members):
    clock = Clock()
    with ExitStack() as stack:
        mocks = {}
        stack.enter_context(patch.object(rfp.signal, 'SIGKILL', 9, create=True))
        for name, options in (
                ('sys.platform', {'new': 'linux'}),
                ('subprocess.Popen', {'return_value': process}),
                ('_proc_snapshot', {'return_value': {}}),
                ('_members', {'side_effect': members}),
                ('time.monotonic', {'side_effect': clock.monotonic}),
                ('time.sleep', {'side_effect': clock.sleep}),
                ('signal.signal', {'return_value': signal.SIG_DFL})):
            mocks[name] = stack.enter_context(patch('tools.idt.rfp_process.' + name, **options))
        for name in ('killpg', 'kill', 'geteuid'):
            mocks[name] = stack.enter_context(patch.object(rfp.os, name, create=True))
        mocks['geteuid'].return_value = 1000
        yield clock, mocks


class RfpSupervisionTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.target = {'id': 'rx671-wifi', 'rfp_lock': str(Path(self.folder.name) / 'rfp.lock')}

    def sentinel(self):
        return Path(self.target['rfp_lock'] + '.unsafe.json')

    def test_success_requires_reaped_parent_and_empty_group(self):
        command = ['sudo', '-n', 'rfp-cli']
        with supervision(Process([0]), lambda *_: {}) as (_, mocks):
            result = rfp.run_guarded(command, target=self.target, timeout=10)
            self.assertEqual(0, result.returncode)
            self.assertEqual(command, result.args)
            mocks['subprocess.Popen'].assert_called_once_with(command, start_new_session=True)
            mocks['killpg'].assert_not_called()
        self.assertFalse(self.sentinel().exists())

    def test_nonzero_exit_keeps_check_true_semantics(self):
        with supervision(Process([7]), lambda *_: {}), self.assertRaises(subprocess.CalledProcessError) as caught:
            rfp.run_guarded(['rfp-cli'], target=self.target, timeout=10)
        self.assertEqual(7, caught.exception.returncode)
        self.assertFalse(self.sentinel().exists())

    def test_timeout_reserves_term_grace_inside_total_budget(self):
        process = Process([None])
        term_sent = False

        def members(*_):
            if term_sent:
                process.returncode = -signal.SIGTERM
                return {}
            return {4321: member()}

        with supervision(process, members) as (clock, mocks):
            def term(*_):
                nonlocal term_sent
                term_sent = True
            mocks['killpg'].side_effect = term
            with self.assertRaises(subprocess.TimeoutExpired):
                rfp.run_guarded(['rfp-cli'], target=self.target, timeout=10, privileged=False)
            self.assertGreaterEqual(clock.now, 5)
            self.assertLessEqual(clock.now, 10)
            mocks['killpg'].assert_called_once_with(4321, signal.SIGTERM)
            mocks['kill'].assert_not_called()
            self.assertEqual([call(signal.SIGINT, signal.SIG_IGN), call(signal.SIGTERM, signal.SIG_IGN),
                              call(signal.SIGTERM, signal.SIG_DFL), call(signal.SIGINT, signal.SIG_DFL)],
                             mocks['signal.signal'].call_args_list)
        self.assertFalse(self.sentinel().exists())

    def test_root_child_survival_is_unsafe_even_after_parent_exit(self):
        with supervision(Process([0]), lambda *_: {4322: member(4322, uid=0)}) as (clock, mocks):
            with self.assertRaises(rfp.UnsafeRfpError):
                rfp.run_guarded(['sudo', 'unit-secret-never-record'], target=self.target, timeout=10)
            self.assertLessEqual(clock.now, 10)
            mocks['kill'].assert_not_called()
            mocks['killpg'].assert_called_once_with(4321, signal.SIGTERM)
        raw = self.sentinel().read_text()
        self.assertNotIn('unit-secret-never-record', raw)
        self.assertEqual('privileged-process-remains', json.loads(raw)['reason'])
        with self.assertRaises(rfp.UnsafeRfpError):
            rfp.raise_if_rfp_unsafe(self.target)

    def test_same_uid_kill_is_individual_and_followed_by_reap(self):
        process = Process([None])
        killed = False

        def members(*_):
            if killed:
                process.returncode = -signal.SIGKILL
                return {}
            return {4321: member()}

        with supervision(process, members) as (clock, mocks):
            def kill(*_):
                nonlocal killed
                killed = True
            mocks['kill'].side_effect = kill
            with self.assertRaises(subprocess.TimeoutExpired):
                rfp.run_guarded(['rfp-cli'], target=self.target, timeout=10, privileged=False)
            self.assertLessEqual(clock.now, 10)
            mocks['kill'].assert_called_once_with(4321, signal.SIGKILL)
            mocks['killpg'].assert_called_once_with(4321, signal.SIGTERM)
            self.assertEqual(-signal.SIGKILL, process.returncode)
        self.assertFalse(self.sentinel().exists())

    def test_unknown_visibility_persists_sentinel_and_never_blind_kills(self):
        with supervision(Process([None]), Mock(side_effect=PermissionError('hidden'))) as (_, mocks):
            with self.assertRaises(rfp.UnsafeRfpError):
                rfp.run_guarded(['rfp-cli'], target=self.target, timeout=10)
            mocks['kill'].assert_not_called()
        self.assertEqual('process-visibility-unknown', json.loads(self.sentinel().read_text())['reason'])

    def test_interrupt_waits_for_safe_termination_then_reraises(self):
        with supervision(Process([KeyboardInterrupt(), 0]), lambda *_: {}) as (_, mocks):
            with self.assertRaises(KeyboardInterrupt):
                rfp.run_guarded(['rfp-cli'], target=self.target, timeout=10, privileged=False)
            mocks['killpg'].assert_called_once_with(4321, signal.SIGTERM)
        self.assertFalse(self.sentinel().exists())

    def test_privileged_timeout_is_unsafe_even_when_observed_group_terminates(self):
        process = Process([None])
        term_sent = False

        def members(*_):
            if term_sent:
                process.returncode = -signal.SIGTERM
                return {}
            return {4321: member()}

        with supervision(process, members) as (_, mocks):
            def term(*_):
                nonlocal term_sent
                term_sent = True
            mocks['killpg'].side_effect = term
            with self.assertRaises(rfp.UnsafeRfpError):
                rfp.run_guarded(['sudo', 'rfp-cli'], target=self.target, timeout=10)
            mocks['kill'].assert_not_called()
        self.assertEqual('privileged-command-interrupted', json.loads(self.sentinel().read_text())['reason'])

    def test_privileged_interrupt_is_unsafe_even_when_observed_group_empty(self):
        with supervision(Process([KeyboardInterrupt(), 0]), lambda *_: {}):
            with self.assertRaises(rfp.UnsafeRfpError):
                rfp.run_guarded(['sudo', 'rfp-cli'], target=self.target, timeout=10)
        self.assertEqual('privileged-command-interrupted', json.loads(self.sentinel().read_text())['reason'])

    def test_quiet_uses_devnull_for_all_streams(self):
        command = ['sudo', 'rfp-cli']
        with supervision(Process([0]), lambda *_: {}) as (_, mocks):
            rfp.run_guarded(command, target=self.target, timeout=10, quiet=True)
            mocks['subprocess.Popen'].assert_called_once_with(command, start_new_session=True,
                                                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                                            stderr=subprocess.DEVNULL)

    def test_second_interrupt_during_cleanup_becomes_persistent_unsafe(self):
        with supervision(Process([KeyboardInterrupt(), KeyboardInterrupt()]), lambda *_: {}):
            with self.assertRaises(rfp.UnsafeRfpError):
                rfp.run_guarded(['rfp-cli'], target=self.target, timeout=10)
        self.assertEqual('process-termination-interrupted', json.loads(self.sentinel().read_text())['reason'])

    def test_worker_cleanup_does_not_change_process_signal_handlers(self):
        with supervision(Process([KeyboardInterrupt(), 0]), lambda *_: {}) as (_, mocks), \
                patch.object(rfp.threading, 'current_thread', return_value=object()):
            with self.assertRaises(KeyboardInterrupt):
                rfp.run_guarded(['rfp-cli'], target=self.target, timeout=10, privileged=False)
            mocks['signal.signal'].assert_not_called()

    def test_preexisting_sentinel_refuses_spawn_and_is_not_replaced(self):
        self.sentinel().write_text('manual recovery evidence')
        with supervision(Process([0]), lambda *_: {}) as (_, mocks):
            with self.assertRaises(rfp.UnsafeRfpError):
                rfp.run_guarded(['rfp-cli'], target=self.target, timeout=10)
            mocks['subprocess.Popen'].assert_not_called()
        self.assertEqual('manual recovery evidence', self.sentinel().read_text())

    def test_dangling_sentinel_symlink_is_refused(self):
        with patch.object(rfp.os, 'lstat', return_value=Mock(st_mode=0o120777)):
            with self.assertRaises(rfp.UnsafeRfpError):
                rfp.raise_if_rfp_unsafe(self.target)

    def test_preflight_unknown_visibility_refuses_spawn(self):
        with supervision(Process([0]), lambda *_: {}) as (_, mocks):
            mocks['_proc_snapshot'].side_effect = PermissionError('proc unreadable')
            with self.assertRaises(rfp.UnsafeRfpError):
                rfp.run_guarded(['rfp-cli'], target=self.target, timeout=10)
            mocks['subprocess.Popen'].assert_not_called()
        self.assertTrue(self.sentinel().is_file())

    def test_input_validation_and_nonlinux_never_spawn(self):
        for timeout in (0, -1, float('nan'), float('inf'), True):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                rfp.run_guarded(['rfp-cli'], target=self.target, timeout=timeout)
        with self.assertRaises(ValueError):
            rfp.run_guarded('rfp-cli', target=self.target, timeout=10)
        with patch.object(rfp.sys, 'platform', 'win32'), patch.object(rfp.subprocess, 'Popen') as spawn:
            with self.assertRaisesRegex(RuntimeError, 'Linux'):
                rfp.run_guarded(['rfp-cli'], target=self.target, timeout=10)
            spawn.assert_not_called()


class ProcInspectionTests(unittest.TestCase):
    def test_known_descendants_remain_visible_after_parent_exit_and_reparent(self):
        parent = member()
        monitor = member(4322, uid=0, pgrp=4322, ppid=4321, session=4322, starttime=456)
        orphan = member(4322, uid=0, pgrp=4322, ppid=1, session=4322, starttime=456)
        known = {}
        with patch.object(rfp, '_proc_snapshot', side_effect=[{4321: parent, 4322: monitor}, {4322: orphan}]):
            self.assertEqual({4321, 4322}, set(rfp._members(4321, known)))
            self.assertEqual({4322}, set(rfp._members(4321, known)))

    def test_reused_pid_is_not_a_known_descendant(self):
        unrelated = member(4322, pgrp=999, session=999, starttime=789)
        with patch.object(rfp, '_proc_snapshot', return_value={4322: unrelated}):
            self.assertEqual({}, rfp._members(4321, {4322: 456}))

    def test_reused_leader_pid_or_reused_pid_in_group_is_unknown(self):
        for process in (member(starttime=789), member(4322, starttime=789)):
            with self.subTest(pid=process.pid), patch.object(rfp, '_proc_snapshot', return_value={process.pid: process}):
                with self.assertRaises(OSError):
                    rfp._members(4321, {process.pid: 123})

    def test_hidepid_and_unknown_proc_mount_are_refused(self):
        for mounts in ('12 1 0:1 / /proc rw - proc proc rw,hidepid=2\n',
                       '12 1 0:1 / /else rw - proc proc rw\n'):
            with self.subTest(mounts=mounts), patch.object(Path, 'read_text', return_value=mounts):
                with self.assertRaises(OSError):
                    rfp._proc_visible()

    def test_unrestricted_proc_mount_is_accepted(self):
        with patch.object(Path, 'read_text', return_value='12 1 0:1 / /proc rw - proc proc rw,hidepid=0\n'):
            rfp._proc_visible()

    def test_unreadable_process_prevents_empty_group_proof(self):
        with patch.object(rfp, '_proc_visible'), patch.object(Path, 'iterdir', return_value=[Path('/proc/4322')]), \
                patch.object(Path, 'read_text', side_effect=PermissionError('hidden')):
            with self.assertRaises(PermissionError):
                rfp._proc_snapshot()


if __name__ == '__main__':
    unittest.main()

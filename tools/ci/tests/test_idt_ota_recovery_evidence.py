"""Offline composition of admission and one privately supplied candidate."""
from dataclasses import replace
import unittest
from unittest.mock import Mock, patch

from tools.idt.ota_admission import RunIdentity
from tools.idt.ota_profile_evidence import EvidenceError
from tools.idt.ota_recovery_evidence import inspect_candidate


class RecoveryEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.original = RunIdentity('123456789012', 'us-east-1', '38', '100', '101', 'a' * 40, 'run')
        self.cert = 'certificate'
        self.record = {'request_id': 'request', 'state': 'ACTIVE', 'profile_intent': {
            'certificates': [self.cert], 'before': [{'profileName': 'old'}]}}
        self.store = Mock()
        self.store.inspect.return_value = (self.record, 'etag', 'version')
        self.args = dict(role_arn='arn:aws:iam::123456789012:role/path/runner',
                         certificate_arn=self.cert, profile_name='profile', thing_arn='thing',
                         iot_job_id='job', events=[], iot=Mock(), signer=Mock())

    @patch('tools.idt.ota_recovery_evidence.verify_live_profile', return_value={'checked': True})
    @patch('tools.idt.ota_recovery_evidence.match_created_profile', return_value={'candidate': True})
    def test_exact_record_and_actor(self, match, live):
        result = inspect_candidate(self.store, self.original, ('request', 'version'), **self.args)
        self.assertEqual(result['live'], {'checked': True})
        self.store.inspect.assert_called_once_with(self.original)
        self.assertEqual(match.call_args.kwargs['run_actor_arn'],
                         'arn:aws:sts::123456789012:assumed-role/runner/gitlab38-101')
        self.assertEqual(match.call_args.kwargs['before_names'], ['old'])
        self.assertEqual(live.call_args.kwargs['thing_arn'], 'thing')
        self.assertEqual(live.call_args.kwargs['iot_job_id'], 'job')
        self.record['state'] = 'UNKNOWN'
        inspect_candidate(self.store, self.original, ('request', 'version'), **self.args)

    @patch('tools.idt.ota_recovery_evidence.match_created_profile')
    def test_reject_unbound_inputs_before_live_calls(self, match):
        for expected in [('old', 'version'), ('request', 'old')]:
            with self.subTest(expected=expected), self.assertRaises(EvidenceError):
                inspect_candidate(self.store, self.original, expected, **self.args)
        self.record['state'] = 'CLEANED'
        with self.assertRaises(EvidenceError):
            inspect_candidate(self.store, self.original, ('request', 'version'), **self.args)
        self.record['state'] = 'ACTIVE'
        self.record['profile_intent']['certificates'] = []
        with self.assertRaises(EvidenceError):
            inspect_candidate(self.store, self.original, ('request', 'version'), **self.args)
        self.record['profile_intent']['certificates'] = [self.cert]
        self.args['role_arn'] = 'arn:aws:iam::999999999999:role/runner'
        with self.assertRaises(EvidenceError):
            inspect_candidate(self.store, self.original, ('request', 'version'), **self.args)
        self.args['role_arn'] = 'arn:aws:iam::123456789012:role/runner'
        with self.assertRaises(EvidenceError):
            inspect_candidate(self.store, replace(self.original, project_id='39'), ('request', 'version'), **self.args)
        match.assert_not_called()

    @patch('tools.idt.ota_recovery_evidence.verify_live_profile', return_value={'checked': True})
    def test_real_event_match_uses_recorded_intent(self, live):
        from tools.ci.tests.test_idt_ota_profile_evidence import ProfileEvidenceTests
        fixture = ProfileEvidenceTests()
        fixture.setUp()
        actor = 'arn:aws:sts::123456789012:assumed-role/runner/gitlab38-101'
        for event in (fixture.events[0], fixture.events[3]):
            event['userIdentity']['arn'] = actor
        self.record['profile_intent']['certificates'] = [fixture.cert]
        self.args.update(certificate_arn=fixture.cert, profile_name='profile1', events=fixture.events)
        result = inspect_candidate(self.store, self.original, ('request', 'version'), **self.args)
        self.assertEqual(result['candidate']['otaUpdateId'], 'ota1')
        self.assertEqual(live.call_args.args[0]['signingJobId'], 'job1')
        self.record['profile_intent']['before'] = [{'profileName': 'profile1'}]
        with self.assertRaises(EvidenceError):
            inspect_candidate(self.store, self.original, ('request', 'version'), **self.args)


if __name__ == '__main__':
    unittest.main()

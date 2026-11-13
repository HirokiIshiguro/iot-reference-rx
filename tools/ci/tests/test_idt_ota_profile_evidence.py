import copy
import unittest

from tools.idt.ota_profile_evidence import EvidenceError, match_created_profile


class ProfileEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.cert = 'arn:aws:acm:us-east-1:123456789012:certificate/12345678-1234-1234-1234-123456789abc'
        self.actor = 'arn:aws:sts::123456789012:assumed-role/run/session'
        self.role = 'arn:aws:sts::123456789012:assumed-role/iot/session'
        self.issuer = 'arn:aws:iam::123456789012:role/iot'
        arn = 'arn:aws:signer:us-east-1:123456789012:/signing-profiles/profile1'
        self.events = [
            self.event('1', 'acm.amazonaws.com', 'ImportCertificate', self.actor, {}, {'certificateArn': self.cert}),
            self.event('2', 'signer.amazonaws.com', 'PutSigningProfile', self.role,
                       {'profileName': 'profile1', 'signingMaterial': {'certificateArn': self.cert}},
                       {'arn': arn, 'profileVersion': 'abcdefghij', 'profileVersionArn': arn + '/abcdefghij'}, True),
            self.event('3', 'signer.amazonaws.com', 'StartSigningJob', self.role,
                       {'profileName': 'profile1'}, {'jobId': 'job1'}, True),
            self.event('4', 'iot.amazonaws.com', 'CreateOTAUpdate', self.actor,
                       {'otaUpdateId': 'ota1', 'roleArn': self.issuer, 'files': [{'codeSigning': {'startSigningJobParameter': {
                           'signingProfileName': 'profile1', 'signingProfileParameter': {'certificateArn': self.cert}}}}]},
                       {'otaUpdateId': 'ota1', 'otaUpdateArn': 'arn:aws:iot:us-east-1:123456789012:otaupdate/ota1'}),
        ]

    @staticmethod
    def event(eid, source, name, actor, request, response, service=False):
        identity = {'arn': actor}
        if service:
            identity['invokedBy'] = 'iot.amazonaws.com'
            identity['sessionContext'] = {'sessionIssuer': {'arn': 'arn:aws:iam::123456789012:role/iot'}}
        return {'eventID': eid, 'eventSource': source, 'eventName': name, 'userIdentity': identity,
                'requestParameters': request, 'responseElements': response}

    def match(self):
        return match_created_profile(self.events, run_actor_arn=self.actor, certificate_arn=self.cert,
                                     profile_name='profile1', before_names=[])

    def test_unique_chain(self):
        result = self.match()
        self.assertEqual((result['profileVersion'], result['signingJobId'], result['otaUpdateId']),
                         ('abcdefghij', 'job1', 'ota1'))

    def test_preexisting_name_rejected(self):
        with self.assertRaises(EvidenceError):
            match_created_profile(self.events, run_actor_arn=self.actor, certificate_arn=self.cert,
                                  profile_name='profile1', before_names=['profile1'])

    def test_other_profile_using_same_certificate_does_not_hide_match(self):
        other = copy.deepcopy(self.events[1])
        other['eventID'] = '5'
        other['requestParameters']['profileName'] = 'profile2'
        self.events.append(other)
        self.assertEqual(self.match()['profileName'], 'profile1')

    def test_mismatched_ota_response_rejected(self):
        self.events[3]['responseElements']['otaUpdateId'] = 'unrelated'
        with self.assertRaises(EvidenceError):
            self.match()

    def test_missing_edges_and_mismatched_actor_are_rejected(self):
        original = copy.deepcopy(self.events)
        for index in range(4):
            self.events = copy.deepcopy(original)
            self.events.pop(index)
            with self.subTest(index=index), self.assertRaises(EvidenceError):
                self.match()
        self.events = copy.deepcopy(original)
        self.events[2]['userIdentity']['sessionContext']['sessionIssuer']['arn'] += 'other'
        with self.assertRaises(EvidenceError):
            self.match()

    def test_ambiguous_or_inconsistent_identity_rejected(self):
        extra = copy.deepcopy(self.events[1])
        extra['eventID'] = '5'
        self.events.append(extra)
        with self.assertRaises(EvidenceError):
            self.match()
        self.events.pop()
        self.events[1]['responseElements']['profileVersionArn'] += 'x'
        with self.assertRaises(EvidenceError):
            self.match()

    def test_failed_or_duplicate_events_do_not_prove_chain(self):
        self.events[1]['errorCode'] = 'AccessDenied'
        with self.assertRaises(EvidenceError):
            self.match()
        self.events[1].pop('errorCode')
        self.events[1]['eventID'] = '1'
        with self.assertRaises(EvidenceError):
            self.match()


if __name__ == '__main__':
    unittest.main()

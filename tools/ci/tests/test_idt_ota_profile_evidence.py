import copy
import unittest
from unittest.mock import Mock

from tools.idt.ota_profile_evidence import EvidenceError, match_created_job, match_created_profile, verify_live_profile


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


class CreatedJobEvidenceTests(unittest.TestCase):
    def setUp(self):
        fixture = ProfileEvidenceTests()
        fixture.setUp()
        self.events, self.actor, self.cert = fixture.events, fixture.actor, fixture.cert
        self.thing = 'arn:aws:iot:us-east-1:123456789012:thing/device'
        self.events[3]['requestParameters']['targets'] = [self.thing]
        self.events.append(fixture.event('5', 'iot.amazonaws.com', 'CreateJob', fixture.role,
                           {'jobId': 'AFR_OTA-ota1', 'targets': [self.thing]},
                           {'jobId': 'AFR_OTA-ota1',
                            'jobArn': 'arn:aws:iot:us-east-1:123456789012:job/AFR_OTA-ota1'}, True))

    def match(self):
        return match_created_job(self.events, run_actor_arn=self.actor, certificate_arn=self.cert,
                                 profile_name='profile1', before_names=[])

    def test_unique_job(self):
        result = self.match()
        self.assertEqual((result['thingArn'], result['iotJobId'], result['eventIds']['CreateJob']),
                         (self.thing, 'AFR_OTA-ota1', '5'))

    def test_mismatches_fail_closed(self):
        original = copy.deepcopy(self.events)
        changes = [
            (3, ('requestParameters', 'targets'), []),
            (3, ('requestParameters', 'targets'), [self.thing, self.thing]),
            (3, ('requestParameters', 'targets'), [self.thing.replace('123456789012', '999999999999')]),
            (4, ('requestParameters', 'targets'), []),
            (4, ('requestParameters', 'jobId'), 'other'),
            (4, ('responseElements', 'jobId'), 'other'),
            (4, ('responseElements', 'jobArn'), 'other'),
            (4, ('userIdentity', 'invokedBy'), 'other'),
            (4, ('userIdentity', 'sessionContext', 'sessionIssuer', 'arn'), 'other'),
            (4, ('eventSource',), 'other'),
            (4, ('eventID',), '4'),
            (4, ('errorCode',), 'AccessDenied'),
        ]
        for index, path, value in changes:
            self.events = copy.deepcopy(original)
            node = self.events[index]
            for key in path[:-1]:
                node = node[key]
            node[path[-1]] = value
            with self.subTest(path=path, value=value), self.assertRaises(EvidenceError):
                self.match()

    def test_duplicate_job_and_missing_job_fail(self):
        duplicate = copy.deepcopy(self.events[-1])
        duplicate['eventID'] = '6'
        self.events.append(duplicate)
        with self.assertRaises(EvidenceError):
            self.match()
        self.events = self.events[:4]
        with self.assertRaises(EvidenceError):
            self.match()
        self.assertEqual(match_created_profile(self.events, run_actor_arn=self.actor,
                                               certificate_arn=self.cert, profile_name='profile1',
                                               before_names=[])['otaUpdateId'], 'ota1')


class LiveProfileEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.thing = 'arn:aws:iot:us-east-1:123456789012:thing/device'
        self.cert = 'arn:aws:acm:us-east-1:123456789012:certificate/12345678-1234-1234-1234-123456789abc'
        profile_arn = 'arn:aws:signer:us-east-1:123456789012:/signing-profiles/profile1'
        self.candidate = {'profileName': 'profile1', 'profileVersion': 'abcdefghij', 'certificateArn': self.cert,
                          'otaUpdateId': 'ota1', 'signingJobId': 'job1', 'arn': profile_arn,
                          'profileVersionArn': profile_arn + '/abcdefghij'}
        self.iot = Mock()
        self.signer = Mock()
        self.iot.meta.region_name = self.signer.meta.region_name = 'us-east-1'
        self.update = {'otaUpdateId': 'ota1', 'otaUpdateArn': 'arn:aws:iot:us-east-1:123456789012:otaupdate/ota1',
                       'targets': [self.thing], 'awsIotJobId': 'iotjob',
                       'awsIotJobArn': 'arn:aws:iot:us-east-1:123456789012:job/iotjob',
                       'otaUpdateFiles': [{'codeSigning': {'awsSignerJobId': 'job1'}}]}
        self.job = {'jobId': 'job1', 'jobOwner': '123456789012', 'profileName': 'profile1',
                    'profileVersion': 'abcdefghij', 'signingMaterial': {'certificateArn': self.cert}}
        self.iot.get_ota_update.return_value = {'otaUpdateInfo': self.update}
        self.signer.describe_signing_job.return_value = self.job

    def verify(self):
        return verify_live_profile(self.candidate, iot=self.iot, signer=self.signer, account='123456789012',
                                   region='us-east-1', thing_arn=self.thing, iot_job_id='iotjob')

    def test_live_match(self):
        self.assertEqual(self.verify()['signingJobId'], 'job1')
        self.iot.get_ota_update.assert_called_once_with(otaUpdateId='ota1')
        self.signer.describe_signing_job.assert_called_once_with(jobId='job1')

    def test_mismatches_fail_closed(self):
        for field in ('otaUpdateId', 'otaUpdateArn', 'targets', 'awsIotJobId', 'awsIotJobArn', 'otaUpdateFiles'):
            with self.subTest(field=field):
                original = self.update[field]
                self.update[field] = [] if field in ('targets', 'otaUpdateFiles') else 'wrong'
                with self.assertRaises(EvidenceError):
                    self.verify()
                self.update[field] = original
        for field in ('jobId', 'jobOwner', 'profileName', 'profileVersion', 'signingMaterial'):
            with self.subTest(field=field):
                original = self.job[field]
                self.job[field] = {} if field == 'signingMaterial' else 'wrong'
                with self.assertRaises(EvidenceError):
                    self.verify()
                self.job[field] = original

    def test_scope_and_api_failure(self):
        self.signer.meta.region_name = 'us-west-2'
        with self.assertRaises(EvidenceError):
            self.verify()
        self.signer.meta.region_name = 'us-east-1'
        self.iot.get_ota_update.side_effect = RuntimeError('unavailable')
        with self.assertRaises(RuntimeError):
            self.verify()

    def test_other_signing_job_is_rejected_before_signer_lookup(self):
        self.update['otaUpdateFiles'][0]['codeSigning']['awsSignerJobId'] = 'other'
        with self.assertRaises(EvidenceError):
            self.verify()
        self.signer.describe_signing_job.assert_not_called()


if __name__ == '__main__':
    unittest.main()

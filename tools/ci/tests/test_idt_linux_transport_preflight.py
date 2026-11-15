"""No-network tests for the one-shot Transport AWS preflight."""
from __future__ import annotations

import importlib.util
import io
import contextlib
import unittest
from unittest.mock import Mock, patch

from tools.aws.oidc_session import OidcError
from tools.idt import linux_oidc_job as launcher
from tools.ci.tests.test_idt_linux_oidc_job import AMI, config


@unittest.skipUnless(importlib.util.find_spec('boto3'), 'boto3 required')
class TransportPreflightTests(unittest.TestCase):
    def setUp(self):
        from botocore.exceptions import ClientError
        self.ClientError = ClientError
        self.child = {'CI_JOB_ID': '123', 'AWS_ACCESS_KEY_ID': 'fixture-key',
                      'AWS_SECRET_ACCESS_KEY': 'fixture-secret', 'AWS_SESSION_TOKEN': 'fixture-token'}
        self.ssm = Mock()
        self.ssm.get_parameters.return_value = {'Parameters': [{'Name':
            '/aws/service/ami-amazon-linux-latest/amzn2-ami-hvm-x86_64-gp2', 'Value': AMI}]}
        self.ec2 = Mock()
        self.ec2.create_key_pair.side_effect = ClientError(
            {'Error': {'Code': 'DryRunOperation', 'Message': 'fixture'}}, 'CreateKeyPair')
        self.session = Mock()
        self.session.client.side_effect = lambda service, **_kwargs: {'ssm': self.ssm, 'ec2': self.ec2}[service]
        self.factory = Mock(return_value=self.session)

    def test_exact_ami_and_dry_run_are_required(self):
        out = io.StringIO()
        with patch.object(launcher, 'check_child_budget') as budget, contextlib.redirect_stdout(out):
            launcher.verify_transport_aws(self.child, config(), session_factory=self.factory)
        self.assertEqual(budget.call_count, 2)
        self.ec2.create_key_pair.assert_called_once_with(KeyName='idt-ec2-ssh-key-dryrun-gitlab38-123', DryRun=True)
        self.assertIn('preflight passed', out.getvalue())
        self.assertNotIn('fixture-secret', out.getvalue())
        self.assertEqual(self.factory.call_args.kwargs['aws_session_token'], 'fixture-token')

    def test_changed_ami_stops_before_ec2(self):
        self.ssm.get_parameters.return_value['Parameters'][0]['Value'] = 'ami-00000000000000000'
        with patch.object(launcher, 'check_child_budget'):
            with self.assertRaisesRegex(OidcError, 'AMI changed'):
                launcher.verify_transport_aws(self.child, config(), session_factory=self.factory)
        self.ec2.create_key_pair.assert_not_called()

    def test_denied_or_unexpected_dry_run_stops(self):
        for side_effect in (self.ClientError({'Error': {'Code': 'UnauthorizedOperation',
                                                        'Message': 'fixture-secret'}}, 'CreateKeyPair'), None):
            self.ec2.create_key_pair.reset_mock()
            self.ec2.create_key_pair.side_effect = side_effect
            with patch.object(launcher, 'check_child_budget'):
                with self.assertRaises(OidcError) as error:
                    launcher.verify_transport_aws(self.child, config(), session_factory=self.factory)
            self.assertNotIn('fixture-secret', str(error.exception))
            self.ec2.create_key_pair.assert_called_once()


if __name__ == '__main__':
    unittest.main()

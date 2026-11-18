import contextlib
import io
import json
import unittest
from unittest.mock import Mock

from botocore.exceptions import ClientError
from soso.assets import asset_iam_setup as subject
from soso.assets.asset_setup import policies


class IAMSetupTests(unittest.TestCase):
    def setUp(self):
        self.c = {'initialized': True, 'account': '012345678901', 'repo': 'test/project',
                  'role': 'soso-asset-read', 'backup': 'example/backup', 'region': 'us-west-2',
                  'bucket': 'example', 'prefix': 'backup', 'branch': 'main',
                  'subject': 'repo:test/project:ref:refs/heads/main'}
        docs = policies(self.c)
        self.trust, self.read = docs['trust.json'], docs['read.json']
        self.iam, self.sts = Mock(), Mock()
        self.sts.get_caller_identity.return_value = {'Account': self.c['account']}
        self.provider = self.role = self.policy = False
        self.vars = {}
        self.iam.get_open_id_connect_provider.side_effect = lambda **_: self.optional(
            self.provider, {'Url': subject.ISSUER, 'ClientIDList': [subject.AUDIENCE]})
        self.iam.get_role.side_effect = lambda **_: self.optional(
            self.role, {'Role': {'Arn': 'arn:aws:iam::012345678901:role/soso-asset-read', 'RoleId': 'new-role-id',
                                 'AssumeRolePolicyDocument': self.trust}})
        self.iam.create_open_id_connect_provider.side_effect = lambda **_: setattr(self, 'provider', True)
        self.iam.create_role.side_effect = self.create_role
        self.iam.put_role_policy.side_effect = lambda **_: setattr(self, 'policy', True)
        self.iam.list_attached_role_policies.return_value = {'IsTruncated': False, 'AttachedPolicies': []}
        self.iam.list_role_policies.side_effect = lambda **_: {'IsTruncated': False, 'PolicyNames': [subject.POLICY_NAME] if self.policy else []}
        self.iam.get_role_policy.return_value = {'PolicyDocument': self.read}

    def create_role(self, **kwargs):
        self.role = True
        return {'Role': {'RoleId': 'new-role-id'}}

    @staticmethod
    def optional(present, data):
        if not present:
            raise ClientError({'Error': {'Code': 'NoSuchEntity'}}, 'test')
        return data

    def github(self, *args):
        if args[0] == '--method':
            name, value = args[4][5:], args[6][6:]
            self.assertNotIn(name, self.vars)
            self.vars[name] = value
            return ''
        if args == ('repos/test/project',):
            return json.dumps({'full_name': 'test/project', 'default_branch': 'main'})
        return json.dumps([{'total_count': len(self.vars), 'variables': [{'name': k, 'value': v} for k, v in self.vars.items()]}])

    def configure(self, answer, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            return subject.configure(self.c, self.trust, self.read,
                                     ask=answer, aws_client=lambda service, **_: {'sts': self.sts, 'iam': self.iam}[service],
                                     github=self.github, **kwargs)

    def test_dry_run_inspects_without_confirming_or_applying(self):
        self.assertTrue(self.configure(lambda _: self.fail('must not confirm'), dry_run=True))
        self.iam.get_role.assert_called_once()
        self.iam.create_role.assert_not_called()
        self.iam.put_role_policy.assert_not_called()
        self.assertFalse(self.vars)

    def test_create_missing_then_noop(self):
        self.assertTrue(self.configure(lambda _: 'configure'))
        self.assertTrue(self.configure(lambda _: self.fail('already configured')))
        self.iam.create_role.assert_called_once()
        self.iam.put_role_policy.assert_called_once()
        self.assertEqual(len(self.vars), 3)

    def test_decline_and_mismatch_never_write(self):
        self.assertFalse(self.configure(lambda _: ''))
        self.vars['SOSO_AWS_REGION'] = 'not-the-region'
        with self.assertRaisesRegex(ValueError, 'does not match'):
            self.configure(lambda _: self.fail('mismatched configuration'))
        self.iam.create_role.assert_not_called()
        self.iam.create_open_id_connect_provider.assert_not_called()

    def test_existing_partial_role_is_not_modified(self):
        self.role = self.provider = True
        with self.assertRaisesRegex(ValueError, 'policies differ'):
            self.configure(lambda _: self.fail('partial role'))
        self.iam.put_role_policy.assert_not_called()

    def test_recreated_role_gets_no_policy(self):
        def replaced_role(**kwargs):
            self.role = True
            return {'Role': {'RoleId': 'different-role-id'}}
        self.iam.create_role.side_effect = replaced_role
        with self.assertRaisesRegex(ValueError, 'newly created role is unchanged'):
            self.configure(lambda _: 'configure')
        self.iam.put_role_policy.assert_not_called()
        self.assertEqual(self.vars, {})

    def test_rechecks_after_approval(self):
        def move(_):
            self.vars['SOSO_AWS_REGION'] = self.c['region']
            return 'configure'
        with self.assertRaisesRegex(ValueError, 'changed while'):
            self.configure(move)
        self.iam.create_role.assert_not_called()

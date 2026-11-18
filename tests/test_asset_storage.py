import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from soso.assets import asset_storage as s, asset_sync as a


class StorageTests(unittest.TestCase):
    def test_destinations(self):
        self.assertEqual(s.parse('bucket/path'), s.Storage('s3', 'bucket', 'path'))
        self.assertEqual(s.parse('gs://bucket/path').uri('a'*64), 'gs://bucket/path/sha256/aa/'+'a'*64)
        self.assertEqual(s.parse('az://myaccount/photos/path').account, 'myaccount')
        for bad in ['http://bucket', 'gs://bucket/a//b', 'gs://bucket/../a', 'az://ACCOUNT/photos', 'az://account', 'az://account/ab--cd', 's3://buck_et', 'gs://bucket/a?b', 'gs://bucket/a*']:
            with self.subTest(bad=bad), self.assertRaises(ValueError): s.parse(bad)


    def test_unrelated_upload_error_propagates(self):
        from soso.assets import asset_integrity
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'original'; path.write_bytes(b'exact')
            with patch.object(asset_integrity,'upload',side_effect=RuntimeError('AccessDenied')) as mock, self.assertRaises(RuntimeError):
                a.upload(path,a.digest(path),'gs://bucket')
            self.assertEqual(mock.call_count,1)

    def test_lifecycle_fail_closed(self):
        for raw in ('{}','{"Rules":[{"Status":"Enabled","NoncurrentVersionExpiration":{"NoncurrentDays":1}}]}'):
            with patch.object(s,'compatible_run',return_value=raw),self.assertRaises(ValueError): s.verify_b2_retention(s.parse('b2://bucket'))
        with patch.object(s,'compatible_run',side_effect=LookupError('NoSuchLifecycleConfiguration')):
            s.verify_b2_retention(s.parse('b2://bucket'))


class PrefixPromptTests(unittest.TestCase):
    def test_root_defaults_are_explicit_and_preserved(self):
        from unittest.mock import Mock
        for root in ('bucket', 'container'):
            ask = Mock(return_value='')
            self.assertEqual(s.prompt_prefix(ask, '', root), '')
            self.assertIn(f'[{root} root (no prefix)]', ask.call_args.args[0])

    def test_named_prefix_can_be_kept_changed_or_cleared(self):
        from unittest.mock import Mock
        for answer, expected in [('', 'originals'), ('-', ''), ('new/path', 'new/path')]:
            ask = Mock(return_value=answer)
            self.assertEqual(s.prompt_prefix(ask, 'originals'), expected)
            self.assertIn('[originals]', ask.call_args.args[0])

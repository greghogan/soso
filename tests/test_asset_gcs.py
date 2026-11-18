import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from soso.assets import asset_gcs as gcs, asset_storage
from google.api_core.exceptions import Forbidden, PreconditionFailed


class GcsNativeTests(unittest.TestCase):
    def setUp(self):
        self.storage = asset_storage.parse('gs://example-bucket/path')
        self.sha = 'a' * 64

    def test_exact_bytes_create_only_and_no_implicit_cleanup(self):
        with patch.object(gcs, 'client') as factory:
            blob = factory.return_value.bucket.return_value.blob.return_value
            gcs.transfer(self.storage, 'put', self.sha, Path('/tmp/source'))
            factory.return_value.bucket.assert_called_once_with('example-bucket')
            factory.return_value.bucket.return_value.blob.assert_called_once_with('path/sha256/aa/' + self.sha)
            blob.upload_from_filename.assert_called_once_with('/tmp/source', if_generation_match=0, checksum=None, timeout=60)
            blob.delete.assert_not_called()
            gcs.transfer(self.storage, 'get', self.sha, Path('/tmp/output'))
            blob.download_to_filename.assert_called_once_with('/tmp/output', raw_download=True, timeout=60)
            gcs.transfer(self.storage, 'delete', self.sha)
            blob.delete.assert_called_once_with(timeout=60, retry=None)

    def test_conflict_normalized_and_private_errors_redacted(self):
        with patch.object(gcs, 'client') as factory:
            blob = factory.return_value.bucket.return_value.blob.return_value
            blob.upload_from_filename.side_effect = PreconditionFailed('private-details')
            with self.assertRaisesRegex(RuntimeError, '^PreconditionFailed$'):
                gcs.transfer(self.storage, 'put', self.sha, '/tmp/source')
            blob.upload_from_filename.side_effect = Forbidden('private-details')
            with self.assertRaises(RuntimeError) as error:
                gcs.transfer(self.storage, 'put', self.sha, '/tmp/source')
            self.assertNotIn('private-details', str(error.exception))
            blob.delete.assert_not_called()

    def test_native_json_adc_no_redirects(self):
        credentials = object()
        with patch('google.auth.default', return_value=(credentials, 'project')) as auth, patch('google.auth.transport.requests.AuthorizedSession') as session:
            response = session.return_value.__enter__.return_value.get.return_value
            response.status_code = 200
            response.json.return_value = {'kind':'storage#objects'}
            url = 'https://storage.googleapis.com/storage/v1/b/example-bucket/o'
            self.assertEqual(gcs.read_json(url, {'versions':'true'}), {'kind':'storage#objects'})
            auth.assert_called_once_with(scopes=['https://www.googleapis.com/auth/cloud-platform'])
            session.assert_called_once_with(credentials)
            session.return_value.__enter__.return_value.get.assert_called_once_with(url, params={'versions':'true'}, timeout=60, allow_redirects=False)
            response.status_code = 302
            with self.assertRaises(ValueError):
                gcs.read_json(url)
        with self.assertRaises(ValueError):
            gcs.read_json('https://storage.googleapis.com.evil.example/')

    def test_sdk_client_pins_endpoint_and_rejects_emulator(self):
        with patch.dict(gcs.os.environ, {'STORAGE_EMULATOR_HOST':'http://localhost:1234'}):
            with self.assertRaises(ValueError):
                gcs.client()
        with patch.dict(gcs.os.environ, {}, clear=True), patch('google.cloud.storage.Client') as factory:
            gcs.client()
            factory.assert_called_once_with(project=None, client_options={'api_endpoint':'https://storage.googleapis.com'})

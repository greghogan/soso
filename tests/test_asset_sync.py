import hashlib
import io
import json
from types import SimpleNamespace
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from soso.assets import asset_sync as a


class AssetSyncTests(unittest.TestCase):
    def test_destination_and_key(self):
        self.assertEqual(a.destination('s3://soso-backup/private/photos/'), ('soso-backup', 'private/photos'))
        for bad in ['foo/../bar','foo/a//b','foo/a*','foo/a?b','https://foo','foo;evil','127.0.0.1']:
            with self.assertRaises(ValueError): a.destination(bad)
        self.assertEqual(a.key('a'*64), 'sha256/aa/'+'a'*64)

    def test_upload_delegates_metadata_verification(self):
        from soso.assets import asset_integrity
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'source'; path.write_bytes(b'original'); sha=a.digest(path)
            with patch.object(asset_integrity,'upload',return_value={'verification':'service-metadata'}) as native:
                self.assertEqual(a.upload(path,sha,'bucket')['verification'],'service-metadata')
                native.assert_called_once()
            with patch.object(asset_integrity,'upload',side_effect=ValueError('checksum mismatch')), self.assertRaises(ValueError):
                a.upload(path,sha,'bucket')

    def test_prune_protects_current_and_requires_tty(self):
        sha='a'*64
        with patch.object(a,'aws') as aws:
            with self.assertRaises(ValueError): a.prune([sha],{sha},'bucket')
            with patch.object(a.os,'isatty',return_value=False),self.assertRaises(ValueError): a.prune([sha],set(),'bucket')
            aws.assert_not_called()

    def test_confirmed_prune_exact_known_key(self):
        sha='a'*64
        with patch.object(a.os,'isatty',return_value=True), patch('builtins.input',return_value='DELETE 1 HISTORICAL OBJECTS FROM bucket'), patch.object(a,'aws') as aws:
            a.prune([sha],set(),'bucket/prefix')
            aws.assert_called_once_with('s3api','delete-object','--bucket','bucket','--key','prefix/'+a.key(sha))


    def test_decoder_uses_verified_cache_without_jxl_decoder(self):
        from shared import raster_assets
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); (root/'manifests').mkdir(); master=root/'photo.jxl'
            data=b'jpeg'; sha=hashlib.sha256(data).hexdigest(); pixels=b'rgb'
            (root/'manifests/raster-masters.json').write_text(json.dumps({'assets':[{'path':'photo.jxl','reversible_jpeg':True,'original_sha256':sha,'decoded_rgb_sha256':hashlib.sha256(pixels).hexdigest()}]}))
            (root/'manifests/external-assets.json').write_text(json.dumps({'assets':[{'legacy_path':'photo.jxl','sha256':sha}]}))
            original=root/'assets/cache'/a.key(sha); original.parent.mkdir(parents=True); original.write_bytes(data)
            class Image:
                def __enter__(self): return self
                def __exit__(self,*args): pass
                def convert(self,*args): return self
                def tobytes(self): return pixels
            with patch.object(raster_assets,'ROOT',root), patch.object(raster_assets.subprocess,'run') as decoder, patch.dict('sys.modules',{'PIL':SimpleNamespace(Image=SimpleNamespace(open=lambda path:Image()))}):
                target=raster_assets.decoded_asset(master,root/'decoded')
                self.assertEqual(target.read_bytes(),data); decoder.assert_not_called()
            original.write_bytes(b'corrupt')
            with patch.object(raster_assets,'ROOT',root), self.assertRaises(ValueError):
                raster_assets.decoded_asset(master,root/'decoded')
            original.unlink()
            with patch.object(raster_assets,'ROOT',root), self.assertRaisesRegex(FileNotFoundError,'Missing verified original'):
                raster_assets.decoded_asset(master,root/'decoded')


class BackupMetadataTests(unittest.TestCase):
    def test_default_upload_uses_saved_destination_and_requires_complete_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            sha = hashlib.sha256(b'original').hexdigest()
            path = cache / a.key(sha)
            row = {'id': 'x', 'sha256': sha}
            with patch('sys.argv', ['asset_sync']), patch.object(a, 'records', return_value=[row]), \
                 patch.object(a, 'configured_destination', return_value='gs://bucket/photos'), \
                 patch.object(a, 'DEFAULT_CACHE', cache), patch.object(a, 'upload') as upload, \
                 patch.object(a, 'save_verification'), patch('sys.stderr', new_callable=io.StringIO):
                with self.assertRaises(SystemExit):
                    a.main()
                upload.assert_not_called()
                path.parent.mkdir(parents=True)
                path.write_bytes(b'original')
                a.main()
                upload.assert_called_once_with(path, sha, 'gs://bucket/photos')

    def test_verify_reports_complete_and_incomplete_backups_without_writing_remote(self):
        from soso.assets.asset_integrity import BackupObjectMissing
        rows = [{'id': 'image-a', 'sha256': 'a' * 64}, {'id': 'image-b', 'sha256': 'b' * 64}]
        report = {'uri': 's3://bucket/key'}
        for incomplete, verbose in ((True, False), (True, True), (False, False)):
            argv = ['asset_sync', '--verify'] + (['--verbose'] if verbose else [])
            with self.subTest(incomplete=incomplete, verbose=verbose), patch('sys.argv', argv), \
                 patch.object(a, 'records', return_value=rows), \
                 patch.object(a, 'configured_destination', return_value='s3://bucket'), \
                 patch.object(a, 'list_manifest_objects', return_value=None), \
                 patch.object(a, 'verify_backup', side_effect=[BackupObjectMissing() if incomplete else report, report]) as verify, \
                 patch.object(a, 'upload') as upload, patch.object(a, 'save_verification'), \
                 patch('sys.stdout', new_callable=io.StringIO) as out, \
                 patch('sys.stderr', new_callable=io.StringIO) as err:
                if incomplete:
                    with self.assertRaises(SystemExit) as status:
                        a.main()
                    self.assertEqual(status.exception.code, 1)
                    self.assertIn('Backup status: 1/2 verified; 1 not found.', out.getvalue())
                    self.assertEqual('MISSING image-a' in out.getvalue(), verbose)
                else:
                    a.main()
                    self.assertIn('Backup status: 2/2 verified; 0 not found.', out.getvalue())
                self.assertEqual(verify.call_count, 2)
                self.assertEqual(err.getvalue(), '')
                upload.assert_not_called()

    def test_s3_listing_is_limited_to_the_hash_prefix_and_expected_keys(self):
        from soso.assets import asset_aws
        rows = [{'sha256': 'a' * 64}, {'sha256': 'b' * 64}]
        storage = a.asset_storage.parse('s3://bucket/photos')
        expected = storage.object_key(rows[0]['sha256'])
        with patch.object(asset_aws, 'client') as client:
            paginator = client.return_value.get_paginator.return_value
            paginator.paginate.return_value = iter([{'Contents': [{'Key': expected}]},
                                                   {'Contents': [{'Key': 'photos/sha256/historical'}]}])
            self.assertEqual(a.list_manifest_objects(storage, rows), {expected})
            client.return_value.get_paginator.assert_called_once_with('list_objects_v2')
            paginator.paginate.assert_called_once_with(Bucket='bucket', Prefix='photos/sha256/')

    def test_list_permission_denied_falls_back_to_exact_keys(self):
        from botocore.exceptions import ClientError
        from soso.assets import asset_aws
        denied = ClientError({'Error': {'Code': 'AccessDenied'}}, 'ListObjectsV2')
        with patch.object(asset_aws, 'client') as client:
            client.return_value.get_paginator.return_value.paginate.side_effect = denied
            self.assertIsNone(a.list_manifest_objects(a.asset_storage.parse('s3://bucket'), [{'sha256': 'a' * 64}]))

    def test_local_upload_lists_and_reports_each_missing_file_before_uploading(self):
        rows = [{'id': 'image-a', 'sha256': 'a' * 64, 'url': 'https://example.org/existing.jpg'},
                {'id': 'image-b', 'sha256': 'b' * 64, 'url': 'https://example.org/new%20photo.jpg?download=1'}]
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            path = cache / a.key('b' * 64)
            path.parent.mkdir(parents=True)
            path.write_bytes(b'x' * 1234)
            with patch('sys.argv', ['asset_sync']), patch.object(a, 'records', return_value=rows), \
                 patch.object(a, 'configured_destination', return_value='s3://bucket'), \
                 patch.object(a, 'DEFAULT_CACHE', cache), patch.object(a, 'verified', return_value=True), \
                 patch.object(a, 'list_manifest_objects', return_value={a.key('a' * 64)}) as listing, \
                 patch.object(a, 'verify_backup') as verify, patch.object(a, 'upload') as upload, \
                 patch.object(a, 'save_verification'), patch('sys.stdout', new_callable=io.StringIO) as out:
                def check_progress(*args):
                    self.assertIn('Uploading new photo.jpg (1,234 bytes)\n', out.getvalue())
                upload.side_effect = check_progress
                a.main()
                self.assertNotIn('existing.jpg', out.getvalue())
            listing.assert_called_once()
            verify.assert_called_once_with(rows[0], cache, 's3://bucket')
            upload.assert_called_once_with(path, 'b' * 64, 's3://bucket')

    def test_ci_verification_has_no_listing_or_local_setup_dependency(self):
        from soso.assets import asset_sync_ci
        ci = {'GITHUB_ACTIONS': 'true', 'GITHUB_REF': 'refs/heads/main',
              'GITHUB_EVENT_NAME': 'workflow_dispatch', 'SOSO_ASSET_BACKUP': 's3://bucket'}
        with patch.dict(a.os.environ, ci, clear=True), patch.object(a, 'records', return_value=[]), \
             patch.object(a, 'verify_assets', return_value=True) as verify, \
             patch.object(a, 'list_manifest_objects') as listing, patch.object(a, 'configured_destination') as config:
            self.assertEqual(asset_sync_ci.main(), 0)
        verify.assert_called_once_with([], a.DEFAULT_CACHE, 's3://bucket')
        listing.assert_not_called()
        config.assert_not_called()

    def test_metadata_verify_without_cache_never_downloads(self):
        from soso.assets import asset_integrity
        with tempfile.TemporaryDirectory() as tmp:
            record={'id':'x','sha256':'a'*64,'checksums':{'size':1,'md5':'b'*32,'crc32c':'c'*8,'sha1':'d'*40}}
            report={'uri':'s3://bucket/key','checksum':'b'*32}
            with patch.object(asset_integrity,'verify_record',return_value=report) as check, patch.object(a.asset_storage,'transfer') as transfer, patch('urllib.request.urlopen') as get:
                self.assertEqual(a.verify_backup(record,Path(tmp),'bucket'),report)
                self.assertEqual(check.call_args.args[0],{**record['checksums'],'sha256':record['sha256']})
                transfer.assert_not_called();get.assert_not_called()
            a.save_verification(Path(tmp),report)
            self.assertEqual(json.loads((Path(tmp)/'verification.json').read_text()),{report['uri']:report})

    def test_verify_and_repeat_upload_do_not_require_local_report(self):
        from soso.assets import asset_integrity
        with tempfile.TemporaryDirectory() as tmp:
            cache=Path(tmp); path=cache/'source';path.write_bytes(b'original');sha=a.digest(path)
            storage=a.asset_storage.parse('az://account/photos')
            report={'uri':storage.uri(sha),'sha256':sha,'etag':'etag','verification':'service-metadata'}
            record={'id':'x','sha256':sha,'checksums':{'size':8,'md5':'b'*32,'crc32c':'c'*8,'sha1':'d'*40}}
            with patch.object(asset_integrity,'verify_record',return_value=report) as verify:
                a.verify_backup(record,cache,'az://account/photos')
                self.assertEqual(verify.call_args.kwargs,{})
            with patch.object(asset_integrity,'upload',return_value=report) as upload:
                a.upload(path,sha,'az://account/photos')
                self.assertEqual(upload.call_args.kwargs,{})
            self.assertFalse((cache/'verification.json').exists())

    def test_saved_destination_and_explicit_override(self):
        from soso.assets import asset_setup
        with patch.object(asset_setup,'load_storage_config',return_value={'backup':'gs://bucket/path'}) as load:
            self.assertEqual(a.configured_destination(),'gs://bucket/path')
            load.assert_called_once_with(a.ROOT/'assets/setup')
        with patch.object(asset_setup,'load_storage_config') as load:
            self.assertEqual(a.configured_destination('s3://override/path'),'s3://override/path')
            load.assert_not_called()

    def test_saved_compatible_endpoint_binding_applies_to_matching_override(self):
        from soso.assets import asset_setup
        for provider, variable, expected, other in (
            ('r2', 'SOSO_R2_ACCOUNT_ID', 'a' * 32, 'b' * 32),
            ('b2', 'SOSO_B2_REGION', 'us-west-004', 'us-east-005'),
        ):
            uri = f'{provider}://bucket/path'
            saved = {'backup': uri, 'endpoint_identity': expected}
            with self.subTest(provider=provider), patch.object(asset_setup, 'load_storage_config', return_value=saved):
                with patch.dict(a.os.environ, {variable: expected}, clear=True):
                    self.assertEqual(a.configured_destination(), uri)
                    self.assertEqual(a.configured_destination(uri + '/'), uri + '/')
                for env in ({}, {variable: other}):
                    with patch.dict(a.os.environ, env, clear=True):
                        for selected in (None, uri, uri + '/'):
                            with self.assertRaisesRegex(ValueError, variable):
                                a.configured_destination(selected)
                        self.assertEqual(a.configured_destination(f'{provider}://different/path'),
                                         f'{provider}://different/path')


if __name__=='__main__': unittest.main()

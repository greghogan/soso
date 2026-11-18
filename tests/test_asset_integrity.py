import base64
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from soso.assets import asset_integrity as i
from soso.assets.asset_storage import parse


class IntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/'asset'; self.path.write_bytes(b'exact')
        self.local = i.record(self.path); self.sha = self.local['sha256']

    def test_hashes_and_cap(self):
        self.assertEqual(self.local['size'], 5)
        self.assertEqual(set(self.local), {'size', 'sha256', 'md5', 'sha1', 'crc32c'})
        with patch.object(i, 'MAX_BYTES', 4), self.assertRaises(ValueError): i.record(self.path)

    def test_s3_single_request_sha256_md5_no_get(self):
        sdk = MagicMock(); sdk.head_object.return_value = {'ContentLength':5, 'ChecksumSHA256':i.encoded(self.sha)}
        with patch.object(i.asset_aws,'client',return_value=sdk):
            report=i.upload(self.path,self.sha,parse('s3://bucket'))
        params=sdk.put_object.call_args.kwargs
        self.assertEqual(params['ChecksumSHA256'],i.encoded(self.sha))
        self.assertEqual(params['ContentMD5'],i.encoded(self.local['md5']))
        self.assertEqual(params['IfNoneMatch'],'*')
        sdk.head_object.assert_called_once_with(Bucket='bucket',Key='sha256/'+self.sha[:2]+'/'+self.sha,ChecksumMode='ENABLED')
        sdk.get_object.assert_not_called(); sdk.upload_file.assert_not_called()
        self.assertEqual(report['checksum_algorithm'],'sha256')

    def test_s3_verification_reports_safe_actionable_errors(self):
        from botocore.exceptions import ClientError, EndpointConnectionError, NoCredentialsError, ProfileNotFound
        def response(code, status):
            return ClientError({'Error': {'Code': code, 'Message': 'do-not-print-token'},
                                'ResponseMetadata': {'HTTPStatusCode': status}}, 'HeadObject')
        cases = [
            (NoCredentialsError(), 'No AWS credentials found'),
            (ProfileNotFound(profile='do-not-print-token'), 'AWS profile was not found'),
            (response('403', 403), 'object may not exist'),
            (response('ExpiredToken', 403), 'rejected the credentials'),
            (response('NoSuchBucket', 404), 'configured bucket'),
            (EndpointConnectionError(endpoint_url='https://do-not-print-token'), 'Could not reach S3'),
        ]
        for error, message in cases:
            with self.subTest(message=message):
                sdk = MagicMock()
                sdk.head_object.side_effect = error
                with patch.object(i.asset_aws, 'client', return_value=sdk), self.assertRaisesRegex(RuntimeError, message) as err:
                    i.verify_record(self.local, self.sha, parse('s3://bucket'))
                self.assertIn('No object download attempted', str(err.exception))
                self.assertNotIn('do-not-print-token', str(err.exception))
                sdk.get_object.assert_not_called()

    def test_s3_head_not_found_has_separate_status(self):
        from botocore.exceptions import ClientError
        sdk = MagicMock()
        sdk.head_object.side_effect = ClientError(
            {'Error': {'Code': '404'}, 'ResponseMetadata': {'HTTPStatusCode': 404}}, 'HeadObject')
        with patch.object(i.asset_aws, 'client', return_value=sdk), self.assertRaises(i.BackupObjectMissing):
            i.verify_record(self.local, self.sha, parse('s3://bucket'))
        sdk.get_object.assert_not_called()

    def test_r2_md5_and_multipart_rejection(self):
        sdk=MagicMock(); sdk.head_object.return_value={'ContentLength':5,'ETag':'"'+self.local['md5']+'"'}
        with patch.object(i.asset_aws,'client',return_value=sdk):
            self.assertEqual(i.upload(self.path,self.sha,parse('r2://bucket'))['checksum_algorithm'],'md5')
            sdk.head_object.return_value['ETag']='"'+self.local['md5']+'-2"'
            with self.assertRaises(ValueError): i.verify(self.path,self.sha,parse('r2://bucket'))
        sdk.get_object.assert_not_called()

    def test_s3_missing_or_composite_checksum_never_custom_metadata(self):
        sdk=MagicMock()
        for data in [{'ContentLength':5,'Metadata':{'sha256':self.sha}},
                     {'ContentLength':5,'ChecksumSHA256':i.encoded(self.sha),'ChecksumType':'COMPOSITE'},
                     {'ContentLength':5,'ETag':self.local['md5'],'ServerSideEncryption':'aws:kms'}]:
            sdk.head_object.return_value=data
            with self.subTest(data=data), self.assertRaises(ValueError): i.s3_verify(parse('s3://bucket'),self.sha,self.local,sdk)

    def test_gcs_checks_native_md5_crc_and_no_download(self):
        blob=MagicMock(); blob.size=5; blob.generation=123; blob.md5_hash=i.encoded(self.local['md5']);blob.crc32c=i.encoded(self.local['crc32c'])
        with patch.object(i.asset_gcs,'client') as client:
            client.return_value.bucket.return_value.blob.return_value=blob
            report=i.upload(self.path,self.sha,parse('gs://bucket'))
            self.assertEqual(report['checksum_algorithm'],'crc32c')
            self.assertEqual(blob.upload_from_filename.call_args.kwargs['if_generation_match'],0)
            self.assertIsNone(blob.upload_from_filename.call_args.kwargs['checksum'])
            blob.download_to_filename.assert_not_called();blob.delete.assert_not_called()
            blob.crc32c=i.encoded('00000000')
            with self.assertRaises(ValueError):i.verify(self.path,self.sha,parse('gs://bucket'))

    def test_azure_single_put_native_md5_no_download(self):
        props=SimpleNamespace(content_settings=SimpleNamespace(content_md5=bytes.fromhex(self.local['md5'])),size=5,version_id=None,etag='etag-123')
        with patch.object(i.asset_azure,'credential'), patch.object(i.asset_azure,'service_client') as service, patch('azure.storage.blob.BlobServiceClient') as upload_service:
            blob=service.return_value.__enter__.return_value.get_blob_client.return_value
            blob.get_blob_properties.return_value=props
            upload_service.return_value.__enter__.return_value.get_blob_client.return_value.upload_blob.return_value={'etag':'etag-123'}
            report=i.upload(self.path,self.sha,parse('az://account/container'))
            self.assertEqual(i.verify(self.path,self.sha,parse('az://account/container'))['checksum'], self.local['md5'])
            self.assertEqual(upload_service.call_args.kwargs['max_single_put_size'],i.MAX_BYTES)
            up=upload_service.return_value.__enter__.return_value.get_blob_client.return_value.upload_blob.call_args.kwargs
            self.assertEqual(up['content_settings'].content_md5,bytes.fromhex(self.local['md5']))
            self.assertEqual(up['length'],5);self.assertFalse(up['overwrite'])
            self.assertEqual(report['checksum_algorithm'],'md5');blob.download_blob.assert_not_called()

    def test_b2_metadata_native_checksum_no_get(self):
        from botocore.exceptions import ClientError
        sdk=MagicMock(); native=MagicMock();native.prefix=''
        data={'ContentLength':5,'VersionId':'v1'}
        info={'contentLength':5,'contentSha1':self.local['sha1'],'fileId':'v1'}
        sdk.head_object.return_value=data;native.info.return_value=info
        with patch.object(i.asset_aws,'client',return_value=sdk),patch.object(i.asset_b2_metadata,'Metadata',return_value=native):
            self.assertEqual(i.upload(self.path,self.sha,parse('b2://bucket'))['checksum_algorithm'],'sha1')
            sdk.put_object.assert_not_called()
            sdk.head_object.side_effect=[ClientError({'Error':{'Code':'404'},'ResponseMetadata':{'HTTPStatusCode':404}},'HeadObject'),data]
            sdk.put_object.return_value={'VersionId':'v1'}
            with patch.object(i.asset_storage,'verify_b2_retention') as retention:
                i.upload(self.path,self.sha,parse('b2://bucket')); retention.assert_called_once()
            self.assertEqual(sdk.put_object.call_count,1)
            sdk.get_object.assert_not_called()
            native.info.return_value={**info,'contentSha1':'unverified:'+self.local['sha1']}
            sdk.head_object.side_effect=None
            with self.assertRaises(ValueError):i.verify(self.path,self.sha,parse('b2://bucket'))
            sdk.head_object.side_effect=ClientError({'Error':{'Code':'403'},'ResponseMetadata':{'HTTPStatusCode':403}},'HeadObject')
            with self.assertRaises(RuntimeError):i.upload(self.path,self.sha,parse('b2://bucket'))
            self.assertEqual(sdk.put_object.call_count,1)

    def test_native_b2_endpoint_and_identity_validation(self):
        from soso.assets.asset_b2_metadata import Metadata
        auth={'accountId':'account-id','authorizationToken':'private','apiInfo':{'storageApi':{'apiUrl':'https://api001.backblazeb2.com',
              'allowed':{'buckets':[{'id':'bucket-id','name':'bucket'}],'capabilities':['readFiles'],'namePrefix':''}}}}
        info={'accountId':'account-id','action':'upload','fileId':'v1','bucketId':'bucket-id','fileName':'key','contentLength':5,'contentSha1':self.local['sha1']}
        with patch.dict('os.environ',{'SOSO_B2_ACCESS_KEY_ID':'key','SOSO_B2_SECRET_ACCESS_KEY':'secret'},clear=True),patch.object(i.asset_b2_metadata,'request',side_effect=[auth,info]) as request:
            native=Metadata('bucket');self.assertEqual(native.info('key','v1'),info)
            self.assertTrue(request.call_args.args[0].startswith('https://api001.backblazeb2.com/'))
            with self.assertRaises(ValueError):native.check(info,'different','v1')
            with self.assertRaises(ValueError):native.check(info,'key','different')
        auth['apiInfo']['storageApi']['apiUrl']='https://evil.example'
        with patch.dict('os.environ',{'SOSO_B2_ACCESS_KEY_ID':'key','SOSO_B2_SECRET_ACCESS_KEY':'secret'},clear=True),patch.object(i.asset_b2_metadata,'request',return_value=auth) as request:
            with self.assertRaises(ValueError):Metadata('bucket')
            self.assertEqual(request.call_count,1)

    def test_provider_errors_are_sanitized(self):
        from botocore.exceptions import ClientError
        from google.auth.exceptions import DefaultCredentialsError
        with patch.object(i.asset_aws,'client') as client:
            client.return_value.head_object.side_effect=ClientError({'Error':{'Code':'AccessDenied','Message':'secret'}},'HeadObject')
            with self.assertRaises(RuntimeError) as caught: i.verify(self.path,self.sha,parse('s3://bucket'))
            self.assertNotIn('secret',str(caught.exception))
        with patch.object(i.asset_gcs,'client',side_effect=DefaultCredentialsError('secret')):
            with self.assertRaises(RuntimeError) as caught: i.verify(self.path,self.sha,parse('gs://bucket'))
            self.assertNotIn('secret',str(caught.exception))

    def test_azure_verifies_without_local_receipt_but_rejects_bad_metadata(self):
        storage=parse('az://account/container')
        props=SimpleNamespace(content_settings=SimpleNamespace(content_md5=bytes.fromhex(self.local['md5'])),size=5,version_id=None,etag='changed')
        with patch.object(i.asset_azure,'credential'),patch.object(i.asset_azure,'service_client') as service:
            blob=service.return_value.__enter__.return_value.get_blob_client.return_value
            blob.get_blob_properties.return_value=props
            self.assertEqual(i.verify_record(self.local,self.sha,storage)['etag'],'changed')
            for md5,size in [(None,5),(bytes(16),5),(bytes.fromhex(self.local['md5']),6)]:
                props.content_settings.content_md5=md5;props.size=size
                with self.assertRaises(ValueError):i.verify_record(self.local,self.sha,storage)
            blob.download_blob.assert_not_called()

    def test_b2_missing_checksum_or_bad_size_unverified(self):
        storage=parse('b2://bucket')
        for data in [{'fileId':'v1','contentLength':5,'contentSha1':'none'},
                     {'fileId':'v1','contentLength':5,'contentSha1':'unverified:'+self.local['sha1']},
                     {'fileId':'v1','contentLength':6,'contentSha1':self.local['sha1']}]:
            with self.subTest(data=data),self.assertRaises(ValueError):i.b2_native_result(storage,self.sha,self.local,data)

    def test_existing_azure_upload_checks_metadata_without_receipt(self):
        from azure.core.exceptions import ResourceExistsError
        storage=parse('az://account/container')
        props=SimpleNamespace(content_settings=SimpleNamespace(content_md5=bytes.fromhex(self.local['md5'])),size=5,version_id=None,etag='original')
        with patch.object(i.asset_azure,'credential'),patch.object(i.asset_azure,'service_client') as service,patch('azure.storage.blob.BlobServiceClient') as upload_service:
            blob=service.return_value.__enter__.return_value.get_blob_client.return_value
            blob.get_blob_properties.return_value=props
            put=upload_service.return_value.__enter__.return_value.get_blob_client.return_value.upload_blob
            put.side_effect=ResourceExistsError('already exists')
            self.assertEqual(i.upload(self.path,self.sha,storage)['etag'],'original')
            props.content_settings.content_md5=bytes(16)
            with self.assertRaises(ValueError):i.upload(self.path,self.sha,storage)
            self.assertFalse(put.call_args.kwargs['overwrite'])
            blob.download_blob.assert_not_called()

"""Native AWS adapter tests: synthetic credentials and Stubber, no cloud calls."""
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import boto3
from botocore.response import StreamingBody
from botocore.stub import Stubber, ANY
from soso.assets import asset_aws as a


class AwsTests(unittest.TestCase):
    def sdk(self, service='s3'):
        return boto3.client(service, region_name='us-east-1', aws_access_key_id='test', aws_secret_access_key='test')

    def test_error_code_uses_get_body_and_head_is_ambiguous(self):
        sdk = self.sdk()
        with Stubber(sdk) as stub, patch.object(a, 'client', return_value=sdk):
            stub.add_client_error('head_bucket', service_error_code='404', http_status_code=404,
                                  expected_params={'Bucket':'bucket','ExpectedBucketOwner':'123456789012'})
            stub.add_client_error('get_bucket_location', service_error_code='NoSuchBucket', http_status_code=404,
                                  expected_params={'Bucket':'bucket','ExpectedBucketOwner':'123456789012'})
            for operation, code in [('head-bucket','404'),('get-bucket-location','NoSuchBucket')]:
                with self.assertRaises(a.AWSCommandError) as error:
                    a.request('s3api',operation,'--bucket','bucket','--expected-bucket-owner','123456789012')
                self.assertEqual(error.exception.code,code)

    def test_setup_structures_and_pagination(self):
        sdk = self.sdk()
        with Stubber(sdk) as stub, patch.object(a,'client',return_value=sdk):
            stub.add_response('put_public_access_block', {}, {'Bucket':'bucket','PublicAccessBlockConfiguration':{'BlockPublicAcls':True,'IgnorePublicAcls':True,'BlockPublicPolicy':True,'RestrictPublicBuckets':True}})
            a.request('s3api','put-public-access-block','--bucket','bucket','--public-access-block-configuration','BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true')
            stub.add_response('list_objects_v2',{'KeyCount':0,'IsTruncated':False},{'Bucket':'bucket','MaxKeys':1})
            self.assertEqual(a.request('s3api','list-objects-v2','--bucket','bucket','--max-keys','1','--no-paginate')['KeyCount'],0)
        sdk = self.sdk('iam')
        with Stubber(sdk) as stub, patch.object(a,'client',return_value=sdk):
            stub.add_response('list_role_policies',{'PolicyNames':['first'],'IsTruncated':True,'Marker':'next'},{'RoleName':'role'})
            stub.add_response('list_role_policies',{'PolicyNames':['second'],'IsTruncated':False},{'RoleName':'role','Marker':'next'})
            self.assertEqual(a.request('iam','list-role-policies','--role-name','role')['PolicyNames'],['first','second'])

    def test_download_stream_closed(self):
        sdk=self.sdk(); body=StreamingBody(io.BytesIO(b'exact'),5)
        with tempfile.TemporaryDirectory() as tmp, Stubber(sdk) as stub, patch.object(a,'client',return_value=sdk):
            stub.add_response('get_object',{'Body':body},{'Bucket':'bucket','Key':'key'})
            target=Path(tmp)/'file'
            a.request('s3api','get-object','--bucket','bucket','--key','key',str(target))
            self.assertEqual(target.read_bytes(),b'exact')
            self.assertTrue(body._raw_stream.closed)

    def test_compatible_credentials_endpoints_retries(self):
        env={'AWS_PROFILE':'nonexistent','AWS_ACCESS_KEY_ID':'wrong','AWS_SECRET_ACCESS_KEY':'wrong',
             'AWS_SESSION_TOKEN':'wrong','AWS_ENDPOINT_URL':'https://wrong.invalid',
             'SOSO_R2_ACCESS_KEY_ID':'dedicated','SOSO_R2_SECRET_ACCESS_KEY':'private','SOSO_R2_ACCOUNT_ID':'a'*32,
             'SOSO_B2_ACCESS_KEY_ID':'dedicated','SOSO_B2_SECRET_ACCESS_KEY':'private','SOSO_B2_REGION':'us-west-004'}
        with patch.dict(os.environ,env,clear=True):
            for provider in ('r2','b2'):
                sdk=a.client(provider=provider)
                creds=sdk._request_signer._credentials
                self.assertEqual(creds.access_key,'dedicated')
                self.assertEqual(creds.secret_key,'private')
                self.assertIsNone(creds.token)
                self.assertNotIn('wrong',sdk.meta.endpoint_url)
                if provider=='b2': self.assertEqual(sdk.meta.config.retries['total_max_attempts'],1)

    def test_aws_shared_profile_credentials_and_session_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            credentials=Path(tmp)/'credentials'; config=Path(tmp)/'config'
            credentials.write_text('[developer]\naws_access_key_id = local-key\naws_secret_access_key = local-secret\naws_session_token = local-token\n')
            config.write_text('[profile developer]\nregion = us-west-2\n')
            with patch.dict(os.environ, {'AWS_SHARED_CREDENTIALS_FILE':str(credentials), 'AWS_CONFIG_FILE':str(config), 'AWS_PROFILE':'developer', 'AWS_EC2_METADATA_DISABLED':'true'}, clear=True):
                sdk=a.client()
                self.assertEqual(sdk._request_signer._credentials.access_key,'local-key')
                self.assertEqual(sdk._request_signer._credentials.token,'local-token')
                self.assertEqual(a.region_default(),'us-west-2')

    def test_sdk_conditional_put_and_conflict(self):
        sdk=self.sdk()
        with tempfile.TemporaryDirectory() as tmp, Stubber(sdk) as stub, patch.object(a,'client',return_value=sdk):
            source=Path(tmp)/'file';source.write_bytes(b'exact')
            params={'Bucket':'bucket','Key':'key','Body':ANY,'IfNoneMatch':'*','ServerSideEncryption':'AES256'}
            stub.add_response('put_object', {'ETag':'"etag"'},params)
            args=('s3api','put-object','--bucket','bucket','--key','key','--body',str(source),'--if-none-match','*','--server-side-encryption','AES256')
            a.request(*args)
            stub.add_client_error('put_object',service_error_code='PreconditionFailed',http_status_code=412,expected_params=params)
            with self.assertRaisesRegex(RuntimeError,'PreconditionFailed'): a.request(*args)

    def test_delete_never_retries_for_any_s3_provider(self):
        env={'AWS_ACCESS_KEY_ID':'test','AWS_SECRET_ACCESS_KEY':'test',
             'AWS_DEFAULT_REGION':'us-east-1','AWS_MAX_ATTEMPTS':'10',
             'SOSO_R2_ACCESS_KEY_ID':'dedicated','SOSO_R2_SECRET_ACCESS_KEY':'private','SOSO_R2_ACCOUNT_ID':'a'*32,
             'SOSO_B2_ACCESS_KEY_ID':'dedicated','SOSO_B2_SECRET_ACCESS_KEY':'private','SOSO_B2_REGION':'us-west-004'}
        with patch.dict(os.environ,env,clear=True):
            for provider in ('s3','r2','b2'):
                with self.subTest(provider=provider):
                    sdk=a.client(provider=provider, retry=False)
                    self.assertEqual(sdk.meta.config.retries['total_max_attempts'],1)
                    with Stubber(sdk) as stub, patch.object(a,'client',return_value=sdk) as factory:
                        stub.add_response('delete_object',{}, {'Bucket':'bucket','Key':'key'})
                        a.request('s3api','delete-object','--bucket','bucket','--key','key',provider=provider)
                        self.assertFalse(factory.call_args.kwargs['retry'])

    def test_service_errors_redacted_and_missing_is_explicit(self):
        sdk=self.sdk()
        with Stubber(sdk) as stub, patch.object(a,'client',return_value=sdk):
            for code, exception in [('NoSuchKey',a.ObjectNotFound),('404',RuntimeError),('AccessDenied',RuntimeError)]:
                stub.add_client_error('get_object',service_error_code=code,service_message='private diagnostic',http_status_code=404,expected_params={'Bucket':'bucket','Key':'key'})
                with self.assertRaises(exception) as error:
                    a.request('s3api','get-object','--bucket','bucket','--key','key','/unused',provider='b2')
                self.assertNotIn('private diagnostic',str(error.exception))

    def test_put_condition_and_version_pinning(self):
        from types import SimpleNamespace
        storage=SimpleNamespace(provider='r2',bucket='bucket',object_key=lambda sha:'key')
        with patch.object(a,'request',return_value={}) as request:
            a.transfer(storage,'put','a'*64,Path('/tmp/file'))
            self.assertIn('--if-none-match',request.call_args.args)
            self.assertNotIn('--server-side-encryption',request.call_args.args)
            storage.provider='b2'
            a.transfer(storage,'put','a'*64,Path('/tmp/file'))
            self.assertNotIn('--if-none-match',request.call_args.args)
            a.transfer(storage,'get','a'*64,Path('/tmp/file'),version_id='version-123')
            self.assertIn('--version-id',request.call_args.args)
            with self.assertRaises(ValueError): a.transfer(storage,'delete','a'*64,version_id='version-123')


if __name__ == '__main__': unittest.main()

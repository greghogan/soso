"""Metadata-only backup integrity checks. Never retrieves object bodies.

SHA-256 is the content address. Checks assume a dedicated location written by
this workflow. Provider checksum fields are compared; custom user metadata is
never accepted as checksum evidence. Azure content MD5 is trusted under this
workflow assumption, not as proof against an independent metadata writer.
"""
import base64
import hashlib
import re
from pathlib import Path
from functools import wraps

from . import asset_aws, asset_gcs, asset_azure, asset_storage, asset_b2_metadata

MAX_BYTES = 256 * 1024 * 1024


class BackupObjectMissing(RuntimeError):
    """Metadata lookup returned not found at the configured object path."""


def record(path):
    import google_crc32c
    hashes = {name: hashlib.new(name) for name in ('sha256', 'md5', 'sha1')}
    crc = google_crc32c.Checksum()
    size = 0
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            size += len(chunk)
            if size > MAX_BYTES:
                raise ValueError('Asset exceeds 256 MiB single-request upload limit')
            for digest in hashes.values(): digest.update(chunk)
            crc.update(chunk)
    return {'size': size, **{name: h.hexdigest() for name, h in hashes.items()},
            'crc32c': crc.hexdigest().decode('ascii')}


def encoded(value):
    return base64.b64encode(bytes.fromhex(value)).decode('ascii')


def checked(local, sha):
    if local['sha256'] != sha:
        raise ValueError('Refusing unverified local asset')


def result(storage, sha, local, algorithm, actual, size, version=None):
    if size != local['size'] or not isinstance(actual, str) or actual.lower() != local[algorithm]:
        raise ValueError(f'{storage.provider.upper()} stored checksum or size mismatch; no overwrite attempted')
    return {'provider': storage.provider, 'uri': storage.uri(sha), 'sha256': sha,
            'size': size, 'checksum_algorithm': algorithm, 'checksum': actual.lower(),
            'version': version, 'verification': 'service-metadata'}


def decode(value):
    try: return base64.b64decode(value, validate=True).hex()
    except (ValueError, TypeError): raise ValueError('Missing or invalid service checksum; object is UNVERIFIED') from None


def s3_verify(storage, sha, local, sdk, version=None, native=None):
    params = {'Bucket': storage.bucket, 'Key': storage.object_key(sha)}
    if storage.provider == 's3': params['ChecksumMode'] = 'ENABLED'
    if version: params['VersionId'] = version
    data = sdk.head_object(**params)
    size = data.get('ContentLength')
    if storage.provider == 's3' and data.get('ChecksumSHA256'):
        if data.get('ChecksumType', 'FULL_OBJECT') != 'FULL_OBJECT':
            raise ValueError('Composite checksum cannot verify the full object')
        return result(storage, sha, local, 'sha256', decode(data['ChecksumSHA256']), size, data.get('VersionId'))
    if storage.provider == 'b2':
        return b2_verify(storage, sha, local, data, native=native)
    # Only documented single-part ETags, never multipart hashes or opaque Azure ETags.
    etag = data.get('ETag', '').strip('"')
    if (not re.fullmatch('[0-9a-fA-F]{32}', etag) or data.get('ServerSideEncryption') not in (None, 'AES256')
            or data.get('SSECustomerAlgorithm')):
        raise ValueError('No supported service checksum; object is UNVERIFIED')
    return result(storage, sha, local, 'md5', etag, size, data.get('VersionId'))


def s3_service_error(exc, provider):
    """Return fixed, actionable diagnostics, never response text or credential values."""
    from botocore import exceptions as errors
    if isinstance(exc, errors.NoCredentialsError):
        return 'No AWS credentials found. Use the same AWS profile as setup (set AWS_PROFILE if it is not the default).'
    if isinstance(exc, errors.PartialCredentialsError):
        return 'AWS credentials are incomplete. Check the AWS profile and remove any incomplete credential environment variables.'
    if isinstance(exc, errors.ProfileNotFound):
        return 'The selected AWS profile was not found. Use the profile that configured the backup.'
    if isinstance(exc, (errors.UnauthorizedSSOTokenError, errors.TokenRetrievalError)):
        return 'AWS could not refresh credentials. Renew the selected profile or session and retry.'
    if isinstance(exc, (errors.ConnectionError, errors.HTTPClientError)):
        return f'Could not reach {provider.upper()} over HTTPS. Check the network and configured region or endpoint.'
    if not isinstance(exc, errors.ClientError):
        return f'{provider.upper()} request failed. Check the selected profile or provider configuration.'
    code = exc.response.get('Error', {}).get('Code')
    status = exc.response.get('ResponseMetadata', {}).get('HTTPStatusCode')
    if code in {'ExpiredToken', 'ExpiredTokenException', 'InvalidToken', 'InvalidAccessKeyId', 'SignatureDoesNotMatch', 'InvalidClientTokenId'}:
        return f'{provider.upper()} rejected the credentials or session token. Check or refresh the selected profile.'
    if code in {'PermanentRedirect', 'AuthorizationHeaderMalformed', 'IncorrectEndpoint'} or status in (301, 307):
        return f'{provider.upper()} rejected the endpoint or region. Check the configured bucket region.'
    if code == 'NoSuchBucket':
        return f'{provider.upper()} could not find the configured bucket. Check the saved destination.'
    if code in {'NoSuchKey', 'NotFound', '404'} or status == 404:
        return f'{provider.upper()} returned 404 for the object. Check the bucket and prefix; if not yet uploaded, run ./scripts/asset_sync.py.'
    if code in {'AccessDenied', 'Forbidden', '403'} or status == 403:
        if provider == 's3':
            return ('S3 returned 403. The profile may lack s3:GetObject, or the object may not exist '
                    '(S3 can mask a missing object without s3:ListBucket). Check the backup or upload it if it is empty.')
        return f'{provider.upper()} returned 403. Check the configured key and its permission to read this object.'
    if status == 429 or code in {'SlowDown', 'Throttling', 'ThrottlingException'}:
        return f'{provider.upper()} rate-limited the request. Retry later.'
    return f'{provider.upper()} request failed' + (f' (HTTP {status}).' if type(status) is int and 100 <= status <= 599 else '.')


def safe_service_errors(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        from botocore.exceptions import BotoCoreError, ClientError
        from google.api_core.exceptions import GoogleAPICallError
        from google.auth.exceptions import GoogleAuthError
        from azure.core.exceptions import AzureError
        storage = kwargs['storage'] if 'storage' in kwargs else args[2]
        try:
            return function(*args, **kwargs)
        except (BotoCoreError, ClientError) as exc:
            raise RuntimeError(s3_service_error(exc, storage.provider) + ' No object download attempted.') from None
        except GoogleAuthError:
            raise RuntimeError('Google Cloud credentials were missing or rejected. Check Application Default Credentials. No object download attempted.') from None
        except (GoogleAPICallError, AzureError):
            raise RuntimeError('Storage request failed; check credentials, permissions and connectivity. No object download attempted.') from None
    return wrapped


def verify(path, sha, storage):
    return verify_record(record(path), sha, storage)


@safe_service_errors
def verify_record(local, sha, storage):
    checked(local, sha)
    if not isinstance(local.get('size'), int) or not 0 <= local['size'] <= MAX_BYTES:
        raise ValueError('Invalid asset size in checksum record')
    for name, length in (('sha256',64),('md5',32),('sha1',40),('crc32c',8)):
        if not re.fullmatch('[0-9a-f]{'+str(length)+'}', local.get(name,'')):
            raise ValueError('Missing or invalid '+name+' checksum in manifest')
    if storage.provider in ('s3', 'r2', 'b2'):
        from botocore.exceptions import ClientError
        sdk = asset_aws.client(provider=storage.provider)
        try:
            return s3_verify(storage, sha, local, sdk)
        except ClientError as exc:
            code = exc.response.get('Error', {}).get('Code')
            # A bare HEAD 404 is not proof the bucket/prefix is correct.
            # Never treat 403 as missing: S3 may mask missing objects as 403.
            if (storage.provider == 's3' and exc.operation_name == 'HeadObject'
                    and code in {'NoSuchKey', 'NotFound', '404'}):
                raise BackupObjectMissing('Not found at the configured backup path') from None
            raise
    if storage.provider == 'gs':
        blob = asset_gcs.client().bucket(storage.bucket).blob(storage.object_key(sha))
        blob.reload(timeout=60)
        report = result(storage, sha, local, 'crc32c', decode(blob.crc32c), blob.size, str(blob.generation))
        if blob.md5_hash:
            result(storage, sha, local, 'md5', decode(blob.md5_hash), blob.size)
            report['md5'] = decode(blob.md5_hash)
        return report
    if storage.provider == 'az':
        with asset_azure.credential() as identity, asset_azure.service_client(storage.account, identity) as service:
            data = service.get_blob_client(container=storage.bucket, blob=storage.object_key(sha)).get_blob_properties()
            md5 = data.content_settings.content_md5
            report = result(storage, sha, local, 'md5', bytes(md5).hex() if md5 else None, data.size, data.version_id)
            report.update(etag=data.etag)
            return report
    raise ValueError('Unsupported storage provider')


@safe_service_errors
def upload(path, sha, storage):
    local = record(path); checked(local, sha)
    if storage.provider in ('s3', 'r2', 'b2'):
        sdk = asset_aws.client(provider=storage.provider)
        from botocore.exceptions import ClientError
        if storage.provider == 'b2':
            native = asset_b2_metadata.Metadata(storage.bucket)
            key = storage.object_key(sha)
            if not key.startswith(native.prefix):
                raise ValueError('B2 key is outside authorized prefix; no upload attempted')
            try:
                return s3_verify(storage, sha, local, sdk, native=native)
            except ClientError as exc:
                # Backblaze documents HEAD object HTTP404 as absent. Authenticate
                # the exact bucket/prefix first; never classify 403 as absence.
                if exc.response.get('ResponseMetadata',{}).get('HTTPStatusCode') != 404:
                    raise
            asset_storage.verify_b2_retention(storage)
            with Path(path).open('rb') as source:
                response = sdk.put_object(Bucket=storage.bucket, Key=key, Body=source,
                                         ContentLength=local['size'], ContentMD5=encoded(local['md5']),
                                         ServerSideEncryption='AES256')
            version = response.get('VersionId')
            if not isinstance(version,str) or not version or version == 'null':
                raise ValueError('B2 upload may have succeeded but returned no version; no retry or cleanup attempted')
            # Native file identity checks fail closed if S3/native version formats differ.
            pinned = b2_native_result(storage,sha,local,native.info(key,version))
            current = s3_verify(storage,sha,local,sdk,native=native)
            return current
        params = {'Bucket': storage.bucket, 'Key': storage.object_key(sha),
                  'ContentMD5': encoded(local['md5']), 'IfNoneMatch': '*'}
        if storage.provider == 's3':
            params.update(ChecksumSHA256=encoded(sha), ServerSideEncryption='AES256')
        try:
            with Path(path).open('rb') as source:
                sdk.put_object(**params, Body=source, ContentLength=local['size'])
        except ClientError as exc:
            if exc.response.get('Error', {}).get('Code') != 'PreconditionFailed': raise
        return s3_verify(storage, sha, local, sdk)
    if storage.provider == 'gs':
        from google.api_core.exceptions import PreconditionFailed
        blob = asset_gcs.client().bucket(storage.bucket).blob(storage.object_key(sha))
        blob.md5_hash, blob.crc32c = encoded(local['md5']), encoded(local['crc32c'])
        try:
            blob.upload_from_filename(str(path), if_generation_match=0, checksum=None, timeout=60)
        except PreconditionFailed: pass
        return verify(path, sha, storage)
    if storage.provider == 'az':
        from azure.core.exceptions import ResourceExistsError, ResourceModifiedError
        from azure.storage.blob import ContentSettings, BlobServiceClient
        with asset_azure.credential() as identity, BlobServiceClient(
                f'https://{storage.account}.blob.core.windows.net', credential=identity,
                max_single_put_size=MAX_BYTES) as service:
            blob = service.get_blob_client(container=storage.bucket, blob=storage.object_key(sha))
            try:
                with Path(path).open('rb') as source:
                    blob.upload_blob(source, length=local['size'], overwrite=False, if_none_match='*',
                                     content_settings=ContentSettings(content_md5=bytes.fromhex(local['md5'])))
            except (ResourceExistsError, ResourceModifiedError): pass
        return verify(path, sha, storage)
    raise ValueError('Unsupported storage provider')


def b2_native_result(storage, sha, local, data):
    size = data.get('contentLength')
    for algorithm, field, length in (('sha1','contentSha1',40), ('md5','contentMd5',32)):
        value = data.get(field)
        if isinstance(value,str) and re.fullmatch('[0-9a-fA-F]{'+str(length)+'}',value):
            return result(storage,sha,local,algorithm,value,size,data['fileId'])
    raise ValueError('B2 native metadata has no validated whole-object checksum; object is UNVERIFIED')


def b2_verify(storage, sha, local, data, native=None):
    native = native or asset_b2_metadata.Metadata(storage.bucket)
    version = data.get('VersionId')
    info = native.info(storage.object_key(sha),version)
    if data.get('ContentLength') != info.get('contentLength'):
        raise ValueError('B2 HEAD/native metadata size mismatch; object is UNVERIFIED')
    return b2_native_result(storage,sha,local,info)

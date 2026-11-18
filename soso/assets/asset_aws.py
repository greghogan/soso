"""Boto3 adapter for asset storage and setup; never logs credentials or raw errors.

The small argument adapter retains the setup wizard's injectable operation calls.
It is not a shell or general-purpose AWS CLI emulator.
"""
import json
import os
from pathlib import Path
import re


class AWSCommandError(RuntimeError):
    def __init__(self, code='Unknown'):
        self.code = code
        super().__init__('AWS operation failed (' + code + '); inspect AWS before retrying mutations.')


class ObjectNotFound(RuntimeError):
    """The service explicitly returned NoSuchKey, never inferred from HTTP 404."""


def client(service='s3', provider='s3', region=None, *, retry=True):
    import boto3
    from botocore.config import Config
    from botocore.session import Session
    from botocore.configprovider import ConstantProvider
    config = dict(connect_timeout=15, read_timeout=45,
                  retries={'mode': 'standard', 'total_max_attempts': 3 if retry else 1})
    if provider == 's3':
        return boto3.Session().client(service, region_name=region, config=Config(**config))
    stem = 'SOSO_' + provider.upper() + '_'
    access = os.environ.get(stem + 'ACCESS_KEY_ID', '')
    secret = os.environ.get(stem + 'SECRET_ACCESS_KEY', '')
    if not access or not secret:
        raise ValueError(f'Set dedicated {stem}ACCESS_KEY_ID and {stem}SECRET_ACCESS_KEY; ambient AWS credentials are never used.')
    if provider == 'r2':
        account = os.environ.get(stem + 'ACCOUNT_ID', '')
        if not re.fullmatch(r'[0-9a-f]{32}', account):
            raise ValueError('SOSO_R2_ACCOUNT_ID must be the 32-character Cloudflare account ID.')
        endpoint, region = f'https://{account}.r2.cloudflarestorage.com', 'auto'
    elif provider == 'b2':
        region = os.environ.get(stem + 'REGION', '')
        if not re.fullmatch(r'[a-z]{2}-[a-z]+-[0-9]{3}', region):
            raise ValueError('SOSO_B2_REGION must be the B2 region, for example us-west-004.')
        endpoint = f'https://s3.{region}.backblazeb2.com'
        # A lost upload response must not silently append another version.
        config['retries'] = {'mode': 'standard', 'total_max_attempts': 1}
    else:
        raise ValueError('Unsupported compatible provider')
    # Separate config prevents ambient AWS profiles, tokens and endpoint settings
    # from selecting another identity or vendor. No process environment mutation.
    session = Session()
    session.set_config_variable('config_file', os.devnull)
    session.set_config_variable('credentials_file', os.devnull)
    session.get_component('config_store').set_config_provider('profile', ConstantProvider(None))
    session.get_component('config_store').set_config_provider('data_path', ConstantProvider(None))
    session.set_credentials(access, secret)
    config.update(ignore_configured_endpoint_urls=True, signature_version='s3v4',
                  s3={'addressing_style': 'path'},
                  request_checksum_calculation='when_required',
                  response_checksum_validation='when_required')
    return boto3.Session(botocore_session=session).client(
        's3', endpoint_url=endpoint, region_name=region,
        aws_access_key_id=access, aws_secret_access_key=secret,
        aws_session_token=None, config=Config(**config))


def region_default():
    import boto3
    return boto3.Session().region_name or ''


_ALLOWED = {
    'sts': {'get-caller-identity'},
    'iam': {'get-open-id-connect-provider', 'get-role', 'list-attached-role-policies',
            'list-role-policies', 'get-role-policy'},
    's3api': {'head-bucket', 'get-bucket-location', 'get-public-access-block',
              'get-bucket-ownership-controls', 'get-bucket-versioning',
              'get-bucket-encryption', 'get-bucket-lifecycle-configuration',
              'list-objects-v2', 'list-object-versions', 'create-bucket',
              'put-public-access-block', 'put-bucket-encryption', 'put-bucket-versioning',
              'get-object', 'put-object', 'delete-object'},
}
_NAMES = {
    'bucket': 'Bucket', 'key': 'Key', 'expected-bucket-owner': 'ExpectedBucketOwner',
    'prefix': 'Prefix', 'max-keys': 'MaxKeys', 'object-ownership': 'ObjectOwnership',
    'create-bucket-configuration': 'CreateBucketConfiguration',
    'public-access-block-configuration': 'PublicAccessBlockConfiguration',
    'server-side-encryption-configuration': 'ServerSideEncryptionConfiguration',
    'versioning-configuration': 'VersioningConfiguration',
    'open-id-connect-provider-arn': 'OpenIDConnectProviderArn',
    'role-name': 'RoleName', 'policy-name': 'PolicyName', 'version-id': 'VersionId',
    'if-none-match': 'IfNoneMatch', 'server-side-encryption': 'ServerSideEncryption',
}
_STRUCTURES = {'CreateBucketConfiguration', 'PublicAccessBlockConfiguration',
               'ServerSideEncryptionConfiguration', 'VersioningConfiguration'}


def request(*args, provider='s3'):
    """Execute one known operation, using service error codes, not stderr parsing."""
    if len(args) < 2 or args[1] not in _ALLOWED.get(args[0], ()):
        raise ValueError('Unsupported asset AWS operation')
    service, operation = args[:2]
    params, region, output, body_path = {}, None, None, None
    paginate = True
    rest = iter(args[2:])
    for arg in rest:
        if arg == '--no-paginate':
            paginate = False
            continue
        if not arg.startswith('--'):
            if operation != 'get-object' or output is not None:
                raise ValueError('Unexpected operation argument')
            output = Path(arg)
            continue
        value = next(rest, None)
        if value is None:
            raise ValueError('Missing operation argument value')
        if arg == '--region':
            region = value
        elif arg == '--body':
            body_path = Path(value)
        elif arg[2:] in _NAMES:
            name = _NAMES[arg[2:]]
            if name in _STRUCTURES:
                if value.startswith('{'):
                    value = json.loads(value)
                else:
                    value = dict(item.split('=', 1) for item in value.split(','))
                    value = {k: {'true': True, 'false': False}.get(v, v) for k, v in value.items()}
            if name == 'MaxKeys':
                value = int(value)
            params[name] = value
        else:
            raise ValueError('Unsupported operation option')
    from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError, PartialCredentialsError
    try:
        # Never replay a deletion after a lost response: another writer may have
        # recreated the key between attempts. Confirmation covers one request.
        sdk = client('s3' if service == 's3api' else service, provider, region,
                     retry=operation != 'delete-object')
        method = operation.replace('-', '_')
        if body_path is not None:
            with body_path.open('rb') as stream:
                result = getattr(sdk, method)(**params, Body=stream)
        elif paginate and sdk.can_paginate(method):
            result = sdk.get_paginator(method).paginate(**params).build_full_result()
        else:
            result = getattr(sdk, method)(**params)
        if operation == 'get-object':
            stream = result.pop('Body')
            try:
                if output is None:
                    raise ValueError('Download requires a destination')
                with output.open('wb') as destination:
                    for block in stream.iter_chunks(chunk_size=1024 * 1024):
                        destination.write(block)
            finally:
                stream.close()
        result.pop('ResponseMetadata', None)
        return result
    except ClientError as error:
        code = error.response.get('Error', {}).get('Code', 'Unknown')
        # Limit output to service codes; untrusted diagnostics are never echoed.
        code = code if re.fullmatch(r'[A-Za-z0-9_.-]{1,80}', code) else 'Unknown'
        if provider != 's3':
            if code == 'PreconditionFailed':
                raise RuntimeError('PreconditionFailed') from None
            if provider == 'b2' and code == 'NoSuchLifecycleConfiguration':
                raise LookupError(code) from None
            if provider == 'b2' and code == 'NoSuchKey':
                raise ObjectNotFound('B2 object is absent') from None
            raise RuntimeError(f'{provider.upper()} request failed; check dedicated credentials, endpoint identity and permissions.') from None
        raise AWSCommandError(code) from None
    except (NoCredentialsError, PartialCredentialsError):
        raise AWSCommandError('CredentialsUnavailable') from None
    except BotoCoreError:
        raise AWSCommandError('TransportOrConfigurationError') from None


def compatible_run(provider, *args):
    return json.dumps(request(*args, provider=provider), default=str)


def transfer(storage, operation, sha, path=None, aws=None, version_id=None):
    """S3/R2 create-only writes; B2 appends and caller verifies exact versions."""
    arguments = ['s3api', {'get': 'get-object', 'put': 'put-object', 'delete': 'delete-object'}[operation],
                 '--bucket', storage.bucket, '--key', storage.object_key(sha)]
    if version_id is not None:
        if storage.provider != 'b2' or operation != 'get' or not re.fullmatch(r'[A-Za-z0-9_.-]{1,1024}', version_id):
            raise ValueError('Version IDs are allowed only for pinned B2 reads')
        arguments += ['--version-id', version_id]
    if operation == 'get':
        arguments += [str(path)]
    if operation == 'put':
        arguments += ['--body', str(path)]
        if storage.provider != 'b2':
            arguments += ['--if-none-match', '*']
        if storage.provider != 'r2':
            arguments += ['--server-side-encryption', 'AES256']
    if storage.provider == 's3' and aws is not None:
        return aws(*arguments)
    return json.dumps(request(*arguments, provider=storage.provider), default=str)

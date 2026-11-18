"""Exact-object storage adapters; no implicit deletions."""
from dataclasses import dataclass
import json
import re


@dataclass(frozen=True)
class Storage:
    provider: str
    bucket: str
    prefix: str = ''
    account: str = ''

    def object_key(self, sha):
        if not re.fullmatch(r'[0-9a-f]{64}', sha):
            raise ValueError('Expected lowercase SHA-256')
        return '/'.join(x for x in (self.prefix, 'sha256', sha[:2], sha) if x)

    def uri(self, sha):
        host = f'{self.account}/{self.bucket}' if self.provider == 'az' else self.bucket
        return f'{self.provider}://{host}/{self.object_key(sha)}'


def parse(value):
    scheme, sep, rest = value.partition('://')
    if not sep:
        scheme, rest = 's3', value  # Existing S3 commands remain valid.
    if scheme not in ('s3', 'gs', 'az', 'r2', 'b2'):
        raise ValueError('Use s3://bucket/prefix, gs://bucket/prefix, az://account/container/prefix, r2://bucket/prefix, or b2://bucket/prefix')
    parts = rest.rstrip('/').split('/')
    account = ''
    if scheme == 'az':
        if len(parts) < 2 or not re.fullmatch(r'[a-z0-9]{3,24}', parts[0]):
            raise ValueError('Azure requires az://account/container[/prefix]')
        account = parts.pop(0)
    bucket = parts.pop(0)
    pattern = r'[a-z0-9][a-z0-9-]{1,61}[a-z0-9]' if scheme == 'az' else r'[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]'
    if not re.fullmatch(pattern, bucket) or '..' in bucket or re.fullmatch(r'[0-9.]+', bucket) or (scheme == 'az' and '--' in bucket) or (scheme == 's3' and '_' in bucket):
        raise ValueError('Invalid bucket/container name')
    if any(not re.fullmatch(r'[A-Za-z0-9_-]+', p) for p in parts):
        raise ValueError('Prefix requires nonempty simple slash-separated names')
    return Storage(scheme, bucket, '/'.join(parts), account)


from . import asset_aws, asset_gcs, asset_azure

ObjectNotFound = asset_aws.ObjectNotFound
compatible_run = asset_aws.compatible_run


def transfer(storage, operation, sha, path=None, aws=None, version_id=None):
    """Transfer an exact object; caller verifies bytes after retrieval."""
    if storage.provider in ('s3', 'r2', 'b2'):
        return asset_aws.transfer(storage, operation, sha, path, aws=aws, version_id=version_id)
    if version_id is not None:
        raise ValueError('Version IDs are supported only for pinned B2 reads')
    if storage.provider == 'gs':
        return asset_gcs.transfer(storage, operation, sha, path)
    if storage.provider == 'az':
        return asset_azure.transfer(storage, operation, sha, path)
    raise ValueError('Unsupported storage provider')


def verify_b2_retention(storage):
    """Require inspectable lifecycle with no expiration before appending versions."""
    try:
        data = json.loads(compatible_run('b2', 's3api', 'get-bucket-lifecycle-configuration', '--bucket', storage.bucket))
    except LookupError:
        return
    rules = data.get('Rules') if isinstance(data, dict) else None
    if not isinstance(rules, list):
        raise ValueError('B2 lifecycle rules could not be verified; no upload attempted')
    for rule in rules:
        if not isinstance(rule, dict) or rule.get('Status') not in ('Enabled', 'Disabled'):
            raise ValueError('Malformed B2 lifecycle rule; no upload attempted')
        if rule['Status'] == 'Enabled' and any(k in rule for k in ('Expiration', 'NoncurrentVersionExpiration')):
            raise ValueError('B2 lifecycle expiration can remove historical assets; no upload attempted')


def prompt_prefix(ask, default='', root='bucket'):
    """Editable prefix; blank input means the bucket/container root."""
    from .asset_prompts import text
    label = 'Optional path prefix' if root == 'container' else 'Optional object prefix'
    return text(ask, label, default, empty_label=f'{root} root (no prefix)', allow_clear=True)

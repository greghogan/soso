"""Guided R2/B2 plan. No provisioning, credential saving, or implicit cloud writes."""
import json

from .asset_prompts import text as prompt_text
import os
import re
from pathlib import Path
from . import asset_storage as storage


def check_endpoint(target, *, require_empty):
    provider = target.provider
    try:
        raw = storage.compatible_run(provider, 's3api', 'list-objects-v2', '--bucket', target.bucket,
                                     '--prefix', target.prefix + '/' if target.prefix else '', '--max-keys', '1', '--no-paginate')
        data = json.loads(raw)
        if (not isinstance(data, dict) or type(data.get('KeyCount')) is not int
                or data['KeyCount'] not in (0, 1) or type(data.get('IsTruncated')) is not bool
                or not isinstance(data.get('Contents', []), list)
                or len(data.get('Contents', [])) != data['KeyCount']
                or any(not isinstance(item, dict) or not isinstance(item.get('Key'), str)
                       for item in data.get('Contents', []))):
            raise ValueError('Malformed live-object listing')
        if data['IsTruncated'] and (data['KeyCount'] == 0 or not data.get('NextContinuationToken')):
            raise ValueError('Inconsistent live-object pagination')
        if not data['IsTruncated'] and data.get('NextContinuationToken'):
            raise ValueError('Inconsistent live-object pagination')
        if require_empty and (data['KeyCount'] != 0 or data['IsTruncated']):
            raise ValueError('New destination live prefix is not empty')
        if provider == 'b2':
            storage.verify_b2_retention(target)
            print('VERIFIED: B2 lifecycle has no expiration rules.')
        print('VERIFIED: endpoint access; existing prefix contents preserved.' if not require_empty
              else 'VERIFIED: endpoint access and empty live prefix only.')
    except (ValueError, RuntimeError, OSError) as error:
        raise ValueError('Endpoint or live prefix could not be verified; check credentials, permissions, lifecycle, and path contents.') from error


def verify_saved(saved):
    target = storage.parse(saved['backup'])
    provider = target.provider
    endpoint = os.environ.get('SOSO_R2_ACCOUNT_ID' if provider == 'r2' else 'SOSO_B2_REGION')
    if not endpoint or endpoint != saved.get('endpoint_identity'):
        raise ValueError('Current endpoint does not match the saved destination; rerun setup to check the intended endpoint.')
    check_endpoint(target, require_empty=False)
    print('UNVERIFIED: bucket privacy, historical objects, effective token permissions, and CI restore require independent review.')
    return 1


def guided_setup(provider, backup=None, output=Path('assets/setup'), ask=input, saved=None, *, dry_run=False):
    if provider not in ('r2', 'b2'):
        raise ValueError('Expected r2 or b2')
    saved = saved or {}
    prior = None
    if saved.get('provider') == provider and saved.get('backup'):
        prior = storage.parse(saved['backup'])
        if prior.provider != provider:
            raise ValueError('Saved provider and destination mismatch')
    def prompt(label, default=''):
        return prompt_text(ask, label, default)
    if backup is None:
        bucket = prompt(f'{provider.upper()} bucket name', prior.bucket if prior else '')
        prefix = storage.prompt_prefix(ask, prior.prefix if prior else '')
        backup = f'{provider}://{bucket}' + ('/' + prefix if prefix else '')
    target = storage.parse(backup)
    if target.provider != provider:
        raise ValueError('Provider and destination mismatch')
    backup = f'{provider}://{target.bucket}' + ('/' + target.prefix if target.prefix else '')
    endpoint_identity = os.environ.get('SOSO_R2_ACCOUNT_ID' if provider == 'r2' else 'SOSO_B2_REGION', '')
    resume = (prior == target and saved.get('initialized') is True
              and bool(endpoint_identity) and saved.get('endpoint_identity') == endpoint_identity)
    default_mode = 'existing' if resume else saved.get('mode', '') if prior == target else ''
    mode = prompt('Plan a new bucket or use an existing bucket? [new/existing]', default_mode).lower()
    if mode not in ('new', 'existing'):
        raise ValueError('Choose new or existing')
    resume = resume and mode == 'existing'
    if resume:
        print('Rechecking the saved destination. Existing objects are expected; no files will be changed.')
    print('PLAN ONLY: no cloud settings or credentials will be changed or saved.')
    print('Inspect the bucket in the provider console. Keep it private; disable public endpoints/custom domains and lifecycle expiration. ' + ('Reuse the saved prefix without deleting existing objects. ' if resume else 'Use a dedicated empty prefix. ') + 'Do not change an existing shared bucket automatically.')
    stem = 'SOSO_' + provider.upper() + '_'
    print(f'Provide dedicated {stem}ACCESS_KEY_ID and {stem}SECRET_ACCESS_KEY through your secret manager/environment, never command arguments. Ambient AWS profiles/credentials are ignored.')
    if provider == 'r2':
        print('Set SOSO_R2_ACCOUNT_ID to the Cloudflare account ID. Only the standard account endpoint is supported (not jurisdiction-specific endpoints).')
        print('Create separate bucket-scoped Object Read tokens for CI and Object Read & Write tokens for local upload. R2 token permissions can include LIST/delete; this is not the AWS exact-key IAM model. Do not grant account-admin tokens.')
        print('R2 uses atomic single-object If-None-Match:* uploads and service MD5 metadata checks without downloading. Deletion remains an explicitly confirmed sync option, never the default.')
        print('R2 does not use the AWS GitHub OIDC role setup. CI tokens need a separate protected secret setup; this wizard does not configure it.')
        print('https://developers.cloudflare.com/r2/api/tokens/')
    else:
        print('Set SOSO_B2_REGION to the bucket region (for example us-west-004). Use a bucket/prefix-scoped application key: CI readFiles only; uploader readFiles, writeFiles, readBucketLifecycleRules. Never grant deleteFiles or writeBucketLifecycleRules.')
        print('B2 uses its always-on version history, not atomic conditional creation: verified existing bytes are reused; missing keys get a new version followed by pinned-version and current checksum metadata checks without downloading. Concurrent writers may create duplicate identical versions. Lifecycle expiration blocks new uploads. Explicit confirmed prune adds a delete marker, never purges versions.')
        print('https://www.backblaze.com/docs/cloud-storage-s3-compatible-api-bucket-versions')
    if dry_run:
        if prior == target and saved.get('endpoint_identity') and saved['endpoint_identity'] != endpoint_identity:
            raise ValueError('Current endpoint does not match the saved destination; no checks or changes were made.')
        if mode == 'new':
            print('Would prepare manual provisioning instructions; no bucket would be created automatically.')
            return 0
        check_endpoint(target, require_empty=not resume)
        print('Would save these endpoint settings; bucket privacy, historical objects, token permissions and CI access are not verified.')
        return 1
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    from .asset_setup import save_storage_config
    label = ('Recheck endpoint access and live prefix now (read-only)? [y/N]: ' if resume
             else 'Check endpoint access and empty live prefix now (read-only)? [y/N]: ')
    if ask(label).strip().lower() == 'y':
        try:
            check_endpoint(target, require_empty=not resume)
            save_storage_config({'provider': provider, 'backup': backup, 'mode': 'existing',
                                 'status': 'endpoint-verified-security-unverified', 'initialized': True,
                                 'endpoint_identity': endpoint_identity}, output)
        except (ValueError, RuntimeError, OSError):
            print('UNVERIFIED: destination check failed; check credentials, permissions, lifecycle and path contents. Saved verified defaults are unchanged. No cloud changes made.')
            return 1
    else:
        defaults = {'provider': provider, 'backup': backup, 'mode': mode,
                    'status': 'unverified-plan', 'initialized': bool(resume)}
        pattern = r'[0-9a-f]{32}' if provider == 'r2' else r'[a-z]{2}-[a-z]+-[0-9]{3}'
        if re.fullmatch(pattern, endpoint_identity):
            defaults['endpoint_identity'] = endpoint_identity
        save_storage_config(defaults, output)
        print('Saved destination defaults. No live checks were performed in this run.')
    print('UNVERIFIED: bucket privacy, lifecycle settings, historical objects, effective token permissions, and CI restore require independent review. This plan is not a completed secure setup; no assets were moved.')
    return 1

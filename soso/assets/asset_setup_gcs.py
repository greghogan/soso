"""GCS setup plan and fail-closed read-only bucket verification. Never provisions IAM."""
from __future__ import annotations

from .asset_prompts import text as prompt_text

import json
import re
import shlex
import urllib.parse
from pathlib import Path

from .asset_gcs import read_json
from .asset_storage import prompt_prefix

DOC = 'https://cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines'


class CheckError(ValueError):
    """Locally authored, safe diagnostic (never raw provider response)."""



def configuration(backup, project, project_number):
    value = backup.removeprefix('gs://').rstrip('/')
    bucket, _, prefix = value.partition('/')
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{1,61}[a-z0-9]', bucket):
        raise CheckError('Use a simple 3–63 character GCS bucket name (no dots).')
    if prefix and (not re.fullmatch(r'[A-Za-z0-9_/-]+', prefix) or any(p in ('', '.', '..') for p in prefix.split('/'))):
        raise CheckError('Use a simple prefix without wildcards or dot segments.')
    if not re.fullmatch(r'[a-z][a-z0-9-]{4,28}[a-z0-9]', project) or not re.fullmatch(r'[0-9]+', project_number):
        raise CheckError('Provide a Google project ID and its numeric project number.')
    return dict(provider='gcs', bucket=bucket, prefix=prefix, project=project,
                project_number=project_number, backup=f'gs://{value}')


def metadata(kind, name):
    if kind == 'project':
        return read_json('https://cloudresourcemanager.googleapis.com/v1/projects/' + urllib.parse.quote(name, safe=''))
    return read_json('https://storage.googleapis.com/storage/v1/b/' + urllib.parse.quote(name, safe=''))


def object_listing(c, *, soft_deleted=False):
    """Read exact prefix, including generations/soft deletes, through native API."""
    params = {'prefix': c['prefix'] + '/' if c['prefix'] else '', 'maxResults': '1',
              'softDeleted' if soft_deleted else 'versions': 'true'}
    return read_json('https://storage.googleapis.com/storage/v1/b/' + c['bucket'] + '/o', params)


def empty_listing(data):
    if not isinstance(data, dict) or data.get('kind') != 'storage#objects':
        raise CheckError('Malformed object listing; emptiness is unverified.')
    if not isinstance(data.get('items', []), list):
        raise CheckError('Malformed object list.')
    # With maxResults=1, a continuation token is enough to refuse emptiness.
    return not data.get('items') and not data.get('nextPageToken') and not data.get('prefixes')


def verify(c, read=metadata, listing=object_listing, *, require_empty=True):
    """Fresh security checks; initial destinations must also be empty. No CI attestation."""
    phase = 'project identity'
    try:
        project = read('project', c['project'])
        if not isinstance(project, dict) or str(project.get('projectNumber')) != c['project_number']:
            raise CheckError('Project ID/number mismatch.')
        phase = 'bucket metadata'
        b = read('bucket', c['bucket'])
        if not isinstance(b, dict) or b.get('name') != c['bucket'] or str(b.get('projectNumber')) != c['project_number']:
            raise CheckError('Bucket name or owning project mismatch.')
        iam = b.get('iamConfiguration', {})
        if not isinstance(iam, dict) or iam.get('uniformBucketLevelAccess', {}).get('enabled') is not True or iam.get('publicAccessPrevention') != 'enforced':
            raise CheckError('Require uniform bucket-level access and explicit public access prevention enforced.')
        versioning = b.get('versioning', {})
        if not isinstance(versioning, dict) or not isinstance(versioning.get('enabled', False), bool):
            raise CheckError('Malformed versioning metadata.')
        lifecycle = b.get('lifecycle', {})
        if not isinstance(lifecycle, dict) or not isinstance(lifecycle.get('rule', []), list):
            raise CheckError('Malformed lifecycle metadata.')
        # Conservative: any lifecycle action needs human review before historical retention is promised.
        if lifecycle.get('rule'):
            raise CheckError('Lifecycle rules present; retention impact needs review. No settings changed.')
        soft = b.get('softDeletePolicy', {})
        if not isinstance(soft, dict) or not str(soft.get('retentionDurationSeconds', '0')).isdigit():
            raise CheckError('Malformed soft-delete metadata.')
        print('Versioning:', versioning.get('enabled', False), '| Soft-delete retention seconds:', soft.get('retentionDurationSeconds', '0'))
        print('Retention policy:', json.dumps(b.get('retentionPolicy', {})))
        print('Encryption:', json.dumps(b.get('encryption', {'default': 'Google-managed encryption at rest'})))
        if require_empty:
            phase = 'live and historical object listing'
            if not empty_listing(listing(c)):
                raise CheckError('Destination contains live or historical objects; choose an empty prefix.')
            phase = 'soft-deleted object listing (including buckets whose current policy is disabled)'
            if not empty_listing(listing(c, soft_deleted=True)):
                raise CheckError('Destination contains soft-deleted objects; choose an empty prefix.')
            print('VERIFIED: project, bucket privacy controls, no lifecycle rules, and empty destination including historical objects.')
        else:
            print('VERIFIED: saved destination project, bucket privacy controls, and no lifecycle rules.')
            print('Existing destination contents retained. Emptiness was not checked; no assets were changed.')
        print('UNVERIFIED: effective inherited IAM, federation trust, and CI restore. Bucket checks alone do not authorize publication.')
        return 0
    except CheckError as exc:
        print('UNVERIFIED:', str(exc), 'No changes made.')
        return 1
    except (ValueError, TypeError, AttributeError, OSError):
        # No exception body from HTTP/provider libraries, which might reveal private URL details.
        print('UNVERIFIED:', phase, 'could not be checked. Check login/permissions and API support; no changes made. A disabled soft-delete policy is not proof that historical soft-deleted objects are absent.')
        return 1


def plan(c, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    role = {'title': 'SOSO asset reader', 'description': 'Read exact content-addressed original objects; no list/write/delete.',
            'stage': 'GA', 'includedPermissions': ['storage.objects.get']}
    (output / 'gcs-read-role.json').write_text(json.dumps(role, indent=2) + '\n')
    root = '/'.join(x for x in (c['prefix'], 'sha256') if x) + '/'
    condition = f'resource.name.startsWith("projects/_/buckets/{c["bucket"]}/objects/{root}")'
    (output / 'gcs-read-condition.json').write_text(json.dumps({'title': 'soso-hash-objects', 'expression': condition}, indent=2) + '\n')
    print('PLAN ONLY: no Google Cloud or GitHub changes made. Review commands and costs before running.')
    print('Local SDK access uses Application Default Credentials (ADC), not the gcloud CLI login. If needed run gcloud auth application-default login. CI uses workload identity federation; never create service-account keys.')
    print(shlex.join(['gcloud', 'projects', 'describe', c['project'], '--format=json']))
    print('For a NEW bucket only (existing bucket settings must not be changed automatically):')
    print(shlex.join(['gcloud', 'storage', 'buckets', 'create', 'gs://' + c['bucket'], '--project=' + c['project'],
                      '--location=CHOOSE_REGION', '--uniform-bucket-level-access', '--public-access-prevention']))
    print('Versioning defaults OFF. Soft delete is separate and may retain deleted bytes and incur costs; inspect its policy before use. Do not silently disable recovery. Encryption at rest is automatic. Avoid lifecycle expiration for historical assets.')
    print('For an existing bucket use read-only verification below; an empty exact prefix, including versions and soft-deleted objects, is required.')
    print('CI federation manual setup: ' + DOC)
    print('Use a dedicated workload identity pool/provider and a dedicated service account. Restrict the provider condition to immutable GitHub repository_owner_id AND repository_id AND the exact protected ref (for example refs/heads/main). Map google.subject=assertion.sub and the repository IDs. Never trust the shared GitHub issuer alone; do not use pull_request workflows for backup access.')
    print('Bind roles/iam.workloadIdentityUser on only that service account to the dedicated pool principalSet restricted to attribute.repository_id. Do not grant service-account token creator or project-wide storage roles.')
    print('Create a project custom role from gcs-read-role.json (storage.objects.get ONLY; objectViewer also grants LIST). Bind it on this bucket to that dedicated service account with the exact condition from gcs-read-condition.json:')
    print(condition)
    print('Use reviewed, SHA-pinned google-github-actions/auth action, id-token: write / contents: read, and the exact provider resource name and service-account email. Prefer a protected GitHub environment and branch protections. No static credentials or signed URL secrets.')
    print('Keep uploader identity separate: prefix-scoped storage.objects.create plus get for verification, no delete; upload with generation-match=0. Setup operator needs listing for initial emptiness only; CI reader does not.')
    print(shlex.join(['gcloud', 'iam', 'workload-identity-pools', 'providers', 'describe', 'PROVIDER_ID', '--workload-identity-pool=POOL_ID', '--location=global', '--project=' + c['project'], '--format=json']))
    print(shlex.join(['gcloud', 'iam', 'service-accounts', 'get-iam-policy', 'READER_SERVICE_ACCOUNT_EMAIL', '--project=' + c['project'], '--format=json']))
    print(shlex.join(['gcloud', 'storage', 'buckets', 'get-iam-policy', 'gs://' + c['bucket'], '--format=json']))
    print('After applying manual changes: inspect provider attribute mapping/condition, service-account IAM and bucket IAM, then verify trusted CI access using service checksum metadata without downloading objects. No full federation verifier is implemented; do not treat a successful bucket check as proof of CI least privilege.')


def save_configuration(c, output):
    # Runtime import avoids the dispatcher/provider import cycle.
    from .asset_setup import save_storage_config
    save_storage_config(c, output)


def verify_saved(saved):
    return verify(saved, require_empty=False)


def guided_setup(backup=None, output=Path('assets/setup'), ask=input, saved=None, *, dry_run=False):
    try:
        saved = saved if saved and saved.get('provider') == 'gcs' else {}

        def prompt(label, default=''):
            return prompt_text(ask, label, default)

        if backup is None:
            bucket = prompt('GCS bucket name', saved.get('bucket', ''))
            prefix = prompt_prefix(ask, saved.get('prefix', ''))
            backup = 'gs://' + bucket + ('/' + prefix if prefix else '')
        project = prompt('Google Cloud project ID', saved.get('project', ''))
        number = prompt('Google Cloud numeric project number', saved.get('project_number', ''))
        c = configuration(backup, project, number)
        resume = saved.get('initialized') is True and all(
            c[key] == saved.get(key) for key in ('backup', 'project', 'project_number'))
        if resume:
            print('Rechecking the saved GCS destination; existing contents may be present and will be retained.')
        else:
            mode = prompt('Use an existing bucket or plan a new one? [existing/new]', 'existing').lower()
            if mode not in ('existing', 'new'):
                raise CheckError('Choose existing or new.')
            if dry_run and mode == 'new':
                print('Would prepare a manual GCS provisioning plan; no bucket would be created automatically.')
                return 0
            if not dry_run:
                plan(c, output)
        if dry_run:
            print('Would save GCS settings only if destination verification succeeds.')
            return verify(c, require_empty=not resume)
        if ask('Run read-only destination verification now? [y/N]: ').strip().lower() == 'y':
            result = verify(c, require_empty=not resume)
            if result == 0:
                save_configuration(dict(c, initialized=True), output)
            return result
        save_configuration(dict(c, initialized=resume), output)
        print('Saved destination defaults. UNVERIFIED: no fresh destination validation completed. No assets were moved.')
        return 1
    except (ValueError, OSError, EOFError, KeyboardInterrupt) as exc:
        print('Setup stopped:', str(exc))
        return 1

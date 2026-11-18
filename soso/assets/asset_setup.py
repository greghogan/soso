"""Guided private asset storage setup for S3, Google Cloud Storage, and Azure Blob Storage."""
from __future__ import annotations

from .asset_prompts import text as prompt_text

import argparse
import importlib
import json
import os
import tempfile
import re
import shlex
import subprocess
import sys
from pathlib import Path

from .asset_storage import prompt_prefix

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / 'assets/setup'

ISSUER = 'token.actions.githubusercontent.com'
POLICY_NAME = 'SosoAssetRead'
DOCS = (
    'https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws',
    'https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_create_for-idp_oidc.html',
    'https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes-enforce.html',
)


def configuration(args, require_subject=True):
    destination = args.backup.removeprefix('s3://').rstrip('/')
    bucket, _, prefix = destination.partition('/')
    if not re.fullmatch(r'[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]', bucket) or '..' in bucket or re.fullmatch(r'[0-9.]+', bucket):
        raise ValueError('Expected a standard S3 bucket name, optionally followed by a prefix.')
    if prefix and (not re.fullmatch(r'[A-Za-z0-9_/-]+', prefix) or any(x in ('', '.', '..') for x in prefix.split('/'))):
        raise ValueError('Prefix must have nonempty path segments without wildcards or dot segments.')
    if not re.fullmatch(r'\d{12}', args.account):
        raise ValueError('--account must be a 12-digit AWS account ID.')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', args.repo):
        raise ValueError('--repo must be OWNER/REPOSITORY.')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', args.role):
        raise ValueError('--role must be a simple IAM role name.')
    if not re.fullmatch(r'[a-z]{2}-[a-z]+-\d', args.region):
        raise ValueError('Expected a commercial AWS region; other partitions need separate policies.')
    owner, repo = args.repo.split('/')
    identity = rf'{re.escape(owner)}(?:@\d+)?/{re.escape(repo)}(?:@\d+)?'
    match = re.fullmatch(rf'repo:({identity}):(ref:refs/heads/([^:*?\s]+)|environment:([^:*?\s]+))', args.subject)
    if (args.subject or require_subject) and (not match or (('@' in match[1]) and match[1].count('@') != 2)):
        raise ValueError('--subject must exactly match this repo and a branch or environment; no wildcards. Use both immutable IDs when enabled.')
    if any(c in args.subject for c in ('"', "'", '\\')):
        raise ValueError('Unsafe subject characters.')
    return dict(bucket=bucket, prefix=prefix, account=args.account, repo=args.repo,
                region=args.region, role=args.role, subject=args.subject,
                backup=destination, environment=match[4] if match else None, branch=match[3] if match else None)


def policies(c):
    root = '/'.join(x for x in (c['prefix'], 'sha256') if x)
    resource = f"arn:aws:s3:::{c['bucket']}/{root}/*"
    read = {'Version': '2012-10-17', 'Statement': [
        {'Effect': 'Allow', 'Action': ['s3:GetObject'], 'Resource': [resource]}]}
    upload = {'Version': '2012-10-17', 'Statement': [
        {'Effect': 'Allow', 'Action': ['s3:GetObject'], 'Resource': [resource]},
        {'Effect': 'Allow', 'Action': ['s3:PutObject'], 'Resource': [resource],
         'Condition': {'StringEquals': {'s3:if-none-match': '*'}}}]}
    trust = {'Version': '2012-10-17', 'Statement': [
        {'Effect': 'Allow', 'Principal': {'Federated': f"arn:aws:iam::{c['account']}:oidc-provider/{ISSUER}"},
         'Action': 'sts:AssumeRoleWithWebIdentity', 'Condition': {'StringEquals': {
             f'{ISSUER}:aud': 'sts.amazonaws.com', f'{ISSUER}:sub': c['subject']}}}]}
    return {'trust.json': trust, 'read.json': read, 'upload.json': upload}


def command(*args):
    return shlex.join(str(x) for x in args)


def plan(c, output, bucket_ready=False):
    output.mkdir(parents=True, exist_ok=True)
    for name, document in {**policies(c), 'config.json': c}.items():
        (output / name).write_text(json.dumps(document, indent=2) + '\n')
    arn = f"arn:aws:iam::{c['account']}:role/{c['role']}"
    print('PLAN ONLY. No AWS or GitHub changes were made. Review each permission before applying.')
    print(f'Files: {output}\nPrivate originals: s3://{c["backup"]}/sha256/ab/<sha256>')
    if bucket_ready:
        print('Bucket settings were checked in this run; no bucket creation or configuration commands are needed.')
        print('Using the workflow subject supplied above; IAM trust must match it exactly.')
    else:
        print('\n1. Verify your AWS identity and review the bucket settings.')
        print(command('aws', 'sts', 'get-caller-identity'))
        print(f'Expected AWS account: {c["account"]}. Stop if it differs. Use a dedicated private bucket or an approved existing bucket.')
        print('In S3 verify all four Block Public Access settings enabled; Object Ownership = Bucket owner enforced; default encryption = SSE-S3 (AES256). New buckets default to versioning OFF to avoid retained-version costs. Conditional hash-key writes prevent normal overwrites, but without versioning deletion cannot be recovered through S3 versions. Keep an independent backup. Existing versioning is never changed.')
        print('For a NEW dedicated bucket only, review and manually run the following. Storage/versioning costs apply. Do not run create-bucket on an existing bucket or change shared settings without review:')
        create = ['aws', 's3api', 'create-bucket', '--bucket', c['bucket'], '--region', c['region'], '--object-ownership', 'BucketOwnerEnforced']
        if c['region'] != 'us-east-1':
            create += ['--create-bucket-configuration', 'LocationConstraint=' + c['region']]
        print(command(*create))
        owner = ['--bucket', c['bucket'], '--expected-bucket-owner', c['account']]
        print(command('aws', 's3api', 'put-public-access-block', *owner, '--public-access-block-configuration', 'BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true'))
        encryption = json.dumps({'Rules': [{'ApplyServerSideEncryptionByDefault': {'SSEAlgorithm': 'AES256'}}]})
        print(command('aws', 's3api', 'put-bucket-encryption', *owner, '--server-side-encryption-configuration', encryption))
        print('\n2. Check the actual OIDC subject format for your repository. Repositories created after July 15, 2026 may include immutable owner/repository IDs.')
        print(command('gh', 'api', f'repos/{c["repo"]}', '--jq', '{owner_id: .owner.id, repository_id: .id}'))
        print(command('gh', 'api', f'repos/{c["repo"]}/actions/oidc/customization/sub'))
        print('IDs and customization settings alone do not prove the emitted subject. BLOCKING MANUAL CHECK: inspect ONLY the sub and aud claims of a token from a trusted branch workflow; never print or save the token. Match them exactly before enabling AWS access. Legacy, immutable, and custom formats differ.')
        print(f'Expected sub: {c["subject"]}')
        if c['environment']:
            print(f'Protect GitHub environment {c["environment"]!r}: restrict deployment branches to main (or your selected release branch), exclude pull requests, and use required reviewers if available. A subject scoped to an environment does NOT constrain its branch.')
        else:
            print(f'Trust is restricted to branch {c["branch"]!r}. Do not add a GitHub environment to the credential job without regenerating its trust subject.')
    print('\n3. In AWS IAM, reuse the GitHub OIDC provider if present; otherwise add provider https://' + ISSUER + ' with audience sts.amazonaws.com.')
    print('For a missing provider only (review before running; do not modify an existing shared provider):')
    print(command('aws', 'iam', 'create-open-id-connect-provider', '--url', 'https://' + ISSUER, '--client-id-list', 'sts.amazonaws.com'))
    print('Create a NEW dedicated role using trust.json; attach read.json as its sole inline policy named ' + POLICY_NAME + '. Do not attach managed policies. Review and approve IAM changes before applying.')
    print('Manual commands (not executed):')
    print(command('aws', 'iam', 'create-role', '--role-name', c['role'], '--assume-role-policy-document', 'file://' + str(output / 'trust.json'), '--max-session-duration', '3600'))
    print(command('aws', 'iam', 'put-role-policy', '--role-name', c['role'], '--policy-name', POLICY_NAME, '--policy-document', 'file://' + str(output / 'read.json')))
    print('CI gets GetObject only, never LIST/PUT/DELETE. upload.json is for a separate local backup identity, NOT the GitHub role. Its conditional writes cannot replace existing hash keys. Deletion requires separate, explicit authorization; never grant it to CI.')
    print('\n4. Set repository variables (configuration, not secrets). No S3 presigned URLs or AWS access keys belong in GitHub secrets:')
    for key, value in [('SOSO_ASSET_BACKUP', c['backup']), ('SOSO_AWS_REGION', c['region']), ('SOSO_AWS_ROLE_ARN', arn)]:
        print(command('gh', 'variable', 'set', key, '--repo', c['repo'], '--body', value))
    print('The credential job needs contents: read and id-token: write, with a pinned aws-actions/configure-aws-credentials action and short sessions. Run only on the trusted branch, never pull_request_target or untrusted fork code. Keep credentials out of Docker builds and artifacts.')
    print('\n5. Run the read-only verification below using your setup administrator identity. AccessDenied means UNVERIFIED, not success:')
    print(command('uv', 'run', '--locked', ROOT / 'scripts/asset_setup.py', '--verify', '--output', output))
    print('Verify uploaded objects using service metadata/checksums, without downloading them. Local checks do NOT prove live OIDC federation or absence of all bucket-policy grants. Byte-for-byte restore testing is a separate optional operation, not part of setup.')
    print('\nOfficial references:\n' + '\n'.join(DOCS))


from .asset_aws import AWSCommandError, request as aws, region_default


def verify(c, run=aws):
    failures = []
    def check(label, operation, predicate):
        try:
            ok = bool(predicate(operation()))
            print(('PASS ' if ok else 'FAIL ') + label)
            if not ok:
                failures.append(label)
        except (OSError, RuntimeError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired):
            print('UNVERIFIED ' + label + ' (missing tool, insufficient read permissions, unexpected response, or timeout)')
            failures.append(label)
    bucket = c['bucket']
    check('AWS account', lambda: run('sts', 'get-caller-identity'), lambda d: d['Account'] == c['account'])
    check('bucket region', lambda: run('s3api', 'get-bucket-location', '--bucket', bucket, '--expected-bucket-owner', c['account']),
          lambda d: ({'EU': 'eu-west-1'}.get(d.get('LocationConstraint'), d.get('LocationConstraint')) or 'us-east-1') == c['region'])
    check('bucket public access block', lambda: run('s3api', 'get-public-access-block', '--bucket', bucket, '--expected-bucket-owner', c['account']),
          lambda d: all(d['PublicAccessBlockConfiguration'].get(k) is True for k in ('BlockPublicAcls','IgnorePublicAcls','BlockPublicPolicy','RestrictPublicBuckets')))
    check('bucket owner enforced', lambda: run('s3api','get-bucket-ownership-controls','--bucket',bucket,'--expected-bucket-owner',c['account']),
          lambda d: d['OwnershipControls']['Rules'] == [{'ObjectOwnership': 'BucketOwnerEnforced'}])
    check('bucket versioning status readable (off is supported)', lambda: run('s3api','get-bucket-versioning','--bucket',bucket,'--expected-bucket-owner',c['account']), lambda d: d.get('Status') in (None, 'Enabled', 'Suspended'))
    check('SSE-S3 encryption (no KMS access required)', lambda: run('s3api','get-bucket-encryption','--bucket',bucket,'--expected-bucket-owner',c['account']),
          lambda d: all(x['ApplyServerSideEncryptionByDefault']['SSEAlgorithm'] == 'AES256' for x in d['ServerSideEncryptionConfiguration']['Rules']) and bool(d['ServerSideEncryptionConfiguration']['Rules']))
    if not c.get('subject'):
        print('UNVERIFIED: GitHub workflow identity has not been saved. Rerun setup to complete GitHub access.')
        return 1
    check('OIDC provider audience', lambda: run('iam','get-open-id-connect-provider','--open-id-connect-provider-arn',f"arn:aws:iam::{c['account']}:oidc-provider/{ISSUER}"),
          lambda d: d['Url'].removeprefix('https://') == ISSUER and 'sts.amazonaws.com' in d['ClientIDList'])
    expected = policies(c)
    check('exact role trust', lambda: run('iam','get-role','--role-name',c['role']), lambda d: d['Role']['AssumeRolePolicyDocument'] == expected['trust.json'])
    check('no attached managed role policies', lambda: run('iam','list-attached-role-policies','--role-name',c['role']), lambda d: d['AttachedPolicies'] == [])
    check('only expected inline role policy', lambda: run('iam','list-role-policies','--role-name',c['role']), lambda d: d['PolicyNames'] == [POLICY_NAME])
    check('exact GetObject-only policy', lambda: run('iam','get-role-policy','--role-name',c['role'],'--policy-name',POLICY_NAME), lambda d: d['PolicyDocument'] == expected['read.json'])
    print('UNVERIFIED: actual GitHub OIDC token subject, environment protections, bucket/access-point policy grants, and live CI retrieval. Static checks do not establish working GitHub access or object integrity.')
    return 1 if failures else 0


def bucket_exists(owner, run=aws):
    """HEAD status alone cannot distinguish absence from denied access."""
    try:
        run('s3api', 'head-bucket', *owner)
        return True
    except AWSCommandError as error:
        if error.code == 'NoSuchBucket':
            return False
        if error.code not in ('404', 'NotFound'):
            raise
    # GetBucketLocation has a structured error body, unlike HEAD. Preserve the
    # expected-owner check; never turn a generic status into creation permission.
    try:
        run('s3api', 'get-bucket-location', *owner)
        return True
    except AWSCommandError as error:
        if error.code == 'NoSuchBucket':
            return False
        raise


def bucket_setup(c, mode, versioning='disabled', run=aws, confirm=input, require_empty=True):
    """Provision only after confirmation, or inspect an existing empty namespace."""
    account = run('sts', 'get-caller-identity').get('Account')
    if account != c['account']:
        raise ValueError('AWS account mismatch; stopping before any changes.')
    bucket = c['bucket']
    owner = ['--bucket', bucket, '--expected-bucket-owner', c['account']]
    if mode == 'create':
        if not sys.stdin.isatty():
            raise ValueError('Bucket creation requires an interactive terminal; piped approval is not accepted.')
        try:
            exists = bucket_exists(owner, run)
        except AWSCommandError as error:
            raise ValueError('Bucket absence is UNVERIFIED. Access denied or ambiguous failure is not permission to create it.') from error
        if exists:
            raise ValueError('Bucket already exists. Rerun setup to check it; creation will not modify it.')
        print(f'Create NEW private bucket {bucket} in AWS account {account}, region {c["region"]}.')
        print('Settings: all public access blocked; ACLs disabled (BucketOwnerEnforced); SSE-S3 encryption; versioning ' + versioning + '.')
        print('Storage costs apply. This creates a bucket and changes its security settings, but does not configure IAM, upload, delete, or publish files.')
        approval = 'create ' + bucket
        if confirm('Type exactly "' + approval + '" to approve: ').strip() != approval:
            print('Canceled. No bucket changes made.')
            return 1
        create = ['s3api', 'create-bucket', '--bucket', bucket, '--region', c['region'], '--object-ownership', 'BucketOwnerEnforced']
        if c['region'] != 'us-east-1':
            create += ['--create-bucket-configuration', 'LocationConstraint=' + c['region']]
        try:
            run(*create)
            run('s3api', 'put-public-access-block', *owner, '--public-access-block-configuration',
                'BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true')
            run('s3api', 'put-bucket-encryption', *owner, '--server-side-encryption-configuration',
                json.dumps({'Rules': [{'ApplyServerSideEncryptionByDefault': {'SSEAlgorithm': 'AES256'}}]}))
            if versioning == 'enabled':
                run('s3api', 'put-bucket-versioning', *owner, '--versioning-configuration', 'Status=Enabled')
        except Exception:
            print('STOP: creation/setup failed. A bucket may now exist with only some settings applied. No rollback or deletion attempted. Inspect AWS before retrying; existing mode never repairs settings.')
            raise
    elif mode != 'existing':
        raise ValueError('Unknown bucket mode.')
    # Each read must succeed; permission failures and malformed responses cannot pass.
    region = run('s3api', 'get-bucket-location', *owner).get('LocationConstraint') or 'us-east-1'
    if {'EU': 'eu-west-1'}.get(region, region) != c['region']:
        raise ValueError('Bucket region differs from configuration.')
    block = run('s3api', 'get-public-access-block', *owner)['PublicAccessBlockConfiguration']
    if not all(block.get(k) is True for k in ('BlockPublicAcls','IgnorePublicAcls','BlockPublicPolicy','RestrictPublicBuckets')):
        raise ValueError('Bucket must have all four public-access blocks enabled. Existing settings were not changed.')
    if run('s3api', 'get-bucket-ownership-controls', *owner)['OwnershipControls']['Rules'] != [{'ObjectOwnership':'BucketOwnerEnforced'}]:
        raise ValueError('Bucket must disable ACLs with BucketOwnerEnforced. Existing settings were not changed.')
    rules = run('s3api', 'get-bucket-encryption', *owner)['ServerSideEncryptionConfiguration']['Rules']
    if not rules or any(r['ApplyServerSideEncryptionByDefault']['SSEAlgorithm'] != 'AES256' for r in rules):
        raise ValueError('Expected SSE-S3 encryption. KMS requires separately reviewed access policy changes.')
    version_status = run('s3api', 'get-bucket-versioning', *owner).get('Status', 'NeverEnabled')
    if version_status not in ('NeverEnabled', 'Enabled', 'Suspended'):
        raise ValueError('Unknown versioning status; cannot verify bucket.')
    if mode == 'create' and versioning == 'disabled' and version_status != 'NeverEnabled':
        raise ValueError('Unexpected versioning state for new versioning-off bucket; inspect before proceeding.')
    if mode == 'create' and versioning == 'enabled' and version_status != 'Enabled':
        raise ValueError('Versioning is not enabled. Existing settings were not changed. Inspect the bucket before proceeding.')
    try:
        lifecycle = run('s3api', 'get-bucket-lifecycle-configuration', *owner)
    except AWSCommandError as error:
        if error.code != 'NoSuchLifecycleConfiguration':
            raise
    else:
        if not isinstance(lifecycle.get('Rules'), list):
            raise ValueError('Lifecycle rules unverified: unexpected AWS response.')
        for rule in lifecycle['Rules']:
            if rule.get('Status') == 'Enabled' and any(k in rule for k in ('Expiration', 'NoncurrentVersionExpiration')):
                raise ValueError('An active lifecycle expiration rule exists. Review its scope before using this bucket; setup conservatively stops and never changes lifecycle rules.')
    if require_empty:
        prefix = c['prefix'].rstrip('/') + '/' if c['prefix'] else ''
        current = run('s3api', 'list-objects-v2', *owner, '--prefix', prefix, '--max-keys', '1', '--no-paginate')
        if not isinstance(current.get('KeyCount'), int) or current.get('IsTruncated') is not False:
            raise ValueError('Current object listing is incomplete or unverified.')
        if current.get('Contents') or current.get('KeyCount', 0) or current.get('IsTruncated'):
            raise ValueError('Selected path is not empty. No files or bucket settings were changed in existing mode.')
        # Even an apparently empty path may contain hidden older versions/delete markers.
        historical = run('s3api', 'list-object-versions', *owner, '--prefix', prefix, '--max-keys', '1', '--no-paginate')
        if historical.get('IsTruncated') is not False:
            raise ValueError('Historical object listing is incomplete or unverified.')
        if historical.get('Versions') or historical.get('DeleteMarkers') or historical.get('IsTruncated'):
            raise ValueError('Selected path contains historical versions or delete markers. Choose another path; nothing was deleted.')
    location = 'bucket root (no prefix)' if not c['prefix'] else 'prefix ' + c['prefix']
    version_label = {'NeverEnabled': 'off', 'Enabled': 'on', 'Suspended': 'suspended'}[version_status]
    print(f'Bucket checks passed: s3://{c["backup"]}/ ({location}).')
    print(f'Checked owner, region, public-access blocking, encryption and retention settings. Versioning: {version_label}.')
    if require_empty:
        print('Selected location is empty, including old versions and deletion markers, as of this check.')
    else:
        print('Reusing your saved location; contents may be present. Existing files were not changed.')
    if mode == 'existing':
        print('No bucket settings or files were changed.')
    else:
        print('Bucket created. No files were uploaded.')
    print('Not checked: access granted to other AWS accounts through bucket policies or access points.')
    print('GitHub access is a separate step; these bucket checks do not confirm it.')
    return 0


def discover_text(arguments):
    """Best-effort non-mutating configuration discovery, never echo CLI errors."""
    if arguments == ['aws', 'configure', 'get', 'region']:
        return region_default()
    try:
        result = subprocess.run(arguments, text=True, capture_output=True, timeout=30)
        return result.stdout.strip() if result.returncode == 0 else ''
    except (OSError, subprocess.TimeoutExpired):
        return ''


def oidc_probe_template(repo):
    """Return the trusted diagnostic workflow for this repository."""
    # No checkout, third-party action, secrets, artifacts, or cloud permissions.
    # Claims come directly from GitHub's runner endpoint, not user-supplied JWTs.
    workflow = """name: Inspect asset identity
on:
  workflow_dispatch:
permissions: {}
jobs:
  inspect:
    if: github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main'
    runs-on: ubuntu-24.04
    permissions:
      id-token: write
    steps:
      - name: Show identity only (no cloud access)
        env:
          EXPECTED_REPOSITORY: REPOSITORY_PLACEHOLDER
        shell: bash
        run: |
          node <<'JS'
          (async () => {
            const url = new URL(process.env.ACTIONS_ID_TOKEN_REQUEST_URL);
            url.searchParams.set('audience', 'sts.amazonaws.com');
            const response = await fetch(url, {headers: {
              Authorization: `Bearer ${process.env.ACTIONS_ID_TOKEN_REQUEST_TOKEN}`
            }});
            if (!response.ok) throw new Error('GitHub identity request failed');
            const {value} = await response.json();
            if (typeof value !== 'string') throw new Error('Missing identity token');
            const claims = JSON.parse(Buffer.from(value.split('.')[1], 'base64url'));
            if (claims.iss !== 'https://token.actions.githubusercontent.com' ||
                claims.aud !== 'sts.amazonaws.com' ||
                claims.repository !== process.env.EXPECTED_REPOSITORY ||
                claims.ref !== 'refs/heads/main' ||
                claims.event_name !== 'workflow_dispatch') {
              throw new Error('Unexpected workflow identity');
            }
            console.log('Verified workflow context. Copy only the subject below:');
            console.log(JSON.stringify({sub: claims.sub, aud: claims.aud}));
          })().catch(() => { console.error('Identity inspection failed; no token logged.'); process.exit(1); });
          JS
"""
    return workflow.replace('REPOSITORY_PLACEHOLDER', repo)


def prepare_oidc_probe(repo, output):
    """Write a diagnostic only; never install/run it or infer an IAM subject."""
    output.mkdir(parents=True, exist_ok=True)
    path = output / 'inspect-asset-identity.yml'
    expected = oidc_probe_template(repo)
    if path.is_symlink():
        raise ValueError(f'Diagnostic is a symbolic link: {path}; not changed or installed.')
    if path.exists():
        if path.read_text() != expected:
            raise ValueError(f'Existing diagnostic differs from the current template for {repo}: {path}. It was preserved. Review and move it aside, then retry; do not run it as the new diagnostic.')
        print(f'Reusing diagnostic for {repo}: {path}')
    else:
        path.write_text(expected)
        print(f'Saved diagnostic for {repo}: {path}')
    return path


def check_local_oidc_probe(path, root):
    """Respect an existing workflow without adding an untracked checkout file."""
    directory = root
    for component in ('.github', 'workflows'):
        directory /= component
        if directory.is_symlink():
            raise ValueError(f'Workflow directory is a symbolic link: {directory}; setup stopped.')
    target = directory / 'inspect-asset-identity.yml'
    if target.is_symlink() or (target.exists() and (
            not target.is_file() or target.read_bytes() != path.read_bytes())):
        raise ValueError(f'Local diagnostic differs or is unsafe: {target}. It was not overwritten; review it before continuing.')


def guide_oidc_probe(repo, path, ask, on_dispatch):
    from .asset_diagnostic_git import publish
    from .asset_diagnostic_run import preflight, run
    print()
    preflight(repo)
    commit = publish(ROOT, repo, path, ask)
    return run(repo, commit, on_dispatch=on_dispatch) if commit else None


def guided_setup(backup, output, run=aws, ask=input, discover=discover_text, saved=None, dry_run=False):
    if not sys.stdin.isatty():
        raise ValueError('Guided setup requires an interactive terminal.')
    print('Checking AWS identity...')
    try:
        account = run('sts', 'get-caller-identity').get('Account')
    except AWSCommandError as error:
        if error.code in ('CredentialsUnavailable', 'ExpiredToken', 'ExpiredTokenException',
                          'InvalidClientTokenId', 'UnrecognizedClientException', 'AuthFailure'):
            raise ValueError('AWS authentication failed. Refresh credentials for your selected AWS profile, then retry. If it uses SSO, run aws sso login --profile PROFILE.') from None
        raise
    if not account or not re.fullmatch(r'\d{12}', account):
        raise ValueError('AWS returned no valid account ID; identity could not be verified.')
    print('AWS account: ' + account)
    saved = saved or {}
    same_destination = saved.get('backup', '').removeprefix('s3://').rstrip('/') == backup.removeprefix('s3://').rstrip('/')
    if same_destination and saved.get('account') != account:
        raise ValueError('Current AWS account does not match saved destination; no changes made.')
    def prompt(label, default=''):
        return prompt_text(ask, label, default)
    # Validate the destination before any bucket calls; the provisional region
    # is never used for creation or saved as detected evidence.
    bucket_args = argparse.Namespace(backup=backup, account=account, repo='local/storage', region='us-east-1',
                                    role='soso-asset-read', subject='')
    if same_destination:
        for field in ('repo', 'role', 'subject'):
            setattr(bucket_args, field, saved[field])
    adopted = False
    while True:
        c = configuration(bucket_args, require_subject=False)
        owner = ['--bucket', c['bucket'], '--expected-bucket-owner', account]
        print(f'Checking bucket {c["bucket"]}...')
        try:
            exists = bucket_exists(owner, run)
        except AWSCommandError:
            print('Cannot verify this bucket or its owner with the current AWS access. It may exist, be inaccessible, or the request may have failed.')
        else:
            if not exists:
                mode = 'new'
                break
            try:
                location = run('s3api', 'get-bucket-location', *owner)
                if 'LocationConstraint' not in location:
                    raise ValueError('Missing bucket region in AWS response.')
                region = location['LocationConstraint']
                region = 'us-east-1' if region is None else {'EU': 'eu-west-1'}.get(region, region)
                if not isinstance(region, str) or not re.fullmatch(r'[a-z]{2}-[a-z]+-\d', region):
                    raise ValueError('Unrecognized bucket region.')
            except (AWSCommandError, ValueError):
                print('Bucket access was verified, but its region could not be verified. No settings changed.')
            else:
                bucket_args.region = region
                c = configuration(bucket_args, require_subject=False)
                print(f'Existing bucket in AWS account {account}, region {region}. Checking settings and selected path...')
                # This verifies emptiness (including old versions), not just access.
                require_empty = not (same_destination and saved.get('initialized') is True and c['backup'] == saved['backup'] and c['region'] == saved.get('region'))
                result = bucket_setup(c, 'existing', run=run, confirm=ask, require_empty=require_empty)
                if result:
                    return result
                adopted = True
                mode = 'existing'
                break
        replacement = ask('Another bucket name (blank to stop): ').strip()
        if not replacement:
            print('Stopped; no bucket changes made.')
            return 1
        if '/' in replacement:
            raise ValueError('Enter a bucket name only; the selected prefix is unchanged.')
        bucket_args.backup = replacement + ('/' + c['prefix'] if c['prefix'] else '')
    if mode == 'new':
        print('Bucket was not found. Choose a region for a new bucket.')
        bucket_args.region = prompt('AWS region', saved.get('region', '') if same_destination else discover(['aws', 'configure', 'get', 'region']))
        c = configuration(bucket_args, require_subject=False)
        mode = prompt('Bucket action: create or skip', 'skip')
        if mode not in ('create', 'skip'):
            raise ValueError('Choose create or skip; no bucket changes made.')
        if mode == 'create' and dry_run:
            print(f'Dry run: would create private bucket {c["bucket"]} in {c["region"]}, with public access blocked, ACLs disabled, SSE-S3 encryption, and versioning off.')
        elif mode == 'create':
            result = bucket_setup(c, mode, run=run, confirm=ask)
            if result:
                return result
    c['initialized'] = adopted or mode == 'create'
    if saved and diagnostic_matches(saved.get('diagnostic'), c):
        c['diagnostic'] = saved['diagnostic']
    if not dry_run:
        output.mkdir(parents=True, exist_ok=True)
        save_storage_config({**c, 'provider': 's3'}, output)
        print('Saved these settings for the next run. Next: GitHub Actions access.')
    return github_access(c, output, ask=ask, discover=discover, run=run,
                         **({'dry_run': True} if dry_run else {}))


def github_access(c, output, ask=input, discover=discover_text, run=aws, dry_run=False):
    def prompt(label, default=''):
        return prompt_text(ask, label, default)
    if c['repo'] == 'local/storage':
        discovered_repo = discover(['gh', 'repo', 'view', '--json', 'nameWithOwner', '--jq', '.nameWithOwner'])
        if re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', discovered_repo):
            c = {**c, 'repo': discovered_repo}
    if c['repo'] != 'local/storage':
        if detect_github_access(c, run=run, discover=discover) is True:
            print('Saved GitHub access configuration already matches. No setup changes are needed.')
            print('Cloud object metadata/checksums and live GitHub access still need separate verification. Setup does not download objects.')
            return 0
    saved_run = c.get('diagnostic')
    print('\nSet up GitHub Actions access to the backup?')
    print('1. Set up GitHub access')
    print('2. I already have the workflow identity (generate templates only)')
    print('3. Skip GitHub access for now')
    access = ask('Choice [1]: ').strip() or '1'
    if access == '3':
        print('GitHub access is not configured by this run.')
        return 0
    if access not in ('1', '2'):
        raise ValueError('Choose 1, 2, or 3; no GitHub or IAM changes made.')
    print()
    repo = prompt('GitHub repository OWNER/REPO', c['repo'] if c['repo'] != 'local/storage' else discover(['gh', 'repo', 'view', '--json', 'nameWithOwner', '--jq', '.nameWithOwner']))
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
        raise ValueError('Expected GitHub OWNER/REPO.')
    bucket_args = argparse.Namespace(**c)
    bucket_args.repo = repo
    if repo != c['repo']:
        bucket_args.subject = ''
        saved_run = None
    resume = saved_run is not None
    state = {**configuration(bucket_args, require_subject=False),
             'provider': 's3', 'initialized': c.get('initialized', False)}
    if saved_run is not None:
        state['diagnostic'] = saved_run

    def remember(run_id):
        state['diagnostic'] = diagnostic_binding(state, run_id)
        save_storage_config(state, output)

    if access == '1':
        if not dry_run:
            save_storage_config(state, output)
        if dry_run and not resume:
            print(f'Dry run: workflow identity for {repo} is pending. Setup would check or publish the diagnostic, obtain approval to run it, and verify its exact result before configuring IAM. No GitHub or AWS changes made.')
            return 0
        if resume:
            from .asset_diagnostic_run import DiagnosticUnavailable, recover
            try:
                subject = recover(repo, saved_run['id'], oidc_probe_template(repo).encode('utf-8'))
            except DiagnosticUnavailable as exc:
                print(f'Saved diagnostic run {saved_run["id"]} cannot be reused: {exc}')
                if dry_run:
                    print('Dry run: would offer a new workflow identity check. No changes made.')
                    return 0
                resume = False
            except ValueError as exc:
                if dry_run:
                    print(f'Dry run: saved run {saved_run["id"]} could not be verified; no retry would be attempted. {exc}')
                    return 0
                raise ValueError(f'{exc} Saved run {saved_run["id"]} was retained; no retry was attempted.') from None
        if not resume:
            print('Preparing the workflow identity diagnostic. Nothing is pushed or run without your approval.')
            path = prepare_oidc_probe(repo, output)
            check_local_oidc_probe(path, ROOT)
            subject = guide_oidc_probe(repo, path, ask, remember)
        if subject is None:
            return 0
        bucket_args.subject = subject
    if access == '2':
        print('\nEnter the exact OIDC subject (sub) from your trusted GitHub workflow run, not a token or credentials. This prepares local IAM policy templates; it does not independently verify the identity or configure access.')
        bucket_args.subject = prompt('GitHub workflow identity (OIDC subject)', bucket_args.subject)
    if access in ('1', '2'):
        planned = configuration(bucket_args)
        if access == '1' and (planned['branch'] != 'main' or planned['environment']):
            raise ValueError('This diagnostic runs on main without an environment; the subject must match that workflow.')
        if not dry_run:
            save_storage_config({**state, **planned}, output)
        if access == '1' and c.get('initialized') is True:
            from .asset_iam_setup import configure
            documents = policies(planned)
            configure({**planned, 'initialized': True}, documents['trust.json'], documents['read.json'], ask=ask, **({'dry_run': True} if dry_run else {}))
        elif dry_run:
            print(f'Dry run: would prepare local IAM policy templates for {repo}; no files written.')
        else:
            plan(planned, output, bucket_ready=c.get('initialized') is True)
    return 0


def provider_module(provider):
    """Import only the selected adapter, for direct and package invocation."""
    name = 'asset_setup_' + provider
    return importlib.import_module('.' + name, __package__) if __package__ else importlib.import_module(name)


def diagnostic_binding(c, run_id):
    return {'id': run_id, **{key: c[key] for key in ('repo', 'backup', 'account', 'region')}}


def diagnostic_matches(diagnostic, c):
    return (isinstance(diagnostic, dict) and type(diagnostic.get('id')) is int
            and diagnostic['id'] > 0 and diagnostic_binding(c, diagnostic['id']) == diagnostic)


def validate_storage_config(saved):
    """Normalize only known, nonsecret fields; saved values never prove live access."""
    if not isinstance(saved, dict) or type(saved.get('initialized', False)) is not bool:
        raise ValueError('Invalid saved storage configuration.')
    provider = {'az': 'azure', 'gs': 'gcs'}.get(saved.get('provider'), saved.get('provider', 's3'))
    if provider == 's3':
        required = ('backup', 'account', 'repo', 'region', 'role', 'subject')
        if any(not isinstance(saved.get(k), str) for k in required):
            raise ValueError('Saved S3 configuration has missing or invalid fields.')
        c = configuration(argparse.Namespace(**saved), require_subject=False)
        if diagnostic_matches(saved.get('diagnostic'), c):
            c['diagnostic'] = saved['diagnostic']
    elif provider == 'gcs':
        c = provider_module('gcs').configuration(saved['backup'], saved['project'], saved['project_number'])
    elif provider == 'azure':
        c = provider_module('azure').configuration(saved['backup'], saved['subscription'], saved['tenant'], saved['group'], saved['location'])
    elif provider in ('r2', 'b2'):
        from .asset_storage import parse
        storage = parse(saved['backup'])
        if storage.provider != provider:
            raise ValueError('Saved provider and destination conflict.')
        c = dict(backup=f'{provider}://{storage.bucket}' + ('/' + storage.prefix if storage.prefix else ''))
        if saved.get('mode') not in (None, 'new', 'existing'):
            raise ValueError('Invalid saved storage mode.')
        if 'mode' in saved:
            c['mode'] = saved['mode']
        if 'status' in saved:
            if saved['status'] not in ('unverified-plan', 'endpoint-verified-security-unverified'):
                raise ValueError('Invalid saved storage status.')
            c['status'] = saved['status']
        if 'endpoint_identity' in saved:
            pattern = r'[0-9a-f]{32}' if provider == 'r2' else r'[a-z]{2}-[a-z]+-[0-9]{3}'
            if not re.fullmatch(pattern, saved['endpoint_identity']):
                raise ValueError('Invalid saved endpoint identity.')
            c['endpoint_identity'] = saved['endpoint_identity']
    else:
        raise ValueError('Unknown saved storage provider.')
    return {**c, 'provider': provider, 'initialized': saved.get('initialized', False)}


def save_storage_config(c, output):
    c = validate_storage_config(c)
    output.mkdir(parents=True, exist_ok=True)
    path = output / 'storage-config.json'
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=output, delete=False) as stream:
        pending = Path(stream.name)
        try:
            stream.write(json.dumps(c, indent=2) + '\n')
            stream.flush()
            os.fsync(stream.fileno())
            os.replace(pending, path)
        finally:
            pending.unlink(missing_ok=True)


def load_storage_config(output):
    path = output / 'storage-config.json'
    if path.exists():
        return validate_storage_config(json.loads(path.read_text()))
    return None


def verify_github_variables(c, discover=discover_text):
    if c['repo'] == 'local/storage':
        print('UNVERIFIED: no GitHub repository has been saved.')
        return False
    variables_match = False
    raw = discover(['gh', 'variable', 'list', '--repo', c['repo'], '--json', 'name,value'])
    try:
        entries = json.loads(raw)
        if not isinstance(entries, list):
            raise ValueError()
        variables = {item['name']: item['value'] for item in entries}
        expected = {'SOSO_ASSET_BACKUP': c['backup'], 'SOSO_AWS_REGION': c['region'],
                    'SOSO_AWS_ROLE_ARN': f"arn:aws:iam::{c['account']}:role/{c['role']}"}
        variables_match = all(variables.get(k) == v for k, v in expected.items())
        if variables_match:
            print('VERIFIED: GitHub repository variables match this saved storage configuration.')
        else:
            print('UNVERIFIED: GitHub repository variables are missing or differ; no changes made.')
    except (ValueError, TypeError, KeyError):
        print('UNVERIFIED: GitHub repository variables could not be read; check gh access if needed.')
    return variables_match


def detect_github_access(c, run=aws, discover=discover_text):
    """Read-only observation, not proof of a live workflow or authorization."""
    print('\nChecking existing GitHub access configuration...')
    variables_match = verify_github_variables(c, discover=discover)
    role_matches = False
    if c.get('subject'):
        role_matches = verify(c, run=run) == 0
        if role_matches:
            print('VERIFIED: AWS static role/policy configuration matches the saved subject. This is not a live GitHub access test.')
    else:
        print('UNVERIFIED: no saved workflow subject to compare with the AWS trust policy.')
    return variables_match and role_matches


def setup_storage(output=DEFAULT_OUTPUT, ask=input, dry_run=False):
    """Collect the storage destination through the interactive wizard."""
    if not sys.stdin.isatty():
        raise ValueError('Guided setup requires an interactive terminal.')
    if dry_run:
        print('Dry run: setup will check what it can without writing files or changing cloud settings.')
    saved = load_storage_config(output)
    provider = None
    print('Choose a storage service:')
    choices = [('s3', 'Amazon S3'), ('gcs', 'Google Cloud Storage'),
               ('azure', 'Azure Blob Storage'), ('r2', 'Cloudflare R2'), ('b2', 'Backblaze B2')]
    saved_provider = (saved or {}).get('provider')
    for number, (choice, label) in enumerate(choices, 1):
        suffix = ' (saved default; press Enter)' if choice == saved_provider else ''
        print(f'{number}. {label}{suffix}')
    aliases = {'1': 's3', 's3': 's3', 'aws': 's3', '2': 'gcs', 'gcs': 'gcs',
               'gs': 'gcs', 'google': 'gcs', '3': 'azure', 'azure': 'azure', 'az': 'azure', '4': 'r2', 'r2': 'r2', '5': 'b2', 'b2': 'b2'}
    default = next((str(i) for i, (choice, _) in enumerate(choices, 1)
                    if choice == saved_provider), '')
    while provider is None:
        answer = (prompt_text(ask, 'Storage service', default) if default
                  else ask('Storage service [1/2/3/4/5]: '))
        provider = aliases.get(answer.strip().lower())
        if provider is None:
            print('Choose 1 (S3), 2 (GCS), 3 (Azure), 4 (R2), or 5 (B2).')
    options = {'ask': ask}
    if saved and saved['provider'] == provider:
        options['saved'] = saved
    if dry_run:
        options['dry_run'] = True
    if provider == 's3':
        default_bucket = (options.get('saved') or {}).get('bucket', '')
        bucket = prompt_text(ask, 'S3 bucket name', default_bucket)
        if not bucket or '/' in bucket:
            raise ValueError('Enter a bucket name only, without a URL or path.')
        default_prefix = (options.get('saved') or {}).get('prefix', '')
        prefix = prompt_prefix(ask, default_prefix)
        backup = bucket + ('/' + prefix if prefix else '')
        return guided_setup(backup, output, **options)
    if provider in ('r2', 'b2'):
        return provider_module('s3compatible').guided_setup(provider=provider, output=output, **options)
    return provider_module(provider).guided_setup(output=output, **options)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--dry-run', action='store_true', help='preview setup using read-only checks; save and change nothing')
    modes.add_argument('--verify', action='store_true', help='check the saved storage configuration without changing it')
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT, help='local setup state directory')
    args = parser.parse_args(argv)
    try:
        if not args.verify:
            return setup_storage(args.output, dry_run=args.dry_run)
        saved = load_storage_config(args.output)
        if saved is None:
            raise ValueError('No saved storage configuration. Run setup first.')
        if saved['provider'] != 's3':
            module = provider_module('s3compatible' if saved['provider'] in ('r2', 'b2') else saved['provider'])
            return module.verify_saved(saved)
        c = configuration(argparse.Namespace(**saved), require_subject=False)
        aws_status = verify(c)
        github_matches = verify_github_variables(c)
        return 0 if aws_status == 0 and github_matches else 1
    except (ValueError, OSError, RuntimeError, KeyError, TypeError, EOFError, subprocess.TimeoutExpired) as error:
        parser.error(str(error))


if __name__ == '__main__':
    raise SystemExit(main())

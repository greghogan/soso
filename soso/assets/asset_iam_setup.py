"""Create missing GitHub/S3 access resources after explicit user approval."""
import json
import re
import subprocess
import time

from botocore.exceptions import BotoCoreError, ClientError

from .asset_aws import client

ISSUER = 'token.actions.githubusercontent.com'
AUDIENCE = 'sts.amazonaws.com'
POLICY_NAME = 'SosoAssetRead'


def gh(*args):
    result = subprocess.run(['gh', 'api', '--hostname', 'github.com', *args],
                            capture_output=True, text=True, timeout=45)
    if result.returncode:
        raise ValueError('GitHub access check or create failed. Check gh authentication and repository permissions.')
    return result.stdout


def optional(read, **kwargs):
    try:
        return read(**kwargs)
    except ClientError as error:
        if error.response.get('Error', {}).get('Code') == 'NoSuchEntity':
            return None
        raise


def configure(c, trust, read, ask=input, *, aws_client=client, github=gh, dry_run=False):
    """Apply missing settings only. Caller verifies the bucket and observed subject."""
    if c.get('initialized') is not True or c.get('branch') != 'main' or c.get('environment'):
        raise ValueError('Automatic access setup requires a checked bucket and a trusted main-branch workflow identity.')
    account, repo, role = c['account'], c['repo'], c['role']
    provider = f'arn:aws:iam::{account}:oidc-provider/{ISSUER}'
    role_arn = f'arn:aws:iam::{account}:role/{role}'
    endpoint = f'repos/{repo}/actions/variables'
    variables = {'SOSO_ASSET_BACKUP': c['backup'], 'SOSO_AWS_REGION': c['region'],
                 'SOSO_AWS_ROLE_ARN': role_arn}
    try:
        iam = aws_client('iam', retry=False)
        sts = aws_client('sts', retry=False)

        def inspect():
            if sts.get_caller_identity()['Account'] != account:
                raise ValueError('Current AWS account does not match the checked bucket account.')
            registered = optional(iam.get_open_id_connect_provider, OpenIDConnectProviderArn=provider)
            if registered is not None and (registered['Url'].removeprefix('https://') != ISSUER
                                           or AUDIENCE not in registered['ClientIDList']):
                raise ValueError('Existing GitHub OIDC provider differs. It was not modified.')
            existing = optional(iam.get_role, RoleName=role)
            if existing is not None:
                actual = existing['Role']
                managed = iam.list_attached_role_policies(RoleName=role)
                inline = iam.list_role_policies(RoleName=role)
                if (actual['Arn'] != role_arn or actual['AssumeRolePolicyDocument'] != trust
                        or actual.get('PermissionsBoundary') or managed.get('IsTruncated') is not False
                        or inline.get('IsTruncated') is not False or managed['AttachedPolicies'] != []
                        or inline['PolicyNames'] != [POLICY_NAME]
                        or iam.get_role_policy(RoleName=role, PolicyName=POLICY_NAME)['PolicyDocument'] != read):
                    raise ValueError(f'Existing IAM role {role} or its policies differ. Nothing was overwritten.')
            repository = json.loads(github(f'repos/{repo}'))
            if repository['full_name'].casefold() != repo.casefold() or repository['default_branch'] != 'main':
                raise ValueError('GitHub repository or default branch no longer matches the trusted workflow.')
            immutable = re.fullmatch(r'repo:[^/@]+@(\d+)/[^/@]+@(\d+):ref:refs/heads/main', c['subject'])
            if immutable and (str(repository['owner']['id']), str(repository['id'])) != immutable.groups():
                raise ValueError('GitHub repository identity changed. Nothing was overwritten.')
            pages = json.loads(github('--paginate', '--slurp', endpoint))
            if not isinstance(pages, list) or not pages:
                raise ValueError('Could not verify existing GitHub variables.')
            current = {}
            for page in pages:
                if not isinstance(page['variables'], list):
                    raise ValueError('Invalid GitHub variable listing.')
                for record in page['variables']:
                    name = record['name']
                    if name in current or not isinstance(record['value'], str):
                        raise ValueError('Ambiguous GitHub variable response.')
                    current[name] = record['value']
            if any(page.get('total_count') != len(current) for page in pages):
                raise ValueError('Incomplete or changing GitHub variable listing. No writes attempted for this check.')
            for name, value in variables.items():
                if name in current and current[name] != value:
                    raise ValueError(f'Existing GitHub variable {name} does not match the planned value {value}. It was not overwritten.')
            return registered is None, existing is None, tuple(name for name in variables if name not in current)

        missing = inspect()
        if any(missing):
            new_provider, new_role, new_variables = missing
            print(f'\nSet up GitHub read access for {repo} in AWS account {account}?')
            if new_provider:
                print(f'Create OIDC provider: https://{ISSUER} (audience {AUDIENCE}).')
            if new_role:
                print(f'Create role {role_arn}, trusted only for {c["subject"]}.')
                print('Allow only s3:GetObject on ' + read['Statement'][0]['Resource'][0] + '.')
            for name in new_variables:
                print(f'Create repository variable {name}={variables[name]}.')
            print('Existing resources will not be overwritten. No asset downloads.')
            if dry_run:
                print('Dry run: no AWS IAM or GitHub variable changes made.')
                return True
            if ask('Type configure to approve, or press Enter to stop: ').strip() != 'configure':
                print('No AWS IAM or GitHub variable changes made.')
                return False
            if inspect() != missing:
                raise ValueError('AWS or GitHub configuration changed while awaiting approval. Rerun setup.')
            if new_provider:
                iam.create_open_id_connect_provider(Url='https://' + ISSUER, ClientIDList=[AUDIENCE])
            if new_role:
                created = iam.create_role(RoleName=role, AssumeRolePolicyDocument=json.dumps(trust), MaxSessionDuration=3600)['Role']
                for delay in (0, 1, 2, 4):
                    if delay:
                        time.sleep(delay)
                    actual = optional(iam.get_role, RoleName=role)
                    if actual is not None:
                        break
                role_now = actual['Role'] if actual is not None else {}
                if (role_now.get('RoleId') != created['RoleId'] or role_now.get('Arn') != role_arn
                        or role_now.get('AssumeRolePolicyDocument') != trust or role_now.get('PermissionsBoundary')):
                    raise ValueError('IAM could not confirm the newly created role is unchanged. No policy was attached; inspect the role.')
                managed = iam.list_attached_role_policies(RoleName=role)
                inline = iam.list_role_policies(RoleName=role)
                if (managed.get('IsTruncated') is not False or inline.get('IsTruncated') is not False
                        or managed['AttachedPolicies'] != [] or inline['PolicyNames'] != []):
                    raise ValueError('New role already has policies or policy state could not be checked. No policy was attached.')
                # IAM has no conditional inline policy PUT. Only attach to the role created by this invocation. Do not upsert on reruns.
                iam.put_role_policy(RoleName=role, PolicyName=POLICY_NAME, PolicyDocument=json.dumps(read))
            for name in new_variables:
                try:
                    github('--method', 'POST', endpoint, '-f', f'name={name}', '-f', f'value={variables[name]}')
                except ValueError as exc:
                    raise ValueError(f'Could not create GitHub variable {name}. Other settings may already have been created; inspect and rerun.') from exc
            if any(inspect()):
                raise ValueError('Some settings are not visible yet. Check AWS and GitHub, then rerun setup.')
    except (BotoCoreError, ClientError, KeyError, TypeError, json.JSONDecodeError, OSError, subprocess.TimeoutExpired):
        raise ValueError('Could not complete or verify AWS/GitHub access setup. Some newly created settings may exist; check permissions and rerun. No rollback was attempted.') from None
    print('AWS IAM and GitHub variables match. Live access has not been tested.')
    return True

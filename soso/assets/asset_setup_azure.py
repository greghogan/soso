"""Azure setup plans and read-only checks. Never creates resources or credentials."""
from __future__ import annotations

from .asset_prompts import text as prompt_text

import re
import shlex
from pathlib import Path

from .asset_storage import parse, prompt_prefix

GUID = r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}'


def read_state(c, require_empty=True):
    """Read public-Azure management and Blob APIs; never mutate resources."""
    from azure.core.exceptions import AzureError
    from azure.mgmt.storage import StorageManagementClient
    from azure.mgmt.resource.subscriptions import SubscriptionClient
    from .asset_azure import credential, service_client
    try:
        with credential() as identity, SubscriptionClient(identity, base_url='https://management.azure.com') as subscriptions, StorageManagementClient(identity, c['subscription'], base_url='https://management.azure.com') as management, service_client(c['account'], identity) as blobs:
            subscription = subscriptions.subscriptions.get(c['subscription']).as_dict()
            account = management.storage_accounts.get_properties(c['group'], c['account']).as_dict()
            container = blobs.get_container_client(c['container'])
            properties = container.get_container_properties()
            try:
                policy = management.management_policies.get(c['group'], c['account'], 'default').as_dict().get('properties', {})
            except AzureError as error:
                # A generic 404 or authorization failure never proves absence.
                if getattr(getattr(error, 'error', None), 'code', None) != 'ManagementPolicyNotFound':
                    raise
                policy = {'policy': {'rules': []}}
            service = management.blob_services.get_service_properties(c['group'], c['account']).as_dict().get('properties', {})
            entries = []
            if require_empty:
                prefix = c['prefix'] + '/' if c['prefix'] else ''
                # Fully consume pageable results, including historical data.
                entries = list(container.list_blobs(name_starts_with=prefix, include=['deleted', 'snapshots', 'versions']))
            return [dict(id=subscription.get('subscriptionId'), tenantId=subscription.get('tenantId'), environmentName='AzureCloud'),
                    {**account, **account.get('properties', {}), 'enableHttpsTrafficOnly': account.get('properties', {}).get('supportsHttpsTrafficOnly')},
                    dict(name=properties.get('name'), properties={'publicAccess': properties.get('public_access', 'UNVERIFIED')}),
                    policy, service, entries]
    except AzureError:
        raise ValueError('Azure read failed; check Entra authentication, permissions and connectivity.') from None


def configuration(backup, subscription, tenant, group, location):
    storage = parse(backup)
    if storage.provider != 'az':
        raise ValueError('Expected az://account/container[/prefix].')
    if not re.fullmatch(GUID, subscription) or not re.fullmatch(GUID, tenant):
        raise ValueError('Subscription and tenant must be UUIDs.')
    if not re.fullmatch(r'[A-Za-z0-9_().-]{1,90}', group) or group.endswith('.'):
        raise ValueError('Use a simple Azure resource group name.')
    if not re.fullmatch(r'[a-z0-9]+', location):
        raise ValueError('Use an Azure location identifier such as eastus.')
    scope = f'/subscriptions/{subscription}/resourceGroups/{group}/providers/Microsoft.Storage/storageAccounts/{storage.account}'
    return dict(provider='az', backup=backup.rstrip('/'), account=storage.account,
                container=storage.bucket, prefix=storage.prefix, subscription=subscription,
                tenant=tenant, group=group, location=location, scope=scope)


def verify(c, require_empty=True):
    """Fail closed on unverified privacy, identity, lifecycle, or adoption emptiness."""
    identity, account, container, policy, service, blobs = read_state(c, require_empty)
    if not isinstance(identity, dict) or identity.get('id') != c['subscription'] or identity.get('tenantId') != c['tenant'] or identity.get('environmentName') != 'AzureCloud':
        raise ValueError('Subscription/tenant mismatch or unsupported sovereign cloud.')
    if not isinstance(account, dict) or str(account.get('id', '')).lower() != c['scope'].lower() or account.get('location') != c['location']:
        raise ValueError('Storage account identity/location could not be verified.')
    if account.get('allowBlobPublicAccess') is not False or account.get('allowSharedKeyAccess') is not False or account.get('enableHttpsTrafficOnly') is not True or account.get('minimumTlsVersion') not in ('TLS1_2', 'TLS1_3'):
        raise ValueError('Require disabled anonymous access and Shared Key, HTTPS only, and TLS 1.2 or newer.')
    if account.get('encryption', {}).get('services', {}).get('blob', {}).get('enabled') is not True:
        raise ValueError('Blob encryption is unverified.')
    if not isinstance(container, dict) or container.get('name') != c['container'] or 'publicAccess' not in container.get('properties', {}) or container['properties']['publicAccess'] not in (None, 'None'):
        raise ValueError('Private container state could not be verified.')
    if not isinstance(policy, dict) or not isinstance(policy.get('policy'), dict) or not isinstance(policy['policy'].get('rules'), list):
        raise ValueError('Lifecycle state unverified.')
    # Deliberately conservative: do not silently interpret complex prefix/tag filters.
    for rule in policy['policy']['rules']:
        if not isinstance(rule, dict) or rule.get('enabled') is not False:
            raise ValueError('Active or unrecognized lifecycle policy: review manually before adoption.')
    if not isinstance(service, dict):
        raise ValueError('Blob service settings unverified.')
    for field in ('deleteRetentionPolicy', 'containerDeleteRetentionPolicy'):
        if not isinstance(service.get(field), dict) or type(service[field].get('enabled')) is not bool:
            raise ValueError('Soft-delete settings unverified.')
    if service.get('isVersioningEnabled') not in (True, False, None):
        raise ValueError('Versioning setting unrecognized.')
    print('Versioning:', service.get('isVersioningEnabled', 'not set'),
          '; blob/container soft delete:', service['deleteRetentionPolicy'], service['containerDeleteRetentionPolicy'])
    if require_empty:
        if not isinstance(blobs, list) or blobs:
            raise ValueError('Selected path is nonempty or listing unverified (including versions/deleted blobs/snapshots).')
    print('Storage checks passed. Federation, inherited access and a cold CI restore remain UNVERIFIED.')
    return True


def plan(c, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    def command(*args):
        print(shlex.join(str(x) for x in args))
    print('PLAN ONLY: no Azure or GitHub changes. Commands below are MANUAL; review costs and permissions before running.')
    print('Use az login with your normal identity. No account keys, SAS URLs, or client secrets. Verify subscription and tenant:')
    command('az', 'account', 'show', '--subscription', c['subscription'])
    print('NEW dedicated account only: use an existing approved resource group. Do not run create against an existing account. Standard_LRS is locally redundant; choose another redundancy tier if desired. Storage costs apply.')
    command('az', 'storage', 'account', 'create', '--subscription', c['subscription'], '--resource-group', c['group'], '--name', c['account'], '--location', c['location'], '--sku', 'Standard_LRS', '--kind', 'StorageV2', '--https-only', 'true', '--min-tls-version', 'TLS1_2', '--allow-blob-public-access', 'false', '--allow-shared-key-access', 'false')
    print('Create a private container using an operator with container-scoped data access; never enable Shared Key to work around authorization errors:')
    command('az', 'storage', 'container', 'create', '--account-name', c['account'], '--name', c['container'], '--subscription', c['subscription'], '--auth-mode', 'login', '--public-access', 'off')
    print('Existing account: do NOT apply account-wide changes automatically. An administrator must review any shared account before changing settings. Adoption requires an empty selected path, including historical versions/snapshots. Existing versioning and soft delete are never changed. New versioning is not enabled by this plan. Do not add lifecycle expiration; default sync preserves historical assets.')
    print('\nCI MANUAL SETUP (not performed): create a dedicated Entra application/service principal, with NO password. Add a GitHub federated credential: issuer https://token.actions.githubusercontent.com, audience api://AzureADTokenExchange, exact repository + main-branch subject from a trusted workflow. Never accept wildcard, pull_request, or an unverified assumed subject. If using an environment, protect its branch and reviewers as well.')
    print('Assign Storage Blob Data Reader to ONLY this dedicated identity at this container scope:')
    print(c['scope'] + '/blobServices/default/containers/' + c['container'])
    print('This role includes listing and reads for the whole container, NOT just the prefix. Use a dedicated container for isolation. Audit inherited/group permissions and all other federated credentials; role assignment at this scope alone does not prove least privilege. Local uploads need separate operator permissions, never CI writer/delete permissions.')
    print('In GitHub, use azure/login pinned to a reviewed commit with client-id, tenant-id and subscription-id (identifiers, not secrets), permissions id-token: write and contents: read. Keep credentials in a trusted main-only job; never expose them to PR code. Authenticate with OIDC, not a client secret. No CI workflow is enabled by this plan.')
    print('Before claiming ready: inspect federated credential issuer/subject/audience and role assignments in Azure, then verify trusted CI access using metadata; checksum verification assumes this workflow is the writer of the dedicated location and downloads no objects. Keep setup output untracked.')
    print('Reference: https://learn.microsoft.com/azure/developer/github/connect-from-azure-openid-connect')
    print('Reference: https://learn.microsoft.com/azure/storage/blobs/assign-azure-role-data-access')


def verify_saved(saved):
    c = configuration(saved['backup'], saved['subscription'], saved['tenant'], saved['group'], saved['location'])
    verify(c, require_empty=False)
    return 0


def guided_setup(backup=None, output=Path('assets/setup'), ask=input, saved=None, *, dry_run=False):
    try:
        # Saved state supplies defaults, never proof of current cloud security.
        prior = None
        if saved and saved.get('provider') in ('az', 'azure'):
            prior = configuration(saved['backup'], saved['subscription'], saved['tenant'],
                                  saved['group'], saved['location'])
        def prompt(label, default=''):
            return prompt_text(ask, label, default)
        if not backup:
            old_storage = parse(prior['backup']) if prior else None
            account = prompt('Azure storage account name', old_storage.account if old_storage else '')
            container = prompt('Private container name', old_storage.bucket if old_storage else '')
            prefix = prompt_prefix(ask, old_storage.prefix if old_storage else '', root='container')
            backup = f'az://{account}/{container}' + (f'/{prefix}' if prefix else '')
        defaults = prior or {}
        c = configuration(backup, prompt('Azure subscription UUID', defaults.get('subscription', '')),
                          prompt('Azure tenant UUID', defaults.get('tenant', '')),
                          prompt('Resource group', defaults.get('group', '')),
                          prompt('Location (e.g. eastus)', defaults.get('location', '')))
        same_destination = prior == c
        mode = prompt('Create new or use existing? [create/existing]', 'existing' if same_destination else '').lower()
        if mode not in ('create', 'existing'):
            raise ValueError('Choose create or existing; nothing changed.')
        from .asset_setup import save_storage_config
        def save_defaults():
            initialized = bool(same_destination and saved.get('initialized') is True)
            save_storage_config({**c, 'provider': 'azure', 'initialized': initialized}, output)
        if dry_run:
            if mode == 'create':
                print('Would prepare a manual Azure provisioning plan; no storage would be created automatically.')
            else:
                print('Would save Azure settings only if destination verification succeeds.')
                verify(c, require_empty=not (same_destination and saved.get('initialized') is True))
            return 0
        plan(c, output)
        if mode == 'create':
            save_defaults()
            print('Run reviewed creation commands manually, then rerun this wizard in existing mode. No automatic creation.')
            return 1
        if ask('Run read-only Azure verification now? [y/N]: ').strip().lower() != 'y':
            save_defaults()
            print('Setup incomplete: storage and CI remain unverified.')
            return 1
        require_empty = not (same_destination and saved.get('initialized') is True)
        if not require_empty:
            print('Rechecking the previously configured Azure destination; existing objects are retained. This is not a new empty-path adoption.')
        verify(c, require_empty=require_empty)
        save_storage_config({**c, 'provider': 'azure', 'initialized': True}, output)
        print('Storage verified; complete manual federation review and metadata access checks before CI use.')
        return 0
    except (ValueError, OSError, KeyError, TypeError, EOFError, KeyboardInterrupt) as error:
        print(f'Azure setup incomplete: {error}')
        return 1

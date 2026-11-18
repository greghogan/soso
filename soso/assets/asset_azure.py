"""Native Azure Blob transfers using Entra credentials, never account keys/SAS."""
from pathlib import Path


def credential():
    from azure.identity import DefaultAzureCredential
    # Public Azure only; never silently launch a browser or consume storage keys.
    return DefaultAzureCredential(authority='https://login.microsoftonline.com',
                                  exclude_interactive_browser_credential=True)


def service_client(account, identity):
    from azure.storage.blob import BlobServiceClient
    return BlobServiceClient(f'https://{account}.blob.core.windows.net', credential=identity)


def transfer(storage, operation, sha, path=None):
    from azure.core.exceptions import AzureError
    if operation not in ('get', 'put', 'delete'):
        raise ValueError('Unknown Azure operation')
    key = storage.object_key(sha)
    try:
        with credential() as identity, service_client(storage.account, identity) as service:
            blob = service.get_blob_client(container=storage.bucket, blob=key)
            if operation == 'get':
                # raw bytes: no content decoding/re-encoding before SHA verification.
                with Path(path).open('wb') as output:
                    blob.download_blob(decompress=False).readinto(output)
            elif operation == 'put':
                with Path(path).open('rb') as source:
                    blob.upload_blob(source, blob_type='BlockBlob', overwrite=False,
                                     if_none_match='*')
            else:
                # Do not request snapshot/version deletion or a permanent purge.
                blob.delete_blob(retry_total=0)
    except AzureError as error:
        code = getattr(error, 'error_code', None)
        if operation == 'put' and code in ('BlobAlreadyExists', 'ConditionNotMet'):
            raise RuntimeError(str(code)) from None
        raise RuntimeError('Azure request failed; check Entra authentication, permissions and connectivity.') from None

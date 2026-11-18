"""Native Google Cloud Storage operations using Application Default Credentials."""
import os


def client():
    # Do not accidentally redirect private assets/credentials to a local emulator.
    if os.environ.get('STORAGE_EMULATOR_HOST'):
        raise ValueError('Unset STORAGE_EMULATOR_HOST when accessing private asset storage.')
    from google.cloud import storage
    return storage.Client(project=None, client_options={'api_endpoint': 'https://storage.googleapis.com'})


def transfer(storage, operation, sha, path=None):
    """Exact bytes and create-only uploads; callers perform SHA-256 readback."""
    if operation not in ('get', 'put', 'delete'):
        raise ValueError('Unknown GCS operation')
    key = storage.object_key(sha)
    from google.api_core.exceptions import PreconditionFailed
    try:
        blob = client().bucket(storage.bucket).blob(key)
        if operation == 'get':
            # Never transparently decompress an original with Content-Encoding.
            blob.download_to_filename(str(path), raw_download=True, timeout=60)
        elif operation == 'put':
            # SDK checksum failure cleanup may issue DELETE; disallow that implicit
            # mutation. The caller downloads and checks the exact SHA-256 instead.
            blob.upload_from_filename(str(path), if_generation_match=0,
                                      checksum=None, timeout=60)
        else:
            # No generation selector: remove only the live object, not old versions.
            # Disable retry so a lost response cannot delete a new concurrent object.
            blob.delete(timeout=60, retry=None)
    except PreconditionFailed:
        raise RuntimeError('PreconditionFailed') from None
    except (ImportError, ValueError):
        raise
    except Exception:
        # Never echo cloud exception URLs or credential/configuration details.
        raise RuntimeError('GCS request failed; check Application Default Credentials and permissions.') from None
    return ''


def read_json(url, params=None):
    """Read Google's native JSON APIs; no bearer token in subprocess arguments."""
    if not url.startswith(('https://storage.googleapis.com/',
                           'https://cloudresourcemanager.googleapis.com/')):
        raise ValueError('Unexpected Google API endpoint')
    try:
        import google.auth
        from google.auth.transport.requests import AuthorizedSession
        credentials, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
        with AuthorizedSession(credentials) as session:
            response = session.get(url, params=params, timeout=60, allow_redirects=False)
            if response.status_code != 200:
                raise RuntimeError('Google API read failed')
            return response.json()
    except Exception:
        raise ValueError('Google API read failed; check Application Default Credentials, project, and read permissions.') from None

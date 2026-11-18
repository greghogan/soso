"""B2 Native metadata only. Tokens stay in memory and never follow redirects."""
import base64
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request(url, token, payload=None):
    req = urllib.request.Request(url, data=None if payload is None else json.dumps(payload).encode(),
                                 headers={'Authorization': token, 'Content-Type':'application/json',
                                          'User-Agent':'asset-sync/1.0'})
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=30) as response:
            return json.loads(response.read(1024 * 1024))
    except (OSError, ValueError):
        raise ValueError('B2 native metadata request failed; no object download or retry attempted') from None


class Metadata:
    def __init__(self, bucket):
        key = os.environ.get('SOSO_B2_ACCESS_KEY_ID','')
        secret = os.environ.get('SOSO_B2_SECRET_ACCESS_KEY','')
        if not key or not secret:
            raise ValueError('Dedicated B2 credentials required')
        auth = request('https://api.backblazeb2.com/b2api/v4/b2_authorize_account',
                       'Basic '+base64.b64encode((key+':'+secret).encode()).decode())
        self.account_id = auth.get('accountId')
        if not isinstance(self.account_id,str) or not self.account_id:
            raise ValueError('B2 authorization returned no account identity')
        api = auth.get('apiInfo',{}).get('storageApi',{})
        self.url, self.token = api.get('apiUrl',''), auth.get('authorizationToken','')
        if not re.fullmatch(r'https://api[0-9]+\.backblazeb2\.com',self.url) or not isinstance(self.token,str) or not self.token:
            raise ValueError('Unexpected B2 metadata endpoint; credentials were not forwarded')
        allowed = api.get('allowed',{})
        self.capabilities = allowed.get('capabilities',[])
        self.prefix = allowed.get('namePrefix') or ''
        buckets = allowed.get('buckets')
        # Bucket-bound keys make native identity verification possible without LIST buckets.
        matches = [x for x in buckets or [] if x.get('name') == bucket and x.get('id')]
        if len(matches) != 1 or 'readFiles' not in self.capabilities:
            raise ValueError('B2 metadata verification requires a key restricted to this bucket with readFiles permission')
        self.bucket_id = matches[0]['id']

    def check(self, data, key, version=None):
        if (not isinstance(data,dict) or data.get('accountId') != self.account_id or data.get('action') != 'upload'
                or data.get('bucketId') != self.bucket_id or data.get('fileName') != key
                or not key.startswith(self.prefix) or not isinstance(data.get('fileId'),str)
                or (version is not None and data['fileId'] != version)):
            raise ValueError('B2 native metadata identity mismatch; object is UNVERIFIED')
        return data

    def info(self, key, version):
        if not isinstance(version,str) or not version or not key.startswith(self.prefix):
            raise ValueError('Missing B2 version identity')
        data = request(self.url+'/b2api/v4/b2_get_file_info?'+urllib.parse.urlencode({'fileId':version}), self.token)
        return self.check(data,key,version)

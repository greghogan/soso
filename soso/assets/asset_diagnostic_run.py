"""Run and verify the exact GitHub identity diagnostic, without exposing tokens."""
import base64
import json
import re
import subprocess
import time


class DiagnosticUnavailable(ValueError):
    """The trusted saved run can no longer provide an identity."""


class ResourceGone(ValueError):
    """GitHub explicitly returned HTTP 410, not an ambiguous 404."""


def api(endpoint, *args, data=None):
    try:
        result = subprocess.run(
            ['gh', 'api', '--hostname', 'github.com', endpoint, *args],
            capture_output=True, input=data, timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise ValueError('GitHub CLI request unavailable or timed out. Check GitHub Actions before retrying.') from None
    if result.returncode:
        if re.search(rb'(?m)^gh: [^\r\n]* \(HTTP 410\)\s*$', result.stderr):
            raise ResourceGone('GitHub reports that the requested resource is gone (HTTP 410).')
        raise ValueError('GitHub CLI request failed. Check authentication, workflow permissions, and GitHub Actions before retrying.')
    return result.stdout


def document(endpoint, *args, data=None):
    response = api(endpoint, *args, data=data)
    try:
        value = json.loads(response)
        if isinstance(value, dict):
            return value
    except (ValueError, UnicodeError):
        pass
    raise ValueError('Could not confirm the GitHub API response. Check GitHub Actions before retrying.')


def preflight(repo):
    details = document(f'repos/{repo}')
    permissions = details.get('permissions')
    if (str(details.get('full_name')).casefold() != repo.casefold()
            or details.get('default_branch') != 'main'
            or not isinstance(permissions, dict) or permissions.get('push') is not True):
        raise ValueError('The GitHub CLI must be authenticated with write access to the selected repository and main must be its default branch.')



def run(repo, commit, *, on_dispatch=None):
    root = f'repos/{repo}/actions'
    workflow = f'{root}/workflows/inspect-asset-identity.yml'
    expected = document(workflow)
    if expected.get('path') != '.github/workflows/inspect-asset-identity.yml' or type(expected.get('id')) is not int:
        raise ValueError('GitHub did not return the expected diagnostic workflow.')
    ref = document(f'repos/{repo}/git/ref/heads/main')
    tip = ref.get('object')
    if not isinstance(tip, dict) or tip.get('sha') != commit:
        raise ValueError('GitHub main changed before the diagnostic was run; nothing was dispatched.')
    dispatch = document(f'{workflow}/dispatches', '--method', 'POST', '--input', '-',
                        data=b'{"ref":"main","return_run_details":true}')
    run_id = dispatch.get('workflow_run_id')
    if type(run_id) is not int or run_id <= 0:
        raise ValueError('GitHub did not return an exact run ID. Check Actions before retrying; setup will not guess or dispatch again.')
    if on_dispatch is not None:
        on_dispatch(run_id)
    print(f'Waiting for https://github.com/{repo}/actions/runs/{run_id}')
    return verify_run(repo, commit, expected['id'], run_id)


def recover(repo, run_id, template_bytes):
    """Recover a known run, verifying the workflow at its historical commit."""
    if type(run_id) is not int or run_id <= 0:
        raise ValueError('Expected a positive GitHub diagnostic run ID.')
    workflow = '.github/workflows/inspect-asset-identity.yml'
    try:
        details = document(f'repos/{repo}/actions/runs/{run_id}')
    except ResourceGone:
        raise DiagnosticUnavailable('GitHub reports that the saved run is gone.') from None
    commit = details.get('head_sha')
    workflow_id = details.get('workflow_id')
    if (details.get('id') != run_id or not isinstance(commit, str)
            or not re.fullmatch(r'[0-9a-f]{40}', commit)
            or type(workflow_id) is not int or workflow_id <= 0
            or details.get('path') not in (workflow, f'{workflow}@main', f'{workflow}@refs/heads/main')
            or details.get('head_branch') != 'main' or details.get('event') != 'workflow_dispatch'
            or details.get('run_attempt') != 1
            or any(not isinstance(item, dict) or str(item.get('full_name')).casefold() != repo.casefold()
                   for item in (details.get('repository'), details.get('head_repository')))):
        raise ValueError('The selected run does not match this repository’s expected main-branch identity diagnostic.')
    record = document(f'repos/{repo}/contents/{workflow}?ref={commit}')
    raw = record.get('content')
    try:
        if record.get('type') != 'file' or record.get('encoding') != 'base64' or not isinstance(raw, str):
            raise ValueError
        data = base64.b64decode(''.join(raw.splitlines()), validate=True)
    except (ValueError, TypeError):
        raise ValueError('Could not verify the historical diagnostic file.') from None
    if data != template_bytes:
        raise ValueError('The historical diagnostic differs from the trusted template. No IAM plan was prepared.')
    return verify_run(repo, commit, workflow_id, run_id)



def verify_run(repo, commit, workflow_id, run_id):
    """Verify an already dispatched run, without any writes or redispatch."""
    root = f'repos/{repo}/actions'
    path = f'{root}/runs/{run_id}'
    deadline = time.monotonic() + 180
    while True:
        try:
            details = document(path)
        except ResourceGone:
            raise DiagnosticUnavailable('GitHub reports that the saved run is gone.') from None
        owner = details.get('head_repository')
        repository = details.get('repository')
        if (details.get('id') != run_id or details.get('workflow_id') != workflow_id
                or details.get('head_sha') != commit or details.get('head_branch') != 'main'
                or details.get('event') != 'workflow_dispatch' or details.get('run_attempt') != 1
                or any(not isinstance(item, dict) or str(item.get('full_name')).casefold() != repo.casefold()
                       for item in (owner, repository))):
            raise ValueError('GitHub returned a run outside the approved repository, workflow, or commit. No IAM plan was prepared.')
        if details.get('status') == 'completed':
            conclusion = details.get('conclusion')
            if conclusion in ('failure', 'cancelled', 'timed_out', 'action_required',
                              'neutral', 'skipped', 'stale', 'startup_failure'):
                raise DiagnosticUnavailable(f'The saved diagnostic completed with conclusion: {conclusion}.')
            if conclusion != 'success':
                raise ValueError('GitHub’s diagnostic conclusion could not be verified. Check the linked run.')
            break
        if time.monotonic() >= deadline:
            raise ValueError('Timed out waiting for the diagnostic. The linked run may still be active; setup did not retry.')
        time.sleep(3)
    jobs = document(f'{path}/attempts/1/jobs')
    items = jobs.get('jobs')
    if jobs.get('total_count') != 1 or not isinstance(items, list) or len(items) != 1:
        raise ValueError('The diagnostic did not have exactly one job.')
    job = items[0]
    steps = [step for step in job.get('steps', []) if step.get('name') == 'Show identity only (no cloud access)']
    if (job.get('name') != 'inspect' or job.get('conclusion') != 'success'
            or job.get('run_id') != run_id or job.get('head_sha') != commit
            or type(job.get('id')) is not int or len(steps) != 1 or steps[0].get('conclusion') != 'success'):
        raise ValueError('Could not verify the exact diagnostic job.')
    try:
        # GitHub’s job logs can contain ANSI sequences. Capture them in memory
        # only; no raw response is printed or passed through to the terminal.
        logs = api(f"{root}/jobs/{job['id']}/logs", '--allow-escape-sequences')
    except ResourceGone:
        raise DiagnosticUnavailable('GitHub reports that the saved diagnostic log has expired.') from None
    except ValueError:
        raise ValueError('Could not read the verified diagnostic job log. Check the GitHub CLI version and Actions log permissions; do not rerun the workflow just to retry reading its log.') from None
    claims = []
    for line in logs.splitlines():
        match = re.fullmatch(rb'(?:\S+ )?(\{"sub":"[^"\r\n]+","aud":"sts\.amazonaws\.com"\})', line.strip())
        if match:
            claims.append(json.loads(match.group(1)))
    owner, name = repo.split('/')
    pattern = rf'repo:{re.escape(owner)}(?:@\d+)?/{re.escape(name)}(?:@\d+)?:ref:refs/heads/main'
    if len(claims) != 1 or not re.fullmatch(pattern, claims[0]['sub'], re.IGNORECASE):
        raise ValueError('The successful diagnostic did not emit one valid main-branch identity. No IAM plan was prepared.')
    print('GitHub workflow identity verified.')
    return claims[0]['sub']

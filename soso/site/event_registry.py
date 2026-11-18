"""Small event registry shared by build entry points; paths are source-root relative."""
from pathlib import Path
import json, re

def load(root):
    root = Path(root)
    entries = json.loads((root / 'manifests/events.json').read_text())['events']
    seen = set()
    for event in entries:
        key = (event['slug'], str(event['year']))
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', key[0]) or not re.fullmatch(r'\d{4}', key[1]) or key in seen:
            raise ValueError(f'Invalid or duplicate event: {key}')
        seen.add(key)
        validate_reference_constraints(event.get('reference_constraints'))
        event['path'] = 'events/' + '/'.join(key)
        if 'documents' in event:
            event['pdfs'] = list(dict.fromkeys(ed['pdf'] for ed in event['documents'].values() if 'pdf' in ed))
        for field in ('pdfs', 'required_inputs', 'site_assets'):
            for name in event.get(field, []):
                safe_path(name)
        for kind, editions in event.get('documents', {}).items():
            if kind not in ('study', 'build', 'exam') or not editions or set(editions) - {'pdf', 'interactive'}:
                raise ValueError(f'Invalid document editions: {kind}')
            if kind == 'exam' and set(editions) != {'pdf'}:
                raise ValueError('Exam references support PDF only')
            for name in editions.values(): safe_path(name)
        for model in event.get('models', []):
            safe_path(model['path'])
            if not model.get('title'): raise ValueError('Model title required')
        for source, target in event.get('promote', {}).items():
            safe_path(source); safe_path(target)
        for command in event['build'] + [event['web_build']]:
            safe_path(command[0].removeprefix('@root/'))
    return entries

def safe_path(value):
    path = Path(value)
    if path.is_absolute() or '..' in path.parts or not value:
        raise ValueError(f'Unsafe registry path: {value}')
    return path

def command(root, event, args, python):
    script = args[0]
    entry = Path(root) / (script[6:] if script.startswith('@root/') else event['path'] + '/' + script)
    return [python, str(entry), *args[1:]]


def validate_reference_constraints(policy):
    """Absent metadata is unknown, never permission or an unlimited allowance."""
    if policy is None:
        return
    status = policy.get('status')
    if status not in ('allowed', 'not_allowed', 'not_applicable', 'unspecified'):
        raise ValueError('Invalid reference constraint status')
    if status != 'allowed':
        if set(policy) - {'status', 'rule_source', 'notes'}:
            raise ValueError('Reference limits require allowed status')
        return
    if policy.get('medium') != 'paper' or policy.get('allocation') not in ('team', 'participant'):
        raise ValueError('Paper reference medium and team/participant allocation required')
    if 'sheet_limit' not in policy:
        raise ValueError('Explicit sheet_limit required; null means unlimited')
    limit = policy['sheet_limit']
    if limit is not None and (type(limit) is not int or limit < 1):
        raise ValueError('sheet_limit must be a positive integer or null')
    if type(policy.get('sides_per_sheet')) is not int or policy['sides_per_sheet'] not in (1, 2):
        raise ValueError('sides_per_sheet must be 1 or 2')
    if policy.get('paper_size') not in ('US Letter', 'any'):
        raise ValueError('Unsupported reference paper size')
    if not policy.get('rule_source'):
        raise ValueError('Reference rule source required')


def reference_page_limit(event):
    """PDF pages per declared allocation; None means explicitly unlimited."""
    policy = event.get('reference_constraints')
    validate_reference_constraints(policy)
    if not policy or policy['status'] != 'allowed':
        raise ValueError('No verified allowance for an exam reference')
    sheets = policy['sheet_limit']
    return None if sheets is None else sheets * policy['sides_per_sheet']


def reference_page_size_points(event):
    """Physical sheet dimensions in PDF points; None means any paper size."""
    reference_page_limit(event)  # Validate the full policy and require permission.
    size = event['reference_constraints']['paper_size']
    return None if size == 'any' else (612, 792)


def validate_reference_page_size(event, width, height):
    expected = reference_page_size_points(event)
    if expected is not None and any(abs(a-b) >= .01 for a,b in zip(sorted((float(width),float(height))), sorted(expected))):
        raise ValueError(f"PDF page must match {event['reference_constraints']['paper_size']}: {expected} pt")

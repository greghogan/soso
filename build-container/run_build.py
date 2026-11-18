#!/usr/bin/env python3
"""Build candidates from read-only retained inputs; never promote approved documents."""
from pathlib import Path
import hashlib
import importlib.metadata
import json
import os
import re
from html.parser import HTMLParser
from urllib.parse import urlsplit, unquote
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

SOURCE = Path(os.environ.get('MANUAL_SOURCE', '/source'))
OUTPUT = Path(os.environ.get('MANUAL_OUTPUT', '/output'))
WORK = Path(os.environ.get('MANUAL_WORK', '/work'))
EXCLUDED = {'asset-setup', 'asset-cache', '.asset-setup', '.asset-cache', '.venv', 'venv', '.aws', '.azure', '.ssh', '.config', '.cache',
            'build', '__pycache__', '.git', 'transfer-records', 'releases', 'qa', 'qa-final',
            'web', 'build-container', 'rules-manuals', 'downloaded-resources', 'private-resources'}
LICENSE_FILES = ('LICENSE.md', 'NOTICE', 'LICENSES/Apache-2.0.txt', 'LICENSES/CC-BY-4.0.txt', 'THIRD_PARTY_NOTICES.txt')
def registry(root):
    sys.path.insert(0, str(SOURCE))
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from soso.site.event_registry import load
    return load(root)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def ignore(directory, names):
    # Host environments contain absolute interpreter symlinks which are invalid
    # inside Docker. Local credential/configuration files are not build inputs.
    return {name for name in names if name in EXCLUDED or name == '.env' or name.startswith('.env.')
            or name.endswith('.zip') or (name.startswith('Science_Olympiad_') and '_Rules_' in name)}

def copy_inputs(source, stage):
    def staged_ignore(directory, names):
        excluded = ignore(directory, names)
        relative = Path(directory).relative_to(source).parts
        allowed = {('assets',): {'cache'}, ('assets', 'cache'): {'sha256'}}.get(relative)
        if allowed is not None:
            excluded.update(set(names) - allowed)
        return excluded
    shutil.copytree(source, stage, ignore=staged_ignore)
    for event in registry(source):
        base = stage / event['path']
        for name in event['pdfs']:
            (base / name).unlink(missing_ok=True)
        for name in event.get('required_inputs', []):
            if not (base / name).is_file():
                raise FileNotFoundError(f'Missing authored runtime input: {base / name}')

def check_web_dependencies(stage):
    missing = []
    class Links(HTMLParser):
        def __init__(self):
            super().__init__(); self.links = []
        def handle_starttag(self, tag, attrs):
            self.links.extend(v for k, v in attrs if k in ('src', 'href') and v)
            for key,value in attrs:
                if key != 'srcset' or not value:continue
                remaining=value
                while remaining.strip(' ,\t\r\n'):
                    remaining=remaining.lstrip(' ,\t\r\n')
                    match=re.match(r'\S+',remaining)
                    token=match[0];self.links.append(token.rstrip(','))
                    remaining=remaining[match.end():]
                    # URL tokens may contain commas (e.g. data URLs). Consume
                    # descriptors up to the next candidate separator separately.
                    if not token.endswith(','):remaining=remaining.partition(',')[2]
    for web in [stage] + list(stage.glob('events/*/*/web')):
        pages = list(stage.glob('index.html')) + list(stage.glob('events/*/*/index.html')) if web == stage else web.rglob('*')
        for path in pages:
            if not path.is_file() or path.suffix not in ('.html', '.css', '.js'):
                continue
            source = path.read_text()
            links = []
            if path.suffix == '.html':
                parser = Links(); parser.feed(source); links.extend(parser.links)
            links.extend(re.findall(r'url\([\"\']?([^\)\"\']+)', source))
            if path.suffix == '.js':
                links.extend(re.findall(r'(?:from\s+|import\s*)[\"\'](\.[^\"\']+)', source))
            for link in links:
                parts = urlsplit(link)
                if parts.scheme or parts.netloc or not parts.path:
                    continue
                target = (path.parent / unquote(parts.path)).resolve()
                if not target.exists():
                    missing.append(f'{path.relative_to(stage)} -> {link}')
    if missing:
        raise RuntimeError('Missing local web dependencies: ' + '; '.join(missing))
    return {'missing_local_dependencies': [], 'scope': 'HTML src/href/srcset, CSS url(), static relative JS imports; not browser execution'}

def web_manifests(stage):
    for web in stage.glob('events/*/*/web'):
        values = {str(p.relative_to(web)): sha(p) for p in sorted(web.rglob('*'))
                  if p.is_file() and p.name != 'MANIFEST.json'}
        (web / 'MANIFEST.json').write_text(json.dumps(values, indent=2) + '\n')

def copy_licenses(source, destination):
    """Preserve scoped licensing and third-party exceptions verbatim; never relicense."""
    for name in LICENSE_FILES:
        path = source / name
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(source.resolve()):
            raise FileNotFoundError(f'Missing or unsafe required license file: {name}')
    for name in LICENSE_FILES:
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / name, target)

def promote_candidates(stage, event):
    """Copy newly built candidates only inside the disposable stage."""
    for source, target in event.get('promote', {}).items():
        shutil.copy2(stage / event['path'] / source, stage / event['path'] / target)

def retain_tex_logs(stage, logs):
    """Keep compiler diagnostics even when compilation fails."""
    problems = []
    for source in stage.rglob('*.log'):
        if 'build' not in source.parts:
            continue
        relative = source.relative_to(stage)
        dest = logs / 'tex' / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        for line in source.read_text(errors='replace').splitlines():
            if ('Missing character:' in line or
                re.search(r'(?:mapping|font).*?(?:not found|cannot be found|not loadable)', line, re.I)):
                problems.append({'path': str(relative), 'warning': line})
    return problems

def build_jobs(event_count):
    """Bound event workers, not individual TeX passes or image operations."""
    requested = os.environ.get('SOSO_BUILD_JOBS', '3')
    if not requested.isdecimal() or int(requested) < 1:
        raise ValueError('SOSO_BUILD_JOBS must be a positive integer')
    cpus = len(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else (os.cpu_count() or 1)
    # Respect Linux container CPU quotas as well as affinity.
    quota = Path('/sys/fs/cgroup/cpu.max')
    if quota.is_file():
        limit, period = quota.read_text().split()
        if limit != 'max':
            cpus = min(cpus, max(1, int(limit) // int(period)))
    # Reserve roughly 1 GiB per event, including its staged assets and TeX work.
    memory_workers = cpus
    meminfo = Path('/proc/meminfo')
    if meminfo.is_file():
        total = int(re.search(r'MemTotal:\s+(\d+)', meminfo.read_text())[1]) * 1024
        memory_limit = Path('/sys/fs/cgroup/memory.max')
        if memory_limit.is_file() and memory_limit.read_text().strip() != 'max':
            total = min(total, int(memory_limit.read_text()))
        memory_workers = max(1, total // (1024 ** 3))
    return min(int(requested), cpus, memory_workers, max(1, event_count))

def build_events(entries, build_event, jobs):
    # Each event is serial internally. Wait for running tasks on failure so their
    # diagnostics are complete; callers must not export/promote a failed build.
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        list(pool.map(build_event, entries))

def main():
    if not (SOURCE / 'manifests/events.json').is_file():
        raise SystemExit('Mount the complete manual source tree at /source.')
    if any(OUTPUT.iterdir()):
        raise SystemExit('Output directory must be empty; no replacement is performed.')
    stage = WORK / 'project'
    cache = WORK / 'cache'
    cache.mkdir(parents=True)
    copy_inputs(SOURCE, stage)
    copy_licenses(SOURCE, stage)
    env = os.environ.copy()
    env.update(SOSO_STAGE_OUTPUTS='1', HOME=str(cache), XDG_CACHE_HOME=str(cache), XDG_CONFIG_HOME=str(cache),
               TEXMF='{/usr/share/texlive/texmf-dist,/usr/share/texmf}',
               TEXMFVAR=str(cache), TEXMFCACHE=str(cache), TEXFORMATS=str(cache) + ':')
    logs = OUTPUT / 'build-logs'
    logs.mkdir()
    report = {'status': 'running', 'commands': [], 'image_requested': env.get('MANUAL_BUILDER_IMAGE'),
              'python': sys.version, 'packages': {name: importlib.metadata.version(name) for name in ('reportlab', 'Pillow', 'PyMuPDF', 'pypdf')},
              'limitations': ['Retained input assets are used; this is not complete regeneration of all artwork.',
                              'No visual approval or promotion is implied by a successful build.',
                              'PDF timestamps/IDs can vary; byte reproducibility is not guaranteed.']}
    started = time.monotonic()
    def run(name, command, cwd=stage, command_env=None):
        record = {'name': name, 'argv': command}
        report['commands'].append(record)
        command_started = time.monotonic()
        try:
            with (logs / (name + '.log')).open('w') as stream:
                subprocess.run(command, cwd=cwd, env=command_env or env, stdout=stream, stderr=subprocess.STDOUT, check=True)
        finally:
            record['seconds'] = round(time.monotonic() - command_started, 3)
    try:
        # The exam builder does not initialize its own format in restricted environments.
        run('tex-format', ['xetex', '--ini', '--etex', '--interaction=nonstopmode', '--halt-on-error', '--jobname=xelatex', '--progname=xelatex', r'\input xelatex.ini'], cache)
        from soso.site.event_registry import command
        entries = registry(stage)
        report['events'] = entries
        report['jobs'] = build_jobs(len(entries))
        def build_event(event):
            event_cache = cache / f"{event['slug']}-{event['year']}"
            event_cache.mkdir()
            shutil.copy2(cache / 'xelatex.fmt', event_cache / 'xelatex.fmt')
            event_env = dict(env, SOSO_EVENT_DIR=str(stage / event['path']),
                             HOME=str(event_cache), XDG_CACHE_HOME=str(event_cache),
                             XDG_CONFIG_HOME=str(event_cache), TEXMFVAR=str(event_cache),
                             TEXMFCACHE=str(event_cache), TEXFORMATS=str(event_cache) + ':')
            for index, args in enumerate(event['build']):
                run(f"{event['slug']}-{event['year']}-{index}", command(stage, event, args, sys.executable), command_env=event_env)
            promote_candidates(stage, event)
        build_events(entries, build_event, report['jobs'])
        report['typesetting_warnings'] = retain_tex_logs(stage, logs)
        if report['typesetting_warnings']:
            raise RuntimeError('Missing glyph/font/mapping diagnostics; inspect retained TeX logs.')
        run('source-notices', [sys.executable, 'shared/provenance.py'])
        run('catalog-build', [sys.executable, '-m', 'soso.site.build_catalog', '--project-root', '.'])
        report['web_dependencies'] = check_web_dependencies(stage)
        web_manifests(stage)
        run('catalog-check', [sys.executable, '-m', 'soso.site.build_catalog', '--project-root', '.', '--check'])
        run('typography-check', [sys.executable, '-m', 'soso.site.audit_pdf_typography', '--root', '.'])
        for event in entries:
            base = Path(event['path'])
            for name in event['pdfs'] + ['index.html'] + event.get('site_assets', []):
                relative = base / name
                dest = OUTPUT / relative
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(stage / relative, dest)
            shutil.copytree(stage / base / 'web', OUTPUT / base / 'web')
        for name in ('index.html', 'shared/reader-navigation.css', 'catalog-data.json'):
            dest = OUTPUT / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(stage / name, dest)
        copy_licenses(stage, OUTPUT)
        report['output_web_dependencies'] = check_web_dependencies(OUTPUT)
        # Private raster identity allows selective PDF photo encoding without
        # mistaking rendered vector diagrams or transparent art for photographs.
        from PIL import Image
        sys.path.insert(0,str(stage/'shared'))
        from raster_assets import decoded_asset, external_masters
        photo_hashes=set()
        external=tuple(stage/path for path in external_masters(stage))
        for event in entries:
            assets={asset for pattern in event.get('photo_asset_globs',[])
                    for asset in (stage / event['path']).glob(pattern)}
            base=stage/event['path']
            assets.update(asset for asset in external if asset.is_relative_to(base)
                          and any(asset.relative_to(base).match(pattern) for pattern in event.get('photo_asset_globs',[])))
            for asset in assets:
                if asset.suffix.lower() not in {'.jpg','.jpeg','.webp','.jxl'}:continue
                with Image.open(decoded_asset(asset,stage/'build/decoded-assets')) as image:
                    if getattr(image,'is_animated',False):continue
                    photo_hashes.add(hashlib.sha256(image.convert('RGB').tobytes()).hexdigest())
        report['photo_pixel_hashes']=sorted(photo_hashes)
        import fitz
        report['pdfs'] = []
        for p in sorted(OUTPUT.rglob('*.pdf')):
            doc = fitz.open(p)
            report['pdfs'].append({'path': str(p.relative_to(OUTPUT)), 'pages': len(doc), 'sha256': sha(p)})
        report['status'] = 'built-candidates-not-visually-approved'
    except Exception as error:
        report['status'] = 'failed'
        report['error'] = str(error)
        raise
    finally:
        report['seconds'] = round(time.monotonic() - started, 3)
        report['commands'].sort(key=lambda record: record['name'])
        if stage.exists():
            retain_tex_logs(stage, logs)
        for name in ('python-installed.txt', 'debian-installed.txt'):
            p = Path('/opt/manual-builder') / name
            if p.exists():
                shutil.copy2(p, logs / name)
        (OUTPUT / 'build-report.json').write_text(json.dumps(report, indent=2) + '\n')
        files = [{'path': str(p.relative_to(OUTPUT)), 'bytes': p.stat().st_size, 'sha256': sha(p)}
                 for p in sorted(OUTPUT.rglob('*')) if p.is_file() and p.name != 'output-manifest.json']
        (OUTPUT / 'output-manifest.json').write_text(json.dumps({'files': files}, indent=2) + '\n')

if __name__ == '__main__':
    main()

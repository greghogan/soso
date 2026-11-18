"""Decode canonical JPEG XL masters into disposable build inputs."""
from pathlib import Path
import hashlib
import json
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def external_masters(root):
    """Record source images by their logical pre-migration master paths."""
    manifest = Path(root) / 'manifests/external-assets.json'
    if not manifest.is_file():
        return {}
    result = {}
    for record in json.loads(manifest.read_text())['assets']:
        path = record['legacy_path']
        if path in result:
            raise ValueError('Duplicate external image path: '+path)
        result[path] = record
    return result


def decoded_asset(path, cache, web=False):
    path = Path(path)
    if path.suffix.lower() != '.jxl':
        return path
    records = json.loads((ROOT / 'manifests/raster-masters.json').read_text())['assets']
    record = next(item for item in records if item['path'] == path.relative_to(ROOT).as_posix())
    suffix = '.jpg' if record['reversible_jpeg'] else '.png'
    external = external_masters(ROOT).get(path.relative_to(ROOT).as_posix())
    if external is not None:
        key = external['sha256']
        if not record['reversible_jpeg'] or key != record['original_sha256']:
            raise ValueError('External image manifest disagrees with raster metadata: '+str(path))
        cache_root = ROOT / 'assets/cache'
        original = cache_root / 'sha256' / key[:2] / key
        if not original.exists() and not original.is_symlink():
            raise FileNotFoundError(f'Missing verified original for {path.name} ({key}); run ./scripts/asset_fetch.py before building.')
        if (original.is_symlink() or not original.is_file()
                or not original.resolve().is_relative_to(cache_root.resolve())):
            raise ValueError('Original-image cache verification failed: '+str(original))
        data = original.read_bytes()
        if hashlib.sha256(data).hexdigest() != key:
            raise ValueError('Original-image cache verification failed: '+str(original))
    else:
        key = hashlib.sha256(path.read_bytes()).hexdigest()
    cache = Path(cache); cache.mkdir(parents=True, exist_ok=True)
    target = cache / (key + '-normalized' + suffix)
    if external is not None:
        from PIL import Image
        from io import BytesIO
        with Image.open(BytesIO(data)) as image:
            if hashlib.sha256(image.convert('RGB').tobytes()).hexdigest() != record['decoded_rgb_sha256']:
                raise ValueError('Original image decoded pixel mismatch: '+str(path))
        if not target.is_file() or target.read_bytes() != data:
            # Publish only fully verified bytes; concurrent renders may share the cache.
            with tempfile.TemporaryDirectory(dir=cache) as directory:
                pending = Path(directory) / 'original'
                pending.write_bytes(data)
                pending.replace(target)
        return target
    if not target.exists():
        subprocess.run(['djxl', str(path), str(target)], check=True, capture_output=True)
        from PIL import Image
        with Image.open(target) as image:
            # Match the existing Pillow PNG path: djxl also writes gamma/chromaticity
            # chunks, which can change XeLaTeX color interpretation without changing pixels.
            if suffix == '.png':
                pixels=image.copy()
                metadata={k:image.info[k] for k in ('icc_profile','exif') if image.info.get(k)}
            actual=hashlib.sha256(image.convert('RGB').tobytes()).hexdigest()
        if suffix == '.png':
            pixels.save(target,'PNG',**metadata)
        if actual != record['decoded_rgb_sha256']:
            target.unlink(); raise ValueError('JPEG XL decoded pixel mismatch: '+str(path))
        if record['reversible_jpeg'] and hashlib.sha256(target.read_bytes()).hexdigest()!=record['original_sha256']:
            target.unlink(); raise ValueError('JPEG reconstruction mismatch: '+str(path))
    if web and suffix == '.png':
        from PIL import Image
        web_target = cache / (key + '-normalized.webp')
        if not web_target.exists():
            with Image.open(target) as image:
                metadata = {k:image.info[k] for k in ('icc_profile','exif') if image.info.get(k)}
                image.save(web_target, 'WEBP', lossless=True, **metadata)
        return web_target
    return target

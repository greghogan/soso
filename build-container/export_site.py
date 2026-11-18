#!/usr/bin/env python3
"""Prepare a NEW local site directory. No Git or network operations; review required."""
from pathlib import Path
import hashlib,json,re,shutil,sys
from io import BytesIO
LICENSE_FILES=('LICENSE.md','NOTICE','LICENSES/Apache-2.0.txt','LICENSES/CC-BY-4.0.txt', 'THIRD_PARTY_NOTICES.txt')
EXTENSIONS={'.html','.css','.js','.svg','.png','.jpg','.jpeg','.webp','.gif','.woff','.woff2','.json','.txt','.pdf'}
def selected(root):
    paths=[Path('index.html'),Path('shared/reader-navigation.css'),Path('catalog-data.json')]
    report=json.loads((root/'build-report.json').read_text())
    entries=report.get('events')
    if entries is None:
        # Read older successful candidate layouts without assuming an event or year.
        entries=[{'path':str(p.relative_to(root)), 'pdfs':[f.name for f in p.glob('*.pdf')],
                  'site_assets':[str(f.relative_to(p)) for f in (p/'assets').rglob('*.svg')]}
                 for p in sorted((root/'events').glob('*/*')) if p.is_dir()]
    for event in entries:
        base=Path(event['path'])
        paths.extend(base/name for name in ['index.html']+event['pdfs']+event.get('site_assets',[]))
        paths.extend(p.relative_to(root) for p in sorted((root/base/'web').rglob('*')) if p.is_file() and p.name != '.DS_Store')
    paths.extend(Path(name) for name in LICENSE_FILES)
    for rel in paths:
        path=root/rel
        if path.is_symlink() or not path.is_file() or (path.suffix.lower() not in EXTENSIONS and str(rel) not in LICENSE_FILES):
            raise ValueError(f'Unsupported or missing site file: {rel}')
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError(f'File escapes candidate tree: {rel}')
    return paths


def optimize_pdf(path, photo_hashes=()):
    """Encode opted-in opaque photos; keep text/vectors and other rasters intact.

    300 ppi is the print target, with 20% headroom before resampling. A shared
    image uses its largest placement anywhere in the document, including crops.
    """
    import fitz
    from PIL import Image,ImageFile
    doc=fitz.open(path)
    images={}
    for page in doc:
        for info in page.get_image_info(xrefs=True):
            xref=info['xref']
            if not xref or info['width']<128 or info['height']<128:continue
            # Transform describes the full image, not just the clipped viewport.
            a,b,c,d,_,_=info['transform']
            width=(a*a+b*b)**.5; height=(c*c+d*d)**.5
            if not width or not height:continue
            size=(min(info['width'],round(width/72*300)),min(info['height'],round(height/72*300)))
            if xref in images:
                prev=images[xref][1];size=(max(prev[0],size[0]),max(prev[1],size[1]))
            images[xref]=(page.number,size,(info['width'],info['height']))
    photo_hashes=set(photo_hashes)
    changed=0
    for xref,(number,size,original) in images.items():
        resize=min(original[0]/max(size[0],1),original[1]/max(size[1],1))>1.2
        # Soft masks / indexed graphics require extra handling: leave untouched.
        # Nonstandard sample depths or decode maps need a separate color path.
        if doc.xref_get_key(xref,'BitsPerComponent')[1]!='8':continue
        if doc.xref_get_key(xref,'Decode')[0]!='null':continue
        extracted=doc.extract_image(xref)
        if extracted.get('smask'):continue
        with Image.open(BytesIO(extracted['image'])) as im:
            if im.mode not in {'RGB','L'}:continue
            photo=hashlib.sha256(im.convert('RGB').tobytes()).hexdigest() in photo_hashes
            if not photo:continue
            opaque=im.mode in {'RGB','L'}
            # Suitable source JPEGs pass through: don't add a needless generation.
            jpeg=photo and opaque and (extracted.get('ext')!='jpeg' or resize)
            if not resize and not jpeg:continue
            if resize:im.thumbnail(size,Image.Resampling.LANCZOS)
            stream=BytesIO()
            if jpeg:
                # Pillow's optimized 4:4:4 encoder needs room for noisy images.
                ImageFile.MAXBLOCK=max(ImageFile.MAXBLOCK,im.width*im.height*4)
                im.save(stream,format='JPEG',quality=90,subsampling=0,optimize=True)
            else:im.save(stream,format='PNG',optimize=True)
        # Do not inflate a compact original JPEG merely to lower its resolution.
        if len(stream.getvalue())>=len(doc.xref_stream_raw(xref)):continue
        # Reuse the original PDF color interpretation (including ICC profiles).
        colorspace=doc.xref_get_key(xref,'ColorSpace')[1]
        doc[number].replace_image(xref,stream=stream.getvalue())
        doc.xref_set_key(xref,'ColorSpace',colorspace)
        changed+=1
    if changed:
        output=doc.tobytes(garbage=4,deflate=True)
        if len(output)<path.stat().st_size:path.write_bytes(output)
    doc.close()
    return changed


def optimize_web_images(dest,paths,photo_hashes=()):
    """Reader-sized derivatives; full masters stay in the source tree.

    A 1600-pixel long edge retains high-density reading and identification views.
    JPEG/WebP photographs and artwork use quality 90. PNG and transparent
    assets stay lossless. Keep originals when encoding is larger.
    """
    photo_hashes=set(photo_hashes)
    changes={}
    for rel in list(paths):
        if 'web' not in rel.parts or rel.suffix.lower() not in {'.jpg','.jpeg','.png','.webp'}:continue
        from PIL import Image,ImageOps
        path=dest/rel
        with Image.open(path) as im:
            if getattr(im,'is_animated',False) or im.mode not in {'RGB','RGBA','L','P'}:continue
            photo=hashlib.sha256(im.convert('RGB').tobytes()).hexdigest() in photo_hashes
            im=ImageOps.exif_transpose(im)
            opaque=im.mode in {'RGB','L'} or ('A' in im.getbands() and im.getchannel('A').getextrema()==(255,255))
            photo=photo and opaque
            resized=photo and max(im.size)>1600
            if photo:im.thumbnail((1600,1600),Image.Resampling.LANCZOS)
            stream=BytesIO()
            opaque=im.mode in {'RGB','L'} or ('A' in im.getbands() and im.getchannel('A').getextrema()==(255,255))
            lossy=opaque and photo
            im.save(stream,format='WEBP',lossless=not lossy,quality=90,method=6,exact=True,
                    **({'icc_profile':im.info['icc_profile']} if im.info.get('icc_profile') else {}))
        data=stream.getvalue()
        # Do not discard resolution for a negligible storage gain.
        if len(data)>=path.stat().st_size*(0.9 if resized else 1):continue
        new=rel.with_suffix('.webp')
        if new!=rel and (dest/new).exists():continue
        (dest/new).write_bytes(data)
        if new!=rel:
            path.unlink();paths[paths.index(rel)]=new;changes[rel]=new
    # Rewrite only local paths relative to each reader file, never source URLs,
    # attribution text, or content hashes in private source provenance records.
    import os
    for rel in paths:
        if rel.suffix not in {'.html','.css','.js','.json'}:continue
        path=dest/rel;text=path.read_text();updated=text
        for old,new in changes.items():
            before=Path(os.path.relpath(old,rel.parent)).as_posix()
            after=Path(os.path.relpath(new,rel.parent)).as_posix()
            # Match complete relative URL tokens, including srcset candidates,
            # optional ./ prefixes and query/fragment suffixes. A slash before
            # the token is not a boundary, so external source URLs stay intact.
            pattern=r'''(?<=[\"'(\s,])(\./)?'''+re.escape(before)+r'''(?=[?#\"')\s,]|$)'''
            updated=re.sub(pattern,lambda match:(match[1] or '')+after,updated)
        if updated!=text:path.write_text(updated)
    return changes

def export(root,dest):
    if dest.exists() or dest.with_name(dest.name+'-export.json').exists():
        raise FileExistsError('Site destination and adjacent export report must not exist; existing files are never replaced.')
    report=json.loads((root/'build-report.json').read_text())
    if report['status']!='built-candidates-not-visually-approved':raise ValueError('Successful candidate build required.')
    paths=selected(root)
    dest.mkdir(parents=True)
    for rel in paths:
        target=dest/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(root/rel,target)
    optimize_web_images(dest,paths,report.get('photo_pixel_hashes',[]))
    for rel in paths:
        if rel.suffix=='.pdf':optimize_pdf(dest/rel,report.get('photo_pixel_hashes',[]))
    # Check the transformed reader, not only the full-resolution candidate.
    import importlib.util
    spec=importlib.util.spec_from_file_location('site_dependency_checks',Path(__file__).with_name('run_build.py'))
    checks=importlib.util.module_from_spec(spec);spec.loader.exec_module(checks)
    checks.check_web_dependencies(dest.resolve())
    for rel in paths:
        if rel.name=='MANIFEST.json' and 'web' in rel.parts:
            folder=(dest/rel).parent
            entries={str(p.relative_to(folder)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.rglob('*')) if p.is_file() and p.name!='MANIFEST.json'}
            (dest/rel).write_text(json.dumps(entries,indent=2)+'\n')
    (dest/'.nojekyll').write_bytes(b'')
    manifest=[{'path':str(p),'sha256':hashlib.sha256((dest/p).read_bytes()).hexdigest()} for p in paths]
    manifest.append({'path':'.nojekyll','sha256':hashlib.sha256(b'').hexdigest()})
    # Audit stays alongside destination, never inside the public site.
    dest.with_name(dest.name+'-export.json').write_text(json.dumps({'status':'local-candidate-not-approved-for-publication','source_bytes':sum((root/p).stat().st_size for p in selected(root)), 'published_bytes':sum((dest/p).stat().st_size for p in paths),'image_policy':{'web_long_edge_px':1600,'web_encoding':'WebP quality 90, method 6 for opaque photos/art; lossless for PNG/transparency; only when smaller','pdf_photo_encoding':'JPEG quality 90, 4:4:4; suitable existing JPEGs unchanged','pdf_target_ppi':300,'pdf_resize_threshold_ppi':360},'files':manifest},indent=2)+'\n')
    return manifest
if __name__=='__main__':
    if len(sys.argv)!=3:raise SystemExit('Usage: export_site.py CANDIDATE_OUTPUT NEW_SITE_DIRECTORY')
    print(f'Prepared {len(export(Path(sys.argv[1]),Path(sys.argv[2])))} files; no publication performed.')

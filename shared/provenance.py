"""Canonical rights records -> guide credits and distribution notices.

Teaching captions stay in event content. Do not copy legal/source metadata there.
"""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def records(root=ROOT):
    return json.loads((Path(root)/'manifests/rights-inventory.json').read_text())['assets']


def source_index(root=ROOT):
    result = {}
    for record in records(root):
        if record.get('id'):
            if record['id'] in result:
                raise ValueError('Duplicate provenance ID: '+record['id'])
            result[record['id']] = record
    return result


def hydrate_photo(row, event, primary=False):
    """Resolve source_id without modifying authored data, failing on a wrong asset."""
    row = dict(row)
    record = source_index()[row['source_id']]
    asset = row.get('image') if primary else row.get('path')
    if (Path(event)/asset).resolve() != (ROOT/record['path']).resolve():
        raise ValueError('Photo source_id refers to a different file: '+row['source_id'])
    credit = record['creator']+' · '+record['license']
    row['source_title'] = record.get('title',row.get('title','Photograph'))
    row['source_changes'] = record.get('modifications','')
    if primary:
        row['caption'] += ' Photo: '+record['creator']+'; '+record['license']+'.'
        row['image_source'] = record['source_url']
        row['image_license_url'] = record['license_url']
    else:
        row.update(credit=credit,description_url=record['source_url'],license_url=record['license_url'])
    return row


def atlas(event, filename='organisms.json'):
    data=json.loads((Path(event)/'source'/filename).read_text())
    data['organisms']=[hydrate_photo(row,event,True) if row.get('image') else row for row in data['organisms']]
    return data


def supplemental(event, filename='supplemental-images.json'):
    return [hydrate_photo(row,event) for row in json.loads((Path(event)/'source'/filename).read_text())['photos']]


def validate_citation(record):
    if record.get('quotation') and not (record.get('locator') and record.get('rights_basis')):
        raise ValueError('Quotation requires locator and rights_basis: '+str(record.get('id','')))
    return record


def citation_detail(record):
    """Optional precise bibliographic context; never infer missing facts."""
    return '; '.join(str(record[k]) for k in ('author','publication_date','version','locator') if record.get(k))


def notices(root=ROOT):
    root=Path(root)
    output=(root/'LICENSES/third-party-preamble.txt').read_text().rstrip()+'\n\n'
    output+='Image credits (generated from manifests/rights-inventory.json)\n'
    output+='These works retain their individual licenses, not the project prose license.\nCC BY-SA terms continue to apply to adaptations of the respective photographs.\n\n'
    manifest=root/'manifests/external-assets.json'
    external={item['legacy_path'] for item in json.loads(manifest.read_text())['assets']} if manifest.is_file() else set()
    for row in sorted(records(root),key=lambda r:r['path']):
        if row.get('historical') or not row.get('creator') or not row.get('source_url'):continue
        if row['path'] not in external and not (root/row['path']).is_file():raise ValueError('Missing credited master: '+row['path'])
        output+='File: '+row['path']+'\n'
        for label,key in [('Title','title'),('Creator','creator'),('License','license'),('License URL','license_url'),('Source','source_url'),('Original source','original_source'),('Changes','modifications')]:
            if row.get(key):output+=label+': '+str(row[key])+'\n'
        output+='\n'
    return output.rstrip()+'\n'


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    target=ROOT/'THIRD_PARTY_NOTICES.txt'
    if args.check:
        if target.read_text()!=notices():raise SystemExit('Stale notices: run python3 shared/provenance.py')
    else:target.write_text(notices())

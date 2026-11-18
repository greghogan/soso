"""Prepare unlabeled retrieval examples while retaining per-photo provenance."""
def practice_records(organisms, photos=()):
    by_id = {row['id']: row for row in organisms}
    records = []
    for row in organisms:
        if row.get('practice') is False or not row.get('image'):
            continue
        record = {key: row.get(key, '') for key in ('id', 'name', 'diagnostic', 'scientific_name', 'ecology', 'caption', 'image_source', 'image_license_url', 'image', 'alt')}
        if row.get('source_title'):
            record['caption'] += ' Source: '+row['source_title']+'. Changes: '+row.get('source_changes','')
        record['organism_id'] = row['id']
        records.append(record)
    for photo in photos:
        row = by_id[photo['organism_id']]
        if photo.get('practice') is False or row.get('practice') is False:
            continue
        records.append({
            'id': photo['id'], 'organism_id': row['id'], 'name': row['name'],
            'scientific_name': row['scientific_name'], 'diagnostic': row['diagnostic'],
            'ecology': row['ecology'], 'image': photo['path'], 'alt': photo['alt'],
            'caption': photo['caption'] + ' Photo: ' + photo['credit'] + '.' + (' Source: '+photo['source_title']+'. Changes: '+photo.get('source_changes','') if photo.get('source_title') else ''),
            'image_source': photo['description_url'], 'image_license_url': photo['license_url'],
        })
    for record in records:
        record['caption'] += ' Published copy may be resized and re-encoded as high-quality WebP or JPEG.'
        if record['organism_id'] in ('snapper', 'sweetlips'):
            record['diagnostic'] += (' Compare several features with the other group, not one color or lip shape. '
                'Thick lips alone do not separate sweetlips from snappers: some snappers also have thick lips. '
                'Do not claim teeth, a tail shape or a size that this view does not show. If the photo is inconclusive, say what additional view you need.')
    return records

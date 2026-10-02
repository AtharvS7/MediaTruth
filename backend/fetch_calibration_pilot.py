"""Bounded Tiny-GenImage calibration/holdout acquisition; research-only, not release data."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import random
import time

from PIL import Image
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from evaluation import read_manifest

DATASET = 'TheKernel01/Tiny-GenImage'
REVISION = '89c4fe9efd0ebc7ce5c7641ef57d578ccd639c69'
GENERATORS = ['Real', 'ADM', 'BigGAN', 'GLIDE', 'Midjourney', 'SD14', 'SD15', 'VQDM', 'Wukong']


def fetch(destination, per_class=24, resume=False):
    if not 2 <= per_class <= 200:
        raise ValueError('Per-class budget must be between 2 and 200')
    destination.mkdir(parents=True, exist_ok=resume)
    records, failures, seen, total_bytes = [], [], set(), 0
    if resume:
        for split in ('validation','test'):
            rows=read_manifest(destination/f'{split}.jsonl')
            if any(r['source_revision']!=REVISION or r['split']!=split for r in rows):
                raise ValueError('Existing acquisition identity mismatch')
            records.extend(rows)
        prior=json.loads((destination/'acquisition.json').read_text())
        if prior['requested_per_class_per_split']!=per_class:
            raise ValueError('Cannot change sampling plan during resume')
        failures=prior['failures']
        seen={r['group_id'] for r in records}
        total_bytes=sum((destination/r['path']).stat().st_size for r in records)
    with requests.Session() as session:
        session.mount('https://',HTTPAdapter(max_retries=Retry(total=3,backoff_factor=2,
            status_forcelist=[429,500,502,503,504],allowed_methods=['GET'],respect_retry_after_header=True)))
        metadata = session.get(f'https://huggingface.co/api/datasets/{DATASET}', timeout=30)
        metadata.raise_for_status()
        if metadata.json()['sha'] != REVISION:
            raise ValueError('Dataset revision changed; review before acquisition')
        card = session.get(f'https://huggingface.co/datasets/{DATASET}/raw/{REVISION}/README.md', timeout=30)
        card.raise_for_status()
        if 'license: cc-by-nc-sa-4.0' not in card.text:
            raise ValueError('Dataset license changed')
        (destination/'SOURCE_README.md').write_text(card.text, encoding='utf-8')
        for source_split, target_split, count in [('train','validation',28000), ('validation','test',7000)]:
            offsets = list(range(count))
            random.Random(f'mediatruth-calibration-v1-{source_split}').shuffle(offsets)
            selected = {0:sum(r['split']==target_split and r['label']=='original' for r in records),
                        1:sum(r['split']==target_split and r['label']=='ai_generated' for r in records)}
            acquired_offsets={r['source_row'] for r in records if r['split']==target_split}
            consecutive_failures = 0
            for offset in offsets[:per_class*12]:
                if min(selected.values()) >= per_class:
                    break
                if offset in acquired_offsets:
                    continue
                try:
                    time.sleep(1)  # Respect the shared public dataset viewer's request budget.
                    response = session.get('https://datasets-server.huggingface.co/rows', params={
                        'dataset':DATASET,'config':'default','split':source_split,'offset':offset,'length':1}, timeout=45)
                    response.raise_for_status()
                    item = response.json()['rows'][0]
                    row = item['row']
                    label, generator = row['label'], row['generator']
                    if item.get('truncated_cells') or label not in (0,1) or generator not in range(9):
                        raise ValueError('Incomplete annotation')
                    if (label==0) != (generator==0):
                        raise ValueError('Conflicting generator label')
                    if selected[label] >= per_class:
                        continue
                    with session.get(row['image']['src'], stream=True, timeout=45) as media:
                        media.raise_for_status()
                        chunks, size = [], 0
                        for chunk in media.iter_content(65536):
                            size += len(chunk)
                            if size > 8_000_000:
                                raise ValueError('Image exceeds byte budget')
                            chunks.append(chunk)
                    raw = b''.join(chunks)
                    with Image.open(io.BytesIO(raw)) as image:
                        if image.width*image.height > 4_000_000:
                            raise ValueError('Image exceeds pixel budget')
                        rgb = image.convert('RGB')
                        pixel_digest = hashlib.sha256(str(rgb.size).encode()+rgb.tobytes()).hexdigest()
                    if pixel_digest in seen:
                        continue
                    total_bytes += len(raw)
                    if total_bytes > 512_000_000:
                        raise RuntimeError('Experiment exceeds total byte budget')
                    seen.add(pixel_digest)
                    name = f'{source_split}-{offset:06d}.image'
                    (destination/name).write_bytes(raw)
                    record = dict(id=f'tiny-{source_split}-{offset}',path=name,
                        label='original' if label==0 else 'ai_generated',
                        sha256=hashlib.sha256(raw).hexdigest(),group_id=pixel_digest,
                        split=target_split,source=f'https://huggingface.co/datasets/{DATASET}',
                        source_revision=REVISION,source_split=source_split,source_row=offset,
                        generator=GENERATORS[generator],license='CC-BY-NC-SA-4.0 (dataset card)',
                        independence_verified=False,
                        encoding='dataset viewer representation; original-byte identity not asserted',
                        provenance_caveat='Derived public subset; parent/training overlap and underlying rights require review')
                    records.append(record)
                    selected[label] += 1
                    consecutive_failures = 0
                    print(json.dumps({'split':target_split,'originals':selected[0],'generated':selected[1]}), flush=True)
                except (requests.RequestException, ValueError, KeyError, IndexError) as error:
                    response=getattr(error,'response',None)
                    failure={'split':source_split,'offset':offset,'type':type(error).__name__,
                             'http_status':response.status_code if response is not None else None}
                    failures.append(failure)
                    print(json.dumps({'failure':failure}),flush=True)
                    consecutive_failures += 1
                    if consecutive_failures >= 3:
                        break
        check = session.get(f'https://huggingface.co/api/datasets/{DATASET}', timeout=30)
        check.raise_for_status()
        if check.json()['sha'] != REVISION:
            raise ValueError('Dataset changed during acquisition')
    for split in ('validation','test'):
        rows = [r for r in records if r['split']==split]
        (destination/f'{split}.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows), encoding='utf-8')
    (destination/'acquisition.json').write_text(json.dumps({'requested_per_class_per_split':per_class,
        'acquired':len(records),'bytes':total_bytes,'failures':failures,'release_eligible':False,
        'selection':'seeded shuffled source offsets, balanced without looking at model scores'},indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination',type=Path)
    parser.add_argument('--per-class',type=int,default=24)
    parser.add_argument('--resume',action='store_true')
    args = parser.parse_args()
    fetch(args.destination,args.per_class,args.resume)

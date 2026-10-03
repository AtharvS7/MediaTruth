"""Acquire a frozen, generator-stratified research wave excluding prior content.

Public source overlap with model training remains unknown. Never mark these
samples independently verified or commercially licensed by acquisition alone.
"""
import argparse
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import random
import time

from PIL import Image
import requests

from evaluation import read_manifest
from fetch_calibration_pilot import DATASET, GENERATORS, REVISION


def pixel_hash(raw, max_pixels=4_000_000):
    with Image.open(io.BytesIO(raw)) as image:
        if image.width * image.height > max_pixels or min(image.size) < 32:
            raise ValueError('Image outside pixel budget')
        rgb = image.convert('RGB')
        return hashlib.sha256(str(rgb.size).encode() + rgb.tobytes()).hexdigest()


def excluded_content(manifests):
    hashes, pixels, ids = set(), set(), set()
    for manifest in manifests:
        for row in read_manifest(manifest):
            hashes.add(row['sha256'])
            pixels.add(pixel_hash((manifest.parent / row['path']).read_bytes(), max_pixels=40_000_000))
            if row['source'] == f'https://huggingface.co/datasets/{DATASET}':
                ids.add(row['id'])
    return hashes, pixels, ids


def candidate(item, counts, quota, excluded_ids):
    row = item['row']
    label, generator = row['label'], row['generator']
    if (item.get('truncated_cells') or type(label) is not int or label not in (0, 1)
            or type(generator) is not int or generator not in range(9)
            or (label == 0) != (generator == 0)):
        raise ValueError('Invalid source annotation')
    key = f"tiny-validation-{item['row_idx']}"
    if key in excluded_ids or counts[generator] >= (8 * quota if generator == 0 else quota):
        return None
    return key, generator


def fetch(destination, exclusions, per_generator=25, resume=False):
    if not 1 <= per_generator <= 25 or not exclusions:
        raise ValueError('Require prior manifests and bounded generator quota 1..25')
    exclusions = [Path(p).resolve() for p in exclusions]
    contract = {'dataset': DATASET, 'revision': REVISION, 'source_split': 'validation',
                'seed': 'mediatruth-frozen-wave-20261003-v1', 'per_generator': per_generator,
                'exclusion_manifest_sha256': sorted(hashlib.sha256(p.read_bytes()).hexdigest() for p in exclusions),
                'release_eligible': False, 'selection': 'shuffled 100-row pages; fixed label quotas; no model scores'}
    destination.mkdir(parents=True, exist_ok=resume)
    contract_path = destination / 'contract.json'
    rows, failures = [], []
    if resume:
        if json.loads(contract_path.read_text()) != contract:
            raise ValueError('Acquisition contract changed')
        if (destination / 'test.jsonl').exists():
            rows = read_manifest(destination / 'test.jsonl')
            failures = json.loads((destination / 'acquisition.json').read_text())['failures']
    else:
        contract_path.write_text(json.dumps(contract, indent=2), encoding='utf-8')
    hashes, pixels, ids = excluded_content(exclusions)
    for row in rows:
        digest = pixel_hash((destination / row['path']).read_bytes())
        if row['sha256'] in hashes or digest in pixels or row['id'] in ids:
            raise ValueError('Resumed sample overlaps excluded or acquired content')
        hashes.add(row['sha256'])
        pixels.add(digest)
        ids.add(row['id'])
    counts = Counter(GENERATORS.index(r['generator']) for r in rows)
    total_bytes = sum((destination / r['path']).stat().st_size for r in rows)

    def save():
        temp = destination / 'test.jsonl.tmp'
        temp.write_text(''.join(json.dumps(r) + '\n' for r in rows), encoding='utf-8')
        temp.replace(destination / 'test.jsonl')
        (destination / 'acquisition.json').write_text(json.dumps({
            'acquired': len(rows), 'requested': 16 * per_generator, 'counts': dict(counts),
            'bytes': total_bytes, 'failures': failures, 'release_eligible': False}, indent=2), encoding='utf-8')

    save()
    with requests.Session() as session:
        metadata = session.get(f'https://huggingface.co/api/datasets/{DATASET}', timeout=30)
        metadata.raise_for_status()
        if metadata.json()['sha'] != REVISION:
            raise ValueError('Source revision changed')
        card = session.get(f'https://huggingface.co/datasets/{DATASET}/raw/{REVISION}/README.md', timeout=30)
        card.raise_for_status()
        if 'license: cc-by-nc-sa-4.0' not in card.text:
            raise ValueError('Source license changed')
        (destination / 'SOURCE_README.md').write_text(card.text, encoding='utf-8')
        pages = list(range(0, 7000, 100))
        random.Random(contract['seed']).shuffle(pages)
        consecutive_failures = 0
        for offset in pages:
            if len(rows) == 16 * per_generator:
                break
            time.sleep(1)
            response = session.get('https://datasets-server.huggingface.co/rows', params={
                'dataset': DATASET, 'config': 'default', 'split': 'validation',
                'offset': offset, 'length': 100}, timeout=45)
            response.raise_for_status()
            for item in response.json()['rows']:
                selected = candidate(item, counts, per_generator, ids)
                if selected is None:
                    continue
                key, generator = selected
                try:
                    time.sleep(.25)
                    with session.get(item['row']['image']['src'], stream=True, timeout=30) as media:
                        media.raise_for_status()
                        chunks, size = [], 0
                        for chunk in media.iter_content(65536):
                            size += len(chunk)
                            if size > 8_000_000:
                                raise ValueError('Image exceeds byte budget')
                            chunks.append(chunk)
                    raw = b''.join(chunks)
                    digest, pixel = hashlib.sha256(raw).hexdigest(), pixel_hash(raw)
                    if digest in hashes or pixel in pixels:
                        ids.add(key)
                        continue
                    if total_bytes + len(raw) > 128_000_000:
                        raise RuntimeError('Total byte budget exceeded')
                    name = f"validation-{item['row_idx']:06d}.image"
                    (destination / name).write_bytes(raw)
                    rows.append(dict(id=key, path=name, sha256=digest, group_id=pixel, split='test',
                        source=f'https://huggingface.co/datasets/{DATASET}', source_revision=REVISION,
                        source_split='validation', source_row=item['row_idx'], generator=GENERATORS[generator],
                        label='original' if generator == 0 else 'ai_generated',
                        license='CC-BY-NC-SA-4.0 (dataset card)', independence_verified=False,
                        encoding='dataset viewer representation; parent/training overlap unknown'))
                    total_bytes += len(raw)
                    hashes.add(digest)
                    pixels.add(pixel)
                    ids.add(key)
                    counts[generator] += 1
                    consecutive_failures = 0
                    save()
                    print(json.dumps({'acquired': len(rows), 'requested': 16 * per_generator}), flush=True)
                except (requests.RequestException, ValueError) as error:
                    failures.append({'id': key, 'error_type': type(error).__name__})
                    consecutive_failures += 1
                    save()
                    if consecutive_failures >= 3:
                        raise RuntimeError('Acquisition stopped after three consecutive failures') from None
        check = session.get(f'https://huggingface.co/api/datasets/{DATASET}', timeout=30)
        check.raise_for_status()
        if check.json()['sha'] != REVISION:
            raise ValueError('Source revision changed during acquisition; do not evaluate')
    if len(rows) != 16 * per_generator:
        raise ValueError('Incomplete quotas; do not silently evaluate a biased subset')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--exclude', type=Path, action='append', required=True)
    parser.add_argument('--per-generator', type=int, default=25)
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    fetch(args.destination, args.exclude, args.per_generator, args.resume)

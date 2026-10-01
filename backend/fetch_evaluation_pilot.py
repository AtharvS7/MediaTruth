"""Fetch a bounded SafeIMG research pilot; never a representative release dataset.

Usage: python fetch_evaluation_pilot.py ../evaluation/data/safeimg --count 12
Images are synthetic evidence, not records of real events. Non-commercial only.
"""
import argparse
import hashlib
import json
from pathlib import Path

import requests

DATASET = 'Snowstorm1492/SafeIMG'
SOURCE = f'https://huggingface.co/datasets/{DATASET}'


def fetch(destination: Path, count: int):
    if not 1 <= count <= 48:
        raise ValueError('Pilot count must be between 1 and 48')
    # Prevent mixing an old pilot with a changed source revision.
    destination.mkdir(parents=True, exist_ok=False)
    with requests.Session() as client:
        response = client.get(f'https://huggingface.co/api/datasets/{DATASET}', timeout=30)
        response.raise_for_status()
        revision = response.json()['sha']
        response = client.get(f'{SOURCE}/raw/{revision}/README.md', timeout=30)
        response.raise_for_status()
        if 'https://creativecommons.org/licenses/by-nc-sa/4.0/' not in response.text:
            raise ValueError('Dataset license changed; review before downloading')
        (destination/'SOURCE_README.md').write_text(response.text, encoding='utf-8')
        manifest = []
        # The viewer serves encoded images: preserve these bytes and identify them
        # explicitly instead of claiming that they are the original image files.
        first = client.get('https://datasets-server.huggingface.co/rows', params={
            'dataset': DATASET, 'config': 'default', 'split': 'test', 'offset': 0, 'length': 1}, timeout=30)
        first.raise_for_status()
        total = first.json()['num_rows_total']
        if total < count:
            raise ValueError('Dataset smaller than requested pilot')
        for index in range(count):
            offset = index * total // count
            response = client.get('https://datasets-server.huggingface.co/rows', params={
                'dataset': DATASET, 'config': 'default', 'split': 'test',
                'offset': offset, 'length': 1}, timeout=30)
            response.raise_for_status()
            row = response.json()['rows'][0]['row']
            data = bytearray()
            with client.get(row['image']['src'], stream=True, timeout=60) as media:
                media.raise_for_status()
                for chunk in media.iter_content(65536):
                    data.extend(chunk)
                    if len(data) > 8_000_000:
                        raise ValueError('Pilot image exceeds 8 MB limit')
            filename = f'{offset:06d}.image'
            (destination/filename).write_bytes(data)
            manifest.append({'id': f'safeimg-{offset}', 'path': filename,
                'label': 'ai_generated', 'source': SOURCE, 'license': 'CC-BY-NC-SA-4.0',
                'sha256': hashlib.sha256(data).hexdigest(),
                'group_id': f'safeimg-{offset}', 'split': 'test',
                'source_revision': revision, 'source_image_id': row['image_id'],
                'category': row['category'], 'generator': 'GPT Image 2',
                'encoding': 'Hugging Face dataset viewer representation',
                'independence': 'parent independence not verified; pilot only'})
        response = client.get(f'https://huggingface.co/api/datasets/{DATASET}', timeout=30)
        response.raise_for_status()
        if response.json()['sha'] != revision:
            raise ValueError('Dataset changed during download; do not use this pilot')
    (destination/'manifest.jsonl').write_text(
        ''.join(json.dumps(row)+'\n' for row in manifest), encoding='utf-8')
    print(json.dumps({'samples': len(manifest), 'revision': revision, 'pilot_only': True}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--count', type=int, default=12)
    args = parser.parse_args()
    fetch(args.destination, args.count)

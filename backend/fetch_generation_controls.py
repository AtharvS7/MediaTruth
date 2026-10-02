"""Bounded public research benchmark with raw bytes, controls and provenance."""
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path

from PIL import Image
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DATASET = 'OwensLab/CommunityForensics-Eval'
SOURCE = f'https://huggingface.co/datasets/{DATASET}'


def read_json(client, url, **kwargs):
    with client.get(url, stream=True, timeout=90, **kwargs) as response:
        response.raise_for_status()
        data = bytearray()
        for chunk in response.iter_content(65536):
            data.extend(chunk)
            if len(data) > 48_000_000:
                raise ValueError('Dataset response exceeds bounded research download')
    return json.loads(data)


def decode_row(item):
    if 'image_data' in item.get('truncated_cells', []):
        raise ValueError('Dataset viewer truncated image bytes; do not benchmark this row')
    row = item['row']
    if row['label'] not in (0,1) or row['split'] != 'test':
        raise ValueError('Unexpected label or split')
    encoded = row['image_data']
    data = base64.b64decode(encoded, validate=True) if isinstance(encoded,str) else bytes(encoded)
    if len(data) > 32_000_000:
        raise ValueError('Sample exceeds 32 MB research limit')
    with Image.open(io.BytesIO(data)) as image:
        image.verify()
    return row, data


def fetch(destination: Path, count: int):
    if not 2 <= count <= 256:
        raise ValueError('Count must be between 2 and 256')
    destination.mkdir(parents=True, exist_ok=False)
    with requests.Session() as client:
        client.mount('https://', HTTPAdapter(max_retries=Retry(
            total=3, backoff_factor=.5, status_forcelist=[429,500,502,503,504],
            allowed_methods=['GET'])))
        revision = read_json(client, f'https://huggingface.co/api/datasets/{DATASET}')['sha']
        card = client.get(f'{SOURCE}/raw/{revision}/README.md', timeout=30)
        card.raise_for_status()
        if 'cc-by-nc-sa-4.0' not in card.text:
            raise ValueError('Review changed dataset terms')
        (destination/'SOURCE_README.md').write_text(card.text,encoding='utf-8')
        params = {'dataset':DATASET,'config':'default','split':'CompEval','offset':0,'length':1}
        total = read_json(client,'https://datasets-server.huggingface.co/rows',params=params)['num_rows_total']
        rows, seen, failures = [], set(), []
        downloaded, consecutive_failures = 0, 0
        for index in range(count):
            # Predeclared systematic sampling across the entire source, never scores.
            offset = index*total//count
            params['offset'] = offset
            try:
                item = read_json(client,'https://datasets-server.huggingface.co/rows',params=params)['rows'][0]
                row, data = decode_row(item)
            except (requests.RequestException, ValueError) as error:
                failures.append({'offset':offset,'reason':type(error).__name__})
                print(json.dumps({'unavailable_offset':offset,'reason':type(error).__name__}),flush=True)
                consecutive_failures += 1
                if consecutive_failures >= 3:
                    break  # Stop burdening an unavailable provider; preserve partial evidence.
                continue
            consecutive_failures = 0
            downloaded += len(data)
            if downloaded > 1_000_000_000:
                raise ValueError('Experiment exceeds 1 GB media budget')
            digest = hashlib.sha256(data).hexdigest()
            if digest in seen:
                continue  # Repeated real controls across generators count only once.
            seen.add(digest)
            filename = f'{offset:06d}.image'
            (destination/filename).write_bytes(data)
            label = 'original' if row['label']==0 else 'ai_generated'
            source_group = f"{row['real_source']}:{row['image_name']}" if label=='original' else f"{row['model_name']}:{row['image_name']}"
            rows.append({'id':f'commfor-{offset}','path':filename,'sha256':digest,
                'label':label,'source':SOURCE,'license':'CC-BY-NC-SA-4.0',
                'source_revision':revision,'source_image_id':row['image_name'],
                'group_id':source_group,'split':'test','generator':row['model_name'],
                'real_source':row['real_source'],'architecture':row['architecture'],
                'encoding':'base64 decoded source image_data; no re-encoding',
                'independence':'Public benchmark; parent identity from source names, near duplicates not verified'})
            print(json.dumps({'downloaded':index+1,'unique_samples':len(rows),'bytes':downloaded}),flush=True)
        if read_json(client,f'https://huggingface.co/api/datasets/{DATASET}')['sha'] != revision:
            raise ValueError('Source changed during acquisition')
    (destination/'manifest.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf-8')
    (destination/'acquisition.json').write_text(json.dumps({'requested':count,
        'available_unique':len(rows),'failures':failures,'source_revision':revision,
        'selection':'systematic offsets across source; failures omitted without replacement',
        'caveat':'Acquisition failures can bias the sample; report alongside scores'},indent=2),encoding='utf-8')
    print(json.dumps({'acquisition_finished':True,'complete':not failures and len(rows)==count,
        'samples':len(rows),'originals':sum(r['label']=='original' for r in rows)}))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('destination',type=Path)
    p.add_argument('--count',type=int,default=96)
    a=p.parse_args()
    fetch(a.destination,a.count)

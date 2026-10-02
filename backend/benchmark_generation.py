"""Compare fixed upstream binary rules on verified manifests; never promotes models."""
import argparse
from dataclasses import asdict
import hashlib
import importlib.metadata
import json
import io
from pathlib import Path
import time

from PIL import Image
from evaluation import read_manifest, release_gates
from inference_pipeline.generation_candidates import CANDIDATES, GenerationCandidate


def run(name, weights, manifest, output, jpeg_quality=None):
    if output.exists():
        raise ValueError('Preserve existing benchmark evidence; choose a new output')
    rows = read_manifest(manifest)
    if any(r['label'] not in {'original','ai_generated'} for r in rows):
        raise ValueError('This experiment supports binary generation labels only')
    import torch
    torch.set_num_threads(2)
    start = time.monotonic()
    detector = GenerationCandidate(name, weights)
    load_seconds = time.monotonic()-start
    predictions = []
    for row in rows:
        if row['split'] != 'test':
            continue
        start = time.monotonic()
        try:
            with Image.open(manifest.parent/row['path']) as image:
                if jpeg_quality is None:
                    result = detector.predict(image)
                else:
                    buffer=io.BytesIO()
                    image.convert('RGB').save(buffer,format='JPEG',quality=jpeg_quality)
                    buffer.seek(0)
                    with Image.open(buffer) as recompressed:
                        result=detector.predict(recompressed)
            result['available'] = True
        except Exception as error:
            result = {'available': False, 'score': None, 'label': 'inconclusive',
                      'failure_type': type(error).__name__}
        predictions.append({'id':row['id'], 'sha256':row['sha256'], 'truth':row['label'],
            'generator':row.get('generator'), 'source':row['source'],
            'seconds':time.monotonic()-start, **result})
    report = {'scope':'Exploratory; public benchmark, not independent release approval',
        'release_eligible':False,
        'manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest(),
        'software_versions':{package:importlib.metadata.version(package)
                             for package in ('torch','timm','Pillow','safetensors')},
        'variant':'source_bytes' if jpeg_quality is None else f'jpeg_quality_{jpeg_quality}',
        'candidate':name, 'model':asdict(CANDIDATES[name]), 'load_seconds':load_seconds,
        'threshold_selection':'Fixed upstream rules; no tuning on this dataset',
        'metrics':release_gates(rows, [{'id':p['id'],'label':p['label']} for p in predictions]),
        'failures':sum(not p['available'] for p in predictions), 'predictions':predictions}
    acquisition = manifest.parent/'acquisition.json'
    if acquisition.exists():
        report['acquisition']=json.loads(acquisition.read_text(encoding='utf-8'))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({'candidate':name,'failures':report['failures'],'metrics':report['metrics']}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('candidate',choices=CANDIDATES)
    p.add_argument('weights',type=Path)
    p.add_argument('manifest',type=Path)
    p.add_argument('output',type=Path)
    p.add_argument('--jpeg-quality',type=int,choices=range(1,101))
    a = p.parse_args()
    run(a.candidate,a.weights,a.manifest,a.output,a.jpeg_quality)

"""Offline, noncommercial FSD research evaluation; never enables product verdicts.

Requires the pinned upstream checkout with evaluation/experiments/fsd_streaming.patch
applied and separately downloaded, verified weights. No implicit downloads.
"""
import argparse
import hashlib
import importlib.metadata
import io
import json
import math
from pathlib import Path
import sys
import time

from PIL import Image

from evaluation import read_manifest, release_gates

ARTIFACTS = Path(__file__).resolve().parents[1] / 'evaluation/experiments/fsd_artifacts.json'


def verify_artifacts(source, weights, artifacts):
    """Verify reviewed source and all tensor-only inputs before importing upstream."""
    for name, expected in artifacts['patched_source_sha256'].items():
        content = (source / 'fsd' / name).read_text(encoding='utf-8')
        if hashlib.sha256(content.encode()).hexdigest() != expected:
            raise ValueError(f'FSD reviewed source mismatch: {name}')
    for name, spec in artifacts['weights'].items():
        path = weights / name
        if path.stat().st_size != spec['bytes']:
            raise ValueError(f'FSD weight size mismatch: {name}')
        with path.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != spec['sha256']:
                raise ValueError(f'FSD weight digest mismatch: {name}')


def run(source, weights, manifest, output, jpeg_quality=None):
    if output.exists():
        raise ValueError('Preserve existing benchmark evidence; choose a new output')
    artifacts = json.loads(ARTIFACTS.read_text())
    verify_artifacts(source, weights, artifacts)
    rows = read_manifest(manifest)
    if any(row['label'] not in {'original', 'ai_generated'} for row in rows):
        raise ValueError('FSD experiment supports binary generation labels only')
    import torch
    torch.set_num_threads(2)
    sys.path.insert(0, str(source.resolve()))
    import fsd
    if Path(fsd.__file__).resolve().parent != (source / 'fsd').resolve():
        raise ValueError('An unexpected FSD package was already imported')
    detector = fsd.FSDDetector.load(weights_dir=weights, device='cpu', attribution=False)
    predictions = []
    for row in rows:
        if row['split'] != 'test':
            continue
        start = time.monotonic()
        try:
            with Image.open(manifest.parent / row['path']) as image:
                w, h = image.size
                if min(w, h) < 32 or w*h > 4_000_000 or max(w, h)/min(w, h) > 4:
                    raise ValueError('Image outside bounded FSD research dimensions')
                if jpeg_quality is None:
                    result = detector.score(image)
                else:
                    buffer = io.BytesIO()
                    image.convert('RGB').save(buffer, format='JPEG', quality=jpeg_quality)
                    buffer.seek(0)
                    with Image.open(buffer) as recompressed:
                        result = detector.score(recompressed)
            if not math.isfinite(result.z_score):
                raise ValueError('Non-finite FSD output')
            prediction = {'available': True, 'z_score': result.z_score,
                          'threshold': result.threshold,
                          'label': 'ai_generated' if result.is_fake else 'original'}
        except Exception as error:
            prediction = {'available': False, 'label': 'inconclusive', 'z_score': None,
                          'failure_type': type(error).__name__}
        prediction.update(id=row['id'], sha256=row['sha256'], truth=row['label'],
                          seconds=time.monotonic()-start)
        predictions.append(prediction)
        print(json.dumps(prediction, allow_nan=False), flush=True)
    report = {'candidate': 'FSD v1.2.0, streaming patches', 'release_eligible': False,
              'scope': 'Exploratory, public pilot; not independent validation',
              'score_semantics': 'GMM standardized log likelihood, not an AI probability',
              'threshold_selection': 'Unchanged upstream -2.0; no test-set tuning',
              'artifacts': artifacts,
              'software_versions': {p: importlib.metadata.version(p)
                                    for p in ('numpy', 'scipy', 'torch', 'Pillow')},
              'manifest_sha256': hashlib.sha256(manifest.read_bytes()).hexdigest(),
              'variant': 'source_bytes' if jpeg_quality is None else f'jpeg_quality_{jpeg_quality}',
              'metrics': release_gates(rows, predictions), 'predictions': predictions}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write('\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('weights', type=Path)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--jpeg-quality', type=int, choices=range(1, 101))
    args = parser.parse_args()
    run(args.source, args.weights, args.manifest, args.output, args.jpeg_quality)

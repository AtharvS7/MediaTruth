"""Bounded, nonprofit TruFor localization pilot on official CocoGlide pairs."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import random
import time
import zipfile

import numpy as np
from PIL import Image

from trufor_research import TruForResearch, localization_metrics


def run(source, weights, artifacts, archive, output, count=12):
    if output.exists() or not 1 <= count <= 32:
        raise ValueError('Require new output directory and 1..32 pairs')
    output.mkdir(parents=True)
    spec = json.loads(artifacts.read_text())
    with zipfile.ZipFile(archive) as bundle:
        licenses = json.loads(bundle.read('licenses.json'))
        license_ids = {r['id']: r['license'] for r in licenses['images']}
        rows = list(csv.DictReader(io.StringIO(bundle.read('table.csv').decode())))
        # Explicitly avoid NoDerivs images; preserve source license attribution.
        rows = [r for r in rows if license_ids.get(int(Path(r['real']).stem.rsplit('_', 1)[1])) in (4, 5)]
        random.Random('mediatruth-cocoglide-v1').shuffle(rows)
        selected = rows[:count]
        if len(selected) != count:
            raise ValueError('Insufficient eligible pairs')
        manifest = []
        for index, row in enumerate(selected):
            pair = {'id': Path(row['real']).stem.rsplit('_', 1)[1], 'files': {}}
            pair['license_id'] = license_ids[int(pair['id'])]
            for kind in ('real', 'fake', 'mask'):
                info = bundle.getinfo(row[kind])
                if info.file_size > 8_000_000:
                    raise ValueError('Oversized sample')
                raw = bundle.read(info)
                path = output / f'{index}-{kind}.png'
                path.write_bytes(raw)
                pair['files'][kind] = {'path': path.name, 'sha256': hashlib.sha256(raw).hexdigest(),
                                       'archive_path': row[kind]}
            manifest.append(pair)
    provenance = {'source': 'https://www.grip.unina.it/download/prog/TruFor/CocoGlide.zip',
                  'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
                  'selection': 'seeded shuffle of license IDs 4/5, before inference',
                  'licenses': [r for r in licenses['licenses'] if r['id'] in (4, 5)],
                  'samples': manifest}
    (output / 'manifest.json').write_text(json.dumps(provenance, indent=2), encoding='utf-8')
    model = TruForResearch(source, weights, spec, threads=2)
    predictions = []
    for pair in manifest:
        with Image.open(output / pair['files']['mask']['path']) as image:
            raw_mask = np.asarray(image.convert('L'))
            if not np.isin(raw_mask, [0, 255]).all():
                raise ValueError('Mask is not binary; do not guess mask semantics')
            mask = raw_mask > 0
        for kind in ('real', 'fake'):
            start = time.monotonic()
            result = model.predict(output / pair['files'][kind]['path'])
            truth = mask if kind == 'fake' else np.zeros_like(mask)
            metrics = localization_metrics(truth, result['score_map'], .5)
            prediction = {'id': pair['id'], 'kind': kind, 'seconds': time.monotonic()-start,
                          'attribution': 'inconclusive', **metrics}
            predictions.append(prediction)
            with (output / 'checkpoint.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(prediction)+'\n')
            print(json.dumps(prediction), flush=True)
    edited = [r for r in predictions if r['kind'] == 'fake']
    originals = [r for r in predictions if r['kind'] == 'real']
    report = {'model': spec, 'data': provenance, 'threshold': .5, 'samples': predictions,
              'mean_edited_iou': float(np.mean([r['iou'] for r in edited])),
              'mean_edited_dice': float(np.mean([r['dice'] for r in edited])),
              'mean_original_false_positive_area': float(np.mean([r['false_positive_area_original'] for r in originals])),
              'release_eligible': False,
              'limitations': ['Small source-published benchmark; not independent release certification.',
                              'Anomaly localization is not AI-versus-conventional attribution.',
                              'Research/nonprofit model license; no commercial serving approval.']}
    (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ('source', 'weights', 'artifacts', 'archive', 'output'):
        parser.add_argument(field, type=Path)
    parser.add_argument('--count', type=int, default=12)
    run(**vars(parser.parse_args()))

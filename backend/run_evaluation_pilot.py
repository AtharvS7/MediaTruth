"""Run the actual isolated public image pipeline against a manifest, serially.

Outputs remain local. No remote inference, model downloads or database writes.
This measures the deployed abstention policy, not raw detector accuracy.
"""
import argparse
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from evaluation import read_manifest, release_gates
from services.jobs import run_isolated


async def run(manifest: Path, destination: Path):
    rows = read_manifest(manifest)
    destination.mkdir(parents=True, exist_ok=False)
    predictions = []
    for row in rows:
        if row['split'] != 'test':
            continue
        job = SimpleNamespace(id=row['id'], kind='image', stage='queued',
                              path=str((manifest.parent/row['path']).resolve()))
        result = await run_isolated(job, timeout=300)
        if result.get('final_verdict') != 'Inconclusive':
            raise ValueError('Unexpected public verdict; review label mapping before evaluation')
        predictions.append({'id': row['id'], 'label': 'inconclusive'})
        # Store ordinal filenames rather than accepting paths from manifest IDs.
        (destination/f'report-{len(predictions):04d}.json').write_text(
            json.dumps(result, allow_nan=False), encoding='utf-8')
        print(f'Processed {len(predictions)}', flush=True)
    (destination/'predictions.jsonl').write_text(
        ''.join(json.dumps(row)+'\n' for row in predictions), encoding='utf-8')
    metrics = release_gates(rows, predictions)
    metrics['scope'] = 'Public pipeline pilot only; not raw detector accuracy or a release approval'
    metrics['parent_independence_verified'] = False
    (destination/'metrics.json').write_text(json.dumps(metrics, indent=2), encoding='utf-8')
    print(json.dumps({'samples': metrics['samples'], 'coverage': metrics['coverage']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    asyncio.run(run(args.manifest, args.destination))

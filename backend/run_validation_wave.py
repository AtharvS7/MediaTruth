"""Freeze calibration policy, then run a resumable CPU-only validation wave."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from benchmark_fsd import run
from calibrate_generation import score_holdout
from calibrate_two_tail import fit, predict
from evaluation import binary_production_gates, read_manifest


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(manifest, scores, output):
    report = json.loads(scores.read_text())
    if report.get('manifest_sha256') != digest(manifest) or report.get('evaluation_split') != 'validation':
        raise ValueError('Calibration score identity mismatch')
    state = fit(read_manifest(manifest), report['predictions'])
    state['inputs'] = {'manifest_sha256': digest(manifest), 'scores_sha256': digest(scores)}
    with output.open('x', encoding='utf-8') as stream:
        json.dump(state, stream, indent=2, allow_nan=False)


def evaluate_wave(source, weights, manifest, frozen, one_tail, output, allow_missing_sd14=False):
    rows = read_manifest(manifest)
    contract = json.loads((manifest.parent / 'contract.json').read_text())
    expected_count = 375 if allow_missing_sd14 else 400
    if contract['per_generator'] != 25 or len(rows) != expected_count or any(r['split'] != 'test' for r in rows):
        raise ValueError('Require exact declared wave support')
    counts = Counter(r['generator'] for r in rows)
    from fetch_calibration_pilot import GENERATORS
    expected_generators = [g for g in GENERATORS if not (allow_missing_sd14 and g == 'SD14')]
    if counts != Counter({g: 200 if g == 'Real' else 25 for g in expected_generators}):
        raise ValueError('Generator quotas do not match predeclared contract')
    two_policy = json.loads(frozen.read_text())
    one_policy = json.loads(one_tail.read_text())
    output.mkdir(parents=True, exist_ok=True)
    identity = {'manifest_sha256': digest(manifest), 'two_tail_sha256': digest(frozen),
                'one_tail_sha256': digest(one_tail), 'contract_sha256': digest(manifest.parent / 'contract.json'),
                'allow_missing_sd14': allow_missing_sd14,
                'original_400_sample_plan_complete': not allow_missing_sd14}
    lock = output / 'frozen-inputs.json'
    if lock.exists():
        if json.loads(lock.read_text()) != identity:
            raise ValueError('Cannot resume with changed policy or dataset')
    else:
        lock.write_text(json.dumps(identity, indent=2), encoding='utf-8')
    raw = output / 'raw.json'
    if not raw.exists():
        run(source, weights, manifest, raw, threads=2,
            resume=raw.with_suffix('.json.checkpoint.jsonl').exists())
    raw_report = json.loads(raw.read_text())
    if raw_report['manifest_sha256'] != digest(manifest):
        raise ValueError('Raw predictions belong to another manifest')
    predictions = raw_report['predictions']
    _, one = score_holdout(one_policy, rows, predictions)
    _, two = predict(two_policy, rows, predictions)
    baseline_policy = {**one_policy, 'threshold': -2.0}
    _, baseline = score_holdout(baseline_policy, rows, predictions)
    result = {'inputs': identity, 'release_eligible': False, 'raw_report_sha256': digest(raw),
              'upstream': binary_production_gates(rows, baseline),
              'frozen_one_tail': binary_production_gates(rows, one),
              'frozen_two_tail': binary_production_gates(rows, two),
              'note': 'Fresh project samples from a previously used public source; model-training overlap unknown.'}
    with (output / 'comparison.json').open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
    print(json.dumps({key: result[key]['accuracy'] for key in ('upstream', 'frozen_one_tail', 'frozen_two_tail')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prep = commands.add_parser('prepare')
    for field in ('manifest', 'scores', 'output'):
        prep.add_argument(field, type=Path)
    evaluate = commands.add_parser('evaluate')
    for field in ('source', 'weights', 'manifest', 'frozen', 'one_tail', 'output'):
        evaluate.add_argument(field, type=Path)
    evaluate.add_argument('--allow-missing-sd14', action='store_true',
                          help='Explicit exploratory 375-sample scope; original 400-sample plan failed')
    args = vars(parser.parse_args())
    command = args.pop('command')
    (prepare if command == 'prepare' else evaluate_wave)(**args)

"""Fit a binary score threshold using validation data only; never approve deployment."""
import argparse
import hashlib
import json
import math
from pathlib import Path

from evaluation import evaluate, read_manifest, wilson


def fit_threshold(rows, predictions, score_key='z_score', higher_is_ai=False, max_fpr=.01):
    if not rows or any(row['split'] != 'validation' for row in rows):
        raise ValueError('Threshold fitting requires validation-only data; test data is forbidden')
    if not 0 <= max_fpr < 1:
        raise ValueError('Invalid false-positive budget')
    for field in ('id', 'sha256', 'group_id'):
        if len({r[field] for r in rows}) != len(rows):
            raise ValueError('Calibration requires unique sample, content and parent identifiers')
    if {r['label'] for r in rows} != {'original', 'ai_generated'}:
        raise ValueError('Calibration requires both binary classes')
    indexed = {p['id']:p for p in predictions}
    if len(indexed) != len(predictions) or set(indexed) != {r['id'] for r in rows}:
        raise ValueError('Calibration predictions must match the entire partition')
    scores = []
    for row in rows:
        prediction = indexed[row['id']]
        value = prediction.get(score_key)
        if prediction.get('sha256') != row['sha256']:
            raise ValueError('Prediction content does not match manifest')
        if value is None or not math.isfinite(value) or prediction.get('available') is False:
            raise ValueError('Incomplete calibration scores; never silently drop failures')
        scores.append(value if higher_is_ai else -value)
    originals = sum(r['label']=='original' for r in rows)
    generated = len(rows)-originals
    # Positive iff normalized_score > threshold. Include both endpoint decisions.
    candidates = [math.nextafter(min(scores), -math.inf), *sorted(set(scores))]
    eligible = []
    for threshold in candidates:
        fp = sum(s>threshold and r['label']=='original' for s,r in zip(scores,rows))
        tp = sum(s>threshold and r['label']=='ai_generated' for s,r in zip(scores,rows))
        if fp/originals <= max_fpr:
            eligible.append((tp, -fp, threshold))
    tp, negative_fp, threshold = max(eligible)
    return {'schema_version':1, 'release_eligible':False, 'score_key':score_key,
            'higher_is_ai':higher_is_ai, 'threshold':threshold if higher_is_ai else -threshold,
            'comparison':'>' if higher_is_ai else '<', 'max_calibration_fpr':max_fpr,
            'calibration_support':len(rows), 'original_support':originals,
            'generated_support':generated, 'calibration_recall':tp/generated,
            'calibration_fpr':-negative_fp/originals,
            'calibration_fpr_95':wilson(-negative_fp, originals),
            'calibration_groups':[r['group_id'] for r in rows],
            'calibration_hashes':[r['sha256'] for r in rows],
            'note':'Fitted calibration performance is not a held-out accuracy estimate'}


def score_holdout(policy, rows, predictions):
    if not rows or any(r['split'] != 'test' for r in rows):
        raise ValueError('Evaluation requires test-only data')
    if any(r['group_id'] in policy['calibration_groups'] or r['sha256'] in policy['calibration_hashes'] for r in rows):
        raise ValueError('Calibration/holdout leakage detected')
    indexed = {p['id']:p for p in predictions}
    if len(indexed)!=len(predictions) or set(indexed)!={r['id'] for r in rows}:
        raise ValueError('Holdout predictions must match the entire partition')
    output = []
    for row in rows:
        p = indexed[row['id']]
        if p.get('sha256') != row['sha256']:
            raise ValueError('Prediction content does not match manifest')
        score = p.get(policy['score_key'])
        if p.get('available') is False or score is None or not math.isfinite(score):
            label = 'inconclusive'
        else:
            positive = score > policy['threshold'] if policy['higher_is_ai'] else score < policy['threshold']
            label = 'ai_generated' if positive else 'original'
        output.append({'id':row['id'], 'label':label})
    return evaluate(rows, output), output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('report', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--score-key', default='z_score')
    parser.add_argument('--higher-is-ai', action='store_true')
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Refusing to overwrite a fitted policy')
    report = json.loads(args.report.read_text())
    if report.get('manifest_sha256') != hashlib.sha256(args.manifest.read_bytes()).hexdigest():
        raise ValueError('Prediction report does not belong to this calibration manifest')
    if report.get('evaluation_split') != 'validation':
        raise ValueError('Prediction report must explicitly identify the validation partition')
    policy = fit_threshold(read_manifest(args.manifest), report['predictions'], args.score_key, args.higher_is_ai)
    policy['manifest_sha256'] = hashlib.sha256(args.manifest.read_bytes()).hexdigest()
    policy['prediction_report_sha256'] = hashlib.sha256(args.report.read_bytes()).hexdigest()
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(policy, stream, indent=2, allow_nan=False)

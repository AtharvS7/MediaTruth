"""Research-only two-tail density test, fitted on calibration originals only.

Some synthetic images have unusually high rather than low FSD likelihood.
This hypothesis is not calibrated probability or evidence of universal accuracy.
"""
import math

from calibrate_generation import fit_threshold, score_holdout
from evaluation import evaluate


def fit(rows, predictions):
    # Reuse strict partition/content/finite/completeness validation.
    fit_threshold(rows, predictions)
    indexed = {p['id']: p for p in predictions}
    real = [indexed[r['id']]['z_score'] for r in rows if r['label'] == 'original']
    return {'schema_version': 1, 'method': 'calibration_original_min_max_two_tail',
            'lower': min(real), 'upper': max(real),
            'calibration_groups': [r['group_id'] for r in rows],
            'calibration_hashes': [r['sha256'] for r in rows],
            'calibration_original_support': len(real),
            'release_eligible': False,
            'note': 'Zero empirical calibration false positives; population FPR is unknown.'}


def predict(policy, rows, predictions):
    lower, upper = policy['lower'], policy['upper']
    if not all(math.isfinite(v) for v in (lower, upper)) or lower > upper:
        raise ValueError('Invalid frozen two-tail bounds')
    # Enforce test-only, no calibration overlap, matching content, complete IDs.
    _, output = score_holdout({**policy, 'threshold': lower, 'higher_is_ai': False,
                              'score_key': 'z_score'}, rows, predictions)
    indexed = {p['id']: p for p in predictions}
    for guess in output:
        if guess['label'] != 'inconclusive':
            score = indexed[guess['id']]['z_score']
            guess['label'] = 'ai_generated' if score < lower or score > upper else 'original'
    return evaluate(rows, output), output

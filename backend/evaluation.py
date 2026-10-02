"""Evaluate labeled, licensed media without counting abstentions as correct.

Usage: python evaluation.py manifest.jsonl predictions.jsonl
Manifest paths are relative to the manifest. Predictions have id and label.
This reports categorical metrics, not unvalidated probability calibration.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

LABELS = {"original", "ai_generated", "ai_edited", "traditional_edit", "mixed"}


def wilson(successes: int, total: int) -> list[float] | None:
    """95% Wilson interval. Undefined denominators never pass a release gate."""
    if not total:
        return None
    z = 1.959963984540054
    p = successes / total
    denominator = 1 + z*z/total
    center = (p + z*z/(2*total)) / denominator
    radius = z * math.sqrt(p*(1-p)/total + z*z/(4*total*total)) / denominator
    return [max(0.0, center-radius), min(1.0, center+radius)]


def release_gates(rows, predictions, minimum_support=200):
    """Descriptive acceptance checks; never auto-approve a model for deployment.

    For binomial intervals select one independent observation per parent group.
    Robustness variants must be evaluated separately, not treated as new originals.
    """
    metrics = evaluate(rows, predictions)
    samples = [row for row in rows if row['split'] == 'test']
    groups = [row.get('group_id') for row in samples]
    independent = (all(groups) and len(groups) == len(set(groups))
                   and all(row.get('independence_verified') is True for row in samples))
    confusion = {(item['truth'], item['prediction']): item['count'] for item in metrics['confusion']}
    original_count = metrics['per_class']['original']['support']
    false_flags = sum(n for (truth, guess), n in confusion.items()
                      if truth == 'original' and guess not in {'original', 'inconclusive'})
    fpr_ci = wilson(false_flags, original_count)
    gates = {}
    for label, value in metrics['per_class'].items():
        tp = confusion.get((label, label), 0)
        predicted = sum(n for (_, guess), n in confusion.items() if guess == label)
        precision_ci = wilson(tp, predicted)
        checks = {
            'independent_groups': independent,
            'category_support': value['support'] >= minimum_support,
            'original_support': original_count >= minimum_support,
            'precision': value['precision'] is not None and value['precision'] >= .90,
            'precision_lower_95': precision_ci is not None and precision_ci[0] >= .85,
            'original_fpr_upper_95': fpr_ci is not None and fpr_ci[1] <= .05,
            'recall': value['recall'] is not None and value['recall'] >= .50,
        }
        gates[label] = {'passed': all(checks.values()), 'checks': checks,
                        'precision_95': precision_ci,
                        'recall_95': wilson(tp, value['support'])}
    return {**metrics, 'original_fpr_95': fpr_ci, 'release_gates': gates,
            'approval_note': 'Metrics alone do not approve licensing, holdouts or deployment.'}


def read_manifest(path: Path) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    seen_ids, seen_hashes, groups = set(), set(), {}
    for row in rows:
        for field in ("id", "path", "label", "source", "license", "sha256", "group_id", "split"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                raise ValueError(f"Missing {field}")
        if row["label"] not in LABELS or row["split"] not in {"train", "validation", "test"}:
            raise ValueError("Unknown label or split")
        if row["id"] in seen_ids or row["sha256"] in seen_hashes:
            raise ValueError("Duplicate sample or content")
        if groups.setdefault(row["group_id"], row["split"]) != row["split"]:
            raise ValueError("Related samples cross dataset splits")
        media = (path.parent / row["path"]).resolve()
        if not media.is_relative_to(path.parent.resolve()):
            raise ValueError("Media path escapes dataset directory")
        with media.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != row["sha256"]:
                raise ValueError("Content hash mismatch")
        seen_ids.add(row["id"])
        seen_hashes.add(row["sha256"])
    return rows


def binary_production_gates(rows, predictions):
    """95% target for a named still-image distribution, never universal certification."""
    if any(r['label'] not in {'original','ai_generated'} for r in rows):
        raise ValueError('Binary production target cannot validate editing/video categories')
    result = release_gates(rows, predictions)
    classes = result['per_class']
    recalls = [classes[c]['recall'] for c in ('original','ai_generated')]
    balanced = sum(recalls)/2 if all(v is not None for v in recalls) else None
    correct = sum(c['count'] for c in result['confusion'] if c['truth']==c['prediction'])
    accuracy = correct/result['samples']
    interval = wilson(correct,result['samples'])
    checks = {
        'existing_release_checks':all(result['release_gates'][c]['passed'] for c in ('original','ai_generated')),
        'balanced_accuracy_95':balanced is not None and balanced >= .95,
        'each_class_precision_95':all(classes[c]['precision'] is not None and classes[c]['precision']>=.95
                                      for c in ('original','ai_generated')),
        'each_class_recall_95':all(v is not None and v>=.95 for v in recalls),
        'accuracy_lower_bound_95':interval[0]>=.95,
    }
    return {**result,'accuracy':accuracy,'accuracy_95':interval,'balanced_accuracy':balanced,
            'production_target_checks':checks,'statistical_target_passed':all(checks.values()),
            'deployment_approved':False,
            'scope_note':'Requires independent licensing, robustness and operational approval; no universal accuracy guarantee'}


def evaluate(rows: list[dict], predictions: list[dict]) -> dict:
    samples = {row["id"]: row for row in rows if row["split"] == "test"}
    guessed = {}
    for prediction in predictions:
        key, label = prediction["id"], prediction["label"]
        if key not in samples or key in guessed or label not in LABELS | {"inconclusive"}:
            raise ValueError("Invalid, duplicate or non-test prediction")
        guessed[key] = label
    if set(guessed) != set(samples) or not samples:
        raise ValueError("Provide exactly one prediction for every test sample")
    confusion = Counter((row["label"], guessed[key]) for key, row in samples.items())
    total = len(samples)
    abstentions = sum(label == "inconclusive" for label in guessed.values())
    classes = {}
    for label in sorted(LABELS):
        tp = confusion[label, label]
        actual = sum(count for (truth, _), count in confusion.items() if truth == label)
        predicted = sum(count for (_, guess), count in confusion.items() if guess == label)
        classes[label] = {"support": actual, "precision": tp / predicted if predicted else None,
                          "recall": tp / actual if actual else None}
    originals = classes["original"]["support"]
    false_flags = sum(count for (truth, guess), count in confusion.items()
                      if truth == "original" and guess not in {"original", "inconclusive"})
    return {"samples": total, "coverage": (total - abstentions) / total,
            "abstentions": abstentions, "per_class": classes,
            "false_positive_rate_originals": false_flags / originals if originals else None,
            "confusion": [{"truth": truth, "prediction": guess, "count": count}
                          for (truth, guess), count in sorted(confusion.items())]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("predictions", type=Path)
    args = parser.parse_args()
    predictions = [json.loads(line) for line in args.predictions.read_text(encoding="utf-8").splitlines()
                   if line.strip()]
    print(json.dumps(release_gates(read_manifest(args.manifest), predictions), indent=2))

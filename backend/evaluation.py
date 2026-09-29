"""Evaluate labeled, licensed media without counting abstentions as correct.

Usage: python evaluation.py manifest.jsonl predictions.jsonl
Manifest paths are relative to the manifest. Predictions have id and label.
This reports categorical metrics, not unvalidated probability calibration.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

LABELS = {"original", "ai_generated", "ai_edited", "traditional_edit", "mixed"}


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
    print(json.dumps(evaluate(read_manifest(args.manifest), predictions), indent=2))

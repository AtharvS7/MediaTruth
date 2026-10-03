"""Offline evaluation of declared edit histories and output-coordinate masks.

No model, source attribution heuristic, threshold fitting or serving approval.
Run: python edit_evaluation.py MANIFEST PREDICTIONS --threshold 0.5
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

from evaluation import evaluate, read_manifest

EDIT_LABELS = {"ai_edited", "traditional_edit", "mixed"}


def _artifact(root, item):
    if not isinstance(item, dict) or not all(
        isinstance(item.get(key), str) and item[key].strip() for key in ("path", "sha256")
    ):
        raise ValueError("Artifact requires path and sha256")
    path = (root / item["path"]).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Artifact path escapes dataset directory")
    with path.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != item["sha256"]:
            raise ValueError("Artifact content hash mismatch")
    return path


def _mask(path, shape):
    with Image.open(path) as image:
        if image.mode not in {"1", "L"}:
            raise ValueError("Mask must be a binary grayscale image")
        mask = np.asarray(image)
    if mask.shape != shape or not np.isin(mask, [0, 1, 255]).all():
        raise ValueError("Mask must be binary and match output image dimensions")
    return mask != 0


def read_edit_manifest(path):
    """Validate integrity and declared lineage; this cannot verify truthful labels."""
    path = Path(path)
    rows = read_manifest(path)
    lineage_groups = {}
    for row in rows:
        if row["label"] not in EDIT_LABELS | {"original"}:
            raise ValueError("Editing benchmark excludes fully generated images")
        original = row.get("original")
        original_path = _artifact(path.parent, original)
        for field in ("source", "license"):
            if not isinstance(original.get(field), str) or not original[field].strip():
                raise ValueError(f"Original requires {field}")
        with Image.open(original_path) as image:
            image.verify()
        with Image.open(path.parent / row["path"]) as image:
            shape = (image.height, image.width)
        mask = _mask(_artifact(path.parent, row.get("mask")), shape)
        if bool(mask.any()) != (row["label"] in EDIT_LABELS):
            raise ValueError("Edited samples require nonempty masks; originals require empty masks")
        history = row.get("edit_history")
        if not isinstance(history, list):
            raise ValueError("Missing ordered edit_history")
        previous = original["sha256"]
        kinds = set()
        hashes = [previous, row["sha256"]]
        for step in history:
            if not isinstance(step, dict) or any(
                not isinstance(step.get(key), str) or not step[key].strip()
                for key in ("kind", "tool", "version", "operation", "input_sha256", "output_sha256")
            ):
                raise ValueError("Each history step requires kind, tool, version, operation and hashes")
            if step["kind"] not in {"ai", "traditional", "delivery"}:
                raise ValueError("Unknown edit history kind")
            if step["input_sha256"] != previous:
                raise ValueError("Broken edit history chain")
            previous = step["output_sha256"]
            if len(previous) != 64 or any(c not in "0123456789abcdef" for c in previous):
                raise ValueError("Invalid edit history hash")
            hashes.append(previous)
            if step["kind"] != "delivery":
                kinds.add(step["kind"])
        expected = {"original": set(), "ai_edited": {"ai"},
                    "traditional_edit": {"traditional"}, "mixed": {"ai", "traditional"}}[row["label"]]
        if kinds != expected or previous != row["sha256"]:
            raise ValueError("Edit history does not support declared label or output hash")
        for digest in hashes:
            # Identical original/intermediate/output content must share one group,
            # even if submitters assign different group IDs to hide leakage.
            if lineage_groups.setdefault(digest, row["group_id"]) != row["group_id"]:
                raise ValueError("Shared lineage content assigned to different groups")
    return rows


def evaluate_edits(manifest_path, predictions_path, threshold):
    """Fixed externally selected threshold; never optimize on these test masks."""
    if isinstance(threshold, bool) or not math.isfinite(threshold) or not 0 < threshold < 1:
        raise ValueError("Threshold must be finite and strictly between zero and one")
    manifest_path, predictions_path = Path(manifest_path), Path(predictions_path)
    rows = read_edit_manifest(manifest_path)
    predictions = [json.loads(line) for line in predictions_path.read_text(encoding="utf-8").splitlines()
                   if line.strip()]
    categorical = evaluate(rows, predictions)  # Requires exactly one result per test image.
    by_id = {row["id"]: row for row in rows if row["split"] == "test"}
    results = []
    for prediction in predictions:
        row = by_id[prediction["id"]]
        with Image.open(manifest_path.parent / row["path"]) as image:
            shape = (image.height, image.width)
        truth = _mask(_artifact(manifest_path.parent, row["mask"]), shape)
        if "score_map" not in prediction:
            raise ValueError("Prediction requires score_map artifact or explicit null abstention")
        available = prediction["score_map"] is not None
        detected = np.zeros(shape, dtype=bool)
        if available:
            scores = np.load(_artifact(predictions_path.parent, prediction["score_map"]), allow_pickle=False)
            if (not isinstance(scores, np.ndarray) or scores.shape != shape
                    or scores.dtype.kind not in "fiu" or not np.isfinite(scores).all()
                    or np.any(scores < 0) or np.any(scores > 1)):
                raise ValueError("Score map must be finite, numeric, in [0,1] and match output dimensions")
            detected = scores >= threshold
        intersection = int(np.count_nonzero(truth & detected))
        union = int(np.count_nonzero(truth | detected))
        edited = row["label"] in EDIT_LABELS
        results.append({"id": row["id"], "label": row["label"], "group_id": row["group_id"],
                        "available": available,
                        "iou": intersection / union if edited else None,
                        "dice": 2 * intersection / (int(truth.sum()) + int(detected.sum())) if edited else None,
                        "original_false_positive_area": float(detected.mean()) if not edited and available else None})
    per_class = {}
    for label in sorted(EDIT_LABELS | {"original"}):
        subset = [r for r in results if r["label"] == label]
        areas = [r["original_false_positive_area"] for r in subset
                 if r["original_false_positive_area"] is not None]
        per_class[label] = {
            "support": len(subset), "available": sum(r["available"] for r in subset),
            "mean_iou": sum(r["iou"] for r in subset) / len(subset) if subset and label in EDIT_LABELS else None,
            "mean_dice": sum(r["dice"] for r in subset) / len(subset) if subset and label in EDIT_LABELS else None,
            "original_mean_false_positive_area": sum(areas) / len(areas) if areas else None,
            "original_any_false_positive_rate": sum(v > 0 for v in areas) / len(areas) if areas else None,
        }
    return {"schema_version": 1, "threshold": threshold,
            "inputs": {"manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                       "predictions_sha256": hashlib.sha256(predictions_path.read_bytes()).hexdigest()},
            "attribution": categorical,
            "localization": {"coverage": sum(r["available"] for r in results) / len(results),
                             "unique_groups": len({r["group_id"] for r in results}),
                             "per_class": per_class, "samples": results},
            "deployment_approved": False,
            "limitations": ["Declared histories and license strings are not independent verification.",
                            "Masks identify all substantive edits, not which pixels used AI.",
                            "Per-image descriptive metrics are not independent population confidence intervals.",
                            "No editing model or release gate is validated by this evaluator."]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("predictions", type=Path)
    parser.add_argument("--threshold", type=float, required=True)
    args = parser.parse_args()
    print(json.dumps(evaluate_edits(args.manifest, args.predictions, args.threshold), indent=2, allow_nan=False))

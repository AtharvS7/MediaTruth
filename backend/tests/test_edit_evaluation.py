import hashlib
import json

import numpy as np
from PIL import Image
import pytest

from edit_evaluation import evaluate_edits, read_edit_manifest


def artifact(path):
    return {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def write_rows(path, rows):
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")


@pytest.fixture
def benchmark(tmp_path):
    rows, predictions = [], []
    for i, label in enumerate(["original", "ai_edited", "traditional_edit", "mixed"]):
        original = tmp_path / f"original-{i}.png"
        Image.new("RGB", (4, 4), (i * 20, 0, 0)).save(original)
        output = original
        mask = np.zeros((4, 4), dtype=np.uint8)
        if i:
            output = tmp_path / f"output-{i}.png"
            Image.new("RGB", (4, 4), (i * 20, 255, 0)).save(output)
            mask[:2, :2] = 255
        mask_path = tmp_path / f"mask-{i}.png"
        Image.fromarray(mask).save(mask_path)
        kinds = {0: [], 1: ["ai"], 2: ["traditional"], 3: ["ai", "traditional"]}[i]
        previous, history = artifact(original)["sha256"], []
        for j, kind in enumerate(kinds):
            digest = artifact(output)["sha256"] if j == len(kinds) - 1 else "f" * 64
            history.append(dict(kind=kind, tool="fixture", version="1", operation="fixture",
                                input_sha256=previous, output_sha256=digest))
            previous = digest
        rows.append(dict(id=str(i), **artifact(output), label=label, source="fixture",
                         license="test-only", group_id=str(i), split="test",
                         original={**artifact(original), "source": "fixture", "license": "test-only"},
                         mask=artifact(mask_path), edit_history=history))
        score_path = tmp_path / f"score-{i}.npy"
        np.save(score_path, mask / 255.0)
        predictions.append(dict(id=str(i), label=label, score_map=artifact(score_path)))
    manifest, scores = tmp_path / "manifest.jsonl", tmp_path / "predictions.jsonl"
    write_rows(manifest, rows)
    write_rows(scores, predictions)
    return manifest, scores, rows, predictions


def test_perfect_fixture_has_separate_attribution_and_localization(benchmark):
    manifest, scores, _, _ = benchmark
    report = evaluate_edits(manifest, scores, .5)
    assert report["deployment_approved"] is False
    assert report["attribution"]["coverage"] == 1
    for label in ("ai_edited", "traditional_edit", "mixed"):
        assert report["localization"]["per_class"][label]["mean_iou"] == 1
    original = report["localization"]["per_class"]["original"]
    assert original["mean_iou"] is None
    assert original["original_mean_false_positive_area"] == 0


def test_abstentions_never_count_as_clean_or_successful_localization(benchmark):
    manifest, scores, _, predictions = benchmark
    for prediction in predictions:
        prediction.update(label="inconclusive", score_map=None)
    write_rows(scores, predictions)
    report = evaluate_edits(manifest, scores, .5)
    assert report["localization"]["coverage"] == 0
    assert report["localization"]["per_class"]["ai_edited"]["mean_iou"] == 0
    assert report["localization"]["per_class"]["original"]["original_any_false_positive_rate"] is None
    assert report["attribution"]["per_class"]["mixed"]["recall"] == 0


def test_wrong_region_not_rescued_by_map_inversion(benchmark):
    manifest, scores, _, predictions = benchmark
    score_path = scores.parent / predictions[1]["score_map"]["path"]
    np.save(score_path, 1 - np.load(score_path))
    predictions[1]["score_map"] = artifact(score_path)
    write_rows(scores, predictions)
    assert evaluate_edits(manifest, scores, .5)["localization"]["per_class"]["ai_edited"]["mean_dice"] == 0


@pytest.mark.parametrize("change,match", [
    (lambda r: r[1].update(label="mixed"), "support declared label"),
    (lambda r: r[1]["edit_history"][0].update(input_sha256="a" * 64), "Broken"),
    (lambda r: r[1]["original"].update(path="../outside.png"), "escapes"),
    (lambda r: r[1]["mask"].update(sha256="b" * 64), "hash mismatch"),
    (lambda r: r[1].pop("edit_history"), "edit_history"),
    (lambda r: r[1].update(mask=r[0]["mask"]), "nonempty"),
])
def test_rejects_unusable_ground_truth(benchmark, change, match):
    manifest, _, rows, _ = benchmark
    change(rows)
    write_rows(manifest, rows)
    with pytest.raises(ValueError, match=match):
        read_edit_manifest(manifest)


def test_content_lineage_catches_different_group_ids_across_splits(benchmark):
    manifest, _, rows, _ = benchmark
    rows[2]["original"] = rows[1]["original"]
    rows[2]["edit_history"][0]["input_sha256"] = rows[1]["original"]["sha256"]
    rows[2]["split"] = "validation"
    write_rows(manifest, rows)
    with pytest.raises(ValueError, match="Shared lineage"):
        read_edit_manifest(manifest)


@pytest.mark.parametrize("value", [np.full((4, 4), np.nan), np.full((4, 4), 2.),
                                   np.zeros((2, 2)), np.full((4, 4), "bad")])
def test_rejects_invalid_prediction_maps(benchmark, value):
    manifest, scores, _, predictions = benchmark
    score_path = scores.parent / predictions[1]["score_map"]["path"]
    np.save(score_path, value)
    predictions[1]["score_map"] = artifact(score_path)
    write_rows(scores, predictions)
    with pytest.raises(ValueError, match="Score map"):
        evaluate_edits(manifest, scores, .5)


@pytest.mark.parametrize("threshold", [0, 1, float("nan"), float("inf"), True])
def test_rejects_invalid_threshold(benchmark, threshold):
    with pytest.raises(ValueError, match="Threshold"):
        evaluate_edits(*benchmark[:2], threshold)


def test_pixel_counts_and_original_false_positive_area(benchmark):
    manifest, scores, _, predictions = benchmark
    for index in (0, 1):
        score_path = scores.parent / predictions[index]["score_map"]["path"]
        np.save(score_path, np.ones((4, 4)))
        predictions[index]["score_map"] = artifact(score_path)
    write_rows(scores, predictions)
    metrics = evaluate_edits(manifest, scores, .5)["localization"]["per_class"]
    assert metrics["ai_edited"]["mean_iou"] == .25
    assert metrics["ai_edited"]["mean_dice"] == .4
    assert metrics["original"]["original_mean_false_positive_area"] == 1


def test_missing_map_is_not_silently_abstained(benchmark):
    manifest, scores, _, predictions = benchmark
    predictions[0].pop("score_map")
    write_rows(scores, predictions)
    with pytest.raises(ValueError, match="explicit null"):
        evaluate_edits(manifest, scores, .5)

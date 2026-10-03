"""Offline bounded face-forgery pilot; reports abstentions, never enables serving.

Run: python video_candidate_evaluation.py --manifest FILE --weights FILE --output FILE
Manifest is JSON with samples: id,path,kind (aligned_face/video),label (real/fake),
source_id,split (pilot/calibration/validation),rights_note. Paths resolve relative
to the manifest. At most 200 samples, 12 video frames and one face per frame.
"""

import argparse
import hashlib
import json
from pathlib import Path
import time

import cv2
import numpy as np
from PIL import Image
import torch

from inference_pipeline.mesonet_research import Meso4Research, SOURCE_REVISION, WEIGHTS_SHA256
from utils.video_utils import extract_frames, get_video_metadata


def validate_manifest(data, root):
    samples = data.get("samples", [])
    if not 1 <= len(samples) <= 200:
        raise ValueError("Require 1..200 samples.")
    ids, hashes, sources = set(), {}, {}
    for row in samples:
        if row.get("kind") not in {"aligned_face", "video"} or row.get("label") not in {"real", "fake"}:
            raise ValueError("Unsupported kind or label.")
        if row.get("split") not in {"pilot", "calibration", "validation"}:
            raise ValueError("Explicit split required.")
        if any(not isinstance(row.get(key), str) or not row[key].strip()
               for key in ["id", "path", "source_id", "rights_note"]):
            raise ValueError("Sample identity, path, source and rights note required.")
        if row["id"] in ids:
            raise ValueError("Duplicate sample id.")
        ids.add(row["id"])
        path = (root / row["path"]).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError('Sample path escapes manifest directory.')
        if not path.is_file() or path.stat().st_size > 100 * 1024 * 1024:
            raise ValueError("Missing sample or sample exceeds 100MB.")
        with path.open("rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
        if row.get('sha256', digest) != digest:
            raise ValueError('Sample content does not match declared hash.')
        row['sha256'] = digest
        if digest in hashes:
            raise ValueError("Duplicate sample bytes are not independent evidence.")
        hashes[digest] = row["id"]
        source_split = sources.setdefault(row["source_id"], row["split"])
        if source_split != row["split"]:
            raise ValueError("Source overlap between partitions.")
    return samples


class YuNetFaces:
    """Pinned OpenCV Zoo face detector, MIT; face boxes are not forgery evidence."""
    def __init__(self, weights):
        path = Path(weights)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4":
            raise ValueError("Expected pinned official YuNet 2023mar ONNX weights.")
        self.detector = cv2.FaceDetectorYN.create(str(path), "", (320, 320), .9, .3, 5000)

    def detect_faces(self, frame):
        self.detector.setInputSize((frame.shape[1], frame.shape[0]))
        _, faces = self.detector.detect(frame)
        return [] if faces is None else [row[:4] for row in faces if min(row[2:4]) >= 48]


def score_video(model, path, detector):
    metadata = get_video_metadata(str(path))
    frames, timestamps = extract_frames(str(path), max_frames=12)
    scores, faces = [], []
    for frame, timestamp in zip(frames, timestamps):
        boxes = detector.detect_faces(frame)
        # Multiple faces require tracking/identity policy, which this pilot lacks.
        if len(boxes) != 1:
            faces.append({"timestamp": timestamp, "faces_detected": len(boxes), "scored": False})
            continue
        x, y, width, height = map(int, boxes[0])
        margin = round(max(width, height) * .2)
        crop = frame[max(0, y-margin):min(frame.shape[0], y+height+margin),
                     max(0, x-margin):min(frame.shape[1], x+width+margin)]
        score = model.score_face(Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)))
        scores.append(score)
        faces.append({"timestamp": timestamp, "faces_detected": 1, "scored": True,
                      "fake_score": score, "box_xywh": [x, y, width, height]})
    # Predeclared engineering coverage gate, not a validated decision threshold.
    adequate = len(scores) >= 3 and len(scores) >= .5 * len(frames)
    return {"fake_score": float(np.mean(scores)) if adequate else None,
            "abstention_reason": None if adequate else "insufficient_single_face_coverage",
            "frames_sampled": len(frames), "frames_scored": len(scores),
            "frame_count": metadata["frame_count"], "faces": faces}


def evaluate(manifest, weights, output, face_detector_weights=None):
    if Path(output).exists():
        raise ValueError('Preserve prior reports; choose a new output path.')
    torch.set_num_threads(2)
    cv2.setNumThreads(2)
    manifest = Path(manifest)
    samples = validate_manifest(json.loads(manifest.read_text(encoding="utf-8-sig")), manifest.parent)
    model = Meso4Research.from_weights(weights)
    detector = None
    if any(row["kind"] == "video" for row in samples):
        if not face_detector_weights:
            raise ValueError("Video evaluation requires --face-detector-weights (YuNet).")
        detector = YuNetFaces(face_detector_weights)
    rows = []
    for row in samples:
        path = (manifest.parent / row["path"]).resolve()
        start = time.perf_counter()
        if row["kind"] == "aligned_face":
            with Image.open(path) as image:
                if image.width * image.height > 8_294_400:
                    raise ValueError("Face image exceeds pixel budget.")
                result = {"fake_score": model.score_face(image), "abstention_reason": None}
        else:
            result = score_video(model, path, detector)
        score = result["fake_score"]
        result.update({key: row[key] for key in ["id", "kind", "label", "source_id", "split", "rights_note", "sha256"]})
        result.update({"prediction": None if score is None else "fake" if score >= .5 else "real",
                       "elapsed_seconds": time.perf_counter() - start})
        rows.append(result)
    summaries = []
    for split in sorted({row["split"] for row in rows}):
        for kind in sorted({row["kind"] for row in rows if row["split"] == split}):
            group = [row for row in rows if row["split"] == split and row["kind"] == kind]
            summaries.append({"split": split, "kind": kind, "total": len(group),
                              "correct": sum(r["prediction"] == r["label"] for r in group),
                              "abstentions": sum(r["prediction"] is None for r in group),
                              "accuracy_including_abstentions": sum(r["prediction"] == r["label"] for r in group) / len(group)})
    report = {"candidate": "Meso4_DF", "source_revision": SOURCE_REVISION, "weights_sha256": WEIGHTS_SHA256,
              'manifest_sha256': hashlib.sha256(manifest.read_bytes()).hexdigest(),
              "public_enabled": False, "release_gate_passed": False, "threshold": .5,
              "score_semantics": "uncalibrated_face_forgery_score", "summaries": summaries, "samples": rows,
              "limitations": ["Face-specific 2018 model; no general AI-video capability.",
                              "YuNet face crops differ from original aligned preprocessing; no tracking.",
                              "Source examples are smoke tests, not independent validation.",
                              "Rights notes record provenance; they do not certify commercial permission."]}
    Path(output).write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["manifest", "weights", "output"]:
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--face-detector-weights")
    args = parser.parse_args()
    report = evaluate(args.manifest, args.weights, args.output, args.face_detector_weights)
    print(json.dumps(report["summaries"], indent=2))

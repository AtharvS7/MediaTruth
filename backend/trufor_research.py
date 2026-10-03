"""Isolated TruFor CPU research adapter; deliberately absent from public serving.

Upstream code/weights permit informational and nonprofit use only. This adapter
does not grant additional rights or attribute anomalies to particular editors.
"""
import hashlib
import importlib
from pathlib import Path
import sys

import numpy as np
from PIL import Image


def verify_artifacts(source, checkpoint, spec):
    source, checkpoint = Path(source).resolve(), Path(checkpoint)
    declared = spec.get("source_sha256", {})
    if not declared:
        raise ValueError("Missing source integrity inventory")
    for relative, expected in declared.items():
        path = (source / relative).resolve()
        if not path.is_relative_to(source) or not path.is_file():
            raise ValueError("Invalid source path")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Source integrity mismatch: {relative}")
    actual_python = {p.relative_to(source).as_posix() for p in source.rglob("*.py")}
    if actual_python != {p for p in declared if p.endswith(".py")}:
        raise ValueError("Unreviewed Python source file")
    if checkpoint.stat().st_size != spec["weights"]["bytes"]:
        raise ValueError("Checkpoint size mismatch")
    with checkpoint.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != spec["weights"]["sha256"]:
            raise ValueError("Checkpoint digest mismatch")


def image_array(path, max_pixels=512 * 512):
    """Match upstream TestDataset: stored RGB raster divided by 256, not 255."""
    with Image.open(path) as image:
        if image.width * image.height > max_pixels or min(image.size) < 32:
            raise ValueError("Image dimensions exceed research trial limits")
        return np.asarray(image.convert("RGB"), dtype=np.float32).transpose(2, 0, 1) / 256.0


class _Config(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as error:
            raise AttributeError(name) from error


def _config(value):
    return _Config({k: _config(v) for k, v in value.items()}) if isinstance(value, dict) else value


class TruForResearch:
    def __init__(self, source, checkpoint, spec, threads=2):
        if threads not in (1, 2):
            raise ValueError("CPU trial permits one or two threads")
        verify_artifacts(source, checkpoint, spec)
        import torch
        import yaml
        version = tuple(int(p) for p in torch.__version__.split("+")[0].split(".")[:2])
        if version < (2, 6):
            raise ValueError("Restricted checkpoint loading requires PyTorch >=2.6")
        torch.set_num_threads(threads)
        source = Path(source).resolve()
        # Avoid accidental reuse of an unrelated/already loaded lib namespace.
        if any(name == "lib" or name.startswith("lib.") for name in sys.modules):
            raise RuntimeError("Run research adapter in a fresh process")
        sys.path.insert(0, str(source))
        module = importlib.import_module("lib.models.cmx.builder_np_conf")
        raw = yaml.safe_load((source / "lib/config/trufor_ph3.yaml").read_text(encoding="utf-8"))
        # Upstream YAML represents this tuple as text; membership behavior is
        # explicit here. Disable all secondary/pretraining checkpoint loaders.
        raw["MODEL"]["MODS"] = ["RGB", "NP++"]
        raw["MODEL"]["PRETRAINED"] = None
        raw["MODEL"]["EXTRA"]["NP_WEIGHTS"] = None
        self.model = module.EncoderDecoder(_config(raw)).cpu().eval()
        # This hash-pinned upstream checkpoint stores a NumPy scalar loss beside
        # tensor weights. Permit only those reviewed numeric constructors, never
        # arbitrary pickle or a dynamic allowlist supplied by the checkpoint.
        allowed = {'numpy.core.multiarray.scalar', 'numpy.dtype'}
        if set(torch.serialization.get_unsafe_globals_in_checkpoint(checkpoint)) - allowed:
            raise ValueError('Unexpected checkpoint globals')
        with torch.serialization.safe_globals([
            (np._core.multiarray.scalar, 'numpy.core.multiarray.scalar'),
            np.dtype, np.dtypes.Float64DType,
        ]):
            payload = torch.load(checkpoint, map_location="cpu", weights_only=True)
        state = payload.get("state_dict") if isinstance(payload, dict) else None
        if not isinstance(state, dict) or not state or not all(
            isinstance(key, str) and isinstance(value, torch.Tensor) for key, value in state.items()
        ):
            raise ValueError("Checkpoint lacks a tensor-only state_dict")
        self.model.load_state_dict(state, strict=True)
        del payload, state
        self.torch = torch

    def predict(self, image_path):
        data = image_array(image_path)
        with self.torch.inference_mode():
            logits, _, _, _ = self.model(self.torch.from_numpy(data[None]))
            score_map = self.torch.softmax(logits, dim=1)[0, 1].cpu().numpy().copy()
        if score_map.shape != data.shape[1:] or not np.isfinite(score_map).all():
            raise ValueError("Model produced invalid localization output")
        return {"label": "inconclusive", "score_map": score_map,
                "model": "TruFor-research", "deployment_approved": False,
                "note": "Anomaly localization does not identify AI or conventional edit origin."}


def localization_metrics(truth, scores, threshold=.5):
    """Descriptive fixed-threshold metrics, never threshold fitted or inverted."""
    truth, scores = np.asarray(truth), np.asarray(scores)
    if (truth.ndim != 2 or truth.shape != scores.shape or not np.isin(truth, [0, 1]).all()
            or not np.isfinite(scores).all() or np.any(scores < 0) or np.any(scores > 1)
            or not 0 < threshold < 1):
        raise ValueError("Invalid truth, scores or threshold")
    truth, predicted = truth.astype(bool), scores >= threshold
    true_positive = int(np.count_nonzero(truth & predicted))
    union = int(np.count_nonzero(truth | predicted))
    denominator = int(truth.sum() + predicted.sum())
    return {"iou": true_positive / union if truth.any() else None,
            "dice": 2 * true_positive / denominator if truth.any() else None,
            "false_positive_area_original": float(predicted.mean()) if not truth.any() else None,
            "truth_pixels": int(truth.sum()), "predicted_pixels": int(predicted.sum())}

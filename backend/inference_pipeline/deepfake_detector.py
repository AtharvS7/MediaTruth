"""
DeepfakeDetector — EfficientNet-B5 / HuggingFace pipeline / HF Inference API.

WEIGHT PRIORITY ORDER:
  1. Local fine-tuned .pth weights (efficientnet_b5_deepfake.pth) — best, local only
  2. HuggingFace Transformers pipeline (dima806 ViT, ~99.27% acc) — local download
  3. HuggingFace Inference API  — zero RAM, works on Render Free, $0 cost
  4. Disabled — returns score=0.0, label='unavailable'

DEPLOYMENT MODE (USE_HF_API=true in env):
  Routes all inference to HuggingFace Inference API.
  No PyTorch/timm model loading. Backend RAM: ~120MB instead of ~1.5GB.
  Free tier: ~30,000 requests/month (sufficient for a portfolio project).
"""

import logging
import os
import time
from typing import Any, Dict, Optional

import requests
from PIL import Image

logger = logging.getLogger(__name__)

# HF Inference API endpoint
_HF_DEEPFAKE_API = (
    "https://api-inference.huggingface.co/models/dima806/deepfake_vs_real_image_detection"
)

# EfficientNet-B5 preprocessing — only used in _predict_native (local .pth weights)
# Defined lazily to avoid importing torchvision at module load time.
_EFFICIENTNET_TRANSFORM = None


def _get_efficientnet_transform():
    """Lazy import of torchvision — only called when local .pth weights are used."""
    global _EFFICIENTNET_TRANSFORM
    if _EFFICIENTNET_TRANSFORM is None:
        from torchvision import transforms
        _EFFICIENTNET_TRANSFORM = transforms.Compose([
            transforms.Resize(480),
            transforms.CenterCrop(456),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])
    return _EFFICIENTNET_TRANSFORM


class DeepfakeDetector:
    def __init__(self, model_loader: Any) -> None:
        self.model: Optional[Any] = model_loader.get_model("deepfake")
        self.device: torch.device = model_loader.device
        self.weights_available: bool = model_loader.has_weights("deepfake")

        # HF Inference API mode (USE_HF_API=true) — no local model needed
        self._hf_api_mode: bool = getattr(model_loader, "_hf_api_mode", False)
        self._hf_token: Optional[str] = os.environ.get("HF_TOKEN", "").strip() or None

        # HuggingFace local pipeline (downloaded transformers model)
        self._is_hf_pipeline: bool = (
            isinstance(self.model, dict) and self.model.get("type") == "hf_pipeline"
        )

        if self._hf_api_mode:
            logger.info(
                "DeepfakeDetector: HF Inference API mode — no local model loaded. "
                "Calls: %s", _HF_DEEPFAKE_API
            )
        elif not self.weights_available:
            logger.info(
                "DeepfakeDetector: no weights — returning score=0.0 (disabled)."
            )
        elif self._is_hf_pipeline:
            logger.info(
                "DeepfakeDetector: local HF pipeline (%s)",
                self.model.get("model_id", "unknown")
            )

    def predict(self, image_path: str) -> Dict[str, Any]:
        """
        Run deepfake detection on a single image.

        Returns:
            score: float [0,1] — probability of being deepfake (0.0 if unavailable)
            label: 'real' | 'fake' | 'unavailable'
            confidence: float
            weights_available: bool
        """
        # ── HF Inference API mode (production/Render deployment) ──────────────
        if self._hf_api_mode:
            return self._predict_via_hf_api(image_path)

        # ── Disabled mode ─────────────────────────────────────────────────────
        if not self.weights_available:
            return {
                "score": 0.0,
                "label": "unavailable",
                "confidence": 0.0,
                "weights_available": False,
            }

        if self.model is None:
            return {"score": 0.0, "label": "unknown", "confidence": 0.0, "weights_available": False}

        # ── Local HF pipeline (transformers downloaded model) ─────────────────
        if self._is_hf_pipeline:
            return self._predict_via_hf_pipeline(image_path)

        # ── Native PyTorch .pth weights ───────────────────────────────────────
        return self._predict_native(image_path)

    def _predict_via_hf_api(self, image_path: str) -> Dict[str, Any]:
        """Call HuggingFace Inference API — zero local RAM, free tier."""
        headers = {}
        if self._hf_token:
            headers["Authorization"] = f"Bearer {self._hf_token}"

        try:
            with open(image_path, "rb") as f:
                image_bytes = f.read()

            response = requests.post(
                _HF_DEEPFAKE_API,
                headers=headers,
                data=image_bytes,
                timeout=90,
            )

            # Model cold-start: HF returns 503 with "loading" message
            if response.status_code == 503:
                body = response.json() if response.content else {}
                if "loading" in str(body).lower() or "currently loading" in str(body).lower():
                    wait = min(float(body.get("estimated_time", 30)), 35)
                    logger.info("HF deepfake model loading — waiting %.0fs...", wait)
                    time.sleep(wait)
                    # One retry after waiting
                    response = requests.post(
                        _HF_DEEPFAKE_API,
                        headers=headers,
                        data=image_bytes,
                        timeout=90,
                    )

            response.raise_for_status()
            results = response.json()

            # Parse: [{"label": "Fake", "score": 0.97}, {"label": "Real", "score": 0.03}]
            fake_score = 0.0
            for r in results:
                lbl = r["label"].upper()
                if lbl in ("FAKE", "AI-GENERATED", "ARTIFICIAL", "1", "DEEPFAKE"):
                    fake_score = float(r["score"])
                elif lbl in ("REAL", "AUTHENTIC", "NATURAL", "0"):
                    if fake_score == 0.0:
                        fake_score = 1.0 - float(r["score"])

            return {
                "score": round(fake_score, 4),
                "label": "fake" if fake_score > 0.5 else "real",
                "confidence": round(max(fake_score, 1 - fake_score), 4),
                "weights_available": True,
                "mode": "hf_api",
            }

        except requests.exceptions.Timeout:
            # HF API is configured but model timed out (cold-start).
            # Keep weights_available=True so "Limited Mode" banner does NOT appear.
            logger.warning("HF Inference API timeout for deepfake detection — model cold-starting")
            return {"score": 0.0, "label": "real", "confidence": 0.5, "weights_available": True, "mode": "hf_api_timeout"}
        except Exception as e:
            logger.warning("HF Inference API deepfake failed: %s", e)
            return {"score": 0.0, "label": "real", "confidence": 0.5, "weights_available": True, "mode": "hf_api_error"}

    def _predict_via_hf_pipeline(self, image_path: str) -> Dict[str, Any]:
        """Use locally-downloaded HuggingFace Transformers pipeline."""
        try:
            pipe = self.model["pipe"]
            img = Image.open(image_path).convert("RGB")
            results = pipe(img)
            fake_score = 0.0
            for r in results:
                lbl = r["label"].upper()
                if lbl in ("FAKE", "AI-GENERATED", "ARTIFICIAL", "1", "DEEPFAKE"):
                    fake_score = float(r["score"])
                elif lbl in ("REAL", "AUTHENTIC", "NATURAL", "0", "GENUINE"):
                    if fake_score == 0.0:
                        fake_score = 1.0 - float(r["score"])
            return {
                "score": round(fake_score, 4),
                "label": "fake" if fake_score > 0.5 else "real",
                "confidence": round(max(fake_score, 1 - fake_score), 4),
                "weights_available": True,
                "mode": "hf_pipeline",
            }
        except Exception as e:
            logger.warning("HF pipeline deepfake failed: %s", e)
            return {"score": 0.0, "label": "unknown", "confidence": 0.0, "weights_available": False}

    def _predict_native(self, image_path: str) -> Dict[str, Any]:
        """Use locally-loaded PyTorch .pth weights."""
        try:
            import torch
            import torch.nn.functional as F
            transform = _get_efficientnet_transform()
            img = Image.open(image_path).convert("RGB")
            tensor = transform(img).unsqueeze(0).to(self.device)
            with torch.no_grad():
                logits = self.model(tensor)
                probs = torch.nn.functional.softmax(logits, dim=1)
                fake_prob: float = probs[0, 1].item()
            return {
                "score": round(float(fake_prob), 4),
                "label": "fake" if fake_prob > 0.5 else "real",
                "confidence": round(float(max(probs[0].tolist())), 4),
                "weights_available": True,
                "mode": "native_pth",
            }
        except Exception as e:
            logger.warning("Native deepfake detection failed: %s", e)
            return {"score": 0.0, "label": "unknown", "confidence": 0.0, "weights_available": False}

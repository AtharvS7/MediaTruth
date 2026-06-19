"""
GANDetector — ResNet-50 / HuggingFace pipeline / HF Inference API.

WEIGHT PRIORITY ORDER:
  1. Local fine-tuned .pth weights (cnn_detect.pth) — best, local only
  2. HuggingFace Transformers pipeline (umm-maybe/AI-image-detector) — local download
  3. HuggingFace Inference API  — zero RAM, works on Render Free, $0 cost
  4. Disabled — returns score=0.0, label='unavailable'

DEPLOYMENT MODE (USE_HF_API=true in env):
  Routes all inference to HuggingFace Inference API.
  Model: umm-maybe/AI-image-detector
  Labels: "artificial" (GAN/AI) | "human" (real)
"""

import logging
import os
import time
from typing import Any, Dict, Optional

import requests
from PIL import Image

logger = logging.getLogger(__name__)

# HF Inference API endpoint
_HF_GAN_API = (
    "https://api-inference.huggingface.co/models/umm-maybe/AI-image-detector"
)

# ResNet-50 preprocessing — only used in _predict_native (local .pth weights)
_GAN_TRANSFORM = None


def _get_gan_transform():
    """Lazy import of torchvision — only called when local .pth weights are used."""
    global _GAN_TRANSFORM
    if _GAN_TRANSFORM is None:
        from torchvision import transforms
        _GAN_TRANSFORM = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])
    return _GAN_TRANSFORM


class GANDetector:
    def __init__(self, model_loader: Any) -> None:
        self.model: Optional[Any] = model_loader.get_model("gan_detect")
        self.device: torch.device = model_loader.device
        self.weights_available: bool = model_loader.has_weights("gan_detect")

        # HF Inference API mode (USE_HF_API=true)
        self._hf_api_mode: bool = getattr(model_loader, "_hf_api_mode", False)
        self._hf_token: Optional[str] = os.environ.get("HF_TOKEN", "").strip() or None

        # HuggingFace local pipeline
        self._is_hf_pipeline: bool = (
            isinstance(self.model, dict) and self.model.get("type") == "hf_pipeline"
        )

        if self._hf_api_mode:
            logger.info(
                "GANDetector: HF Inference API mode — no local model loaded. "
                "Calls: %s", _HF_GAN_API
            )
        elif not self.weights_available:
            logger.info("GANDetector: no weights — returning score=0.0 (disabled).")
        elif self._is_hf_pipeline:
            logger.info(
                "GANDetector: local HF pipeline (%s)",
                self.model.get("model_id", "unknown")
            )

    def predict(self, image_path: str) -> Dict[str, Any]:
        """
        Returns:
            score: float [0,1] — probability of being GAN/AI-generated (0.0 if unavailable)
            label: 'real' | 'gan' | 'unavailable'
            confidence: float
            weights_available: bool
        """
        # ── HF Inference API mode ──────────────────────────────────────────────
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

        # ── Local HF pipeline ─────────────────────────────────────────────────
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
                _HF_GAN_API,
                headers=headers,
                data=image_bytes,
                timeout=90,
            )

            # Model cold-start handling
            if response.status_code == 503:
                body = response.json() if response.content else {}
                if "loading" in str(body).lower():
                    wait = min(float(body.get("estimated_time", 30)), 35)
                    logger.info("HF GAN model loading — waiting %.0fs...", wait)
                    time.sleep(wait)
                    response = requests.post(
                        _HF_GAN_API,
                        headers=headers,
                        data=image_bytes,
                        timeout=90,
                    )

            response.raise_for_status()
            results = response.json()

            # Parse: [{"label": "artificial", "score": 0.92}, {"label": "human", "score": 0.08}]
            fake_score = 0.0
            for r in results:
                lbl = r["label"].upper()
                if lbl in ("ARTIFICIAL", "FAKE", "AI", "GAN", "GENERATED", "1", "AI-GENERATED"):
                    fake_score = float(r["score"])
                elif lbl in ("HUMAN", "REAL", "AUTHENTIC", "NATURAL", "0"):
                    if fake_score == 0.0:
                        fake_score = 1.0 - float(r["score"])

            return {
                "score": round(fake_score, 4),
                "label": "gan" if fake_score > 0.5 else "real",
                "confidence": round(max(fake_score, 1 - fake_score), 4),
                "weights_available": True,
                "mode": "hf_api",
            }

        except requests.exceptions.Timeout:
            # HF API configured but cold-starting — keep weights_available=True.
            logger.warning("HF Inference API timeout for GAN detection — model cold-starting")
            return {"score": 0.0, "label": "real", "confidence": 0.5, "weights_available": True, "mode": "hf_api_timeout"}
        except Exception as e:
            logger.warning("HF Inference API GAN failed: %s", e)
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
                if lbl in ("ARTIFICIAL", "FAKE", "AI", "GAN", "GENERATED", "1"):
                    fake_score = float(r["score"])
                elif lbl in ("HUMAN", "REAL", "AUTHENTIC", "0"):
                    if fake_score == 0.0:
                        fake_score = 1.0 - float(r["score"])
            return {
                "score": round(fake_score, 4),
                "label": "gan" if fake_score > 0.5 else "real",
                "confidence": round(max(fake_score, 1 - fake_score), 4),
                "weights_available": True,
                "mode": "hf_pipeline",
            }
        except Exception as e:
            logger.warning("HF pipeline GAN failed: %s", e)
            return {"score": 0.0, "label": "unknown", "confidence": 0.0, "weights_available": False}

    def _predict_native(self, image_path: str) -> Dict[str, Any]:
        """Use locally-loaded CNNDetect ResNet-50 .pth weights."""
        try:
            import torch
            transform = _get_gan_transform()
            img = Image.open(image_path).convert("RGB")
            tensor = transform(img).unsqueeze(0).to(self.device)
            with torch.no_grad():
                logit = self.model(tensor)
                prob: float = torch.sigmoid(logit).item()
            return {
                "score": round(float(prob), 4),
                "label": "gan" if prob > 0.5 else "real",
                "confidence": round(float(max(prob, 1 - prob)), 4),
                "weights_available": True,
                "mode": "native_pth",
            }
        except Exception as e:
            logger.warning("Native GAN detection failed: %s", e)
            return {"score": 0.0, "label": "unknown", "confidence": 0.0, "weights_available": False}

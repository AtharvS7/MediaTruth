"""
DeepfakeDetector — Nahrawy/AIorNot HF Inference API.

WEIGHT PRIORITY ORDER:
  1. Local fine-tuned .pth weights (efficientnet_b5_deepfake.pth) — best, local only
  2. HuggingFace Transformers pipeline (local download)
  3. HuggingFace Inference API  (Nahrawy/AIorNot) — zero RAM, all image types, $0
  4. Disabled — returns score=0.0, api_success=False

MODEL CHANGE (2026-06):
  Previous: dima806/deepfake_vs_real_image_detection  ← FACE-ONLY, always returns
            "real" for logos/artwork/landscapes (score=0.0 → authentic 77%)
  Current:  Nahrawy/AIorNot  ← general AI image detector, works for all image
            types including logos, illustrations, art, and photographs
  Labels:   "real" → authentic | "ai" → ai-generated

API_SUCCESS FLAG:
  Every return dict now includes api_success: bool.
  True  → model ran and returned a real score
  False → timeout / cold-start / error / disabled
  The aggregator uses this flag to switch to Mode B (metadata-only weights)
  instead of treating 0.0 as a "clean" signal.
"""

import logging
import os
import time
from typing import Any, Dict, Optional

import requests
from PIL import Image

logger = logging.getLogger(__name__)

# HF Inference API endpoint — Nahrawy/AIorNot (verified available 2026-06-19)
_HF_DEEPFAKE_API = (
    "https://api-inference.huggingface.co/models/Nahrawy/AIorNot"
)

# Retry configuration
_MAX_RETRIES = 2
_RETRY_BACKOFF = [20, 35]   # seconds between retries (exponential)


class DeepfakeDetector:
    """
    Deepfake / AI-image detection.

    In HF API mode (USE_HF_API=true): calls Nahrawy/AIorNot inference API.
    Returns a score in [0, 1] where 1.0 = definitely AI-generated.
    """

    def __init__(self, model_loader: Any) -> None:
        self.model_loader = model_loader
        self.model = getattr(model_loader, "deepfake_model", None)
        self.weights_available: bool = self.model is not None

        # HF Inference API mode (USE_HF_API=true) — no local model needed
        self._hf_api_mode: bool = getattr(model_loader, "_hf_api_mode", False)
        self._hf_token: Optional[str] = os.environ.get("HF_TOKEN", "").strip() or None

        # HuggingFace local pipeline (downloaded transformers model)
        self._is_hf_pipeline: bool = (
            isinstance(self.model, dict) and self.model.get("type") == "hf_pipeline"
        )

        if self._hf_api_mode:
            logger.info(
                "DeepfakeDetector: HF Inference API mode — Nahrawy/AIorNot. "
                "Detects AI-generated images of all types (photos, logos, art)."
            )
        elif not self.weights_available:
            logger.info(
                "DeepfakeDetector: no weights — returning score=0.0, api_success=False."
            )

    def predict(self, image_path: str) -> Dict[str, Any]:
        """
        Run AI-image detection on a single image.

        Returns:
            score:        float [0,1] — probability of being AI-generated
            label:        'ai' | 'real' | 'unavailable'
            confidence:   float
            weights_available: bool
            api_success:  bool — True if the model actually ran a real inference
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
                "api_success": False,
            }

        if self.model is None:
            return {
                "score": 0.0,
                "label": "unknown",
                "confidence": 0.0,
                "weights_available": False,
                "api_success": False,
            }

        # ── Local HF pipeline (transformers downloaded model) ─────────────────
        if self._is_hf_pipeline:
            return self._predict_via_hf_pipeline(image_path)

        # ── Native PyTorch .pth weights ───────────────────────────────────────
        return self._predict_native(image_path)

    def _predict_via_hf_api(self, image_path: str) -> Dict[str, Any]:
        """
        Call HuggingFace Inference API (Nahrawy/AIorNot).
        Labels: "real" (authentic photo) | "ai" (AI-generated image).
        Includes exponential-backoff retry for cold-start 503 responses.
        """
        headers = {}
        if self._hf_token:
            headers["Authorization"] = f"Bearer {self._hf_token}"

        try:
            with open(image_path, "rb") as f:
                image_bytes = f.read()

            response = None
            for attempt in range(_MAX_RETRIES + 1):
                resp = requests.post(
                    _HF_DEEPFAKE_API,
                    headers=headers,
                    data=image_bytes,
                    timeout=90,
                )

                # Model cold-start (503) — wait and retry
                if resp.status_code == 503:
                    body = resp.json() if resp.content else {}
                    if "loading" in str(body).lower():
                        if attempt < _MAX_RETRIES:
                            wait = min(
                                float(body.get("estimated_time", _RETRY_BACKOFF[attempt])),
                                _RETRY_BACKOFF[attempt],
                            )
                            logger.info(
                                "DeepfakeDetector: HF model cold-starting — "
                                "waiting %.0fs (attempt %d/%d)...",
                                wait, attempt + 1, _MAX_RETRIES,
                            )
                            time.sleep(wait)
                            continue
                    # Non-loading 503 or retries exhausted
                    resp.raise_for_status()

                response = resp
                break

            if response is None:
                raise RuntimeError("All retry attempts failed")

            response.raise_for_status()
            results = response.json()

            # Parse: [{"label": "ai", "score": 0.97}, {"label": "real", "score": 0.03}]
            # OR:    [{"label": "real", "score": 0.95}, {"label": "ai", "score": 0.05}]
            ai_score = 0.0
            for r in results:
                lbl = r["label"].upper().strip()
                if lbl in ("AI", "AI-GENERATED", "ARTIFICIAL", "FAKE", "1"):
                    ai_score = float(r["score"])
                elif lbl in ("REAL", "HUMAN", "AUTHENTIC", "NATURAL", "0"):
                    # If we see the "real" label first, infer ai_score = 1 - real
                    if ai_score == 0.0:
                        ai_score = 1.0 - float(r["score"])

            return {
                "score": round(ai_score, 4),
                "label": "ai" if ai_score > 0.5 else "real",
                "confidence": round(max(ai_score, 1.0 - ai_score), 4),
                "weights_available": True,
                "api_success": True,
                "mode": "hf_api",
            }

        except requests.exceptions.Timeout:
            logger.warning(
                "DeepfakeDetector: HF API timeout after %ds — model cold-starting. "
                "api_success=False so aggregator uses metadata-only weights.",
                90,
            )
            return {
                "score": 0.0,
                "label": "unavailable",
                "confidence": 0.0,
                "weights_available": True,   # API is configured, just slow
                "api_success": False,
                "mode": "hf_api_timeout",
            }
        except Exception as e:
            logger.warning("DeepfakeDetector: HF API error: %s", e)
            return {
                "score": 0.0,
                "label": "unavailable",
                "confidence": 0.0,
                "weights_available": True,
                "api_success": False,
                "mode": "hf_api_error",
            }

    def _predict_via_hf_pipeline(self, image_path: str) -> Dict[str, Any]:
        """Use locally-downloaded HuggingFace Transformers pipeline."""
        try:
            pipe = self.model["pipe"]
            img = Image.open(image_path).convert("RGB")
            results = pipe(img)
            ai_score = 0.0
            for r in results:
                lbl = r["label"].upper()
                if lbl in ("AI", "FAKE", "1", "AI-GENERATED", "ARTIFICIAL"):
                    ai_score = float(r["score"])
                elif lbl in ("REAL", "HUMAN", "0"):
                    if ai_score == 0.0:
                        ai_score = 1.0 - float(r["score"])
            return {
                "score": round(ai_score, 4),
                "label": "ai" if ai_score > 0.5 else "real",
                "confidence": round(max(ai_score, 1.0 - ai_score), 4),
                "weights_available": True,
                "api_success": True,
                "mode": "hf_pipeline",
            }
        except Exception as e:
            logger.error("DeepfakeDetector: HF pipeline failed: %s", e)
            return {
                "score": 0.0,
                "label": "unknown",
                "confidence": 0.0,
                "weights_available": False,
                "api_success": False,
            }

    def _predict_native(self, image_path: str) -> Dict[str, Any]:
        """Run native EfficientNet-B5 / custom .pth model."""
        try:
            import torch
            import torchvision.transforms as T

            transform = T.Compose([
                T.Resize((224, 224)),
                T.ToTensor(),
                T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
            ])
            img = Image.open(image_path).convert("RGB")
            tensor = transform(img).unsqueeze(0)

            device = getattr(self.model_loader, "device", "cpu")
            self.model.eval()
            with torch.no_grad():
                output = self.model(tensor.to(device))
                prob = torch.sigmoid(output).item()

            return {
                "score": round(prob, 4),
                "label": "ai" if prob > 0.5 else "real",
                "confidence": round(max(prob, 1.0 - prob), 4),
                "weights_available": True,
                "api_success": True,
                "mode": "native_pth",
            }
        except Exception as e:
            logger.error("DeepfakeDetector native predict failed: %s", e)
            return {
                "score": 0.0,
                "label": "unknown",
                "confidence": 0.0,
                "weights_available": False,
                "api_success": False,
            }

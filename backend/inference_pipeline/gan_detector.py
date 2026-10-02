"""
GANDetector — umm-maybe/AI-image-detector HF Inference API.

WEIGHT PRIORITY ORDER:
  1. Local fine-tuned .pth weights (cnn_detect.pth) — best, local only
  2. HuggingFace Transformers pipeline (local download)
  3. HuggingFace Inference API  — zero RAM, works on Render Free, $0 cost
  4. Disabled — returns score=0.0, api_success=False

API_SUCCESS FLAG:
  Every return dict includes api_success: bool.
  True  → model ran and returned a real inference score
  False → timeout / cold-start / error / disabled
  Aggregator uses this to switch to Mode B (metadata-dominant weights).
"""

import logging
import math
import os
import time
from typing import Any, Dict, Optional

import requests
from PIL import Image
from inference_pipeline.model_scores import parse_ai_score

logger = logging.getLogger(__name__)

# HF Inference API endpoint
_HF_GAN_API = (
    "https://api-inference.huggingface.co/models/umm-maybe/AI-image-detector"
)

# Retry configuration
_MAX_RETRIES = 2
_RETRY_BACKOFF = [20, 35]   # seconds between retries (exponential)


class GANDetector:
    """
    GAN / AI-image detection using umm-maybe/AI-image-detector.
    Labels: "artificial" (GAN/diffusion/AI) | "human" (real photograph).
    Returns score in [0, 1] where 1.0 = definitely GAN/AI-generated.
    """

    def __init__(self, model_loader: Any) -> None:
        self.model_loader = model_loader
        self.model = model_loader.get_model("gan_detect")
        self.weights_available: bool = model_loader.has_weights("gan_detect") and self.model is not None

        self._hf_api_mode: bool = getattr(model_loader, "_hf_api_mode", False)
        self._hf_token: Optional[str] = os.environ.get("HF_TOKEN", "").strip() or None

        self._is_hf_pipeline: bool = (
            isinstance(self.model, dict) and self.model.get("type") == "hf_pipeline"
        )

        if self._hf_api_mode:
            logger.info(
                "GANDetector: HF Inference API mode — umm-maybe/AI-image-detector. "
                "Calls: %s", _HF_GAN_API,
            )
        elif not self.weights_available:
            logger.info(
                "GANDetector: no weights — returning score=0.0, api_success=False."
            )

    def predict(self, image_path: str) -> Dict[str, Any]:
        """
        Run GAN/AI detection on a single image.

        Returns:
            score:        float [0,1] — probability of being AI/GAN-generated
            label:        'gan' | 'real' | 'unavailable'
            confidence:   float
            weights_available: bool
            api_success:  bool — True if model returned real inference data
        """
        if self._hf_api_mode:
            return self._predict_via_hf_api(image_path)

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

        if self._is_hf_pipeline:
            return self._predict_via_hf_pipeline(image_path)

        return self._predict_native(image_path)

    def _predict_via_hf_api(self, image_path: str) -> Dict[str, Any]:
        """
        Call HuggingFace Inference API (umm-maybe/AI-image-detector).
        Labels: "artificial" (AI/GAN) | "human" (real photo).
        Exponential-backoff retry for cold-start 503 responses.
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
                    _HF_GAN_API,
                    headers=headers,
                    data=image_bytes,
                    timeout=90,
                )

                if resp.status_code == 503:
                    body = resp.json() if resp.content else {}
                    if "loading" in str(body).lower():
                        if attempt < _MAX_RETRIES:
                            wait = min(
                                float(body.get("estimated_time", _RETRY_BACKOFF[attempt])),
                                _RETRY_BACKOFF[attempt],
                            )
                            logger.info(
                                "GANDetector: HF model cold-starting — "
                                "waiting %.0fs (attempt %d/%d)...",
                                wait, attempt + 1, _MAX_RETRIES,
                            )
                            time.sleep(wait)
                            continue
                    resp.raise_for_status()

                response = resp
                break

            if response is None:
                raise RuntimeError("All retry attempts failed")

            response.raise_for_status()
            results = response.json()

            # Parse: [{"label": "artificial", "score": 0.92}, {"label": "human", "score": 0.08}]
            fake_score = parse_ai_score(results)
            return {
                "score": round(fake_score, 4),
                "label": "gan" if fake_score > 0.5 else "real",
                "confidence": round(max(fake_score, 1.0 - fake_score), 4),
                "weights_available": True,
                "api_success": True,
                "mode": "hf_api",
            }

        except requests.exceptions.Timeout:
            logger.warning(
                "GANDetector: HF API timeout after 90s — model cold-starting. "
                "api_success=False so aggregator uses metadata-only weights."
            )
            return {
                "score": 0.0,
                "label": "unavailable",
                "confidence": 0.0,
                "weights_available": True,
                "api_success": False,
                "mode": "hf_api_timeout",
            }
        except Exception as e:
            logger.warning("GANDetector: HF API error: %s", e)
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
            fake_score = parse_ai_score(results)
            return {
                "score": round(fake_score, 4),
                "label": "gan" if fake_score > 0.5 else "real",
                "confidence": round(max(fake_score, 1.0 - fake_score), 4),
                "weights_available": True,
                "api_success": True,
                "mode": "hf_pipeline",
            }
        except Exception as e:
            logger.error("GANDetector: HF pipeline failed: %s", e)
            return {
                "score": 0.0,
                "label": "unknown",
                "confidence": 0.0,
                "weights_available": False,
                "api_success": False,
            }

    def _predict_native(self, image_path: str) -> Dict[str, Any]:
        """Run native ResNet-50 / custom .pth model."""
        try:
            import torch
            import torchvision.transforms as T

            transform = T.Compose([
                # Upstream CNNDetect supports center cropping without resizing.
                # Preserve forensic pixel scale; bound CPU memory to a 224px crop.
                T.CenterCrop(224),
                T.ToTensor(),
                T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
            ])
            with Image.open(image_path) as img:
                tensor = transform(img.convert("RGB")).unsqueeze(0)

            device = getattr(self.model_loader, "device", "cpu")
            self.model.eval()
            with torch.no_grad():
                output = self.model(tensor.to(device))
                prob = torch.sigmoid(output).item()
            if not math.isfinite(prob):
                raise ValueError('Model produced a non-finite score')

            return {
                "score": round(prob, 4),
                "label": "gan" if prob > 0.5 else "real",
                "confidence": round(max(prob, 1.0 - prob), 4),
                "weights_available": True,
                "api_success": True,
                "mode": "native_pth",
            }
        except Exception as e:
            logger.error("GANDetector native predict failed: %s", e)
            return {
                "score": 0.0,
                "label": "unknown",
                "confidence": 0.0,
                "weights_available": False,
                "api_success": False,
            }

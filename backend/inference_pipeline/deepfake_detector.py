"""
DeepfakeDetector — EfficientNet-B5 or HuggingFace pipeline deepfake classifier.

WEIGHT PRIORITY ORDER:
  1. Local fine-tuned .pth weights (efficientnet_b5_deepfake.pth) — best accuracy
  2. HuggingFace pipeline (dima806/deepfake-vs-real-image-detection) — ~98% on CIFAKE
  3. No weights — returns score=0.0 (disabled mode, prevents noise)

CORRECTNESS NOTE:
  Without fine-tuned weights and without a HF fallback, EfficientNet runs with a
  *randomly initialized* 2-class head on top of ImageNet features, which outputs
  softmax(random) ≈ [0.5, 0.5] for every image — pure noise.

  model_loader.has_weights("deepfake") is checked before running inference.
  If False, returns score=0.0 so the aggregator treats this signal as absent.
"""

import logging
from typing import Dict, Any, Optional

import torch
import torch.nn.functional as F
from PIL import Image
from torchvision import transforms

logger = logging.getLogger(__name__)

# EfficientNet-B5 standard preprocessing
EFFICIENTNET_TRANSFORM = transforms.Compose([
    transforms.Resize(480),
    transforms.CenterCrop(456),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])


class DeepfakeDetector:
    def __init__(self, model_loader: Any) -> None:
        self.model: Optional[Any] = model_loader.get_model("deepfake")
        self.device: torch.device = model_loader.device
        self.weights_available: bool = model_loader.has_weights("deepfake")

        # Detect if model is a HuggingFace pipeline dict
        self._is_hf_pipeline: bool = (
            isinstance(self.model, dict) and self.model.get("type") == "hf_pipeline"
        )
        if not self.weights_available:
            logger.info(
                "DeepfakeDetector: no fine-tuned weights — returning score=0.0. "
                "This prevents random noise from poisoning the aggregator."
            )
        elif self._is_hf_pipeline:
            logger.info(
                "DeepfakeDetector: using HuggingFace pipeline (%s)",
                self.model.get("model_id", "unknown")
            )

    def predict(self, image_path: str) -> Dict[str, Any]:
        """
        Run deepfake detection on a single image.

        Returns:
            score: float in [0, 1] — probability of being a deepfake (0.0 if unavailable)
            label: 'real', 'fake', or 'unavailable'
            confidence: float (0.0 if unavailable)
            weights_available: bool — whether fine-tuned weights are loaded
        """
        if not self.weights_available:
            return {
                "score": 0.0,
                "label": "unavailable",
                "confidence": 0.0,
                "weights_available": False,
            }

        if self.model is None:
            return {"score": 0.0, "label": "unknown", "confidence": 0.0, "weights_available": False}

        # ── HuggingFace pipeline inference ────────────────────────────────────
        if self._is_hf_pipeline:
            try:
                pipe = self.model["pipe"]
                img = Image.open(image_path).convert("RGB")
                results = pipe(img)
                # HF pipeline returns: [{"label": "FAKE", "score": 0.97}, {"label": "REAL", "score": 0.03}]
                # Label names vary by model — handle multiple naming conventions
                fake_score = 0.0
                for r in results:
                    lbl = r["label"].upper()
                    if lbl in ("FAKE", "AI-GENERATED", "ARTIFICIAL", "1", "DEEPFAKE"):
                        fake_score = float(r["score"])
                    elif lbl in ("REAL", "AUTHENTIC", "NATURAL", "0", "GENUINE"):
                        if fake_score == 0.0:
                            fake_score = 1.0 - float(r["score"])
                return {
                    "score": fake_score,
                    "label": "fake" if fake_score > 0.5 else "real",
                    "confidence": float(max(fake_score, 1 - fake_score)),
                    "weights_available": True,
                }
            except Exception as e:
                logger.warning(f"HuggingFace deepfake pipeline failed: {e}")
                return {"score": 0.0, "label": "unknown", "confidence": 0.0, "weights_available": False}

        # ── Native PyTorch inference ───────────────────────────────────────────
        try:
            img = Image.open(image_path).convert("RGB")
            tensor = EFFICIENTNET_TRANSFORM(img).unsqueeze(0).to(self.device)

            with torch.no_grad():
                logits = self.model(tensor)
                probs = F.softmax(logits, dim=1)
                fake_prob: float = probs[0, 1].item()

            return {
                "score": float(fake_prob),
                "label": "fake" if fake_prob > 0.5 else "real",
                "confidence": float(max(probs[0].tolist())),
                "weights_available": True,
            }
        except Exception as e:
            logger.warning(f"Deepfake detection failed: {e}")
            return {"score": 0.0, "label": "unknown", "confidence": 0.0, "weights_available": False}

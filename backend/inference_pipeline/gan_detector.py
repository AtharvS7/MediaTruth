"""
GANDetector — ResNet-50 or HuggingFace pipeline GAN-generated image detector.

WEIGHT PRIORITY ORDER:
  1. Local fine-tuned .pth weights (cnn_detect.pth) — best accuracy
  2. HuggingFace pipeline (umm-maybe/AI-image-detector) — auto-downloaded
  3. No weights — returns score=0.0 (disabled mode, prevents noise)

CORRECTNESS NOTE:
  ResNet-50's fc layer is replaced with a 1-output sigmoid classifier.
  WITHOUT fine-tuned weights, this layer is *randomly initialized*, so
  torch.sigmoid(random_fc(features)) ≈ 0.5 for every image — noise.

  model_loader.has_weights("gan_detect") is checked before running inference.
  If False, returns score=0.0 to avoid poisoning the aggregator with noise.
"""

import logging
from typing import Dict, Any, Optional

import torch
import torch.nn.functional as F
from PIL import Image
from torchvision import transforms

logger = logging.getLogger(__name__)

GAN_TRANSFORM = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])


class GANDetector:
    def __init__(self, model_loader: Any) -> None:
        self.model: Optional[Any] = model_loader.get_model("gan_detect")
        self.device: torch.device = model_loader.device
        self.weights_available: bool = model_loader.has_weights("gan_detect")

        # Detect if model is a HuggingFace pipeline dict
        self._is_hf_pipeline: bool = (
            isinstance(self.model, dict) and self.model.get("type") == "hf_pipeline"
        )
        if not self.weights_available:
            logger.info(
                "GANDetector: no fine-tuned weights — returning score=0.0. "
                "This prevents random noise from poisoning the aggregator."
            )
        elif self._is_hf_pipeline:
            logger.info(
                "GANDetector: using HuggingFace pipeline (%s)",
                self.model.get("model_id", "unknown")
            )

    def predict(self, image_path: str) -> Dict[str, Any]:
        """
        Returns:
            score: float in [0, 1] — probability of being GAN-generated (0.0 if unavailable)
            label: 'gan', 'real', or 'unavailable'
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
                # Handle multiple HF label naming conventions
                fake_score = 0.0
                for r in results:
                    lbl = r["label"].upper()
                    if lbl in ("FAKE", "AI", "ARTIFICIAL", "GAN", "GENERATED", "1", "AI-GENERATED"):
                        fake_score = float(r["score"])
                    elif lbl in ("REAL", "AUTHENTIC", "NATURAL", "HUMAN", "0", "GENUINE"):
                        if fake_score == 0.0:
                            fake_score = 1.0 - float(r["score"])
                return {
                    "score": fake_score,
                    "label": "gan" if fake_score > 0.5 else "real",
                    "confidence": float(max(fake_score, 1 - fake_score)),
                    "weights_available": True,
                }
            except Exception as e:
                logger.warning(f"HuggingFace GAN pipeline failed: {e}")
                return {"score": 0.0, "label": "unknown", "confidence": 0.0, "weights_available": False}

        # ── Native PyTorch inference ───────────────────────────────────────────
        try:
            img = Image.open(image_path).convert("RGB")
            tensor = GAN_TRANSFORM(img).unsqueeze(0).to(self.device)

            with torch.no_grad():
                logit = self.model(tensor)
                prob: float = torch.sigmoid(logit).item()

            return {
                "score": float(prob),
                "label": "gan" if prob > 0.5 else "real",
                "confidence": float(max(prob, 1 - prob)),
                "weights_available": True,
            }
        except Exception as e:
            logger.warning(f"GAN detection failed: {e}")
            return {"score": 0.0, "label": "unknown", "confidence": 0.0, "weights_available": False}

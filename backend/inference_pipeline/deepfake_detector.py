"""
DeepfakeDetector — EfficientNet-B5 based deepfake classifier.

Predicts probability that a face image is AI-generated (deepfake).
"""

import logging
from typing import Dict, Any

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from torchvision import transforms

logger = logging.getLogger(__name__)

EFFICIENTNET_TRANSFORM = transforms.Compose([
    transforms.Resize((456, 456)),
    transforms.CenterCrop(456),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])


class DeepfakeDetector:
    def __init__(self, model_loader):
        self.model = model_loader.get_model("deepfake")
        self.device = model_loader.device

    def predict(self, image_path: str) -> Dict[str, Any]:
        """
        Run deepfake detection on a single image.

        Returns:
            score: float in [0, 1] — probability of being a deepfake
            label: 'real' or 'fake'
            confidence: float
        """
        try:
            img = Image.open(image_path).convert("RGB")
            tensor = EFFICIENTNET_TRANSFORM(img).unsqueeze(0).to(self.device)

            with torch.no_grad():
                logits = self.model(tensor)
                probs = F.softmax(logits, dim=1)
                fake_prob = probs[0, 1].item()

            return {
                "score": float(fake_prob),
                "label": "fake" if fake_prob > 0.5 else "real",
                "confidence": float(max(probs[0].tolist())),
            }
        except Exception as e:
            logger.warning(f"Deepfake detection failed: {e}")
            return {"score": 0.0, "label": "unknown", "confidence": 0.0}

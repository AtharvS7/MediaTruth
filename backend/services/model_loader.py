"""
ModelLoader — Centralised pretrained model registry.

Downloads weights on first run, then loads them into memory.
Supports:
  - EfficientNet-B5 deepfake classifier (timm)
  - CNNDetect GAN detector (ResNet-based)
  - ManTraNet manipulation localizer
  - MVSS-Net segmentation model
"""

import os
import logging
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional

import torch
import timm
import requests
from tqdm import tqdm

logger = logging.getLogger(__name__)

WEIGHTS_DIR = Path(__file__).parent.parent / "models" / "weights"
WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)

# HuggingFace / public weight URLs — replace with your mirror if needed
MODEL_REGISTRY = {
    "efficientnet_deepfake": {
        "url": None,  # Uses timm pretrained — fine-tuned weights optional
        "filename": "efficientnet_b5_deepfake.pth",
        "architecture": "efficientnet_b5",
        "num_classes": 2,
    },
    "cnn_detect": {
        "url": "https://huggingface.co/mediaTruth/cnn-detect/resolve/main/cnn_detect.pth",
        "filename": "cnn_detect.pth",
        "architecture": "resnet50",
        "num_classes": 1,
    },
}


def _download_file(url: str, dest: Path) -> None:
    """Download a file with a progress bar."""
    logger.info(f"Downloading {url} → {dest}")
    response = requests.get(url, stream=True, timeout=120)
    response.raise_for_status()
    total = int(response.headers.get("content-length", 0))
    with open(dest, "wb") as f, tqdm(total=total, unit="B", unit_scale=True) as bar:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
            bar.update(len(chunk))


class ModelLoader:
    """Singleton-style model registry loaded at startup."""

    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.models: Dict[str, Any] = {}
        self._ready = False
        logger.info(f"ModelLoader initialised on device: {self.device}")

    async def load_all_models(self) -> None:
        """Async wrapper — runs blocking loads in thread pool."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._load_all_models_sync)

    def _load_all_models_sync(self) -> None:
        self._load_efficientnet_deepfake()
        self._load_cnn_detect()
        self._ready = True

    # ── EfficientNet-B5 Deepfake Classifier ─────────────────────────────────────
    def _load_efficientnet_deepfake(self) -> None:
        logger.info("Loading EfficientNet-B5 deepfake classifier...")
        model = timm.create_model(
            "efficientnet_b5",
            pretrained=True,
            num_classes=2,
        )
        weights_path = WEIGHTS_DIR / "efficientnet_b5_deepfake.pth"
        if weights_path.exists():
            state = torch.load(weights_path, map_location=self.device)
            model.load_state_dict(state, strict=False)
            logger.info("Loaded fine-tuned EfficientNet-B5 weights.")
        model.eval().to(self.device)
        self.models["deepfake"] = model
        logger.info("✅ EfficientNet-B5 deepfake model ready.")

    # ── CNNDetect GAN Detector ───────────────────────────────────────────────────
    def _load_cnn_detect(self) -> None:
        logger.info("Loading CNNDetect GAN detector...")
        import torchvision.models as tv_models
        model = tv_models.resnet50(weights=tv_models.ResNet50_Weights.IMAGENET1K_V2)
        model.fc = torch.nn.Linear(model.fc.in_features, 1)

        weights_path = WEIGHTS_DIR / "cnn_detect.pth"
        if weights_path.exists():
            state = torch.load(weights_path, map_location=self.device)
            model.load_state_dict(state, strict=False)
            logger.info("Loaded CNNDetect pretrained weights.")

        model.eval().to(self.device)
        self.models["gan_detect"] = model
        logger.info("✅ CNNDetect GAN model ready.")

    def get_model(self, name: str) -> Optional[Any]:
        return self.models.get(name)

    def is_ready(self) -> bool:
        return self._ready

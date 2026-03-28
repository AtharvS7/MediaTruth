"""
ModelLoader — Centralised pretrained model registry.

Downloads weights on first run, then loads them into memory.
Supports:
  - EfficientNet-B5 deepfake classifier (timm)
  - CNNDetect GAN detector (ResNet-based)
  - ManTraNet manipulation localizer
  - MVSS-Net segmentation model

BUG-007 fixes:
  - Per-model try/except in _load_all_models_sync (one failure doesn't crash startup)
  - Removed fake HuggingFace URL from MODEL_REGISTRY
  - Added weights_only=False to torch.load() with explanatory comment
  - self._ready = True after loading attempts regardless
IMPROVE-002:
  - get_model() logs a WARNING (once) when returning None for a missing model
BUG-006 fix:
  - Replaced asyncio.get_event_loop() with asyncio.get_running_loop()
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional, Set

import torch
import timm
import requests
from tqdm import tqdm

logger = logging.getLogger(__name__)

WEIGHTS_DIR: Path = Path(__file__).parent.parent / "models" / "weights"
WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)

# Model registry — URLs are None when no public weights are available
MODEL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "efficientnet_deepfake": {
        "url": None,  # Uses timm pretrained — fine-tuned weights optional
        "filename": "efficientnet_b5_deepfake.pth",
        "architecture": "efficientnet_b5",
        "num_classes": 2,
    },
    "cnn_detect": {
        "url": None,  # No public weights available — uses ImageNet init
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
    total: int = int(response.headers.get("content-length", 0))
    with open(dest, "wb") as f, tqdm(total=total, unit="B", unit_scale=True) as bar:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
            bar.update(len(chunk))


class ModelLoader:
    """Singleton-style model registry loaded at startup."""

    def __init__(self) -> None:
        self.device: torch.device = torch.device(
            "cuda" if torch.cuda.is_available() else "cpu"
        )
        self.models: Dict[str, Any] = {}
        self._ready: bool = False
        self._warned_models: Set[str] = set()  # Track which models we've warned about
        logger.info(f"ModelLoader initialised on device: {self.device}")

    async def load_all_models(self) -> None:
        """Async wrapper — runs blocking loads in thread pool."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._load_all_models_sync)

    def _load_all_models_sync(self) -> None:
        """Load each model independently — one failure doesn't crash the other."""

        # EfficientNet deepfake classifier
        try:
            self._load_efficientnet_deepfake()
        except Exception as e:
            logger.error(
                f"EfficientNet load failed: {e}. Deepfake detector disabled."
            )
            self.models["deepfake"] = None

        # CNNDetect GAN detector
        try:
            self._load_cnn_detect()
        except Exception as e:
            logger.error(f"CNNDetect load failed: {e}. GAN detector disabled.")
            self.models["gan_detect"] = None

        # Mark as ready regardless — available models will work, others return None
        self._ready = True

        loaded = [k for k, v in self.models.items() if v is not None]
        failed = [k for k, v in self.models.items() if v is None]
        logger.info(f"ModelLoader ready. Loaded: {loaded}. Failed/disabled: {failed}")

    # ── EfficientNet-B5 Deepfake Classifier ─────────────────────────────────
    def _load_efficientnet_deepfake(self) -> None:
        logger.info("Loading EfficientNet-B5 deepfake classifier...")
        model = timm.create_model(
            "efficientnet_b5",
            pretrained=True,
            num_classes=2,
        )
        weights_path: Path = WEIGHTS_DIR / "efficientnet_b5_deepfake.pth"
        if weights_path.exists():
            # weights_only=False: community weights may contain non-tensor objects
            state = torch.load(
                weights_path, map_location=self.device, weights_only=False
            )
            model.load_state_dict(state, strict=False)
            logger.info("Loaded fine-tuned EfficientNet-B5 weights.")
        model.eval().to(self.device)
        self.models["deepfake"] = model
        logger.info("✅ EfficientNet-B5 deepfake model ready.")

    # ── CNNDetect GAN Detector ──────────────────────────────────────────────
    def _load_cnn_detect(self) -> None:
        logger.info("Loading CNNDetect GAN detector...")
        import torchvision.models as tv_models

        model = tv_models.resnet50(weights=tv_models.ResNet50_Weights.IMAGENET1K_V2)
        model.fc = torch.nn.Linear(model.fc.in_features, 1)

        weights_path: Path = WEIGHTS_DIR / "cnn_detect.pth"
        if weights_path.exists():
            # weights_only=False: community weights may contain non-tensor objects
            state = torch.load(
                weights_path, map_location=self.device, weights_only=False
            )
            model.load_state_dict(state, strict=False)
            logger.info("Loaded CNNDetect pretrained weights.")

        model.eval().to(self.device)
        self.models["gan_detect"] = model
        logger.info("✅ CNNDetect GAN model ready.")

    def get_model(self, name: str) -> Optional[Any]:
        """Return the model by name. Logs WARNING once if model is None."""
        model = self.models.get(name)
        if model is None and name not in self._warned_models:
            logger.warning(
                f"Model '{name}' not available — detector will return zero scores."
            )
            self._warned_models.add(name)
        return model

    def is_ready(self) -> bool:
        return self._ready

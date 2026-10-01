"""
ModelLoader — Centralised pretrained model registry.

Loads ML models at startup and keeps them in memory for inference.
Supports:
  - EfficientNet-B5 deepfake classifier (timm)  [local .pth or HF pre-trained]
  - CNNDetect GAN detector (ResNet-50)           [local .pth or HF pre-trained]
  - HuggingFace Transformers pipeline fallback   [auto-downloads on first boot]

Weight priority order:
  1. Local fine-tuned .pth in models/weights/    ← best (your trained model)
  2. HuggingFace pre-trained download            ← good (public academic weights)
  3. Random ImageNet-only backbone               ← disabled (returns 0.0)

Features:
  - Per-model try/except: one failure doesn't crash startup
  - Graceful degradation: missing models return zero scores
  - GPU auto-detection with CPU fallback
"""

import asyncio
import hashlib
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional, Set

# torch, timm, tqdm are imported lazily inside _load_* methods.
# In USE_HF_API=true mode those methods are never called,
# so torch does NOT need to be installed on Render.
import requests

logger = logging.getLogger(__name__)

WEIGHTS_DIR: Path = Path(__file__).parent.parent / "models" / "weights"
WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)

# ─── HuggingFace pre-trained fallback sources ─────────────────────────────────
# These are publicly available models that work WITHOUT any form submission.
# They activate automatically when no local .pth weights are found.
# Source: https://huggingface.co/dima806/deepfake_vs_real_image_detection
# External model-card results do not establish accuracy on MediaTruth workloads.
HF_DEEPFAKE_MODEL_ID = "dima806/deepfake_vs_real_image_detection"
# GAN fallback — general AI image detector
HF_GAN_MODEL_ID = "umm-maybe/AI-image-detector"

MODEL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "efficientnet_deepfake": {
        "url": None,
        "filename": "efficientnet_b5_deepfake.pth",
        "architecture": "efficientnet_b5",
        "num_classes": 2,
    },
    "cnn_detect": {
        "url": None,
        "filename": "cnn_detect.pth",
        "architecture": "resnet50",
        "num_classes": 1,
    },
}


def _download_file(url: str, dest: Path) -> None:
    """Download a file with a progress bar."""
    logger.info(f"Downloading {url} → {dest}")
    from tqdm import tqdm
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
        # Lazy device detection — only import torch when actually loading local models.
        # In USE_HF_API=true mode, torch is never imported on Render (no PyTorch needed).
        try:
            import torch as _torch
            self.device = _torch.device("cuda" if _torch.cuda.is_available() else "cpu")
        except ImportError:
            self.device = "cpu"  # type: ignore[assignment]  # HF API mode: device unused
        self.models: Dict[str, Any] = {}
        self._ready: bool = False
        self._warned_models: Set[str] = set()
        self._weights_loaded: Set[str] = set()
        self.weight_fingerprints = {}

        # ─── HuggingFace Inference API mode ─────────────────────────────────────
        # When USE_HF_API=true, no local PyTorch models are loaded.
        # All ML inference is delegated to HuggingFace Inference API (free tier).
        # RAM usage: ~120MB (vs ~1.5GB with local models) — works on Render Free.
        import os
        self._hf_api_mode: bool = os.environ.get("USE_HF_API", "").lower() in ("1", "true", "yes")

        if self._hf_api_mode:
            logger.info(
                "ModelLoader: HF Inference API mode enabled (USE_HF_API=true). "
                "No local models loaded. ML inference via huggingface.co API."
            )
        else:
            logger.info(f"ModelLoader initialised on device: {self.device}")

    async def load_all_models(self) -> None:
        """Async wrapper — runs blocking loads in thread pool."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._load_all_models_sync)

    def _load_all_models_sync(self) -> None:
        """Load each model independently — one failure doesn't crash the other."""

        # ─── HF Inference API mode: skip all local model loading ───────────────
        # All ML inference routes to HuggingFace API. No PyTorch models loaded.
        # This keeps RAM < 200MB so the service runs on Render Free (512MB).
        if self._hf_api_mode:
            # Mark both detectors as available — API provides real inference
            self._weights_loaded.add("deepfake")
            self._weights_loaded.add("gan_detect")
            self.models["deepfake"] = {"type": "hf_api", "model_id": HF_DEEPFAKE_MODEL_ID}
            self.models["gan_detect"] = {"type": "hf_api", "model_id": HF_GAN_MODEL_ID}
            self._ready = True
            logger.info(
                "ModelLoader ready (HF API mode). "
                "Deepfake: %s | GAN: %s", HF_DEEPFAKE_MODEL_ID, HF_GAN_MODEL_ID
            )
            return

        # EfficientNet deepfake classifier (local weights → HF pre-trained → disabled)
        deepfake_weights = WEIGHTS_DIR / "efficientnet_b5_deepfake.pth"
        if deepfake_weights.exists():
            # Local fine-tuned weights — use EfficientNet
            try:
                self._load_efficientnet_deepfake()
            except Exception as e:
                logger.error(f"EfficientNet load failed: {e}. Attempting HuggingFace fallback...")
                try:
                    self._load_hf_deepfake_pipeline()
                except Exception as e2:
                    logger.error(f"HuggingFace deepfake fallback failed: {e2}. Detector disabled.")
                    self.models["deepfake"] = None
        else:
            # No local weights — go straight to HuggingFace pre-trained model
            logger.info("No local deepfake weights found — loading HuggingFace pre-trained model...")
            try:
                self._load_hf_deepfake_pipeline()
            except Exception as e:
                logger.error(f"HuggingFace deepfake pipeline failed: {e}. Detector disabled.")
                self.models["deepfake"] = None

        # CNNDetect GAN detector (local weights → HF pre-trained → disabled)
        try:
            self._load_cnn_detect()
        except Exception as e:
            logger.error(f"CNNDetect load failed: {e}. Attempting HuggingFace fallback...")
            try:
                self._load_hf_gan_pipeline()
            except Exception as e2:
                logger.error(f"HuggingFace GAN fallback failed: {e2}. Detector disabled.")
                self.models["gan_detect"] = None

        self._ready = True

        loaded = [k for k, v in self.models.items() if v is not None]
        failed = [k for k, v in self.models.items() if v is None]
        fine_tuned = list(self._weights_loaded)
        logger.info(
            "ModelLoader ready. Models loaded: %s. Fine-tuned weights: %s. Failed: %s.",
            loaded, fine_tuned, failed
        )
        if not fine_tuned:
            logger.warning(
                "NO fine-tuned model weights are loaded. Deepfake and GAN detectors "
                "are DISABLED (returning 0.0). Analysis relies on ELA and metadata only. "
                "This is expected for a new installation without model weights."
            )

    def _load_efficientnet_deepfake(self) -> None:
        logger.info("Loading EfficientNet-B5 deepfake classifier...")
        import torch
        import timm
        model = timm.create_model(
            "efficientnet_b5",
            pretrained=False,
            num_classes=2,
        )
        weights_path: Path = WEIGHTS_DIR / "efficientnet_b5_deepfake.pth"
        if weights_path.exists():
            # SEC-09: Use weights_only=True (safe deserialization)
            try:
                state = torch.load(weights_path, map_location=self.device, weights_only=True)
            except Exception:
                logger.warning(
                    "weights_only=True failed for EfficientNet-B5 weights — "
                    "rejecting unsafe checkpoint deserialization."
                )
                raise ValueError("Checkpoint cannot be loaded safely; convert it to a plain state dictionary.")
            model.load_state_dict(state, strict=True)
            self._weights_loaded.add("deepfake")
            logger.info("EfficientNet-B5: fine-tuned deepfake weights loaded.")
            with weights_path.open("rb") as stream:
                self.weight_fingerprints["deepfake"] = hashlib.file_digest(stream, "sha256").hexdigest()
        else:
            logger.warning(
                "EfficientNet-B5: NO fine-tuned weights found at %s. "
                "Running with random classification head — deepfake_score will be 0.0 (disabled). "
                "Add efficientnet_b5_deepfake.pth to models/weights/ to enable deepfake detection.",
                weights_path,
            )
        model.eval().to(self.device)
        self.models["deepfake"] = model
        logger.info("EfficientNet-B5 deepfake model ready (weights: %s).",
                    "fine-tuned" if "deepfake" in self._weights_loaded else "disabled/random-head")

    def _load_cnn_detect(self) -> None:
        if not (WEIGHTS_DIR / "cnn_detect.pth").exists():
            raise FileNotFoundError("No trained CNNDetect checkpoint; use the configured fallback.")
        logger.info("Loading CNNDetect GAN detector...")
        import torch
        import torchvision.models as tv_models

        model = tv_models.resnet50(weights=None)
        model.fc = torch.nn.Linear(model.fc.in_features, 1)

        weights_path: Path = WEIGHTS_DIR / "cnn_detect.pth"
        if weights_path.exists():
            # SEC-09: Safe deserialization
            try:
                state = torch.load(weights_path, map_location=self.device, weights_only=True)
            except Exception:
                logger.warning(
                    "weights_only=True failed for CNNDetect weights — "
                    "rejecting unsafe checkpoint deserialization."
                )
                raise ValueError("Checkpoint cannot be loaded safely; convert it to a plain state dictionary.")
            # Upstream training checkpoints wrap weights alongside optimizer state.
            # Deserialization above remains weights_only=True; only tensors reach the model.
            if isinstance(state, dict) and "model" in state:
                state = state["model"]
            if not isinstance(state, dict) or not state or not all(
                isinstance(key, str) and isinstance(value, torch.Tensor)
                for key, value in state.items()
            ):
                raise ValueError("CNNDetect checkpoint has no tensor state dictionary.")
            # CNNDetect was trained with DataParallel — strip 'module.' prefix
            if any(k.startswith("module.") for k in state.keys()):
                state = {k.replace("module.", "", 1): v for k, v in state.items()}
                logger.info("CNNDetect: stripped DataParallel 'module.' prefix from state dict.")
            model.load_state_dict(state, strict=True)
            self._weights_loaded.add("gan_detect")
            logger.info("CNNDetect: fine-tuned GAN detector weights loaded.")
            with weights_path.open("rb") as stream:
                self.weight_fingerprints["gan_detect"] = hashlib.file_digest(stream, "sha256").hexdigest()
        else:
            logger.warning(
                "CNNDetect: NO fine-tuned weights found at %s. "
                "Running with random fc layer — gan_score will be 0.0 (disabled). "
                "Add cnn_detect.pth to models/weights/ to enable GAN detection.",
                weights_path,
            )
        model.eval().to(self.device)
        self.models["gan_detect"] = model
        logger.info("CNNDetect GAN model ready (weights: %s).",
                    "fine-tuned" if "gan_detect" in self._weights_loaded else "disabled/random-head")

    def _load_hf_deepfake_pipeline(self) -> None:
        """Download and cache a pre-trained deepfake detector from HuggingFace Hub.

        Uses dima806/deepfake-vs-real-image-detection — a ViT model trained on
        CIFAKE achieving ~98.25% accuracy. Falls back gracefully if network unavailable.
        """
        if os.getenv("ALLOW_MODEL_DOWNLOADS", "false").lower() != "true":
            raise RuntimeError("Model downloads disabled; prepare reviewed local weights first.")
        logger.info("Loading HuggingFace pre-trained deepfake detector: %s", HF_DEEPFAKE_MODEL_ID)
        try:
            from transformers import pipeline as hf_pipeline
        except ImportError:
            raise RuntimeError("transformers package not installed. Run: pip install transformers")

        # Use GPU if available, else CPU
        device_id = 0 if (lambda: __import__('torch').cuda.is_available())() else -1
        pipe = hf_pipeline(
            "image-classification",
            model=HF_DEEPFAKE_MODEL_ID,
            device=device_id,
        )
        self.models["deepfake"] = {"type": "hf_pipeline", "pipe": pipe, "model_id": HF_DEEPFAKE_MODEL_ID}
        self._weights_loaded.add("deepfake")
        logger.info("HuggingFace deepfake pipeline ready: %s", HF_DEEPFAKE_MODEL_ID)

    def _load_hf_gan_pipeline(self) -> None:
        """Download and cache a pre-trained AI image detector from HuggingFace Hub.

        Uses umm-maybe/AI-image-detector — trained to detect GAN/AI-generated images.
        """
        if os.getenv("ALLOW_MODEL_DOWNLOADS", "false").lower() != "true":
            raise RuntimeError("Model downloads disabled; prepare reviewed local weights first.")
        logger.info("Loading HuggingFace pre-trained AI image detector: %s", HF_GAN_MODEL_ID)
        try:
            from transformers import pipeline as hf_pipeline
        except ImportError:
            raise RuntimeError("transformers package not installed. Run: pip install transformers")

        device_id = 0 if (lambda: __import__('torch').cuda.is_available())() else -1
        pipe = hf_pipeline(
            "image-classification",
            model=HF_GAN_MODEL_ID,
            device=device_id,
        )
        self.models["gan_detect"] = {"type": "hf_pipeline", "pipe": pipe, "model_id": HF_GAN_MODEL_ID}
        self._weights_loaded.add("gan_detect")
        logger.info("HuggingFace GAN pipeline ready: %s", HF_GAN_MODEL_ID)

    def get_model(self, name: str) -> Optional[Any]:
        """Return the model by name. Logs WARNING once if model is None."""
        model = self.models.get(name)
        if model is None and name not in self._warned_models:
            logger.warning(
                f"Model '{name}' not available — detector will return zero scores."
            )
            self._warned_models.add(name)
        return model

    def has_weights(self, name: str) -> bool:
        """
        Return True ONLY if fine-tuned task-specific weights were successfully loaded.

        When False, the model uses a randomly initialized classification head on top
        of ImageNet features, which produces ~0.5 noise for any input — not useful.
        Detectors MUST check this and return score=0.0 when False.
        """
        return name in self._weights_loaded

    @property
    def ready(self) -> bool:
        return self._ready

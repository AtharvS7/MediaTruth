"""Offline Meso4 face-forgery candidate; never registered for public verdicts.

Architecture adapted from DariusAf/MesoNet (Apache-2.0), revision
2144d56a30e48cdcac1976ff13a1c5cdc86376c6. See licenses/MESONET_*.
Only pinned numeric HDF5 arrays are read; no downloaded Python or pickle runs.
"""

import hashlib
from pathlib import Path

import numpy as np
from PIL import Image
import torch
from torch import nn

WEIGHTS_SHA256 = "036ed30d04ffd9c7506f825b97c86aa64915f5818931da96817b169aad790af5"
SOURCE_REVISION = "2144d56a30e48cdcac1976ff13a1c5cdc86376c6"


class Meso4Research(nn.Module):
    def __init__(self):
        super().__init__()
        self.convs = nn.ModuleList([nn.Conv2d(a, b, k, padding=k // 2)
                                   for a, b, k in [(3, 8, 3), (8, 8, 5), (8, 16, 5), (16, 16, 5)]])
        # Keras BatchNormalization defaults to epsilon=0.001, not PyTorch's 1e-5.
        self.norms = nn.ModuleList([nn.BatchNorm2d(c, eps=.001) for c in [8, 8, 16, 16]])
        self.dense = nn.Linear(1024, 16)
        self.output = nn.Linear(16, 1)

    def forward(self, x):
        for index, (conv, norm) in enumerate(zip(self.convs, self.norms)):
            x = torch.nn.functional.max_pool2d(norm(torch.relu(conv(x))), 4 if index == 3 else 2)
        # Original Keras flatten order is NHWC; flattening NCHW silently changes scores.
        x = x.permute(0, 2, 3, 1).reshape(x.shape[0], -1)
        x = torch.nn.functional.leaky_relu(self.dense(x), negative_slope=.1)
        return torch.sigmoid(self.output(x))

    @classmethod
    def from_weights(cls, path):
        import h5py  # Optional research dependency, not needed by serving.

        path = Path(path)
        if path.stat().st_size != 156128 or hashlib.sha256(path.read_bytes()).hexdigest() != WEIGHTS_SHA256:
            raise ValueError("Expected pinned official Meso4_DF.h5 weights.")
        model = cls().eval()
        with h5py.File(path, "r") as weights, torch.no_grad():
            def array(group, name):
                return torch.from_numpy(np.asarray(weights[f"{group}/{group}/{name}:0"], dtype=np.float32))

            for index, (conv, norm) in enumerate(zip(model.convs, model.norms), start=5):
                group = f"conv2d_{index}"
                conv.weight.copy_(array(group, "kernel").permute(3, 2, 0, 1))
                conv.bias.copy_(array(group, "bias"))
                group = f"batch_normalization_{index}"
                for target, source in [(norm.weight, "gamma"), (norm.bias, "beta"),
                                       (norm.running_mean, "moving_mean"), (norm.running_var, "moving_variance")]:
                    target.copy_(array(group, source))
            for layer, index in [(model.dense, 3), (model.output, 4)]:
                layer.weight.copy_(array(f"dense_{index}", "kernel").T)
                layer.bias.copy_(array(f"dense_{index}", "bias"))
        return model

    @torch.inference_mode()
    def score_face(self, image: Image.Image) -> float:
        # Official ImageDataGenerator uses RGB /255 and nearest resize by default.
        rgb = np.asarray(image.convert("RGB").resize((256, 256), Image.Resampling.NEAREST), dtype=np.float32) / 255.
        value = float(self(torch.from_numpy(rgb).permute(2, 0, 1).unsqueeze(0)).item())
        if not np.isfinite(value):
            raise ValueError("Non-finite model output.")
        # Official directory labels: df=0, real=1. Output is real, not fake.
        return 1. - value

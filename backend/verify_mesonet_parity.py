"""Optional CPU parity check against Keras layers; requires keras==3.11.3.

This builds the published architecture using Keras with a torch backend, rather
than executing downloaded code. It verifies layer semantics and weight mapping,
not cross-backend TensorFlow parity or scientific detection accuracy.
"""
import argparse
import json
import os
from pathlib import Path

os.environ["KERAS_BACKEND"] = "torch"

import numpy as np
from PIL import Image
import torch
import keras
from inference_pipeline.mesonet_research import Meso4Research


def verify(weights, images):
    torch.set_num_threads(2)
    x = keras.Input((256, 256, 3))
    y = x
    for index, (channels, kernel) in enumerate([(8, 3), (8, 5), (16, 5), (16, 5)]):
        y = keras.layers.Conv2D(channels, kernel, padding="same", activation="relu")(y)
        y = keras.layers.BatchNormalization()(y)
        y = keras.layers.MaxPooling2D(pool_size=4 if index == 3 else 2, padding="same")(y)
    y = keras.layers.Flatten()(y)
    y = keras.layers.Dropout(.5)(y)
    y = keras.layers.Dense(16)(y)
    y = keras.layers.LeakyReLU(negative_slope=.1)(y)
    y = keras.layers.Dropout(.5)(y)
    y = keras.layers.Dense(1, activation="sigmoid")(y)
    reference = keras.Model(x, y)
    candidate = Meso4Research.from_weights(weights)  # Validate hash before either load.
    reference.load_weights(weights)
    comparisons = []
    for path in sorted(Path(images).rglob("*.jpg")):
        with Image.open(path) as image:
            value = np.asarray(image.convert("RGB").resize((256, 256), Image.Resampling.NEAREST), np.float32) / 255.
            expected = 1. - float(reference.predict(value[None], verbose=0)[0, 0])
            actual = candidate.score_face(image)
        comparisons.append({"file": path.name, "keras_fake_score": expected,
                            "torch_fake_score": actual, "absolute_difference": abs(expected - actual)})
    if not comparisons or max(row["absolute_difference"] for row in comparisons) > 1e-5:
        raise ValueError("Parity check failed.")
    return {"reference": "Keras 3.11.3 / torch backend", "tolerance": 1e-5,
            "passed": True, "comparisons": comparisons}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ["weights", "images", "output"]:
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    result = verify(args.weights, args.images)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))

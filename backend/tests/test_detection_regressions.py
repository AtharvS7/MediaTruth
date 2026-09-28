from types import SimpleNamespace
from unittest.mock import Mock
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from inference_pipeline.aggregator import ConfidenceAggregator
from inference_pipeline.deepfake_detector import DeepfakeDetector
from inference_pipeline.gan_detector import GANDetector
from api.routes.health_routes import readiness
import pytest
from inference_pipeline.model_scores import parse_ai_score


@pytest.mark.parametrize("results", [[], [{"label": "LABEL_0", "score": .99}],
    [{"label": "ai", "score": float("nan")}], [{"label": "real", "score": 2}],
    [{"label": "ai", "score": .9}, {"label": "real", "score": .9}]])
def test_unknown_or_malformed_model_output_is_rejected(results):
    with pytest.raises(ValueError):
        parse_ai_score(results)


def test_model_label_order_and_zero_score():
    assert parse_ai_score([{"label": "ai", "score": 0}, {"label": "real", "score": 1}]) == 0
    assert parse_ai_score([{"label": "human", "score": .8}]) == pytest.approx(.2)


def test_native_two_class_deepfake_uses_softmax(tmp_path):
    import torch
    from PIL import Image
    class Model:
        def eval(self):
            pass
        def __call__(self, tensor):
            return torch.tensor([[0.0, 2.0]])
    loader = SimpleNamespace(get_model=lambda name: Model(), has_weights=lambda name: True,
                             _hf_api_mode=False, device="cpu")
    path = tmp_path / "image.png"
    Image.new("RGB", (32, 32)).save(path)
    result = DeepfakeDetector(loader).predict(str(path))
    assert result["api_success"] is True
    assert result["score"] == pytest.approx(.8808)


@pytest.mark.parametrize("detector,name", [(DeepfakeDetector, "deepfake"), (GANDetector, "gan_detect")])
def test_detectors_use_registry_and_require_trained_weights(detector, name):
    model = object()
    loader = SimpleNamespace(get_model=Mock(return_value=model), has_weights=Mock(return_value=True), _hf_api_mode=False)
    instance = detector(loader)
    assert instance.model is model
    loader.get_model.assert_called_once_with(name)
    loader.has_weights.return_value = False
    assert detector(loader).predict("unused")["api_success"] is False


def test_explicit_model_failure_is_not_overridden_by_loaded_weights():
    result = ConfidenceAggregator().aggregate(
        {"api_success": False, "weights_available": True, "score": .9}, {}, {}, {}
    )
    assert result["verdict"] == "Inconclusive"
    assert result["ml_available"] is False


def test_inconclusive_video_does_not_become_ai_generated():
    result = ConfidenceAggregator().aggregate_video([
        {"final_verdict": "Inconclusive", "ml_available": False, "limited_mode": True}
    ] * 3)
    assert result["verdict"] == "Inconclusive"
    assert result["confidence"] == 0
    assert result["limited_mode"] is True


def test_partial_video_marks_coverage_gap():
    result = ConfidenceAggregator().aggregate_video([
        {"ml_available": True, "ai_generated_probability": .9, "authentic_probability": .1},
        {"ml_available": False, "final_verdict": "Inconclusive"},
    ])
    assert result["limited_mode"] is True
    assert result["confidence"] <= .65


@pytest.mark.asyncio
async def test_readiness_uses_loader_property():
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(model_loader=SimpleNamespace(ready=True))))
    assert await readiness(request) == {"ready": True}

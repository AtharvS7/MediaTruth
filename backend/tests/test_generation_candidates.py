import math

import pytest
from PIL import Image

from inference_pipeline.generation_candidates import (
    CANDIDATES, GenerationCandidate, build_transform, interpret_logit,
)


def test_opposite_score_directions_are_explicit():
    assert interpret_logit(10, CANDIDATES['community'])['label'] == 'ai_generated'
    assert interpret_logit(10, CANDIDATES['modern_clip'])['label'] == 'original'
    assert interpret_logit(-10, CANDIDATES['modern_clip'])['score'] > .99


def test_upstream_temperature_and_abstention_band():
    spec = CANDIDATES['modern_clip']
    logit = math.log(.92/.08) * spec.temperature
    result = interpret_logit(logit, spec)
    assert result['label'] == 'inconclusive'
    assert result['score'] == pytest.approx(.08)


@pytest.mark.parametrize('logit', [float('nan'), float('inf'), -float('inf')])
def test_nonfinite_is_not_an_authentic_prediction(logit):
    with pytest.raises(ValueError, match='Non-finite'):
        interpret_logit(logit, CANDIDATES['community'])


def test_weights_are_verified_before_deserialization(tmp_path):
    weights = tmp_path/'bad.safetensors'
    weights.write_bytes(b'not reviewed weights')
    with pytest.raises(ValueError, match='hash mismatch'):
        GenerationCandidate('community', weights)


def test_transforms_preserve_the_two_distinct_upstream_contracts():
    import torch
    image = Image.new('RGB', (512,256), 'black')
    image.paste('white', (144,16,368,240))
    community = build_transform('community')(image)
    modern = build_transform('modern_clip')(image)
    assert community.shape == (3,224,224)
    assert modern.shape == (3,256,256)
    assert torch.allclose(community[0], torch.full((224,224), (1-.485)/.229))
    assert modern[0,128,0] == pytest.approx(-.481/.269)

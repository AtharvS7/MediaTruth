import numpy as np
from PIL import Image
import pytest

from trufor_research import image_array, localization_metrics, verify_artifacts


def test_preprocessing_matches_upstream_scale(tmp_path):
    path = tmp_path / 'image.png'
    Image.new('RGB', (32, 32), 'white').save(path)
    result = image_array(path)
    assert result.shape == (3, 32, 32)
    assert float(result.max()) == 255 / 256
    with pytest.raises(ValueError, match='dimensions'):
        image_array(path, max_pixels=100)


def test_localization_never_inverts_bad_predictions():
    truth = np.array([[0, 1], [1, 0]])
    assert localization_metrics(truth, 1-truth)['iou'] == 0
    assert localization_metrics(truth, truth)['iou'] == 1
    result = localization_metrics(np.zeros((2, 2)), np.ones((2, 2)))
    assert result['iou'] is None
    assert result['false_positive_area_original'] == 1


def test_rejects_nonfinite_or_invalid_maps():
    with pytest.raises(ValueError, match='Invalid'):
        localization_metrics(np.zeros((2, 2)), np.full((2, 2), np.nan))


def test_requires_source_inventory(tmp_path):
    with pytest.raises(ValueError, match='inventory'):
        verify_artifacts(tmp_path, tmp_path/'weights', {})

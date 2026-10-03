from collections import Counter
import io

from PIL import Image
import pytest

from fetch_validation_wave import candidate, pixel_hash


def item(generator=2, label=1):
    return {'row_idx': 23, 'row': {'generator': generator, 'label': label}}


def test_excludes_seen_ids_and_full_generator_quotas():
    assert candidate(item(), Counter(), 25, {'tiny-validation-23'}) is None
    assert candidate(item(), Counter({2: 25}), 25, set()) is None
    assert candidate(item(0, 0), Counter({0: 199}), 25, set()) == ('tiny-validation-23', 0)
    assert candidate(item(0, 0), Counter({0: 200}), 25, set()) is None


@pytest.mark.parametrize('row', [item(0, 1), item(9, 1), item(True, 1),
                                 {**item(), 'truncated_cells': ['image']}])
def test_invalid_annotation_fails_closed(row):
    with pytest.raises(ValueError, match='annotation'):
        candidate(row, Counter(), 25, set())


def test_pixel_dedup_ignores_lossless_encoding():
    image = Image.new('RGB', (64, 32), 'blue')
    a, b = io.BytesIO(), io.BytesIO()
    image.save(a, format='PNG', compress_level=0)
    image.save(b, format='PNG', compress_level=9)
    assert a.getvalue() != b.getvalue()
    assert pixel_hash(a.getvalue()) == pixel_hash(b.getvalue())

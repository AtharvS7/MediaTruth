import hashlib

import pytest

from benchmark_fsd import verify_artifacts


def fixture_artifacts(tmp_path):
    source = tmp_path / 'source'
    (source / 'fsd').mkdir(parents=True)
    (source / 'fsd' / 'fre.py').write_text('reviewed\n')
    weights = tmp_path / 'weights'
    weights.mkdir()
    (weights / 'fre.pt').write_bytes(b'tensor fixture')
    spec = {'patched_source_sha256': {'fre.py': hashlib.sha256(b'reviewed\n').hexdigest()},
            'weights': {'fre.pt': {'bytes': 14, 'sha256': hashlib.sha256(b'tensor fixture').hexdigest()}}}
    return source, weights, spec


def test_modified_upstream_source_rejected_before_import(tmp_path):
    source, weights, spec = fixture_artifacts(tmp_path)
    verify_artifacts(source, weights, spec)
    (source / 'fsd' / 'fre.py').write_text('unreviewed\n')
    with pytest.raises(ValueError, match='source mismatch'):
        verify_artifacts(source, weights, spec)


def test_same_length_modified_weights_rejected_before_loading(tmp_path):
    source, weights, spec = fixture_artifacts(tmp_path)
    (weights / 'fre.pt').write_bytes(b'changed tensor')
    with pytest.raises(ValueError, match='digest mismatch'):
        verify_artifacts(source, weights, spec)

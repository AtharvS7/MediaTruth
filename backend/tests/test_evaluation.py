import hashlib
import json
import pytest
from evaluation import read_manifest, evaluate


def test_manifest_rejects_leakage_between_related_variants(tmp_path):
    rows = []
    for index, split in enumerate(['train', 'test']):
        payload = bytes([index])
        (tmp_path / str(index)).write_bytes(payload)
        rows.append(dict(id=str(index), path=str(index), label='original', source='fixture',
                         license='test-only', sha256=hashlib.sha256(payload).hexdigest(),
                         group_id='same-original', split=split))
    manifest = tmp_path / 'manifest.jsonl'
    manifest.write_text('\n'.join(map(json.dumps, rows)))
    with pytest.raises(ValueError, match='cross dataset splits'):
        read_manifest(manifest)


def test_abstention_is_reported_and_reduces_recall():
    rows = [dict(id='1', label='original', split='test'),
            dict(id='2', label='original', split='test')]
    metrics = evaluate(rows, [dict(id='1', label='original'), dict(id='2', label='inconclusive')])
    assert metrics['coverage'] == 0.5
    assert metrics['per_class']['original']['recall'] == 0.5
    assert metrics['false_positive_rate_originals'] == 0
    with pytest.raises(ValueError, match='exactly one'):
        evaluate(rows, [dict(id='1', label='original')])

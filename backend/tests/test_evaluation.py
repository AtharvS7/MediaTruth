import hashlib
import json
import pytest
from evaluation import read_manifest, evaluate
from evaluation import release_gates, wilson


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


def test_perfect_tiny_benchmark_cannot_enable_a_category():
    rows = [dict(id='1', label='original', split='test', group_id='one')]
    report = release_gates(rows, [dict(id='1', label='original')])
    assert not report['release_gates']['original']['passed']
    assert wilson(0, 0) is None
    assert wilson(0, 200)[1] < .05


def test_independent_perfect_benchmark_passes_but_variants_do_not():
    rows = [dict(id=str(i), label='original' if i < 200 else 'ai_generated',
                 split='test', group_id=str(i)) for i in range(400)]
    predictions = [dict(id=r['id'], label=r['label']) for r in rows]
    result = release_gates(rows, predictions)
    assert result['release_gates']['ai_generated']['passed']
    assert not result['release_gates']['ai_edited']['passed']
    rows[1]['group_id'] = rows[0]['group_id']
    assert not release_gates(rows, predictions)['release_gates']['ai_generated']['passed']

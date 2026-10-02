import hashlib
import json

from PIL import Image
import pytest

import benchmark_generation as benchmark


def manifest_fixture(tmp_path):
    image = tmp_path / 'image.png'
    Image.new('RGB', (32, 32), 'red').save(image)
    digest = hashlib.sha256(image.read_bytes()).hexdigest()
    row = dict(id='one', path=image.name, label='ai_generated', source='test fixture',
               license='test only', sha256=digest, group_id='one', split='test')
    manifest = tmp_path / 'manifest.jsonl'
    manifest.write_text(json.dumps(row) + '\n')
    return manifest, image, digest


def test_failed_inference_is_retained_and_cannot_pass_release(tmp_path, monkeypatch):
    manifest, _, _ = manifest_fixture(tmp_path)

    class BrokenDetector:
        def __init__(self, *args):
            pass

        def predict(self, image):
            raise ValueError('invalid model result')

    monkeypatch.setattr(benchmark, 'GenerationCandidate', BrokenDetector)
    output = tmp_path / 'report.json'
    benchmark.run('community', tmp_path / 'unused', manifest, output)
    report = json.loads(output.read_text())
    assert report['failures'] == 1
    assert report['predictions'][0]['label'] == 'inconclusive'
    assert report['metrics']['per_class']['ai_generated']['recall'] == 0
    assert report['release_eligible'] is False
    assert not report['metrics']['release_gates']['ai_generated']['passed']


def test_jpeg_variant_preserves_source_and_parent_identity(tmp_path, monkeypatch):
    manifest, source, digest = manifest_fixture(tmp_path)

    class RecordingDetector:
        def __init__(self, *args):
            pass

        def predict(self, image):
            assert image.format == 'JPEG'
            return {'label': 'ai_generated', 'score': .75}

    monkeypatch.setattr(benchmark, 'GenerationCandidate', RecordingDetector)
    output = tmp_path / 'report.json'
    benchmark.run('community', tmp_path / 'unused', manifest, output, jpeg_quality=85)
    report = json.loads(output.read_text())
    assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
    assert report['predictions'][0]['sha256'] == digest
    assert report['variant'] == 'jpeg_quality_85'
    assert report['metrics']['samples'] == 1


def test_existing_evidence_is_not_overwritten(tmp_path):
    output = tmp_path / 'existing.json'
    output.write_text('preserve')
    with pytest.raises(ValueError, match='Preserve existing'):
        benchmark.run('community', tmp_path / 'unused', tmp_path / 'unused', output)
    assert output.read_text() == 'preserve'

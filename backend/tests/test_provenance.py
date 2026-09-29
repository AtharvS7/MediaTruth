from PIL import Image
from inference_pipeline.provenance import inspect_provenance


def test_unsigned_image_is_absent_not_authentic(tmp_path):
    path = tmp_path / 'ordinary.png'
    Image.new('RGB', (20, 20)).save(path)
    result = inspect_provenance(str(path))
    assert result['status'] == 'absent'
    assert result['network_access'] is False
    assert result['watermark_status'] == 'not_checked'
    assert result['actions'] == []


def test_corrupt_data_never_becomes_verified(tmp_path):
    path = tmp_path / 'broken.jpg'
    path.write_bytes(b'not an image')
    assert inspect_provenance(str(path))['status'] not in ('trusted', 'valid_untrusted')

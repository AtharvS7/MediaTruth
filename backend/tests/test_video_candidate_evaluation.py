import numpy as np
import pytest

from video_candidate_evaluation import validate_manifest, score_video


def manifest(tmp_path):
    (tmp_path / "one").write_bytes(b"one")
    (tmp_path / "two").write_bytes(b"two")
    return {"samples": [dict(id=name, path=name, source_id="source", kind="video", label="real",
                             split="pilot", rights_note="owned synthetic test") for name in ["one", "two"]]}


def test_manifest_rejects_source_leakage(tmp_path):
    data = manifest(tmp_path)
    data["samples"][1]["split"] = "validation"
    with pytest.raises(ValueError, match="Source overlap"):
        validate_manifest(data, tmp_path)


def test_manifest_rejects_duplicates(tmp_path):
    data = manifest(tmp_path)
    (tmp_path / "two").write_bytes(b"one")
    with pytest.raises(ValueError, match="Duplicate sample bytes"):
        validate_manifest(data, tmp_path)


def test_manifest_requires_rights_note(tmp_path):
    data = manifest(tmp_path)
    data["samples"][0]["rights_note"] = ""
    with pytest.raises(ValueError, match="rights note"):
        validate_manifest(data, tmp_path)


def test_manifest_rejects_escaping_path(tmp_path):
    data = manifest(tmp_path)
    data['samples'][0]['path'] = '../outside.mp4'
    with pytest.raises(ValueError, match='escapes'):
        validate_manifest(data, tmp_path)


def test_manifest_rejects_changed_content(tmp_path):
    data = manifest(tmp_path)
    data['samples'][0]['sha256'] = '0' * 64
    with pytest.raises(ValueError, match='declared hash'):
        validate_manifest(data, tmp_path)


@pytest.mark.parametrize("boxes", [[], [(0, 0, 48, 48), (50, 0, 48, 48)]])
def test_no_or_multiple_faces_abstain(monkeypatch, boxes):
    import video_candidate_evaluation as module
    monkeypatch.setattr(module, "get_video_metadata", lambda _: {"frame_count": 100})
    monkeypatch.setattr(module, "extract_frames", lambda *a, **k: ([np.zeros((100, 100, 3), np.uint8)] * 3, [0, 1, 2]))
    class Detector:
        def detect_faces(self, *args, **kwargs):
            return boxes
    result = score_video(None, "test", Detector())
    assert result["fake_score"] is None
    assert result["frames_scored"] == 0
    assert result["abstention_reason"] == "insufficient_single_face_coverage"


def test_single_face_coverage_and_score(monkeypatch):
    import video_candidate_evaluation as module
    monkeypatch.setattr(module, "get_video_metadata", lambda _: {"frame_count": 100})
    monkeypatch.setattr(module, "extract_frames", lambda *a, **k: ([np.zeros((64, 64, 3), np.uint8)] * 3, [0, 1, 2]))
    class Detector:
        def detect_faces(self, *args, **kwargs):
            return [(0, 0, 48, 48)]
    class Model:
        def score_face(self, image):
            return .75
    result = score_video(Model(), "test", Detector())
    assert result["fake_score"] == .75
    assert result["frames_scored"] == 3
    assert result["abstention_reason"] is None

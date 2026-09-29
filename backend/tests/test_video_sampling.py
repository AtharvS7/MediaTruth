import cv2
import numpy as np
from utils.video_utils import extract_frames


def test_scene_sampling_is_bounded_and_preserves_timestamps(tmp_path):
    path = str(tmp_path / 'scenes.avi')
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*'MJPG'), 10, (64, 64))
    assert writer.isOpened()
    for i in range(40):
        writer.write(np.full((64, 64, 3), 0 if i < 17 else 255, dtype=np.uint8))
    writer.release()
    frames, times = extract_frames(path, max_frames=4)
    assert len(frames) == len(times) == 4
    assert times == sorted(times)
    assert times[0] == 0
    assert any(1.7 <= t <= 2.0 for t in times)
    assert all(f.shape[:2] == (64,64) for f in frames)

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from PIL import Image
import pytest

import benchmark_fsd


def setup_run(tmp_path, monkeypatch, predictor):
    rows=[]
    for i,color in enumerate(['red','blue']):
        path=tmp_path/f'{i}.png'
        Image.new('RGB',(32,32),color).save(path)
        rows.append(dict(id=str(i),path=path.name,label='original',source='test',license='test',
                         sha256=hashlib.sha256(path.read_bytes()).hexdigest(),group_id=str(i),split='validation'))
    manifest=tmp_path/'validation.jsonl'
    manifest.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    source=tmp_path/'source'
    module=SimpleNamespace(__file__=str(source/'fsd/__init__.py'),
                           FSDDetector=SimpleNamespace(load=lambda **kwargs:SimpleNamespace(score=predictor)))
    monkeypatch.setitem(benchmark_fsd.sys.modules,'fsd',module)
    monkeypatch.setattr(benchmark_fsd,'verify_artifacts',lambda *args:None)
    return source,manifest,tmp_path/'result.json'


def test_interrupted_run_resumes_without_rescoring_completed_images(tmp_path,monkeypatch):
    calls=[]
    def interrupted(image):
        calls.append(image.getpixel((0,0)))
        if len(calls)==2:
            raise KeyboardInterrupt()
        return SimpleNamespace(z_score=0.0,threshold=-2,is_fake=False)
    source,manifest,output=setup_run(tmp_path,monkeypatch,interrupted)
    with pytest.raises(KeyboardInterrupt):
        benchmark_fsd.run(source,tmp_path,manifest,output,split='validation')
    assert not output.exists()
    assert len(Path(str(output)+'.checkpoint.jsonl').read_text().splitlines())==2
    benchmark_fsd.run(source,tmp_path,manifest,output,split='validation',resume=True)
    assert len(calls)==3
    report=json.loads(output.read_text())
    assert report['evaluation_split']=='validation'
    assert len(report['predictions'])==2
    assert report['release_eligible'] is False


def test_checkpoint_rejects_changed_execution_config(tmp_path,monkeypatch):
    def interrupted(image):
        raise KeyboardInterrupt()
    source,manifest,output=setup_run(tmp_path,monkeypatch,interrupted)
    with pytest.raises(KeyboardInterrupt):
        benchmark_fsd.run(source,tmp_path,manifest,output,split='validation')
    with pytest.raises(ValueError,match='configuration mismatch'):
        benchmark_fsd.run(source,tmp_path,manifest,output,split='validation',threads=4,resume=True)

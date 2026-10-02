import hashlib
import json

import pytest

import run_calibration_experiment as experiment


def fixture(tmp_path, monkeypatch, missing_score=False):
    dataset=tmp_path/'data'
    dataset.mkdir()
    for split in ('validation','test'):
        rows=[dict(id=f'{split}-{i}',sha256=f'{split}-{i}',group_id=f'{split}-{i}',split=split,
                   label='original' if i<24 else 'ai_generated') for i in range(48)]
        (dataset/f'{split}.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    read=lambda path:[json.loads(line) for line in path.read_text().splitlines()]
    monkeypatch.setattr(experiment,'read_manifest',read)
    monkeypatch.setattr(experiment,'__file__',str(tmp_path/'backend/run_calibration_experiment.py'))
    destination=tmp_path/'reports'
    events=[]
    def fake_run(source,weights,manifest,output,split='test',threads=4,jpeg_quality=None,resume=False):
        if split=='test':
            assert (destination/'frozen-policy.json').exists()
        events.append((split,jpeg_quality))
        rows=read(manifest)
        predictions=[dict(id=r['id'],sha256=r['sha256'],label=r['label'],available=True,
                          z_score=0 if r['label']=='original' else -10) for r in rows]
        if missing_score:
            predictions.pop()
        output.write_text(json.dumps({'predictions':predictions,'artifacts':{'revision':'fixture'},
            'software_versions':{'runtime':'fixture'},'evaluation_split':split,'cpu_threads':threads,
            'manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest()}))
    monkeypatch.setattr(experiment,'run',fake_run)
    return dataset,destination,events


def test_policy_is_frozen_before_holdout_and_jpeg_variants(tmp_path,monkeypatch):
    dataset,destination,events=fixture(tmp_path,monkeypatch)
    experiment.experiment(tmp_path,tmp_path,dataset,destination)
    assert events==[('validation',None),('test',None),('test',85)]
    result=json.loads((destination/'holdout-comparison.json').read_text())
    assert result['calibrated']['accuracy']==1
    assert not result['calibrated']['statistical_target_passed']
    assert not result['release_eligible']


def test_incomplete_calibration_never_reaches_holdout(tmp_path,monkeypatch):
    dataset,destination,events=fixture(tmp_path,monkeypatch,missing_score=True)
    with pytest.raises(ValueError,match='entire partition'):
        experiment.experiment(tmp_path,tmp_path,dataset,destination)
    assert events==[('validation',None)]
    assert not (destination/'frozen-policy.json').exists()

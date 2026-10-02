"""Score calibration, freeze a policy, then evaluate untouched holdout images locally."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from benchmark_fsd import run
from calibrate_generation import fit_threshold, score_holdout
from evaluation import binary_production_gates, read_manifest


def experiment(source, weights, dataset, destination, threads=4):
    destination.mkdir(parents=True,exist_ok=True)
    def status(phase):
        (destination/'status.json').write_text(json.dumps({'phase':phase,
            'updated_at':datetime.now(timezone.utc).isoformat(),'release_eligible':False},indent=2))
    status('checking_dataset')
    calibration_manifest=dataset/'validation.jsonl'
    test_manifest=dataset/'test.jsonl'
    calibration_rows=read_manifest(calibration_manifest)
    test_rows=read_manifest(test_manifest)
    for rows,split in [(calibration_rows,'validation'),(test_rows,'test')]:
        if len(rows)!=48 or any(r['split']!=split for r in rows):
            raise ValueError('This predeclared pilot requires 48 samples in each partition')
        if any(sum(r['label']==label for r in rows)!=24 for label in ['original','ai_generated']):
            raise ValueError('Each partition requires 24 originals and 24 generated images')
    if {r['group_id'] for r in calibration_rows}&{r['group_id'] for r in test_rows}:
        raise ValueError('Cross-partition parent overlap')
    calibration=destination/'calibration.json'
    status('scoring_calibration')
    if not calibration.exists():
        run(source,weights,calibration_manifest,calibration,split='validation',threads=threads,resume=True)
    calibration_report=json.loads(calibration.read_text())
    if calibration_report['evaluation_split']!='validation' or calibration_report['cpu_threads']!=threads:
        raise ValueError('Saved calibration execution configuration differs')
    if calibration_report['manifest_sha256']!=hashlib.sha256(calibration_manifest.read_bytes()).hexdigest():
        raise ValueError('Saved calibration report has different inputs')
    policy=fit_threshold(calibration_rows,calibration_report['predictions'])
    policy['calibration_report_sha256']=hashlib.sha256(calibration.read_bytes()).hexdigest()
    policy_path=destination/'frozen-policy.json'
    if policy_path.exists():
        if json.loads(policy_path.read_text())!=policy:
            raise ValueError('Frozen policy changed; start a new experiment')
    else:
        with policy_path.open('x',encoding='utf-8') as stream:
            json.dump(policy,stream,indent=2,allow_nan=False)
    print(json.dumps({'phase':'policy_frozen','threshold':policy['threshold'],
                      'calibration_fpr':policy['calibration_fpr']}),flush=True)
    # Prior diagnostics are checked only after fitting; they are never optimization inputs.
    root=Path(__file__).resolve().parents[1]
    diagnostic=root/'evaluation/reports/fsd-all-20261002.json'
    diagnostic_manifests=[root/'evaluation/data'/name/'manifest.jsonl'
                         for name in ('safeimg-pilot-20261001','commfor-controls-20261002-v2')]
    if diagnostic.exists() and all(path.exists() for path in diagnostic_manifests):
        raw=json.loads(diagnostic.read_text())
        if raw['source_revision']!=calibration_report['artifacts']['revision']:
            raise ValueError('Prior diagnostic model identity differs')
        diagnostic_rows=[row for path in diagnostic_manifests for row in read_manifest(path)]
        metrics,_=score_holdout(policy,diagnostic_rows,raw['predictions'])
        diagnostic_output=destination/'prior-diagnostic-comparison.json'
        if not diagnostic_output.exists():
            with diagnostic_output.open('x',encoding='utf-8') as stream:
                json.dump({'scope':'Previously inspected diagnostic set, not an independent holdout',
                           'policy_sha256':hashlib.sha256(policy_path.read_bytes()).hexdigest(),
                           'calibrated':metrics,'release_eligible':False},stream,indent=2)
    # Holdout inference starts only after the policy has been frozen on disk.
    for quality in (None,85):
        name='holdout' if quality is None else 'holdout-jpeg85'
        status('scoring_'+name)
        output=destination/f'{name}.json'
        if not output.exists():
            run(source,weights,test_manifest,output,jpeg_quality=quality,threads=threads,resume=True)
        report=json.loads(output.read_text())
        if report['manifest_sha256']!=hashlib.sha256(test_manifest.read_bytes()).hexdigest():
            raise ValueError('Saved holdout report has different inputs')
        if report['artifacts']!=calibration_report['artifacts'] or report['software_versions']!=calibration_report['software_versions']:
            raise ValueError('Calibration and holdout model environments differ')
        _,predictions=score_holdout(policy,test_rows,report['predictions'])
        comparison={'release_eligible':False,'policy_sha256':hashlib.sha256(policy_path.read_bytes()).hexdigest(),
                    'baseline':binary_production_gates(test_rows,report['predictions']),
                    'calibrated':binary_production_gates(test_rows,predictions),
                    'predictions':predictions,
                    'note':'Public research pilot; no independent provenance or production approval'}
        result=destination/f'{name}-comparison.json'
        if not result.exists():
            with result.open('x',encoding='utf-8') as stream:
                json.dump(comparison,stream,indent=2,allow_nan=False)
        print(json.dumps({'phase':name,'baseline_balanced_accuracy':comparison['baseline']['balanced_accuracy'],
                          'calibrated_balanced_accuracy':comparison['calibrated']['balanced_accuracy']}),flush=True)
    status('complete_research_only')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('source','weights','dataset','destination'):
        parser.add_argument(name,type=Path)
    parser.add_argument('--threads',type=int,choices=range(1,5),default=4)
    args=parser.parse_args()
    try:
        experiment(args.source,args.weights,args.dataset,args.destination,args.threads)
    except Exception as error:
        args.destination.mkdir(parents=True,exist_ok=True)
        (args.destination/'status.json').write_text(json.dumps({'phase':'failed',
            'failure_type':type(error).__name__,'updated_at':datetime.now(timezone.utc).isoformat()}))
        raise

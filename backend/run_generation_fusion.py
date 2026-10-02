"""Fit or evaluate the predeclared experimental combiner; no automatic promotion."""
import argparse
import hashlib
import json
from pathlib import Path

from evaluation import binary_production_gates, read_manifest
from generation_fusion import fit, predict


def run(mode,manifest,fsd,community,output,state_path=None):
    if output.exists():
        raise ValueError('Preserve existing evidence; choose a new output')
    rows=read_manifest(manifest)
    a,b=(json.loads(path.read_text()) for path in (fsd,community))
    digest=hashlib.sha256(manifest.read_bytes()).hexdigest()
    for report in (a,b):
        if report.get('manifest_sha256')!=digest:
            raise ValueError('Score report was not generated from this manifest')
    if mode=='fit':
        if any(report.get('evaluation_split')!='validation' for report in (a,b)):
            raise ValueError('Fit requires calibration reports')
        result=fit(rows,a,b)
    else:
        state=json.loads(state_path.read_text())
        predictions=predict(state,rows,a,b)
        result={'release_eligible':False,'scope':'Development comparison on previously inspected data',
                'metrics':binary_production_gates(rows,predictions),'predictions':predictions,
                'fitted_state_sha256':hashlib.sha256(state_path.read_bytes()).hexdigest()}
    result['input_report_sha256']={name:hashlib.sha256(path.read_bytes()).hexdigest()
                                  for name,path in [('fsd',fsd),('community',community)]}
    result['manifest_sha256']=digest
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as stream:
        json.dump(result,stream,indent=2,allow_nan=False)
    print(json.dumps({'mode':mode,'output':str(output),'accuracy':result.get('metrics',{}).get('accuracy')}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('fit','evaluate'))
    for name in ('manifest','fsd','community','output'):
        parser.add_argument(name,type=Path)
    parser.add_argument('--state',type=Path)
    args=parser.parse_args()
    if args.mode=='evaluate' and args.state is None:
        parser.error('--state is required for evaluation')
    run(args.mode,args.manifest,args.fsd,args.community,args.output,args.state)

"""Experimental two-feature combiner. No production or calibrated-probability claim."""
import math

import numpy as np


def model_contract(fsd_report, community_report):
    return {'fsd':fsd_report['artifacts'], 'community':community_report['model']}


def features(rows, fsd_report, community_report):
    indexed=[]
    for report in (fsd_report,community_report):
        predictions=report['predictions']
        table={p['id']:p for p in predictions}
        if len(table)!=len(predictions) or set(table)!={r['id'] for r in rows}:
            raise ValueError('Exactly one prediction per sample is required')
        indexed.append(table)
    values,available=[],[]
    for row in rows:
        a,b=(table[row['id']] for table in indexed)
        if any(p.get('sha256')!=row['sha256'] for p in (a,b)):
            raise ValueError('Model input content differs from manifest')
        z,p=a.get('z_score'),b.get('score')
        valid=(a.get('available') is not False and b.get('available') is not False
               and z is not None and p is not None and math.isfinite(z) and math.isfinite(p)
               and 0<=p<=1)
        available.append(valid)
        if valid:
            p=min(max(p,1e-6),1-1e-6)
            values.append([min(max(-z,-50),50),math.log(p/(1-p))])
        else:
            values.append([0,0])
    return np.asarray(values,dtype=np.float64),available


def fit(rows,fsd_report,community_report):
    if not rows or any(r['split']!='validation' for r in rows):
        raise ValueError('Fit requires validation-only rows, never test rows')
    if {r['label'] for r in rows}!={'original','ai_generated'}:
        raise ValueError('Both binary classes required')
    for field in ('id','group_id','sha256'):
        if len({r[field] for r in rows})!=len(rows):
            raise ValueError('Repeated calibration sample or parent')
    x,available=features(rows,fsd_report,community_report)
    if not all(available):
        raise ValueError('Cannot fit by silently dropping failed calibration predictions')
    center=x.mean(axis=0)
    scale=x.std(axis=0)
    scale=np.where(scale<1e-8,1.0,scale)
    x=(x-center)/scale
    y=np.array([r['label']=='ai_generated' for r in rows],dtype=np.float64)
    weights=np.zeros(2,dtype=np.float64)
    intercept=0.0
    for _ in range(2000):
        logits=np.clip(x@weights+intercept,-50,50)
        residual=1/(1+np.exp(-logits))-y
        weights-=.05*(x.T@residual/len(rows)+.1*weights)
        intercept-=.05*residual.mean()
    return {'schema_version':1,'release_eligible':False,'model_contract':model_contract(fsd_report,community_report),
            'center':center.tolist(),'scale':scale.tolist(),'weights':weights.tolist(),'intercept':float(intercept),
            'threshold':.5,'l2':.1,'iterations':2000,'learning_rate':.05,
            'calibration_groups':[r['group_id'] for r in rows],
            'calibration_hashes':[r['sha256'] for r in rows],
            'score_semantics':'experimental logistic score; not a validated probability'}


def predict(state,rows,fsd_report,community_report):
    if model_contract(fsd_report,community_report)!=state['model_contract']:
        raise ValueError('Input model identities differ from fitted model')
    if any(r['split']!='test' for r in rows):
        raise ValueError('Evaluation requires test rows')
    if any(r['group_id'] in state['calibration_groups'] or r['sha256'] in state['calibration_hashes'] for r in rows):
        raise ValueError('Calibration/evaluation overlap')
    x,available=features(rows,fsd_report,community_report)
    logits=np.clip(((x-np.array(state['center']))/np.array(state['scale']))@np.array(state['weights'])+state['intercept'],-50,50)
    scores=1/(1+np.exp(-logits))
    return [{'id':r['id'],'sha256':r['sha256'],'available':valid,
             'label':('ai_generated' if score>state['threshold'] else 'original') if valid else 'inconclusive',
             'score':float(score) if valid else None} for r,score,valid in zip(rows,scores,available)]

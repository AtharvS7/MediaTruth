import pytest

from calibrate_generation import fit_threshold, score_holdout
from evaluation import binary_production_gates


def data(split='validation'):
    rows=[dict(id=str(i),group_id=str(i),sha256=str(i),split=split,
               label='original' if i<2 else 'ai_generated') for i in range(4)]
    scores=[dict(id=str(i),sha256=str(i),z_score=s,available=True)
            for i,s in enumerate([0,-3,-2,-10])]
    return rows,scores


def test_fit_reduces_false_flags_without_fitting_test_data():
    rows,scores=data()
    policy=fit_threshold(rows,scores)
    assert policy['calibration_fpr']==0
    assert policy['calibration_recall']==.5
    assert policy['threshold']==-3
    assert policy['release_eligible'] is False
    with pytest.raises(ValueError,match='test data is forbidden'):
        fit_threshold(data('test')[0],scores)


def test_same_threshold_direction_is_used_for_holdout():
    rows,scores=data()
    policy=fit_threshold(rows,scores)
    test_rows=[{**r,'split':'test','group_id':'test-'+r['id'],'sha256':'test-'+r['id']} for r in rows]
    test_scores=[{**p,'sha256':'test-'+p['id']} for p in scores]
    metrics,guesses=score_holdout(policy,test_rows,test_scores)
    assert [g['label'] for g in guesses]==['original','original','original','ai_generated']
    assert metrics['false_positive_rate_originals']==0


def test_calibration_rejects_missing_or_nonfinite_scores():
    rows,scores=data()
    with pytest.raises(ValueError,match='entire partition'):
        fit_threshold(rows,scores[:-1])
    scores[0]['z_score']=float('nan')
    with pytest.raises(ValueError,match='Incomplete'):
        fit_threshold(rows,scores)


def test_changed_content_and_cross_partition_parents_rejected():
    rows,scores=data()
    policy=fit_threshold(rows,scores)
    with pytest.raises(ValueError,match='leakage'):
        score_holdout(policy,[{**r,'split':'test'} for r in rows],scores)
    scores[0]['sha256']='different'
    with pytest.raises(ValueError,match='content'):
        fit_threshold(rows,scores)


def test_class_imbalance_cannot_fake_95_percent_quality():
    rows=[dict(id=str(i),group_id=str(i),split='test',independence_verified=True,
               label='original' if i<950 else 'ai_generated') for i in range(1000)]
    predictions=[dict(id=r['id'],label='original') for r in rows]
    report=binary_production_gates(rows,predictions)
    assert report['accuracy']==.95
    assert report['balanced_accuracy']==.5
    assert not report['statistical_target_passed']


def test_perfect_tiny_set_still_fails_production_target():
    rows,_=data('test')
    report=binary_production_gates(rows,[dict(id=r['id'],label=r['label']) for r in rows])
    assert report['accuracy']==1
    assert not report['statistical_target_passed']

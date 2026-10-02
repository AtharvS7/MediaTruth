import copy

import pytest

from generation_fusion import fit, predict


def fixture(split='validation'):
    rows=[dict(id=str(i),group_id=f'{split}-{i}',sha256=f'{split}-{i}',split=split,
               label='original' if i<3 else 'ai_generated') for i in range(6)]
    a={'artifacts':{'revision':'pinned'},'predictions':[
        dict(id=r['id'],sha256=r['sha256'],z_score=0 if i<3 else -10,available=True) for i,r in enumerate(rows)]}
    b={'model':{'revision':'pinned'},'predictions':[
        dict(id=r['id'],sha256=r['sha256'],score=.1 if i<3 else .9,available=True) for i,r in enumerate(rows)]}
    return rows,a,b


def test_fit_rejects_test_rows_and_unavailable_calibration_scores():
    with pytest.raises(ValueError,match='validation-only'):
        fit(*fixture('test'))
    rows,a,b=fixture()
    a['predictions'][0]['z_score']=float('nan')
    with pytest.raises(ValueError,match='dropping'):
        fit(rows,a,b)


def test_reproducible_fit_and_missing_feature_abstention():
    state=fit(*fixture())
    assert state==fit(*fixture())
    rows,a,b=fixture('test')
    b['predictions'][0]['available']=False
    results=predict(state,rows,a,b)
    assert results[0]['label']=='inconclusive'
    assert results[0]['score'] is None
    assert [p['label'] for p in results[1:]]==['original','original','ai_generated','ai_generated','ai_generated']
    assert state['release_eligible'] is False


def test_input_identity_and_model_identity_are_enforced():
    state=fit(*fixture())
    rows,a,b=fixture('test')
    changed=copy.deepcopy(b)
    changed['model']['revision']='different'
    with pytest.raises(ValueError,match='model identities'):
        predict(state,rows,a,changed)
    a['predictions'][0]['sha256']='different'
    with pytest.raises(ValueError,match='content'):
        predict(state,rows,a,b)


def test_no_calibration_parent_can_be_evaluated_as_holdout():
    rows,a,b=fixture()
    state=fit(rows,a,b)
    with pytest.raises(ValueError,match='overlap'):
        predict(state,[{**r,'split':'test'} for r in rows],a,b)

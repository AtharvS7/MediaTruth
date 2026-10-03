import pytest

from calibrate_two_tail import fit, predict


def data(split='validation'):
    rows = [dict(id=str(i), sha256=f'{split}-{i}', group_id=f'{split}-{i}', split=split,
                 label='original' if i < 2 else 'ai_generated') for i in range(4)]
    scores = [dict(id=r['id'], sha256=r['sha256'], available=True, z_score=z)
              for r, z in zip(rows, [-1., .4, -5., .6])]
    return rows, scores


def test_fit_uses_only_original_bounds():
    policy = fit(*data())
    assert (policy['lower'], policy['upper']) == (-1., .4)
    rows, scores = data('test')
    _, guesses = predict(policy, rows, scores)
    assert [g['label'] for g in guesses] == [r['label'] for r in rows]
    assert policy['release_eligible'] is False


def test_missing_score_is_abstention_not_original():
    policy = fit(*data())
    rows, scores = data('test')
    scores[0]['z_score'] = float('nan')
    metrics, guesses = predict(policy, rows, scores)
    assert guesses[0]['label'] == 'inconclusive'
    assert metrics['coverage'] == .75


def test_leakage_and_test_fitting_rejected():
    with pytest.raises(ValueError, match='test data is forbidden'):
        fit(*data('test'))
    policy = fit(*data())
    rows, scores = data()
    with pytest.raises(ValueError, match='leakage'):
        predict(policy, [{**r, 'split': 'test'} for r in rows], scores)

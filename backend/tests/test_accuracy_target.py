import pytest

from evaluation import binary_production_gates, binary_slices


def samples(correct_ai):
    rows = [dict(id=str(i), group_id=str(i), split='test', independence_verified=True,
                 generator='Real' if i < 1000 else 'ExampleAI', source='fixture',
                 label='original' if i < 1000 else 'ai_generated') for i in range(2000)]
    guesses = [dict(id=r['id'], label=r['label'] if i < 1000+correct_ai else 'original')
               for i, r in enumerate(rows)]
    return rows, guesses


def test_exactly_90_recall_is_not_above_90():
    result = binary_production_gates(*samples(900))
    assert result['accuracy'] == .95
    assert not result['production_target_checks']['each_class_recall_above_90']
    assert not result['statistical_target_passed']


def test_above_90_can_pass_without_requiring_95_recall():
    result = binary_production_gates(*samples(930))
    assert result['statistical_target_passed']
    assert not result['deployment_approved']
    assert result['target_policy']['confidence_level'] == .95


def test_slices_expose_blind_spot_and_count_abstention_as_failure():
    rows, guesses = samples(930)
    rows[-1]['generator'] = 'Unseen'
    guesses[-1]['label'] = 'inconclusive'
    result = binary_slices(rows, guesses)['generator']['Unseen']
    assert result['accuracy'] == 0
    assert result['coverage'] == 0
    assert result['abstentions'] == 1
    with pytest.raises(ValueError, match='exactly one'):
        binary_slices(rows, guesses[:-1])

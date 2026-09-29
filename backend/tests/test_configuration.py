import pytest
from utils.configuration import validate_configuration
from services.evidence import public_report


def test_misplaced_secret_is_rejected_without_echo():
    with pytest.raises(RuntimeError) as exc:
        validate_configuration({'SUPABASE_URL': 'https://example.test',
                                'SUPABASE_SERVICE_KEY': 'fixture', 'USE_HF_API': 'hf_secret'})
    assert 'hf_secret' not in str(exc.value)
    assert 'HF_TOKEN' in str(exc.value)


def test_unvalidated_scores_never_become_public_verdicts():
    source = {'final_verdict': 'AI Generated', 'confidence': .99,
              'ai_generated_probability': .99, 'provenance': {'status': 'trusted'},
              'per_frame_results': [{'final_verdict': 'Authentic / Original'}]}
    result = public_report(source)
    assert result['final_verdict'] == 'Inconclusive'
    assert result['per_frame_results'][0]['final_verdict'] == 'Inconclusive'
    assert result['provenance'] == source['provenance']
    assert source['final_verdict'] == 'AI Generated'

"""Public reports abstain until independent validation enables a capability.

No category currently has an approved independent benchmark. Raw detector
outputs are retained as experimental evidence, never presented as probabilities.
"""


def public_report(result):
    report = dict(result)
    report.update(report_schema_version=2, processing_version='2.0.0',
                  final_verdict='Inconclusive', confidence=0.0, limited_mode=True,
                  score_semantics='withheld_pending_validation',
                  validation_status='not_validated',
                  explanation='Detection verdict withheld: independent evaluation has not passed. '
                              'Provenance and metadata findings are reported separately.')
    for key in ('ai_generated_probability', 'ai_edited_probability',
                'traditional_edit_probability', 'authentic_probability'):
        report[key] = 0.0  # Legacy numeric columns; schema v2 UI must treat as unavailable.
    report['origin_assessment'] = {'status': 'not_validated', 'verdict': 'inconclusive'}
    report['editing_assessment'] = {'status': 'not_validated', 'verdict': 'inconclusive'}
    report['localization'] = {'status': 'not_validated', 'kind': 'diagnostic_only'}
    report['manipulation_heatmap'] = None
    if 'per_frame_results' in report:
        report['per_frame_results'] = [public_report(frame) for frame in report['per_frame_results']]
    return report

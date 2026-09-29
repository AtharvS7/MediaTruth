"""Atomic report persistence: a failed RPC must never fall back to partial inserts."""
import asyncio
from unittest.mock import MagicMock
import pytest
from services.supabase_service import SupabaseService


def service():
    result = SupabaseService.__new__(SupabaseService)
    result.client = MagicMock()
    return result


def test_failure_propagates_without_nontransactional_fallback():
    svc = service()
    svc.client.rpc.return_value.execute.side_effect = RuntimeError('transaction failed')
    with pytest.raises(RuntimeError, match='transaction failed'):
        asyncio.run(svc.save_scan('scan', 'owner', 'image', 'x.png', {}, 'a' * 64))
    svc.client.table.assert_not_called()


def test_report_payload_bounded_by_removing_heatmaps_without_mutating_response():
    svc = service()
    report = {'manipulation_heatmap': 'large', 'per_frame_results': [
        {'manipulation_heatmap': 'large', 'verdict': 'Inconclusive'}]}
    asyncio.run(svc.save_scan('scan', 'owner', 'video', 'x.mp4', report, 'b' * 64))
    name, params = svc.client.rpc.call_args.args
    assert name == 'save_scan_atomic'
    assert params['p_input_sha256'] == 'b' * 64
    assert params['p_result'] == {'per_frame_results': [{'verdict': 'Inconclusive'}]}
    assert report['manipulation_heatmap'] == 'large'
    assert report['per_frame_results'][0]['manipulation_heatmap'] == 'large'
    svc.client.table.assert_not_called()

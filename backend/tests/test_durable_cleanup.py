import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from services.durable_jobs import DurableJobs


def coordinator(age_hours=1):
    db = DurableJobs.__new__(DurableJobs)
    db.bucket = MagicMock()
    db.client = MagicMock()
    query = MagicMock()
    db.client.table.return_value = query
    for name in ('select', 'in_', 'or_', 'order', 'limit', 'update', 'eq'):
        getattr(query, name).return_value = query
    row = {'owner': 'owner', 'id': 'job',
           'created_at': (datetime.now(timezone.utc)-timedelta(hours=age_hours)).isoformat()}
    query.execute.return_value.data = [row]
    return db, query


def test_failed_storage_delete_does_not_release_quota():
    db, query = coordinator()
    db.bucket.remove.side_effect = RuntimeError('storage unavailable')
    asyncio.run(db.cleanup())
    query.update.assert_not_called()


def test_recent_terminal_job_keeps_export():
    db, query = coordinator()
    asyncio.run(db.cleanup())
    db.bucket.remove.assert_called_once_with(['owner/job/input'])
    query.update.assert_called_once_with({'input_deleted': True})


def test_expired_job_sweeps_late_input_and_export():
    db, query = coordinator(25)
    asyncio.run(db.cleanup())
    db.bucket.remove.assert_called_once_with(['owner/job/input', 'owner/job/output.png'])
    query.update.assert_called_once_with({'input_deleted': True, 'output_deleted': True})

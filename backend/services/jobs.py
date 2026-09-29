"""Bounded local jobs with killable inference and owner-scoped status.

Single API process only. Pending work does not survive a restart; saved reports do.
"""
import asyncio
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import uuid

from services.supabase_service import SupabaseService
from utils.file_utils import cleanup_temp_file, file_sha256


class QueueFull(Exception):
    pass


@dataclass
class Job:
    id: str
    owner: str
    kind: str
    path: str
    filename: str
    status: str = "queued"
    stage: str = "queued"
    error: str | None = None
    result: dict | None = None
    task: asyncio.Task | None = None
    created: float = field(default_factory=time.monotonic)


async def run_isolated(job: Job, timeout=300):
    """Cancellation and timeout wait for native work to die before file cleanup."""
    with tempfile.TemporaryDirectory(prefix="mediatruth_worker_") as folder:
        output, progress = Path(folder) / "result.json", Path(folder) / "progress"
        env = {key: value for key, value in os.environ.items()
               if not any(word in key.upper() for word in ("SUPABASE", "SECRET", "TOKEN", "PASSWORD"))}
        env.update(USE_HF_API="false", ALLOW_MODEL_DOWNLOADS="false", OMP_NUM_THREADS="2",
                   MKL_NUM_THREADS="2", TMP=folder, TEMP=folder, TMPDIR=folder)
        launch = asyncio.create_task(asyncio.create_subprocess_exec(
            sys.executable, "-m", "services.analysis_worker", "--kind", job.kind,
            "--input", job.path, "--output", str(output), "--progress", str(progress), "--id", job.id,
            cwd=str(Path(__file__).resolve().parents[1]), env=env,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
        ))
        try:
            process = await asyncio.shield(launch)
        except asyncio.CancelledError:
            process = await launch
            if process.returncode is None:
                process.kill()
            await process.wait()
            raise
        try:
            async with asyncio.timeout(timeout):
                while process.returncode is None:
                    if progress.exists():
                        stage = progress.read_text(encoding="utf-8").strip()
                        if stage in {"loading_models", "analyzing"}:
                            job.stage = stage
                    try:
                        await asyncio.wait_for(process.wait(), 0.25)
                    except asyncio.TimeoutError:
                        pass
                if process.returncode != 0 or not output.exists():
                    raise ValueError("Media could not be analyzed. Check its format and duration.")
                if output.stat().st_size > (80 if job.kind == "clean" else 8) * 1024 * 1024:
                    raise ValueError("Analysis report exceeds size limit.")
                if job.kind == "clean":
                    return output.read_bytes()
                return json.loads(output.read_text(encoding="utf-8"))
        finally:
            if process.returncode is None:
                process.kill()
            await process.wait()


class JobManager:
    def __init__(self, runner=run_isolated, database_factory=SupabaseService):
        self.jobs = {}
        self.slot = asyncio.Semaphore(1)
        self.runner, self.database_factory = runner, database_factory

    def submit(self, owner, kind, path, filename):
        self.prune()
        if sum(job.status in {"queued", "running", "saving"} for job in self.jobs.values()) >= 3:
            raise QueueFull()
        if any(job.owner == owner and job.status in {"queued", "running", "saving"}
               for job in self.jobs.values()):
            raise QueueFull()
        job = Job(str(uuid.uuid4()), owner, kind, path, filename)
        self.jobs[job.id] = job
        job.task = asyncio.create_task(self._execute(job))
        return job

    def prune(self):
        finished = [job for job in self.jobs.values() if job.status in {"completed", "failed", "cancelled"}]
        for job in sorted(finished, key=lambda value: value.created):
            if time.monotonic() - job.created > 3600 or len(self.jobs) >= 100:
                self.jobs.pop(job.id, None)

    async def _execute(self, job):
        try:
            async with self.slot:
                job.status = "running"
                result = await self.runner(job)
                job.status = job.stage = "saving"
                digest = await asyncio.to_thread(file_sha256, job.path)
                await self.database_factory().save_scan(job.id, job.owner, job.kind,
                                                       job.filename, result, digest)
                job.result = {"scan_id": job.id, **result}
                job.status = job.stage = "completed"
        except asyncio.CancelledError:
            job.status = job.stage = "cancelled"
        except TimeoutError:
            job.status = job.stage = "failed"
            job.error = "Analysis timed out. Try a smaller image or shorter video."
        except Exception:
            job.status = job.stage = "failed"
            job.error = "Analysis or report saving failed. Check media limits and server configuration."
        finally:
            await cleanup_temp_file(job.path)

    async def cancel(self, job):
        # Once saving starts the transaction may commit despite client disconnect.
        if job.status == "saving":
            return False
        if job.task and not job.task.done():
            job.task.cancel()
            try:
                await job.task
            except asyncio.CancelledError:
                job.status = job.stage = "cancelled"
            await cleanup_temp_file(job.path)
        return True

    async def close(self):
        for job in list(self.jobs.values()):
            if job.status == "saving" and job.task:
                await job.task
            else:
                await self.cancel(job)

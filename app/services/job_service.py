import uuid
import logging
from typing import Dict, Any, Optional
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)

from app.services.cache_service import cache_service

from celery.result import AsyncResult
from app.celery_app import celery_app

class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class JobManager:
    async def get_active_job_by_task(self, task_name: str) -> Optional[str]:
        # We can store a mapping in cache to quickly find active jobs
        active_id = await cache_service.get_cache(f"active_job:{task_name}")
        if active_id:
            job = await self.get_job(active_id)
            if job and job["status"] in [JobStatus.PENDING, JobStatus.PROCESSING]:
                return active_id
        return None

    async def create_job(self, task_name: str) -> str:
        job_id = str(uuid.uuid4())
        job_data = {
            "id": job_id,
            "task": task_name,
            "status": JobStatus.PENDING,
            "result": None,
            "error": None,
            "created_at": datetime.utcnow().isoformat()
        }
        await cache_service.set_cache(f"job:{job_id}", job_data, ttl=86400) # 24h TTL
        # Set active mapping
        await cache_service.set_cache(f"active_job:{task_name}", job_id, ttl=3600)
        logger.info(f"Created job {job_id} for task {task_name}")
        return job_id

    async def update_job(self, job_id: str, status: JobStatus, result: Any = None, error: str = None):
        job_data = await self.get_job_cache(job_id)
        if job_data:
            job_data["status"] = status
            if result is not None:
                job_data["result"] = result
            if error is not None:
                job_data["error"] = error
            job_data["updated_at"] = datetime.utcnow().isoformat()
            await cache_service.set_cache(f"job:{job_id}", job_data, ttl=86400)
            logger.info(f"Updated job {job_id} to {status}")

    async def get_job_cache(self, job_id: str) -> Optional[Dict[str, Any]]:
        return await cache_service.get_cache(f"job:{job_id}")

    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        # Sync with Celery status if possible
        result = AsyncResult(job_id, app=celery_app)
        
        # Try getting our internal cache first for rich metadata
        job_data = await self.get_job_cache(job_id)
        if not job_data:
            return None
            
        # Override with pure celery state if we didn't explicitly finish it
        if result.state == 'FAILURE':
            job_data['status'] = JobStatus.FAILED
            job_data['error'] = str(result.result)
        elif result.state == 'SUCCESS' and not job_data.get('result'):
            job_data['status'] = JobStatus.COMPLETED
            job_data['result'] = result.result
            
        return job_data

job_manager = JobManager()

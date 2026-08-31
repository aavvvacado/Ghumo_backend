import asyncio
import logging
from app.celery_app import celery_app
from app.services.enrichment_service import enrichment_service
from app.services.job_service import job_manager, JobStatus

logger = logging.getLogger(__name__)

def _run_async(coro):
    """Helper to run async code synchronously for Celery"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    return loop.run_until_complete(coro)

@celery_app.task(bind=True, name="app.tasks.miner_tasks.context_enrichment_task")
def context_enrichment_task(self, job_id: str, query: str, lat: float = None, lng: float = None):
    """
    Background worker task to fetch heavy data from YouTube, Reddit, Blogs, and OSM.
    """
    logger.info(f"Worker starting deep enrichment for Job {job_id} on query '{query}'")
    _run_async(job_manager.update_job(job_id, JobStatus.PROCESSING))
    
    try:
        result = _run_async(enrichment_service.run_enrichment_job(query, lat, lng))
        _run_async(job_manager.update_job(job_id, JobStatus.COMPLETED, result=result))
        logger.info(f"Worker completed job {job_id}")
        return result
    except Exception as e:
        logger.error(f"Worker failed on Job {job_id}: {e}")
        _run_async(job_manager.update_job(job_id, JobStatus.FAILED, error=str(e)))
        raise e

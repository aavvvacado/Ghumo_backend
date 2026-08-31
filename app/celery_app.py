import os
import ssl
from celery import Celery
from app.utils.config import settings

# Use Valkey/Redis instance for both message broker and result backend
REDIS_URL = settings.VALKEY_URL

celery_app = Celery(
    "ghumo_worker",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.tasks.miner_tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    worker_concurrency=4,  # Adjust based on server limits
    task_track_started=True,
    task_time_limit=3600, # 1 hour max
    broker_use_ssl={
        'ssl_cert_reqs': ssl.CERT_NONE
    },
    redis_backend_use_ssl={
        'ssl_cert_reqs': ssl.CERT_NONE
    }
)

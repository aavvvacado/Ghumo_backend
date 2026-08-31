---
description: Start all backend services (FastAPI and Celery)
---

This workflow will start the FastAPI server and the Celery worker for the Ghumo backend.

1. **Start FastAPI API Server**
// turbo
```powershell
uvicorn app.main:app --reload
```

2. **Start Celery worker**
// turbo
```powershell
celery -A app.celery_app worker --loglevel=info --pool=solo
```

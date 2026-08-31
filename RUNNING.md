# How to Run the Ghumo Backend

This guide explains how to set up and run the FastAPI server and Celery worker.

## Prerequisites

1.  **Python 3.10+**: Ensure you have Python installed.
2.  **PostgreSQL**: A running instance for the database.
3.  **Redis (or Valkey)**: Used as the message broker for Celery and for caching.
4.  **Virtual Environment**: It's recommended to use the existing `venv` or create a new one.

## Setup

1.  **Activate Virtual Environment**:
    ```powershell
    .\venv\Scripts\Activate.ps1
    ```

2.  **Install Dependencies**:
    ```powershell
    pip install -r requirements.txt
    ```

3.  **Environment Variables**:
    Ensure `.env` is configured correctly. You can use `.env.example` as a template.
    ```powershell
    cp .env.example .env
    ```
    Update `DATABASE_URL`, `VALKEY_URL`, and other API keys as needed.

## Running the Application

### 1. API Server (FastAPI)
Run the following command from the root directory:
```powershell
uvicorn app.main:app --reload
```
The API will be available at `http://localhost:8000`. You can access the Swagger UI at `http://localhost:8000/docs`.

### 2. Celery Worker (Background Tasks)
In a separate terminal, run:
```powershell
celery -A app.celery_app worker --loglevel=info
```
*Note: On Windows, you might need to use `--pool=solo` if you encounter issues with the default pool:*
```powershell
celery -A app.celery_app worker --loglevel=info --pool=solo
```

## Testing
To run the test suite:
```powershell
pytest
```

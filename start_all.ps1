# Start all backend services for Ghumo

# Check if venv is active
if ($null -eq $env:VIRTUAL_ENV) {
    Write-Host "Warning: Virtual environment (venv) is not active. Please activate it before running services." -ForegroundColor Yellow
}

# Start FastAPI in a new window
Start-Process powershell -ArgumentList "-NoExit", "-Command", "uvicorn app.main:app --reload" -WindowStyle Normal

# Start Celery in a new window
# Note: Using --pool=solo for Windows compatibility
Start-Process powershell -ArgumentList "-NoExit", "-Command", "celery -A app.celery_app worker --loglevel=info --pool=solo" -WindowStyle Normal

Write-Host "Both services (API and Worker) are being started in separate terminals..." -ForegroundColor Green

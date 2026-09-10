---
title: Getting Started & Developer Guide
nav_order: 8
---

# 🚀 Getting Started & Developer Guide

This guide walks you through setting up **Ghumo Backend** locally for development and testing.

---

## 🛠️ Prerequisites

Ensure you have the following installed on your machine:
- **Python 3.11+**
- **Git**
- **Redis / Valkey** server running locally (`localhost:6379`) or remotely.
- **PostgreSQL** instance (or a free Supabase PostgreSQL database).

---

## 📥 1. Installation

```bash
# Clone the repository
git clone https://github.com/aavvvacado/Ghumo_backend.git
cd Ghumo_backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

## ⚙️ 2. Environment Configuration (`.env`)

Create a `.env` file in the root directory:

```env
# Database Connections
DATABASE_URL=postgresql://postgres:[PASSWORD]@db.[REF].supabase.co:5432/postgres
VALKEY_URL=redis://localhost:6379

# External API Keys
GEMINI_API_KEY=your_google_gemini_key
UNSPLASH_ACCESS_KEY=your_unsplash_key
GOOGLE_PLACES_API_KEY=your_google_places_key

# Caching & Rating Settings
CACHE_SEARCH_THRESHOLD=3
CACHE_TTL_SECONDS=604800
MIN_FEEDBACK_COUNT=5
```

---

## 🏃 3. Running Services Locally

### A. Run FastAPI Server
```bash
uvicorn app.main:app --reload --port 8000
```
Interactive Swagger documentation is available at: [http://localhost:8000/docs](http://localhost:8000/docs)

### B. Run Celery Background Worker
In a separate terminal:
```bash
celery -A app.celery_app worker --loglevel=info --pool=solo
```

---

## 🧪 4. Running Unit Tests

Run the full pytest suite:

```bash
# Set PYTHONPATH to root directory
# Windows PowerShell:
$env:PYTHONPATH="."; .\venv\Scripts\pytest

# Linux / macOS:
PYTHONPATH=. pytest
```

---

*Return to: [Home Overview & Table of Contents →](/Ghumo_backend/)*

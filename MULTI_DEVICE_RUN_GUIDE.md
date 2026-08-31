# 📱 Multi-Device Setup & Deployment Guide (`MULTI_DEVICE_RUN_GUIDE.md`)

This guide explains how to run the **Ghumo Backend** across different operating systems (Windows, macOS, Linux), connect from mobile devices/emulators (Android Studio, iOS Simulator, Physical Phones), and configure environment variables (`.env`) for different environments.

---

## 🛠️ 1. Environment Variable Configuration (`.env`)

Before launching on any device, create your `.env` file from `.env.example`:

```bash
cp .env.example .env
```

### 🔑 What Needs to Be Replaced in `.env` per Environment:

| Environment Variable | Local Development | Mobile Device / LAN Testing | Cloud / Production Server |
| :--- | :--- | :--- | :--- |
| `DATABASE_URL` | `postgresql://postgres:password@localhost:5432/ghumo` | `postgresql://postgres:password@localhost:5432/ghumo` | `postgresql://user:pass@cloud-db-host:5432/ghumo?sslmode=require` |
| `VALKEY_URL` | `redis://localhost:6379/0` | `redis://localhost:6379/0` | `rediss://default:pass@redis-cloud-host:6379/0` |
| `GROQ_API_KEY` | `gsk_your_actual_groq_key` | `gsk_your_actual_groq_key` | `gsk_your_actual_groq_key` |
| `AI_SOURCE` | `groq` | `groq` | `groq` |
| `OPENTRIPMAP_API_KEY` | `your_opentripmap_key` | `your_opentripmap_key` | `your_opentripmap_key` |
| `GOOGLE_PLACES_API_KEY`| `your_google_key` | `your_google_key` | `your_google_key` |

---

## 🌐 2. Client Connection Matrix (Connecting Frontend / Mobile to Backend)

When connecting your Flutter App, Web Frontend, or Postman to the FastAPI Backend, use the correct Base URL based on where the client is running:

| Client Device | Server Location | API Base URL to set in Mobile App / Frontend |
| :--- | :--- | :--- |
| **PC Browser / Postman** | Same PC | `http://localhost:8000` or `http://127.0.0.1:8000` |
| **Android Studio Emulator** | Same PC | `http://10.0.2.2:8000` *(Special loopback IP for Android)* |
| **iOS Simulator** | Mac PC | `http://127.0.0.1:8000` or `http://localhost:8000` |
| **Physical Phone (Android/iPhone)** | Same Wi-Fi Network | `http://<YOUR_PC_LOCAL_IP>:8000` *(e.g. `http://192.168.1.15:8000`)* |
| **Remote Mobile User** | Cloud Server | `https://api.yourdomain.com` or `http://<PUBLIC_IP>:8000` |

> 💡 **Finding your PC's Local IP**:
> - **Windows**: Open PowerShell and run `ipconfig` (Look for *IPv4 Address*, e.g., `192.168.1.15`).
> - **macOS / Linux**: Open Terminal and run `ifconfig` or `ip a` (Look for `inet` under `en0` or `wlan0`).

---

## 💻 3. Running on Windows

### Prerequisites
- Python 3.10+
- PostgreSQL service running
- Redis or Valkey running on port 6379

### Commands

1. **Activate Virtual Environment**:
   ```powershell
   .\venv\Scripts\Activate.ps1
   ```

2. **Run FastAPI Server (Exposing to LAN for Mobile Access)**:
   ```powershell
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
   *Note: Using `--host 0.0.0.0` allows physical mobile phones on your Wi-Fi to access the server.*

3. **Run Celery Background Worker (Windows Pool Notice)**:
   ```powershell
   celery -A app.celery_app worker --loglevel=info --pool=solo
   ```
   *⚠️ **IMPORTANT FOR WINDOWS**: You MUST append `--pool=solo` to Celery commands on Windows because Windows does not support Unix `fork`.*

4. **Automated Launch (Both Services)**:
   Run the PowerShell starter script:
   ```powershell
   .\start_all.ps1
   ```

---

## 🍎 4. Running on macOS / Linux

### Prerequisites
- Python 3.10+
- PostgreSQL (`brew services start postgresql` or `systemctl start postgresql`)
- Redis (`brew services start redis` or `systemctl start redis`)

### Commands

1. **Activate Virtual Environment**:
   ```bash
   source venv/bin/activate
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run FastAPI Server**:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

4. **Run Celery Background Worker**:
   ```bash
   celery -A app.celery_app worker --loglevel=info
   ```
   *(On macOS/Linux, default `prefork` works out of the box).*

---

## 🐳 5. Running with Docker / Docker Compose

If you want to run everything (FastAPI, Celery, PostgreSQL, Redis) in containers across any machine:

Create a `docker-compose.yml` in the project root:

```yaml
version: '3.8'

services:
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
      POSTGRES_DB: ghumo
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  web:
    build: .
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/ghumo
      - VALKEY_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis

  celery_worker:
    build: .
    command: celery -A app.celery_app worker --loglevel=info
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/ghumo
      - VALKEY_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis
```

Run Docker Compose:
```bash
docker-compose up --build
```

---

## 🛡️ 6. Firewall & Security Checklist for Physical Mobile Testing

If your physical mobile phone cannot connect to `http://192.168.X.X:8000`:

1. **Check Wi-Fi Network**: Ensure your PC and mobile phone are connected to the exact same Wi-Fi network.
2. **Windows Defender Firewall**:
   * Open *Windows Defender Firewall with Advanced Security*.
   * Add an **Inbound Rule** allowing TCP Port `8000`.
3. **Linux Firewall (ufw)**:
   ```bash
   sudo ufw allow 8000/tcp
   ```
4. **CORS Headers**:
   * If accessing from a Web browser on a different port, FastAPI handles CORS. If needed, check `app/main.py` for CORS Middleware settings.

---

## 🔍 Summary Checklist of Replacements

| Item to Change | File Location | Purpose |
| :--- | :--- | :--- |
| `DATABASE_URL` | `.env` | Update DB username, password, host, and port |
| `GROQ_API_KEY` | `.env` | Insert your valid Groq API key |
| `--host 0.0.0.0` | CLI command / script | Expose server to local network for mobile testing |
| `--pool=solo` | Celery CLI command | Required ONLY on Windows machines |
| `baseUrl` | Flutter / Mobile App Code | Replace `localhost` with `10.0.2.2` (Android Emulator) or `192.168.X.X` (Physical Device) |

---
*Maintained for Ghumo Multi-Device Development.*

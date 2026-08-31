# Detailed Workflow: Local Intelligence Engine

This document details the refined step-by-step logic of the Search and Discovery flows.

---

## 🔍 Search Flow (Decoupled)
**Entry Point**: `GET /search`

1. **Request**: User searches for "Bareilly food".
2. **Fast Lookup**:
   - Check **Valkey** for `search:bareilly_food`.
   - If miss, check **PostgreSQL** `AIContext` for synthesized logic.
   - If miss, check **PostgreSQL** `Places` for any known place in "Bareilly".
3. **Immediate Response**:
   - If results found: Return them immediately.
   - If no/shallow results: Return OSM coordinates + `enriching: true`.
4. **Background Trigger**: If `enriching: true`, a Celery job (`context_enrichment_task`) is fired **once** and remains non-blocking.

---

## 🛰 Discovery Flow (Smart)
**Entry Point**: `DiscoveryAgent` (Daily)

1. **Batch Selection**: Pick a random subset of 20 cities/landmarks from the 300+ city registry.
2. **Rate Limited Job**:
   - Trigger `enrichment_service.run_enrichment_job(city)`.
   - **Wait 10-20 minutes** (Jitter) before the next city to avoid IP bans.
3. **Multi-Source Mining**:
   - **OSM**: Overpass POI search.
   - **Reddit**: Search discussions via JSON.
   - **YouTube**: Fetch titles/descriptions (metadata only).
   - **Blogs**: Light scraping for local tips.
4. **Smart Merge & Scoring**:
   - AI (Groq) synthesizes all findings.
   - `knowledge_updater` calculates a **Confidence Score**.
   - **Merge**: Records are updated only if Discovery found *better* or *more verified* data.
5. **Final Sync**: Data is saved to DB and Cache for the next Search Flow.

---

## 🛠 Tech Stack Update
- **Search**: FastAPI + Valkey + PostgreSQL.
- **Discovery**: Celery + Groq (Llama 3) + Scrapy/BeautifulSoup.
- **Rate Limiting**: `asyncio.sleep` + Randomized Jitter.

# Detailed Workflow: Local Intelligence Engine

This document details the refined step-by-step logic of the Search, POI Collision Resolution, and Multi-Source Intelligence flows.

---

## 🔍 Search & Intelligence Flow
**Entry Point**: `GET /search?query={location}`

1. **Request Received**: E.g. User searches for `"majnu ka tila"`, `"muradnagar"`, or `"KIET"`.
2. **Tier 1 - Valkey Hot Cache**:
   - Check cache key `search:{location_lower}`.
   - If rich data exists, return immediately in `< 50ms`.
3. **Tier 2 - Persistent AIContext (PostgreSQL)**:
   - Check if synthesized AI context exists with populated places/food.
   - Increment `search_count`, update `last_searched_at`, and return.
4. **Tier 3 - Anchor Landmark & Collision Resolution**:
   - Check if the query matches a specific landmark (e.g. `"KIET Group of Institutions"`).
   - If matched, retrieve the parent city context (e.g. `"Muradnagar"`).
   - Elevate and prepend the matched landmark to the front of its category (`attractions`, `places`) with duplicate deduplication.
   - Return combined, context-rich result.
5. **Tier 4 - Regional POI Lookup**:
   - Query `Place` table for city/region records, grouping into `attractions`, `food`, `markets`, `hidden_gems`, and attaching travel tips.
6. **Live Multi-Source Research (Fallback on Cache/DB Miss)**:
   - If the location is uncached or has no existing data, execute `enrichment_service.run_enrichment_job()` directly:
     - **Nominatim Geocoding**: Resolve precise GPS coordinates (`lat`, `lng`).
     - **OpenStreetMap Overpass API**: Query physical POIs and amenities within an 8km bounding radius.
     - **YouTube Transcript Mining**: Query `transcriptapi.com` with API key authentication, fetching real travel video itineraries (cached in Valkey for 24h).
     - **Reddit & Blog Sentiment**: Gather traveler reviews, tips, and hidden gems concurrently.
     - **Gemini AI Synthesis**: Synthesize raw data into structured categories.
     - **Quality & Image Validation**: Filter out placeholders and resolve high-res Wikimedia/Unsplash photos.
     - **Database & Cache Sync**: Save verified records to PostgreSQL and cache in Valkey.
     - Return the fully enriched intelligence payload.

---

## 🛰 Streaming Flow (SSE)
**Entry Point**: `GET /search/stream?query={location}` or `POST /search/stream`

1. Emits `init` event.
2. Checks fast cache. If present, immediately emits `cache_hit` and `complete`.
3. If uncached, initiates `run_enrichment_job` via in-process `asyncio.create_task` and emits `mining` progress event.
4. Emits `osm_complete` once map scan finishes, then streams research progress attempts.
5. Emits `complete` with full structured payload upon synthesis completion.

---

## 🛠 Tech Stack Summary
- **Framework**: FastAPI (ASGI)
- **Primary AI**: Google Gemini (`gemini-2.5-flash`, `gemini-2.0-flash`, `gemini-1.5-flash`) with Groq / Ollama fallback
- **Caching**: Valkey / Redis (Sub-millisecond latency, selective hot caching)
- **Database**: Supabase PostgreSQL with SQLAlchemy
- **Data Layers**: OpenStreetMap (Nominatim + Overpass), YouTube Transcripts (`transcriptapi.com`), Reddit API, Web Crawlers
- **Validation**: Place Quality Validator & Creative Commons Image Resolver

---
layout: default
title: Ghumo Backend Documentation
description: Scalable Travel Discovery, Real-time Search Engine & Place Intelligence Documentation
---

# Ghumo Backend API

Welcome to the official technical documentation for the **Ghumo Backend API**.

Ghumo is a high-performance travel discovery and AI-assisted itinerary generation engine designed for seamless place exploration, community recommendations, and intelligent itinerary planning.

---

## Technical Overview

Ghumo Backend is architected for low-latency travel intelligence, sub-200ms search responses, and reliable place data.

| Component | Technology | Role |
| :--- | :--- | :--- |
| **Framework** | **FastAPI** | Async REST API & Server-Sent Events (SSE) |
| **Primary DB** | **Supabase PostgreSQL** | Source of truth for places, searches, and ratings |
| **Hot Cache** | **Valkey / Redis** | Hot cache for high-frequency search queries |
| **Task Queue** | **Celery + Redis** | Asynchronous deep web & map enrichment |
| **AI Engine** | **Google Gemini 1.5** | Natural language reasoning & context extraction |
| **Map Engine** | **Overpass API (OSM)** | Geo-bounding spatial place discovery |
| **Image Engine** | **Wikimedia / Unsplash** | Real place image resolution without AI hallucinations |

---

## System Architecture

```
                       ┌─────────────────────────┐
                       │  Mobile / Web Clients   │
                       └────────────┬────────────┘
                                    │
                                    ▼
                       ┌─────────────────────────┐
                       │     FastAPI Router      │
                       └─────┬──────────────┬────┘
                             │              │
        ┌────────────────────┘              └────────────────────┐
        │                                                        │
        ▼                                                        ▼
┌──────────────┐                                       ┌───────────────────┐
│ Valkey Cache │ (Cache Hit: < 50ms)                   │  Supabase Postgres│
└──────────────┘                                       └─────────┬─────────┘
        │ (Cache Miss)                                           │ (DB Search)
        └────────────────────┐                  ┌────────────────┘
                             │                  │
                             ▼                  ▼
                       ┌─────────────────────────┐
                       │  PlaceQualityValidator  │
                       └────────────┬────────────┘
                                    │ (Passed)
                                    ▼
                       ┌─────────────────────────┐
                       │   PlaceImageResolver    │
                       │ (Wikimedia -> Unsplash) │
                       └────────────┬────────────┘
                                    │
                                    ▼
                       ┌─────────────────────────┐
                       │  Celery Worker (Async)  │
                       │  (OSM + Gemini 1.5 AI)  │
                       └─────────────────────────┘
```

---

## Key Features & Innovations

### 1. PostgreSQL-First Storage with Selective Hot Caching
- **PostgreSQL Source of Truth**: All valid places, AI context, and community ratings are permanently indexed in Supabase PostgreSQL.
- **Selective Promotion**: Valkey (Redis) caches search results **only** when query frequency reaches `CACHE_SEARCH_THRESHOLD` (default: 3 searches).
- **Quality Gate**: Invalid, empty, or placeholder results are **never** stored in cache or database.

### 2. Place Quality Validator
- Pre-enrichment and post-enrichment validation layers strip out generic terms (`unknown`, `n/a`, `point of interest`, `null`).
- Out-of-bounds coordinates and `(0.0, 0.0)` geographic points are automatically rejected.
- Canonical place deduplication normalizes names (punctuation removal, lowercase matching).

### 3. Place & Itinerary Image Resolution Engine
- Eliminates AI hallucination of image URLs.
- Provider pipeline:
  1. **Wikimedia Commons / Wikidata**: Free primary provider matching exact place name and city.
  2. **Unsplash API**: High-resolution fallback provider.
  3. **Google Places API**: Optional fallback when configured.
- Caches image resolution results for 7 days.

### 4. Community Feedback Rating System (1–5 Stars)
- Single active rating per user per target using `TargetFeedback` unique constraint (`user_id_or_anon`, `target_type`, `target_id`).
- Re-submitting a rating dynamically updates the existing vote.
- Computes Bayesian weighted confidence scores:

$$W = \frac{v}{v + m} R + \frac{m}{v + m} C$$

Where $v$ is vote count, $m$ is minimum threshold (5), $R$ is average rating, and $C$ is global mean rating.

---

## API Endpoints

### 1. Fast Intelligence Search
#### `GET /search`
Returns place intelligence for a given query. Executes fast DB/cache lookup; if the place is new, triggers background enrichment.

**Query Parameters:**
- `query` (string, required): E.g., `chandni chowk delhi`

**Sample Response:**
```json
{
  "location": "chandni chowk delhi",
  "coordinates": { "lat": 28.6562, "lng": 77.2310 },
  "places": [
    {
      "name": "Red Fort (Lal Qila)",
      "type": "places",
      "lat": 28.6562,
      "lng": 77.2410,
      "source": "db",
      "image": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/...",
        "provider": "wikimedia",
        "attribution": "Wikimedia Commons"
      },
      "feedback": {
        "averageRating": 4.8,
        "ratingCount": 12,
        "weightedScore": 4.55
      }
    }
  ],
  "food": [],
  "markets": [],
  "hidden_gems": [],
  "tips": [],
  "enriching": false
}
```

---

### 2. Streaming Progress Search (SSE)
#### `GET /search/stream` or `POST /search/stream`
Server-Sent Events (SSE) endpoint providing real-time research progress updates while scanning OpenStreetMap and synthesizing with Gemini AI.

**Event Stream Format:**
```http
event: progress
data: {"step": "init", "message": "Starting intelligence search for manali"}

event: progress
data: {"step": "osm_complete", "message": "Found 12 places via map scan."}

event: complete
data: {"step": "complete", "message": "Research complete", "data": {...}}
```

---

### 3. Place Suggestions & Trending Locations
#### `GET /suggestions`
Returns hot/trending places stored in PostgreSQL that have verified, high-resolution image URLs.

**Query Parameters:**
- `limit` (int, default: `10`): Max records to return.
- `city` (string, optional): Filter by city.
- `category` (string, optional): E.g., `places`, `food`, `markets`.

**Sample Response:**
```json
{
  "total": 3,
  "suggestions": [
    {
      "id": 15,
      "name": "Anangpur Dam",
      "city": "Faridabad",
      "category": "places",
      "lat": 28.4612,
      "lng": 77.2891,
      "search_count": 8,
      "image": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/...",
        "provider": "wikimedia"
      },
      "feedback": {
        "averageRating": 4.5,
        "ratingCount": 6,
        "weightedScore": 4.2
      }
    }
  ]
}
```

---

### 4. Community Target Feedback
#### `POST /target-feedback`
Submit or update a 1 to 5 star rating for any place, itinerary, or recommendation.

**Request Body:**
```json
{
  "user_id_or_anon": "usr_9921",
  "target_type": "place",
  "target_id": "Red Fort (Lal Qila)",
  "rating": 5
}
```

**Response:**
```json
{
  "status": "success",
  "target_type": "place",
  "target_id": "Red Fort (Lal Qila)",
  "average_rating": 4.8,
  "rating_count": 13,
  "weighted_score": 4.58
}
```

---

### 5. Itinerary Planner & Stream
#### `POST /itinerary`
Generates a structured, day-by-day travel plan powered by Gemini AI with resolved image URLs.

**Request Body:**
```json
{
  "location": "Jaipur",
  "time_available": "2 days",
  "interests": ["history", "food", "architecture"],
  "budget": "moderate"
}
```

---

### 6. Video Itinerary Miner
#### `POST /itinerary/video`
Extracts location entities and constructs an itinerary directly from YouTube video URLs or social travel clips.

---

### 7. Additional Endpoints

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/nearby` | `GET` | Geographic radius search (`lat`, `lng`, `radius`) |
| `/hidden-gems` | `GET` | Discover curated offbeat places |
| `/tips` | `GET` | Travel tips by place or city |
| `/search-history` | `GET` | Recent search history |
| `/health` | `GET` | Database & Valkey connection health status |

---

## Local Development & Setup

### Prerequisites
- Python 3.11+
- Redis / Valkey server
- PostgreSQL database (or Supabase instance)

### 1. Installation
```bash
git clone https://github.com/aavvvacado/Ghumo_backend.git
cd Ghumo_backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Configuration (`.env`)
```env
DATABASE_URL=postgresql://postgres:[PASSWORD]@db.[REF].supabase.co:5432/postgres
VALKEY_URL=redis://localhost:6379
GEMINI_API_KEY=your_gemini_api_key
UNSPLASH_ACCESS_KEY=your_unsplash_key
GOOGLE_PLACES_API_KEY=your_google_key
CACHE_SEARCH_THRESHOLD=3
```

### 3. Run FastAPI Application
```bash
uvicorn app.main:app --reload --port 8000
```

### 4. Run Celery Worker
```bash
celery -A app.celery_app worker --loglevel=info --pool=solo
```

### 5. Run Test Suite
```bash
python -m pytest
```

---

## License & Attribution

Designed and built by the **Ghumo Engineering Team**.  
Documentation styled with the [Stygian](https://github.com/ksauraj/stygian) remote theme for Jekyll & GitHub Pages.

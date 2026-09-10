---
layout: docs
title: Ghumo Backend API Documentation
nav_order: 1
---

# Ghumo Backend API Documentation

Welcome to the official technical documentation hub for the **Ghumo Backend API**.

Ghumo is a high-performance travel discovery engine, location intelligence platform, and AI-assisted itinerary planner. Built with **FastAPI**, **Supabase PostgreSQL**, **Valkey (Redis)**, **Celery**, and **Google Gemini 1.5**, Ghumo provides sub-200ms searches, real-time Server-Sent Events (SSE) research streaming, real place image resolution, and community rating calculations.

---

## Master Documentation Index

Navigate through the documentation modules below:

- [1. System Architecture & Async Workflow]({{ site.baseurl }}/docs/architecture/)
- [2. Complete API Reference]({{ site.baseurl }}/docs/api-reference/)
- [3. Place Quality Validator]({{ site.baseurl }}/docs/place-quality-validator/)
- [4. Image Resolution Engine (Zero-Hallucination)]({{ site.baseurl }}/docs/image-resolution-engine/)
- [5. Community Feedback & Bayesian Ratings]({{ site.baseurl }}/docs/community-feedback/)
- [6. Database Schema & Indexing Guide]({{ site.baseurl }}/docs/database-schema/)
- [7. Getting Started & Developer Setup]({{ site.baseurl }}/docs/getting-started/)

### Quick Navigation Grid

| Module | Core Topics | Status |
| :--- | :--- | :--- |
| [**Architecture & Workflow**]({{ site.baseurl }}/docs/architecture/) | PostgreSQL-First persistence, Valkey hot caching, Celery async background workers, Overpass OSM scanning | `v1.2 Active` |
| [**API Reference**]({{ site.baseurl }}/docs/api-reference/) | `/search`, `/search/stream` (SSE), `/suggestions`, `/target-feedback`, `/itinerary`, `/itinerary/video`, `/nearby` | `v1.2 Active` |
| [**Quality Validator**]({{ site.baseurl }}/docs/place-quality-validator/) | Pre/post enrichment validation, generic placeholder filter, canonical name normalization | `v1.2 Active` |
| [**Image Resolution**]({{ site.baseurl }}/docs/image-resolution-engine/) | Wikidata/Wikimedia Commons primary provider, Unsplash fallback, 7-day image caching | `v1.2 Active` |
| [**Community Ratings**]({{ site.baseurl }}/docs/community-feedback/) | 1-5 star user ratings, single-vote deduplication, Bayesian confidence weighted score calculation | `v1.2 Active` |
| [**Database Schema**]({{ site.baseurl }}/docs/database-schema/) | Supabase PostgreSQL tables, composite indexes (`idx_place_norm_city`), migration scripts | `v1.2 Active` |
| [**Getting Started**]({{ site.baseurl }}/docs/getting-started/) | Prerequisites, `.env` config, running `uvicorn`, `celery`, and `pytest` suite | `v1.2 Active` |

---

## Core Highlights

### 1. PostgreSQL-First Storage Engine
- **Single Source of Truth**: All valid places, AI context, search metrics (`search_count`, `last_searched_at`), and community ratings are permanently stored in Supabase PostgreSQL.
- **Hot-Cache Promotion**: Valkey (Redis) caches search queries **only** when query frequency reaches `CACHE_SEARCH_THRESHOLD` (default: 3 searches).

### 2. Zero-Hallucination Image Resolution
- **Provider Pipeline**: Resolves high-resolution images via Wikidata/Wikimedia Commons and Unsplash. Never relies on AI-hallucinated image URLs.
- **7-Day TTL**: Valid resolved images are cached in Valkey for 7 days to eliminate API overhead.

### 3. Bayesian Weighted Rating Formula
- Computes fair community scores even for newly rated locations:

$$W = \frac{v}{v + m} R + \frac{m}{v + m} C$$

*Where $v$ is vote count, $m$ is minimum threshold (5), $R$ is average rating, and $C$ is global mean rating.*

---

## Tech Stack At A Glance

```
       [ Client Apps: iOS / Android / Web ]
                        │
                        ▼
         [ FastAPI Async REST & SSE Gateway ]
          /            │            \
         /             │             \
        ▼              ▼              ▼
[ Valkey Hot Cache ] [ PostgreSQL DB ] [ Celery Worker Queue ]
(Fast Lookup <50ms)  (Source of Truth)  (OSM + Gemini 1.5 AI)
```

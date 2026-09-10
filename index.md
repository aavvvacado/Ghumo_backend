---
layout: default
title: Home Overview & Table of Contents
description: Ghumo Backend API Documentation Hub
order: 1
nav_order: 1
---

# 🌍 Ghumo Backend API Documentation

Welcome to the official technical documentation hub for the **Ghumo Backend API**.

Ghumo is a high-performance travel discovery engine, location intelligence platform, and AI-assisted itinerary planner. Built with **FastAPI**, **Supabase PostgreSQL**, **Valkey (Redis)**, **Celery**, and **Google Gemini 1.5**, Ghumo provides sub-200ms searches, real-time Server-Sent Events (SSE) research streaming, real place image resolution, and community rating calculations.

---

## 📌 Master Table of Contents

Navigate through the documentation modules below:

```
├── 🏠 1. Overview & Quick Summary (This Page)
├── 🏗️ 2. System Architecture & Async Workflow ------> /docs/architecture.html
├── 🔌 3. Complete API Reference ────────────────────> /docs/api-reference.html
├── 🛡️ 4. Place Quality Validator ───────────────────> /docs/place-quality-validator.html
├── 🖼️ 5. Image Resolution Engine (Zero-Hallucination)> /docs/image-resolution-engine.html
├── ⭐ 6. Community Feedback & Bayesian Ratings ─────> /docs/community-feedback.html
├── 🗄️ 7. Database Schema & Indexing Guide ──────────> /docs/database-schema.html
└── 🚀 8. Getting Started & Developer Setup ──────────> /docs/getting-started.html
```

### Quick Navigation Grid

| Module | Core Topics | Status |
| :--- | :--- | :--- |
| [**Architecture & Workflow**](docs/architecture.html) | PostgreSQL-First persistence, Valkey hot caching, Celery async background workers, Overpass OSM scanning | `v1.2 Active` |
| [**API Reference**](docs/api-reference.html) | `/search`, `/search/stream` (SSE), `/suggestions`, `/target-feedback`, `/itinerary`, `/itinerary/video`, `/nearby` | `v1.2 Active` |
| [**Quality Validator**](docs/place-quality-validator.html) | Pre/post enrichment validation, generic placeholder filter, canonical name normalization | `v1.2 Active` |
| [**Image Resolution**](docs/image-resolution-engine.html) | Wikidata/Wikimedia Commons primary provider, Unsplash fallback, 7-day image caching | `v1.2 Active` |
| [**Community Ratings**](docs/community-feedback.html) | 1-5 star user ratings, single-vote deduplication, Bayesian confidence weighted score calculation | `v1.2 Active` |
| [**Database Schema**](docs/database-schema.html) | Supabase PostgreSQL tables, composite indexes (`idx_place_norm_city`), migration scripts | `v1.2 Active` |
| [**Getting Started**](docs/getting-started.html) | Prerequisites, `.env` config, running `uvicorn`, `celery`, and `pytest` suite | `v1.2 Active` |

---

## ⚡ Core Highlights

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

## 🛠️ Tech Stack At A Glance

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

---

*Continue to the next chapter: [System Architecture & Async Workflow →](docs/architecture.html)*

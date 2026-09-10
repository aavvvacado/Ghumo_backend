---
layout: docs
title: System Architecture & Async Workflow
description: In-depth technical guide to Ghumo Backend's architecture, data flows, caching strategies, and task execution.
---

# 🏗️ System Architecture & Async Workflow

This document provides a deep technical breakdown of the **Ghumo Backend** architecture, highlighting data persistence, caching mechanisms, background workers, and real-time streaming engines.

---

## 📐 High-Level Architecture Diagram

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
        ▼ (Fast Cache Check)                                     ▼ (DB Lookup)
┌──────────────┐                                       ┌───────────────────┐
│ Valkey Cache │ (Hit: < 50ms)                         │  Supabase Postgres│
└──────────────┘                                       └─────────┬─────────┘
        │ (Cache Miss)                                           │ (Source of Truth)
        └────────────────────┐                  ┌────────────────┘
                             │                  │
                             ▼                  ▼
                       ┌─────────────────────────┐
                       │  PlaceQualityValidator  │
                       └────────────┬────────────┘
                                    │ (Passed Quality Gate)
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

## 🔄 Search & Discovery Workflow

When a user searches for a destination (e.g., `chandni chowk delhi`), the backend processes the request using a **3-Tier Execution Pipeline**:

```
[Request: GET /search?query=chandni+chowk]
                │
                ▼
  Step 1: Check Valkey Hot Cache
       ├── Cache Hit? ──────> [Return Cached JSON immediately (< 50ms)]
       └── Cache Miss? ─────> Proceed to Step 2
                │
                ▼
  Step 2: Check PostgreSQL Source of Truth
       ├── Found in DB? ────> Increment search_count, check promotion threshold
       │                      └── search_count >= 3 ? Promote to Valkey Cache!
       │                      └── Return DB Result (< 200ms)
       └── Not in DB? ──────> Proceed to Step 3
                │
                ▼
  Step 3: Trigger Background Celery Enrichment
       ├── Dispatch Celery Task: context_enrichment_task.apply_async()
       ├── Scan Overpass API (OpenStreetMap) for POIs & Food
       ├── Synthesize context with Google Gemini 1.5 Flash AI
       ├── Run PlaceQualityValidator (reject generic/corrupt places)
       ├── Resolve real place images via PlaceImageResolver
       └── Save verified results to PostgreSQL (and promote to Valkey if search_count >= 3)
```

---

## ⚡ Selective Hot-Cache Promotion Strategy

Unlike traditional caching strategies that store every user request in Redis regardless of frequency, Ghumo implements **Selective Hot-Cache Promotion**:

1. **PostgreSQL as Primary**: Every search query and place entity is saved to PostgreSQL.
2. **Frequency Tracking**: Each search increments `search_count` and updates `last_searched_at` on the `AIContext` and `Place` models.
3. **Hot-Cache Gate**:
   ```python
   # Excerpt from enrichment_service.py
   if search_count >= settings.CACHE_SEARCH_THRESHOLD:
       await cache_service.set_cache(cache_key, final_data, ttl=settings.CACHE_TTL_SECONDS)
   ```
4. **Invalid Result Rejection**: Responses containing 0 valid places or failing quality checks are **never** written to Valkey.

---

## 👷 Celery Background Workers

Background context enrichment tasks are handled by **Celery** backed by Redis:

- **Task Name**: `context_enrichment_task`
- **Concurrency Model**: Solo event loop (`--pool=solo`) for rate-limited external API calls.
- **Execution Workflow**:
  ```python
  @celery_app.task(name="app.tasks.miner_tasks.context_enrichment_task")
  def context_enrichment_task(job_id: str, location: str, lat: float = None, lng: float = None):
      # 1. Physical scan via OpenStreetMap (Overpass API)
      # 2. Extract context via Gemini 1.5 Flash AI
      # 3. Quality filter & place image resolution
      # 4. Save to PostgreSQL & update job status to COMPLETED
  ```

---

*Next Chapter: [Complete API Reference →](api-reference.html)*

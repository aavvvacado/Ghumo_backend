# Ghumo Backend Architecture: Local Intelligence Engine

This document provides a technical overview of the upgraded Ghumo backend, now functioning as a **Local Intelligence Engine**.

## 🚀 Concept: Decoupled Intelligence
The system is split into two independent layers to ensure high performance and continuous learning.

### 1. Search Engine (Fast & Reliable)
- **Goal**: Never return empty results; Respond in `< 200ms`.
- **Flow**: `Valkey Cache` → `PostgreSQL (AIContext/Places)` → `OSM Fallback`.
- **Behavior**: If the database has "shallow" data, the search returns immediately with the `enriching: true` flag, signaling the UI to show a loading state for deeper data.

### 2. Discovery Engine (Slow & Smart)
- **Goal**: Continuously find new places and improve existing data without getting banned.
- **Workflow**: Scheduled background jobs pick 20 cities daily.
- **Sources**: 
    - **Reddit**: JSON API (Safe).
    - **YouTube**: Metadata only (Anti-ban).
    - **Blogs**: Light scraping.
- **Rate Limiting**: Strict 10-20 minute jitter between discovery jobs.

---

## 🏗 Component Breakdown

### Core Services (`app/services/`)
- **`enrichment_service.py`**: The bridge between Search and Discovery. Handles "fast" results and "deep" background jobs.
- **`knowledge_updater.py`**: The "Brain" that performs **Smart Merges**. It only updates the DB if new discovery data has a higher confidence score.
- **`discovery_agent.py`**: Manages the daily discovery batch and rate limiting.

### Data Model & Scoring (`app/database/models.py`)
Each `Place` and `HiddenGem` now has a `confidence_score` (0.0 to 1.0) calculated from:
- **OSM Presence** (+0.4)
- **Reddit Mentions** (+0.2)
- **Blog Mentions** (+0.2)
- **YouTube Mentions** (+0.2)

---

## 🔄 Self-Improving database
When new data arrives:
1. **Compare**: `new_score` vs `existing_score`.
2. **Merge**: If `new_score > existing_score`, update the record and increment `source_count`.
3. **Persist**: Sync to `AIContext` and `Places` tables for future instant searches.

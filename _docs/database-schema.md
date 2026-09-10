---
layout: docs
title: Database Schema & Indexing Guide
nav_order: 6
---

# 🗄️ Database Schema & Indexing Guide

Ghumo Backend uses **Supabase PostgreSQL** as its primary persistent database.

---

## 📊 Database Models & Entity Schema

```
                     ┌──────────────────┐
                     │      places      │
                     ├──────────────────┤
                     │ id (PK)          │
                     │ external_id (UQ) │
                     │ name             │
                     │ normalized_name  │ ── Index idx_place_norm_city (normalized_name, city)
                     │ category         │
                     │ lat, lng         │
                     │ city             │
                     │ search_count     │ ── Hot-Cache promotion criteria (search_count >= 3)
                     │ last_searched_at │
                     └──────────────────┘
                              │
                              ▼
                     ┌──────────────────┐
                     │  target_feedback │
                     ├──────────────────┤
                     │ id (PK)          │
                     │ user_id_or_anon  │
                     │ target_type      │ ── Unique uq_user_target_feedback
                     │ target_id        │
                     │ rating           │
                     └──────────────────┘
```

---

## 📋 Table Definitions

### 1. `places` Table
Stores physical locations, attractions, food joints, and markets.

| Column | Type | Index | Description |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | `PRIMARY KEY` | Auto-incrementing primary key |
| `external_id` | `VARCHAR` | `UNIQUE` | Google/OSM/OTM external reference |
| `name` | `VARCHAR` | `INDEX` | Human-readable place name |
| `normalized_name`| `VARCHAR` | `INDEX` | Punctuation-stripped lowercase key |
| `category` | `VARCHAR` | - | Category (`places`, `food`, `markets`) |
| `lat`, `lng` | `FLOAT` | - | WGS-84 Geographic coordinates |
| `city` | `VARCHAR` | `INDEX` | Associated city |
| `search_count` | `INTEGER` | `INDEX` | Search frequency counter |
| `last_searched_at`| `TIMESTAMP`| - | Timestamp of last user search |

---

### 2. `ai_context` Table
Caches synthesized travel intelligence and Gemini AI outputs.

| Column | Type | Index | Description |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | `PRIMARY KEY` | Primary Key |
| `query` | `VARCHAR` | `INDEX` | Search query string (lowercase) |
| `ai_response` | `JSON` | - | Synthesized place payload |
| `search_count` | `INTEGER` | `INDEX` | Search count tracking |
| `last_searched_at`| `TIMESTAMP`| - | Last search timestamp |

---

### 3. `target_feedback` Table
Stores community ratings (1–5 stars) per user/target.

| Column | Type | Index | Description |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | `PRIMARY KEY` | Primary Key |
| `user_id_or_anon`| `VARCHAR` | `INDEX` | User ID or anonymous string |
| `target_type` | `VARCHAR` | `INDEX` | Target type (`place`, `itinerary`) |
| `target_id` | `VARCHAR` | `INDEX` | Target name/identifier |
| `rating` | `INTEGER` | - | Rating (1 to 5) |

---

## ⚡ Indexing Strategy

```sql
-- Composite index for fast normalized name + city queries
CREATE INDEX IF NOT EXISTS idx_place_norm_city ON places (normalized_name, city);

-- Normalized name single index
CREATE INDEX IF NOT EXISTS idx_place_norm_name ON places (normalized_name);

-- Target feedback lookup index
CREATE INDEX IF NOT EXISTS idx_feedback_target ON target_feedback (target_type, target_id);
```

---

*Next Chapter: [Getting Started & Developer Guide →](getting-started.html)*

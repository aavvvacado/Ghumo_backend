---
layout: docs
title: Complete API Reference
description: Comprehensive documentation for all REST and Server-Sent Events (SSE) endpoints in Ghumo Backend.
order: 3
nav_order: 3
---

# 🔌 Complete API Reference

This document details all available HTTP endpoints in the **Ghumo Backend API**, including request parameters, response schemas, and curl examples.

---

## 📋 Endpoint Summary Table

| Path | Method | Description | Response Model |
| :--- | :--- | :--- | :--- |
| [`/search`](#1-get-search) | `GET` | Fast intelligence search for places & food | `SearchResponse` |
| [`/search/stream`](#2-getpost-searchstream) | `GET/POST` | SSE streaming search progress updates | `text/event-stream` |
| [`/suggestions`](#3-get-suggestions) | `GET` | Hot places with verified image URLs & ratings | `SuggestionsResponse` |
| [`/target-feedback`](#4-post-target-feedback) | `POST` | Submit 1–5 star user ratings for places | `TargetFeedbackResponse` |
| [`/itinerary`](#5-post-itinerary) | `POST` | Generate AI-driven day-by-day itineraries | `ItineraryResponse` |
| [`/itinerary/stream`](#6-post-itinerarystream) | `POST` | SSE streaming itinerary planner | `text/event-stream` |
| [`/itinerary/video`](#7-post-itineraryvideo) | `POST` | Mine places & itinerary from YouTube video URL | `ItineraryResponse` |
| [`/nearby`](#8-get-nearby) | `GET` | Search POIs within a geographic radius | `NearbyResponse` |
| [`/hidden-gems`](#9-get-hidden-gems) | `GET` | Offbeat recommendations by location | `List[dict]` |
| [`/tips`](#10-get-tips) | `GET` | Travel tips by place ID or city | `List[TravelTipResponse]` |
| [`/health`](#11-get-health) | `GET` | Health check for PostgreSQL & Valkey | `HealthResponse` |

---

## 1. `GET /search`

Fast sub-200ms intelligence search for places, food, markets, hidden gems, and travel tips.

### Query Parameters
- `query` *(string, required)*: The search term (e.g., `chandni chowk delhi`).

### cURL Example
```bash
curl -X GET "http://localhost:8000/search?query=chandni+chowk+delhi" \
     -H "Accept: application/json"
```

### Response Schema (`200 OK`)
```json
{
  "location": "chandni chowk delhi",
  "coordinates": {
    "lat": 28.6562,
    "lng": 77.2310
  },
  "places": [
    {
      "name": "Red Fort (Lal Qila)",
      "type": "places",
      "lat": 28.6562,
      "lng": 77.2410,
      "source": "db",
      "image": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/f/f8/Red_Fort_in_Delhi.jpg",
        "provider": "wikimedia",
        "attribution": "Wikimedia Commons"
      },
      "feedback": {
        "averageRating": 4.8,
        "ratingCount": 14,
        "weightedScore": 4.55
      }
    }
  ],
  "food": [
    {
      "name": "Paranthe Wali Gali",
      "type": "food",
      "lat": 28.6550,
      "lng": 77.2300,
      "source": "db"
    }
  ],
  "markets": [],
  "hidden_gems": [],
  "tips": [
    {
      "text": "Visit early morning to avoid massive crowds in narrow alleys.",
      "category": "culture"
    }
  ],
  "enriching": false
}
```

---

## 2. `GET/POST /search/stream`

Server-Sent Events (SSE) streaming endpoint that pushes real-time progress updates during map scanning and Gemini AI synthesis.

### cURL Example (SSE)
```bash
curl -N -X GET "http://localhost:8000/search/stream?query=manali" \
     -H "Accept: text/event-stream"
```

### Event Output Stream
```http
event: progress
data: {"step": "init", "message": "Starting intelligence search for manali"}

event: progress
data: {"step": "osm_complete", "message": "Found 12 places via map scan."}

event: complete
data: {"step": "complete", "message": "Research complete", "data": {...}}
```

---

## 3. `GET /suggestions`

Returns hot/trending places from PostgreSQL that have **verified high-resolution image URLs** and community ratings.

### Query Parameters
- `limit` *(int, default: 10)*: Number of suggestions to fetch.
- `city` *(string, optional)*: Filter by city.
- `category` *(string, optional)*: Filter by category (e.g. `places`, `food`).

### Response Schema (`200 OK`)
```json
{
  "total": 1,
  "suggestions": [
    {
      "id": 18,
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

## 4. `POST /target-feedback`

Submit or update a 1 to 5 star rating for any place or itinerary. Deduplicated per user/target pair.

### Request Body
```json
{
  "user_id_or_anon": "user_4910",
  "target_type": "place",
  "target_id": "Red Fort (Lal Qila)",
  "rating": 5
}
```

### Response Schema (`200 OK`)
```json
{
  "status": "success",
  "target_type": "place",
  "target_id": "Red Fort (Lal Qila)",
  "average_rating": 4.8,
  "rating_count": 15,
  "weighted_score": 4.62
}
```

---

## 5. `POST /itinerary`

Generates an AI-assisted travel itinerary tailored to user time available, interests, and budget.

### Request Body
```json
{
  "location": "Jaipur",
  "time_available": "2 days",
  "interests": ["history", "food"],
  "budget": "moderate"
}
```

---

## 6. `GET /health`

System health check endpoint verifying live status of Supabase PostgreSQL and Valkey cache.

### Response Schema (`200 OK`)
```json
{
  "status": "ok",
  "database": "ok",
  "valkey": "ok"
}
```

---

*Next Chapter: [Place Quality Validator →](place-quality-validator.html)*

---
layout: docs
title: Complete API Reference
nav_order: 2
---

# Complete API Reference

This document details all available HTTP endpoints in the **Ghumo Backend API**, including request parameters, response schemas, and curl examples.

---

## Endpoint Summary Table

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

Generates an intelligent, chunked travel itinerary using Gemini AI. Supports both free-form natural language prompts (e.g. *"iam visiting goa for 3 days with 10000 budget"*) and structured constraint inputs.

### Request Body (Conversational Prompt)
```json
{
  "prompt": "Visiting Goa for 3 days with a 10000 budget, love beaches and seafood"
}
```

### Request Body (Structured Fields)
```json
{
  "location": "Jaipur",
  "time_available": "2 days",
  "interests": ["heritage", "local food"],
  "budget": "5000 INR"
}
```

### Response Schema (`200 OK`)
```json
{
  "location": "Goa",
  "itinerary": "# Curated Itinerary: Goa\n\n**Total Duration**: 3 days | **Estimated Budget**: 10000 INR\n\n...",
  "recommended_places": ["Anjuna Beach", "Fort Aguada", "Chapora Fort"],
  "recommended_attractions": ["Basilica of Bom Jesus"],
  "parsed_requirements": {
    "destination": "Goa",
    "duration": "3 days",
    "mode": "day_wise",
    "budget": "10000 INR",
    "interests": ["beaches", "seafood"],
    "stay_preference": "Anjuna or Calangute coastal area"
  },
  "plan": {
    "destination": "Goa",
    "total_duration": "3 days",
    "mode": "day_wise",
    "estimated_total_budget": "10000 INR",
    "stay_area": "North Goa (Anjuna / Baga)",
    "summary": "Sun-soaked coastal getaway with historic forts and beachside shacks.",
    "budget_breakdown": {
      "stay": "₹4,500",
      "food": "₹2,500",
      "activities": "₹1,500",
      "transport": "₹1,500"
    },
    "days": [
      {
        "day": 1,
        "title": "North Goa Coastline & Sunset Fortress",
        "stay_recommendation": "Beachside Guesthouse near Anjuna",
        "estimated_day_cost": "₹3,200",
        "activities": [
          {
            "time_slot": "09:00 AM - 12:00 PM",
            "place": "Anjuna Beach",
            "duration": "3 hours",
            "purpose": "Beach walks, watersports & seaside breakfast",
            "cost_estimate": "₹400",
            "image": {
              "url": "https://upload.wikimedia.org/wikipedia/commons/...",
              "source": "wikimedia"
            }
          }
        ]
      }
    ],
    "markdown_table": "| Timing / Slot | Place / Landmark | Duration | Purpose & Highlights | Estimated Cost |\n| :--- | :--- | :--- | :--- | :--- |\n| **DAY 1: North Goa Coastline** | | | | |\n| 09:00 AM - 12:00 PM | **Anjuna Beach** | 3 hours | Beach walks & watersports | ₹400 |"
  }
}
```

---

## 6. `POST /itinerary/stream`

Server-Sent Events (SSE) streaming endpoint for generating itineraries with live progress events (`init`, `intent_parsing`, `ai_generation`, `complete`).

### Request Body
```json
{
  "prompt": "3 days trip to Udaipur on a moderate budget"
}
```

### Response (Event Stream `text/event-stream`)
```http
event: progress
data: {"step": "init", "message": "Initiating itinerary planner for Udaipur..."}

event: progress
data: {"step": "intent_parsing", "message": "Parsing natural language travel prompt and extracting trip requirements..."}

event: progress
data: {"step": "ai_generation", "message": "Generating intelligent chunked travel plan with Gemini AI..."}

event: complete
data: {"step": "complete", "message": "Itinerary successfully generated", "data": { ...ItineraryResponse... }}
```

---

## 7. `POST /itinerary/video`

Extracts travel itinerary, destination landmarks, and food recommendations directly from a YouTube vlog URL.

### Request Body
```json
{
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
}
```

### Response Schema (`200 OK`)
```json
{
  "location": "Manali, Himachal Pradesh",
  "itinerary": "Day 1: Arrive in Old Manali, visit Manu Temple and cafe hopping...",
  "recommended_places": ["Old Manali", "Manu Temple", "Solang Valley"],
  "recommended_attractions": []
}
```

---

## 8. `GET /nearby`

Searches for verified physical attractions, food, and markets within a geographic radius around GPS coordinates.

### Query Parameters
- `lat` *(float, required)*: Latitude (e.g. `28.6139`)
- `lng` *(float, required)*: Longitude (e.g. `77.2090`)
- `radius` *(int, optional, default: 5000)*: Search radius in meters.

### cURL Example
```bash
curl -X GET "http://localhost:8000/nearby?lat=28.6139&lng=77.2090&radius=3000"
```

### Response Schema (`200 OK`)
```json
{
  "places": [
    {
      "name": "India Gate",
      "lat": 28.6129,
      "lng": 77.2295,
      "type": "historic",
      "distance_meters": 1820.5
    }
  ],
  "food": [
    {
      "name": "Pandara Road Market",
      "lat": 28.6080,
      "lng": 77.2340,
      "type": "restaurant",
      "distance_meters": 2400.1
    }
  ],
  "markets": []
}
```

---

## 9. `GET /hidden-gems`

Returns offbeat, lesser-known travel gems and viewpoints discovered through deep web crawling and Reddit mining.

### Query Parameters
- `location` *(string, required)*: Target city or region (e.g., `Jaipur`).

### cURL Example
```bash
curl -X GET "http://localhost:8000/hidden-gems?location=Jaipur"
```

### Response Schema (`200 OK`)
```json
[
  {
    "name": "Panna Meena Ka Kund",
    "category": "Architecture / Stepwell",
    "description": "An exquisite 16th-century symmetrical stepwell tucked away near Amer Fort, quiet and photogenic.",
    "confidence_score": 0.92,
    "source": "osm_and_reddit"
  },
  {
    "name": "Galtaji Temple (Monkey Temple)",
    "category": "Hidden Heritage",
    "description": "Ancient Hindu pilgrimage complex set within a mountain pass with natural water springs.",
    "confidence_score": 0.88,
    "source": "reddit"
  }
]
```

---

## 10. `GET /tips`

Retrieves authentic community tips and local advice for a city or specific landmark.

### Query Parameters
- `city` *(string, optional)*: Filter tips by city name (e.g., `Delhi`).
- `place_id` *(int, optional)*: Filter tips by database place ID.

### cURL Example
```bash
curl -X GET "http://localhost:8000/tips?city=Delhi"
```

### Response Schema (`200 OK`)
```json
[
  {
    "id": 102,
    "city": "Delhi",
    "place_id": 14,
    "tip_text": "Avoid auto-rickshaws charging flat rates outside the station; use the prepaid booth or metro.",
    "source": "reddit",
    "confidence_score": 1.0,
    "created_at": "2026-09-10T14:32:00"
  }
]
```

---

## 11. `GET /health`

System health check endpoint verifying live status of Supabase PostgreSQL and Valkey cache.

### Response Schema (`200 OK`)
```json
{
  "status": "ok",
  "database": "ok",
  "valkey": "ok"
}
```

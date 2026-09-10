---
layout: docs
title: Image Resolution Engine
nav_order: 4
---

# Zero-Hallucination Image Resolution Engine

The **`PlaceImageResolver`** service provides real, place-specific image URLs for search results, place suggestions, and travel itineraries.

---

## Zero-Hallucination Policy

Traditional LLM applications often attempt to guess or synthesize image URLs (e.g. `https://example.com/red_fort.jpg`), leading to broken images and 404 errors. 

**Ghumo Backend strict policy**:
- The LLM is **never** permitted to generate image URLs.
- The backend resolves actual place images concurrently using external providers.

---

## Provider Fallback Pipeline

When resolving an image for a place (e.g., `Anangpur Dam`, city `Faridabad`), `PlaceImageResolver` executes providers in strict priority order:

```
                  ┌───────────────────────────────┐
                  │   1. Check Valkey Image Cache │
                  └───────────────┬───────────────┘
                                  │ (Cache Miss)
                                  ▼
                  ┌───────────────────────────────┐
                  │ 2. Wikidata / Wikimedia Provider│
                  └───────────────┬───────────────┘
                                  │ (No Image Found)
                                  ▼
                  ┌───────────────────────────────┐
                  │    3. Unsplash Provider       │
                  └───────────────┬───────────────┘
                                  │ (No Image Found)
                                  ▼
                  ┌───────────────────────────────┐
                  │ 4. Google Places API Provider │
                  └───────────────────────────────┘
```

### Provider Priority Breakdown:
1. **Wikimedia Commons / Wikidata** *(Primary Free Provider)*:
   Queries Wikidata entity claim `P18` (image filename) and retrieves high-res direct URLs from Wikimedia Commons.
2. **Unsplash API** *(Secondary Provider)*:
   Invoked when `UNSPLASH_ACCESS_KEY` is configured and Wikidata has no image match.
3. **Google Places API** *(Optional Fallback)*:
   Invoked when `GOOGLE_PLACES_API_KEY` is enabled.

---

## Caching Policy & TTL

To prevent unnecessary API requests:
- **Valid Resolved Image**: Cached in Valkey for **7 days** (`604,800s`).
- **No Image Found**: Cached in Valkey for **1 hour** (`3,600s`) to prevent rapid retries.

```python
cache_key = f"image:{p_slug}:{c_slug}:{country_slug}"
ttl = 604800 if image_result else 3600
await cache_service.set_cache(cache_key, {"image": image_result}, ttl=ttl)
```

---

## Batch Concurrent Resolution

When enriching place lists in `/search`, `/suggestions`, or `/itinerary`, `resolve_places_batch` processes items asynchronously with a configurable timeout (default 4.0s):

```python
await place_image_resolver.resolve_places_batch(places_list, timeout=4.0)
```

---
layout: docs
title: Place Quality Validator
description: Documentation for Ghumo Backend's Quality Validation Layer, filtering rules, and canonical place name normalization.
order: 4
nav_order: 4
---

# 🛡️ Place Quality Validator

The **`PlaceQualityValidator`** service is a dedicated quality gate designed to prevent corrupt, empty, or generic placeholders from entering the database, Valkey hot cache, or API responses.

---

## 🎯 Validation Rules & Criteria

Every place item (from OpenStreetMap, Google Places, AI context, or raw web scrapes) must pass the following validation pipeline:

```
[Raw Place Dictionary]
          │
          ▼
   1. Dict Check ──────> Is item a valid dict?
          │
          ▼
   2. Name Check ──────> Name length >= 2 chars & NOT in GENERIC_NAMES list
          │
          ▼
   3. Coords Check ────> -90 <= lat <= 90 AND -180 <= lng <= 180 AND NOT (0.0, 0.0)
          │
          ▼
   4. Sanitization ────> Standardize fields ("type", "name", "category")
          │
          ▼
   [PASSED Quality Gate]
```

---

## 🚫 Generic Placeholder Filter (`GENERIC_NAMES`)

Items with names matching any of the following case-insensitive strings are immediately rejected:

```python
GENERIC_NAMES = {
    "unknown", 
    "point of interest", 
    "place", 
    "n/a", 
    "null", 
    "undefined", 
    "checking...", 
    "none", 
    "location"
}
```

---

## 🔤 Canonical Place Name Normalization

To enforce place deduplication across PostgreSQL and Valkey, `normalize_place_name` transforms place strings into canonical keys:

```python
@classmethod
def normalize_place_name(cls, name: str) -> str:
    """
    Normalizes a place name for canonical deduplication.
    Lowercases, strips punctuation, and collapses whitespace.
    """
    import re
    if not name:
        return ""
    clean = re.sub(r'[^\w\s]', '', str(name).lower())
    return ' '.join(clean.split())
```

### Examples of Normalization:

| Raw Input | Normalized Key |
| :--- | :--- |
| `Red Fort (Lal Qila)` | `red fort lal qila` |
| `The Reader's Cafe!` | `the readers cafe` |
| `  Chandni   Chowk  ` | `chandni chowk` |

---

## 🧪 Unit Tests

Quality validator logic is covered by unit tests in [`tests/test_place_quality_validator.py`](file:///c:/Users/ashki/OneDrive/Documents/Ghumo/ghumo_backend/tests/test_place_quality_validator.py):

```bash
python -m pytest tests/test_place_quality_validator.py
```

---

*Next Chapter: [Zero-Hallucination Image Resolution Engine →](image-resolution-engine.html)*

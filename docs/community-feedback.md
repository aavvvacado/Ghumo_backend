---
layout: docs
title: Community Ratings & Feedback Loop
description: Bayesian weighted confidence rating system, user single-vote deduplication, and feedback service API documentation.
---

# ⭐ Community Ratings & Feedback Loop

Ghumo Backend includes a community feedback engine that accepts 1 to 5 star ratings for places, itineraries, and recommendations.

---

## 🔒 Single Active Rating Per User (`TargetFeedback`)

To prevent rating manipulation, the system enforces a **single active rating per user per target**:

- DB Model: `TargetFeedback`
- Unique Constraint: `uq_user_target_feedback` on `(user_id_or_anon, target_type, target_id)`.
- **Upsert Behavior**: If a user submits a new rating for the same target, the existing record is updated rather than creating duplicate entries.

```python
existing = db.query(TargetFeedback).filter(
    TargetFeedback.user_id_or_anon == user_id_or_anon,
    TargetFeedback.target_type == target_type,
    TargetFeedback.target_id == target_id
).first()

if existing:
    existing.rating = rating
    existing.updated_at = datetime.utcnow()
else:
    new_fb = TargetFeedback(...)
    db.add(new_fb)
```

---

## 🧮 Bayesian Weighted Confidence Formula

To avoid ranking a place with one 5-star review higher than a place with fifty 4.8-star reviews, `feedback_service` calculates a **Bayesian Weighted Score**:

$$W = \frac{v}{v + m} R + \frac{m}{v + m} C$$

### Variable Definitions:
- $v$: Total vote count for the target (`ratingCount`).
- $m$: Minimum threshold of votes required for confidence (configured via `MIN_FEEDBACK_COUNT`, default: `5`).
- $R$: Arithmetic mean rating for the target (`averageRating`).
- $C$: Global prior average rating across all targets (default: `4.0`).

---

## ⚡ API Response Payload Integration

Place objects returned by `/search`, `/search/stream`, and `/suggestions` automatically include the backward-compatible `feedback` block:

```json
"feedback": {
  "averageRating": 4.8,
  "ratingCount": 15,
  "weightedScore": 4.62
}
```

---

## 🧪 Unit Tests

Covered in [`tests/test_community_feedback.py`](file:///c:/Users/ashki/OneDrive/Documents/Ghumo/ghumo_backend/tests/test_community_feedback.py):

```bash
python -m pytest tests/test_community_feedback.py
```

---

*Next Chapter: [Database Schema & Indexing Guide →](database-schema.html)*

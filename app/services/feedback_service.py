import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database.models import TargetFeedback
from app.services.cache_service import cache_service
from app.utils.config import settings

logger = logging.getLogger(__name__)

class FeedbackService:
    """
    Community Feedback Service:
    - Enforces 1 active rating per user per target (updates existing rating on re-submission).
    - Computes aggregated rating metrics and Bayesian confidence-adjusted weighted scores.
    - Manages hot Valkey cache for feedback aggregates.
    """

    async def submit_feedback(
        self,
        db: Session,
        user_id_or_anon: str,
        target_type: str,
        target_id: str,
        rating: int
    ) -> Dict[str, Any]:
        if not (1 <= rating <= 5):
            raise ValueError("Rating must be an integer between 1 and 5.")

        target_type = target_type.lower().strip()
        target_id = str(target_id).strip()
        user_id_or_anon = str(user_id_or_anon).strip()

        if target_type not in {"place", "itinerary", "recommendation"}:
            raise ValueError("Invalid target_type. Allowed: 'place', 'itinerary', 'recommendation'.")

        # Check existing feedback for this user & target
        existing = db.query(TargetFeedback).filter(
            TargetFeedback.user_id_or_anon == user_id_or_anon,
            TargetFeedback.target_type == target_type,
            TargetFeedback.target_id == target_id
        ).first()

        if existing:
            logger.info(f"Updating existing feedback ID {existing.id} for user '{user_id_or_anon}' to rating {rating}")
            existing.rating = rating
        else:
            logger.info(f"Creating new feedback for user '{user_id_or_anon}' on {target_type}:{target_id}")
            new_fb = TargetFeedback(
                user_id_or_anon=user_id_or_anon,
                target_type=target_type,
                target_id=target_id,
                rating=rating
            )
            db.add(new_fb)

        db.commit()

        # Invalidate Valkey cache for this target feedback aggregate
        cache_key = f"feedback_stats:{target_type}:{target_id}"
        try:
            await cache_service.delete_cache(cache_key)
        except Exception as cache_err:
            logger.debug(f"Failed to clear feedback cache key {cache_key}: {cache_err}")

        # Compute updated aggregate
        summary = await self.get_feedback_summary(db, target_type, target_id)
        return summary

    async def get_feedback_summary(self, db: Session, target_type: str, target_id: str) -> Dict[str, Any]:
        target_type = target_type.lower().strip()
        target_id = str(target_id).strip()
        cache_key = f"feedback_stats:{target_type}:{target_id}"

        # 1. Check Valkey hot cache
        try:
            cached = await cache_service.get_cache(cache_key)
            if cached is not None:
                return cached
        except Exception:
            pass

        # 2. Query DB aggregates
        feedbacks = db.query(TargetFeedback.rating).filter(
            TargetFeedback.target_type == target_type,
            TargetFeedback.target_id == target_id
        ).all()

        if not feedbacks:
            result = {
                "averageRating": None,
                "ratingCount": 0,
                "weightedScore": None,
                "distribution": {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
            }
            try:
                await cache_service.set_cache(cache_key, result, ttl=86400)
            except Exception:
                pass
            return result

        ratings = [f.rating for f in feedbacks]
        count = len(ratings)
        avg_rating = round(sum(ratings) / count, 1)

        distribution = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
        for r in ratings:
            str_r = str(r)
            if str_r in distribution:
                distribution[str_r] += 1

        # 3. Bayesian Weighted Rating Calculation
        m = settings.MIN_FEEDBACK_COUNT  # default: 5
        c = 4.0  # global mean assumption
        weighted_score = round(((count / (count + m)) * avg_rating) + ((m / (count + m)) * c), 2)

        result = {
            "averageRating": avg_rating,
            "ratingCount": count,
            "weightedScore": weighted_score if count >= m else None,
            "distribution": distribution
        }

        try:
            await cache_service.set_cache(cache_key, result, ttl=86400)
        except Exception:
            pass

        return result

    async def attach_feedback_to_item(self, db: Session, item: Dict[str, Any], target_type: str = "place") -> Dict[str, Any]:
        if not isinstance(item, dict):
            return item

        target_id = item.get("id") or item.get("name") or item.get("place")
        if not target_id:
            item["feedback"] = {"averageRating": None, "ratingCount": 0}
            return item

        summary = await self.get_feedback_summary(db, target_type, str(target_id))
        item["feedback"] = {
            "averageRating": summary.get("averageRating"),
            "ratingCount": summary.get("ratingCount")
        }
        return item

feedback_service = FeedbackService()

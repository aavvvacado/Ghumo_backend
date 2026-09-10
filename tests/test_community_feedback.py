import pytest
import asyncio
from unittest.mock import MagicMock
from app.services.feedback_service import feedback_service
from app.database.models import Base, TargetFeedback
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

@pytest.fixture
def in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_submit_and_deduplicate_feedback(in_memory_db):
    async def _test():
        # First rating: 4 stars
        summary1 = await feedback_service.submit_feedback(
            db=in_memory_db,
            user_id_or_anon="user123",
            target_type="place",
            target_id="taj_mahal",
            rating=4
        )
        assert summary1["ratingCount"] == 1
        assert summary1["averageRating"] == 4.0

        # User updates rating to 5 stars (should NOT duplicate row)
        summary2 = await feedback_service.submit_feedback(
            db=in_memory_db,
            user_id_or_anon="user123",
            target_type="place",
            target_id="taj_mahal",
            rating=5
        )
        assert summary2["ratingCount"] == 1
        assert summary2["averageRating"] == 5.0

        # Second user rates 3 stars
        summary3 = await feedback_service.submit_feedback(
            db=in_memory_db,
            user_id_or_anon="user456",
            target_type="place",
            target_id="taj_mahal",
            rating=3
        )
        assert summary3["ratingCount"] == 2
        assert summary3["averageRating"] == 4.0

    asyncio.run(_test())

def test_invalid_rating_bounds(in_memory_db):
    async def _test():
        with pytest.raises(ValueError):
            await feedback_service.submit_feedback(
                db=in_memory_db,
                user_id_or_anon="user123",
                target_type="place",
                target_id="taj_mahal",
                rating=6
            )
    asyncio.run(_test())

def test_attach_feedback_to_item(in_memory_db):
    async def _test():
        await feedback_service.submit_feedback(
            db=in_memory_db,
            user_id_or_anon="user123",
            target_type="place",
            target_id="Red Fort",
            rating=5
        )
        item = {"name": "Red Fort", "type": "attraction"}
        enriched = await feedback_service.attach_feedback_to_item(in_memory_db, item, target_type="place")
        assert "feedback" in enriched
        assert enriched["feedback"]["averageRating"] == 5.0
        assert enriched["feedback"]["ratingCount"] == 1

    asyncio.run(_test())

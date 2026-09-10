from sqlalchemy import Column, Integer, String, Float, JSON, ForeignKey, DateTime, Index, UniqueConstraint
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()

class Place(Base):
    __tablename__ = "places"

    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String, unique=True, index=True)  # Google/OSM/OTM ID
    name = Column(String, index=True)
    normalized_name = Column(String, index=True)
    category = Column(String)  # restaurant, attraction, market, etc.
    lat = Column(Float)
    lng = Column(Float)
    city = Column(String, index=True)
    source = Column(String)  # osm, opentripmap
    confidence_score = Column(Float, default=0.0)
    source_count = Column(Integer, default=1)
    search_count = Column(Integer, default=1, index=True)
    last_searched_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_place_norm_city", "normalized_name", "city"),
    )

class Itinerary(Base):
    __tablename__ = "itineraries"

    id = Column(Integer, primary_key=True, index=True)
    location = Column(String)
    time_available = Column(String)
    interests = Column(JSON)
    budget = Column(String)
    content = Column(JSON)  # The structured itinerary
    created_at = Column(DateTime, default=datetime.utcnow)

class HiddenGem(Base):
    __tablename__ = "hidden_gems"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    category = Column(String)
    lat = Column(Float)
    lng = Column(Float)
    city = Column(String, index=True)
    source = Column(String)  # blog, reddit, osm, etc.
    confidence_score = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

class PlaceRelation(Base):
    __tablename__ = "place_relations"

    id = Column(Integer, primary_key=True, index=True)
    place_id = Column(Integer, ForeignKey("places.id"), index=True)
    related_place_id = Column(Integer, ForeignKey("places.id"), index=True, nullable=True)
    relation_type = Column(String)  # nearby, same_cluster, food_near_landmark, market_in_area
    confidence = Column(Float, default=1.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    place = relationship("Place", foreign_keys=[place_id], backref="relations")
    related_place = relationship("Place", foreign_keys=[related_place_id])

class TravelTip(Base):
    __tablename__ = "travel_tips"

    id = Column(Integer, primary_key=True, index=True)
    place_id = Column(Integer, ForeignKey("places.id"), index=True, nullable=True)
    city = Column(String, index=True) # city context
    tip_text = Column(String)
    source = Column(String) # reddit, blog, ai
    confidence_score = Column(Float, default=1.0)
    created_at = Column(DateTime, default=datetime.utcnow)

class AIContext(Base):
    __tablename__ = "ai_context"

    id = Column(Integer, primary_key=True, index=True)
    query = Column(String, index=True)
    ai_response = Column(JSON)
    sources = Column(JSON) # List of sources like ["reddit", "osm"]
    confidence_score = Column(Float)
    search_count = Column(Integer, default=1, index=True)
    last_searched_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

class UserFeedback(Base):
    __tablename__ = "user_feedback"

    id = Column(Integer, primary_key=True, index=True)
    itinerary_id = Column(Integer, ForeignKey("itineraries.id"), index=True)
    rating = Column(Integer) # 1-5
    feedback_text = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    itinerary = relationship("Itinerary", backref="feedbacks")

class TargetFeedback(Base):
    __tablename__ = "target_feedback"

    id = Column(Integer, primary_key=True, index=True)
    user_id_or_anon = Column(String, index=True)
    target_type = Column(String, index=True)  # place, itinerary, recommendation
    target_id = Column(String, index=True)
    rating = Column(Integer)  # 1-5
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id_or_anon", "target_type", "target_id", name="uq_user_target_feedback"),
        Index("idx_target_feedback_target", "target_type", "target_id"),
    )

class ItineraryVersion(Base):
    __tablename__ = "itinerary_versions"

    id = Column(Integer, primary_key=True, index=True)
    itinerary_id = Column(Integer, ForeignKey("itineraries.id"), index=True)
    version = Column(Integer)
    score = Column(Float)
    generated_by = Column(String) # groq, llama, etc.
    content = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

    itinerary = relationship("Itinerary", backref="versions")

class SearchHistory(Base):
    __tablename__ = "search_history"
    id = Column(Integer, primary_key=True, index=True)
    query = Column(String, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class LocalContribution(Base):
    __tablename__ = "local_contributions"

    id = Column(Integer, primary_key=True, index=True)
    location = Column(String, index=True) # City name or general region
    name = Column(String, index=True)
    description = Column(String)
    category = Column(String) # food, market, attraction, hidden_gem
    lat = Column(Float)
    lng = Column(Float)
    submitted_by = Column(String, default="anonymous_captain")
    is_verified = Column(Integer, default=1) # Auto-verified for now as per "captain" role
    created_at = Column(DateTime, default=datetime.utcnow)

class RawScrape(Base):
    __tablename__ = "raw_scrapes"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, unique=True, index=True)
    content = Column(String)
    source = Column(String, index=True) # tripoto, inditales, etc.
    query = Column(String, index=True) # The search query used to find this
    created_at = Column(DateTime, default=datetime.utcnow)

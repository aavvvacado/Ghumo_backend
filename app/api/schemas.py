from pydantic import BaseModel
from typing import List, Optional, Any

class ItineraryRequest(BaseModel):
    location: str
    time_available: str
    interests: List[str]
    budget: str

class SearchStreamRequest(BaseModel):
    query: str

class VideoItineraryRequest(BaseModel):
    url: str

class PlaceResponse(BaseModel):
    name: str
    type: str
    lat: float
    lng: float
    distance: Optional[float] = 0
    source: str

class HiddenGemResponse(BaseModel):
    name: str
    type: str
    lat: float
    lng: float
    description: Optional[str] = "Discovered gem"
    score: float
    source: str

class TravelTipResponse(BaseModel):
    id: int
    tip_text: str
    source: str
    confidence_score: float

class SearchResponse(BaseModel):
    location: str
    coordinates: dict = {}
    places: List[dict] = []
    food: List[dict] = []
    markets: List[dict] = []
    attractions: List[dict] = []
    hidden_gems: List[dict] = []
    tips: List[dict] = []
    enriching: bool = False

class JobResponse(BaseModel):
    job_id: str
    status: str
    message: str

class SearchStatusResponse(BaseModel):
    id: str
    status: str
    result: Optional[SearchResponse] = None
    error: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None

class NearbyResponse(BaseModel):
    restaurants: List[Any]
    attractions: List[Any]
    markets: List[Any]
    transport: List[Any]

class ItineraryResponse(BaseModel):
    location: str
    itinerary: str
    recommended_places: List[Any]
    recommended_attractions: List[Any]

class HealthResponse(BaseModel):
    status: str
    database: str
    valkey: str

class RelationResponse(BaseModel):
    place_name: str
    relations: List[dict]

class SyncResponse(BaseModel):
    status: str
    message: str
    job_id: Optional[str] = None
class FeedbackRequest(BaseModel):
    itinerary_id: int
    rating: int
    feedback_text: Optional[str] = None

class SearchHistoryResponse(BaseModel):
    query: str
    created_at: str

class RecommendationResponse(BaseModel):
    category: str
    places: List[dict]

class ContributionRequest(BaseModel):
    location: str
    name: str
    description: str
    category: str
    lat: float
    lng: float
    submitted_by: Optional[str] = "anonymous_captain"

class ContributionResponse(BaseModel):
    status: str
    message: str
    contribution_id: int

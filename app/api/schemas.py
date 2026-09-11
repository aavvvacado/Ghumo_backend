from pydantic import BaseModel, validator
from typing import List, Optional, Any, Union

class ItineraryActivityItem(BaseModel):
    time_slot: Optional[str] = "Morning"  # e.g., "09:00 AM - 11:30 AM" or "Morning"
    place: str
    duration: Optional[str] = "2 hours"
    purpose: Optional[str] = "Sightseeing and photography"
    cost_estimate: Optional[str] = "Free"
    notes: Optional[str] = None
    image: Optional[dict] = None

class ItineraryDayChunk(BaseModel):
    day: int  # 1, 2, 3...
    title: Optional[str] = "Exploration & Sightseeing"
    stay_recommendation: Optional[str] = None  # Neighborhood or hotel type
    estimated_day_cost: Optional[str] = None
    activities: List[ItineraryActivityItem] = []

class ItineraryTimeChunk(BaseModel):
    slot: str  # "Morning", "Afternoon", "Evening", "Night"
    time_range: Optional[str] = None  # e.g. "09:00 AM - 12:30 PM"
    activities: List[ItineraryActivityItem] = []

class StructuredItineraryPlan(BaseModel):
    mode: str = "day_wise"  # "day_wise" or "time_wise"
    destination: str
    total_duration: str
    estimated_total_budget: str
    stay_area: Optional[str] = None
    summary: Optional[str] = None
    budget_breakdown: Optional[dict] = None  # { "stay": "...", "food": "...", "activities": "...", "transport": "..." }
    days: Optional[List[ItineraryDayChunk]] = None
    time_slots: Optional[List[ItineraryTimeChunk]] = None
    markdown_table: Optional[str] = None

class ItineraryRequest(BaseModel):
    prompt: Optional[str] = None  # Raw conversational text e.g. "visiting Jaipur for 2 days on low budget"
    location: Optional[str] = None
    time_available: Optional[str] = None
    interests: Optional[List[str]] = []
    budget: Optional[str] = None

    @validator("location", always=True)
    def validate_inputs(cls, v, values):
        # Must have either prompt or location
        if not v and not values.get("prompt"):
            raise ValueError("Either 'prompt' or 'location' must be provided.")
        return v

class SearchStreamRequest(BaseModel):
    query: str

class VideoItineraryRequest(BaseModel):
    url: str

class ImageInfo(BaseModel):
    url: Optional[str] = None
    source: Optional[str] = None
    attribution: Optional[str] = None

class PlaceResponse(BaseModel):
    name: str
    type: str
    lat: float
    lng: float
    distance: Optional[float] = 0
    source: str
    image: Optional[ImageInfo] = None

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
    tips: List[Union[dict, str]] = []
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
    recommended_places: List[Any] = []
    recommended_attractions: List[Any] = []
    plan: Optional[StructuredItineraryPlan] = None
    parsed_requirements: Optional[dict] = None

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

class TargetFeedbackRequest(BaseModel):
    target_type: str  # "place", "itinerary", "recommendation"
    target_id: str
    rating: int  # 1-5
    user_id_or_anon: Optional[str] = "anonymous"

class TargetFeedbackResponse(BaseModel):
    status: str
    target_type: str
    target_id: str
    average_rating: Optional[float] = None
    rating_count: int = 0
    weighted_score: Optional[float] = None

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

class PlaceSuggestionItem(BaseModel):
    id: Optional[int] = None
    name: str
    city: Optional[str] = ""
    category: Optional[str] = "places"
    lat: Optional[float] = None
    lng: Optional[float] = None
    search_count: int = 1
    image: Optional[dict] = None
    feedback: Optional[dict] = None

class SuggestionsResponse(BaseModel):
    total: int
    suggestions: List[PlaceSuggestionItem]


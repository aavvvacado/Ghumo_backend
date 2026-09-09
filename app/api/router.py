from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import List, Optional
import logging
import asyncio
import json
from app.api.schemas import (
    ItineraryRequest, SearchResponse, NearbyResponse, 
    ItineraryResponse, HiddenGemResponse, JobResponse, 
    SearchStatusResponse, HealthResponse, RelationResponse,
    SyncResponse, TravelTipResponse, FeedbackRequest,
    SearchHistoryResponse, RecommendationResponse,
    ContributionRequest, ContributionResponse,
    VideoItineraryRequest, SearchStreamRequest)
from app.services.enrichment_service import enrichment_service
from app.services.search_service import search_service
from app.services.nearby_service import nearby_service
from app.services.itinerary_service import itinerary_service
from app.services.opentripmap import opentripmap
from app.services.hidden_gems_service import hidden_gems_service
from app.services.job_service import job_manager, JobStatus
from app.services.knowledge_graph_service import knowledge_graph_service
from app.services.cache_service import cache_service
from app.database.session import engine
from sqlalchemy import text

# Define logger before anything else uses it
logger = logging.getLogger(__name__)

router = APIRouter()

async def run_search_task(job_id: str, query: str):
    try:
        await job_manager.update_job(job_id, JobStatus.PROCESSING)
        result = await search_service.search_all(query)
        await job_manager.update_job(job_id, JobStatus.COMPLETED, result=result)
    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        await job_manager.update_job(job_id, JobStatus.FAILED, error=str(e))

from app.tasks.miner_tasks import context_enrichment_task

@router.get("/search", response_model=SearchResponse)
async def search(query: str):
    logger.info(f"Received fast-search request for: {query}")
    
    # 1. Check cache / fast DB and return immediately if found
    results = await enrichment_service.get_fast_results(query)
    
    # 2. Trigger background enrichment if "shallow" or new
    if results.get("enriching"):
        task_name = f"context_enrichment_{query}"
        job_id = await job_manager.get_active_job_by_task(task_name)
        
        if not job_id:
            logger.info(f"No active job for {query}. Triggering background enrichment...")
            job_id = await job_manager.create_job(task_name)
            lat = results.get("coordinates", {}).get("lat")
            lng = results.get("coordinates", {}).get("lng")
            
            # Trigger Celery
            context_enrichment_task.apply_async(args=[job_id, query, lat, lng], task_id=job_id)
        else:
            logger.info(f"Existing active job found for {query}: {job_id}")

        # --- SMART WAIT LOOP (First-Time User Experience) ---
        # If this is a new place (no results yet), we wait up to 60s for the first batch of results.
        if not results.get("places") and not results.get("food"):
            logger.info(f"New location detected: {query}. Starting synchronous wait for deep research (Up to 60s)...")
            max_attempts = 30  # 30 * 2s = 60 seconds wait
            for attempt in range(max_attempts):
                await asyncio.sleep(2.0)
                
                # Check for intermediate results in cache
                updated_results = await enrichment_service.get_fast_results(query)
                
                # Return as soon as we have places/food OR enrichment finishes
                if (updated_results.get("places") or updated_results.get("food")) or not updated_results.get("enriching"):
                    logger.info(f"Research complete for {query} after {attempt+1} attempts.")
                    return updated_results
                
                if (attempt + 1) % 5 == 0:
                    logger.info(f"Still researching {query}... (Attempt {attempt+1}/{max_attempts})")
            
            logger.warning(f"Wait timed out for {query} after 60s. Returning best available.")
            return await enrichment_service.get_fast_results(query)

    # 3. Return immediately for known places (sub-200ms)
    return results

@router.post("/search/stream")
@router.get("/search/stream")
async def search_stream(request: Optional[SearchStreamRequest] = None, query: Optional[str] = None):
    """
    Server-Sent Events (SSE) streaming endpoint for search enrichment progress.
    Accepts JSON body `{"query": "..."}` via POST or `?query=...` via GET.
    """
    search_query = (request.query if request else None) or query
    if not search_query:
        raise HTTPException(status_code=400, detail="Query parameter or body is required.")

    async def event_generator():
        yield f"event: progress\ndata: {json.dumps({'step': 'init', 'message': f'Starting intelligence search for {search_query}'})}\n\n"
        await asyncio.sleep(0.2)

        # 1. Fast cache check
        results = await enrichment_service.get_fast_results(search_query)
        if not results.get("enriching") and (results.get("places") or results.get("food")):
            yield f"event: progress\ndata: {json.dumps({'step': 'cache_hit', 'message': 'Loaded from intelligence cache'})}\n\n"
            yield f"event: complete\ndata: {json.dumps({'step': 'complete', 'data': results})}\n\n"
            return

        # 2. Trigger background enrichment
        task_name = f"context_enrichment_{search_query}"
        job_id = await job_manager.get_active_job_by_task(task_name)
        if not job_id:
            job_id = await job_manager.create_job(task_name)
            lat = results.get("coordinates", {}).get("lat")
            lng = results.get("coordinates", {}).get("lng")
            context_enrichment_task.apply_async(args=[job_id, search_query, lat, lng], task_id=job_id)

        yield f"event: progress\ndata: {json.dumps({'step': 'mining', 'message': 'Mining YouTube, Reddit, Blogs & OpenStreetMap POIs...', 'job_id': job_id})}\n\n"

        # Poll cache until enrichment completes or max attempts reached
        max_attempts = 40
        for attempt in range(max_attempts):
            await asyncio.sleep(1.5)
            latest = await enrichment_service.get_fast_results(search_query)
            
            milestone = latest.get("milestone")
            if milestone == "physical_scan_complete":
                found_count = len(latest.get("places", []))
                yield f"event: progress\ndata: {json.dumps({'step': 'osm_complete', 'message': f'Found {found_count} places via map scan. Synthesizing AI reasoning with Gemini...', 'data': latest})}\n\n"
            else:
                yield f"event: progress\ndata: {json.dumps({'step': 'researching', 'attempt': attempt+1, 'message': f'Researching... ({attempt+1}/{max_attempts})'})}\n\n"

            if (latest.get("places") or latest.get("food")) and not latest.get("enriching"):
                yield f"event: complete\ndata: {json.dumps({'step': 'complete', 'message': 'Research complete', 'data': latest})}\n\n"
                return

        final_res = await enrichment_service.get_fast_results(search_query)
        yield f"event: complete\ndata: {json.dumps({'step': 'complete', 'message': 'Done', 'data': final_res})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/search-status", response_model=SearchStatusResponse)
async def get_search_status(id: str):
    job = await job_manager.get_job(id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    # Mapping id to id for SearchStatusResponse schema if needed, 
    # but job_service already puts "id" in the dict.
    return job

@router.get("/nearby", response_model=NearbyResponse)
async def nearby(lat: float, lng: float, radius: int = 5000):
    return await nearby_service.get_nearby_all(lat, lng, radius)

@router.get("/place/{id}")
async def get_place(id: str):
    details = await opentripmap.get_place_xid(id)
    if not details:
        raise HTTPException(status_code=404, detail="Place not found")
    return details

@router.post("/itinerary", response_model=ItineraryResponse)
async def create_itinerary(request: ItineraryRequest):
    return await itinerary_service.generate_itinerary(
        request.location,
        request.time_available,
        request.interests,
        request.budget
    )

@router.post("/itinerary/stream")
async def create_itinerary_stream(request: ItineraryRequest):
    """
    Server-Sent Events (SSE) streaming endpoint for itinerary generation.
    Accepts JSON body `ItineraryRequest`.
    """
    async def event_generator():
        yield f"event: progress\ndata: {json.dumps({'step': 'init', 'message': f'Initiating itinerary planner for {request.location}...'})}\n\n"
        await asyncio.sleep(0.3)

        yield f"event: progress\ndata: {json.dumps({'step': 'ai_generation', 'message': f'Generating personalized {request.time_available} travel plan with Gemini AI...'})}\n\n"

        result = await itinerary_service.generate_itinerary(
            request.location,
            request.time_available,
            request.interests,
            request.budget
        )

        yield f"event: complete\ndata: {json.dumps({'step': 'complete', 'message': 'Itinerary successfully generated', 'data': result})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.post("/itinerary/video", response_model=ItineraryResponse)
async def create_video_itinerary(request: VideoItineraryRequest):
    from app.services.social_mining import social_mining
    result = await social_mining.process_video_url(request.url)
    
    return {
        "location": result.get("location", "Unknown"),
        "itinerary": result.get("itinerary", "Could not generate itinerary."),
        "recommended_places": result.get("recommended_places", []),
        "recommended_attractions": []
    }

@router.get("/hidden-gems", response_model=List[dict])
async def get_hidden_gems(location: str):
    return await hidden_gems_service.discover_gems(location)

@router.get("/tips", response_model=List[TravelTipResponse])
async def get_tips(place_id: Optional[int] = None, city: Optional[str] = None):
    from app.database.session import SessionLocal
    from app.database.models import TravelTip
    db = SessionLocal()
    try:
        query = db.query(TravelTip)
        if place_id:
            query = query.filter(TravelTip.place_id == place_id)
        if city:
            query = query.filter(TravelTip.city.ilike(f"%{city}%"))
        return query.limit(20).all()
    finally:
        db.close()

@router.post("/feedback")
async def submit_feedback(request: FeedbackRequest):
    from app.database.session import SessionLocal
    from app.database.models import UserFeedback
    db = SessionLocal()
    try:
        feedback = UserFeedback(
            itinerary_id=request.itinerary_id,
            rating=request.rating,
            feedback_text=request.feedback_text
        )
        db.add(feedback)
        db.commit()
        return {"status": "success", "message": "Feedback submitted successfully"}
    except Exception as e:
        logger.error(f"Error submitting feedback: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        db.close()

@router.get("/feedback/{itinerary_id}")
async def get_feedback(itinerary_id: int):
    from app.database.session import SessionLocal
    from app.database.models import UserFeedback
    db = SessionLocal()
    try:
        feedback = db.query(UserFeedback).filter(UserFeedback.itinerary_id == itinerary_id).all()
        return feedback
    finally:
        db.close()

@router.get("/search-history", response_model=List[SearchHistoryResponse])
async def get_search_history():
    from app.database.session import SessionLocal
    from app.database.models import SearchHistory
    db = SessionLocal()
    try:
        history = db.query(SearchHistory).order_by(SearchHistory.created_at.desc()).limit(20).all()
        # Convert datetime to string for response
        return [{"query": h.query, "created_at": h.created_at.isoformat()} for h in history]
    finally:
        db.close()

@router.get("/recommendations", response_model=List[RecommendationResponse])
async def get_recommendations():
    # A smart learning mechanism to return top rated places based on user feedback
    # For now, we mock the logic of analyzing feedback and returning top recommendations
    return [
        {
            "category": "Top Rated by Travelers",
            "places": [
                {"name": "India Gate", "score": 9.8, "reason": "Consistent 5-star ratings"},
                {"name": "Paranthe Wali Gali", "score": 9.5, "reason": "Highly praised food experiences"}
            ]
        }
    ]

@router.get("/graph/related/{place_id}", response_model=RelationResponse)
async def get_related_places(place_id: int):
    relations = knowledge_graph_service.get_related_places(place_id)
    # Need to fetch place name if we want to be thorough, but for now just name from relations
    # Simplified return
    return {
        "place_name": f"Place ID {place_id}",
        "relations": relations
    }

@router.get("/health", response_model=HealthResponse)
async def health_check():
    db_status = "ok"
    valkey_status = "ok"
    
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"DB Health check failed: {e}")
        db_status = "error"
        
    try:
        if cache_service.valkey_client:
            await cache_service.valkey_client.ping()
        else:
            valkey_status = "error (not connected)"
    except Exception as e:
        logger.error(f"Valkey Health check failed: {e}")
        valkey_status = "error"
        
    return {
        "status": "ok" if db_status == "ok" and valkey_status == "ok" else "degraded",
        "database": db_status,
        "valkey": valkey_status
    }

@router.post("/crawlers/sync", response_model=SyncResponse)
async def trigger_sync(location: str, background_tasks: BackgroundTasks):
    # This would involve calling the crawlers which might be long running
    # For now, a mock job trigger
    job_id = await job_manager.create_job(f"sync_crawl_{location}")
    # background_tasks.add_task(run_crawl_task, job_id, location)
    return {
        "status": "started",
        "message": f"Crawl sync started for {location}",
        "job_id": job_id
    }

@router.post("/contribute", response_model=ContributionResponse)
async def submit_contribution(request: ContributionRequest):
    from app.database.session import SessionLocal
    from app.database.models import LocalContribution
    db = SessionLocal()
    try:
        contribution = LocalContribution(
            location=request.location.lower(),
            name=request.name,
            description=request.description,
            category=request.category,
            lat=request.lat,
            lng=request.lng,
            submitted_by=request.submitted_by
        )
        db.add(contribution)
        db.commit()
        db.refresh(contribution)
        return {"status": "success", "message": "Contribution submitted successfully", "contribution_id": contribution.id}
    except Exception as e:
        logger.error(f"Error submitting contribution: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        db.close()

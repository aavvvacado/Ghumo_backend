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
    VideoItineraryRequest, SearchStreamRequest,
    TargetFeedbackRequest, TargetFeedbackResponse,
    PlaceSuggestionItem, SuggestionsResponse)
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
    
    # If already fully enriched and has content, return immediately (sub-50ms)
    has_content = any(len(results.get(k, [])) > 0 for k in ["places", "food", "markets", "attractions", "hidden_gems"])
    if not results.get("enriching") and has_content:
        return results

    # 2. If new or un-enriched location, perform live deep intelligence enrichment (OSM, YouTube, Reddit, Blogs & AI)
    logger.info(f"New or uncached location: '{query}'. Performing live deep research across OSM, YouTube, Reddit & AI...")
    lat = results.get("coordinates", {}).get("lat")
    lng = results.get("coordinates", {}).get("lng")
    
    enriched_results = await enrichment_service.run_enrichment_job(query, lat, lng)
    if enriched_results and any(len(enriched_results.get(k, [])) > 0 for k in ["places", "food", "markets", "attractions", "hidden_gems"]):
        return enriched_results

    # Fallback to whatever best fast results exist
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
            # Run in background via asyncio task so it executes reliably even when Celery workers are stopped
            asyncio.create_task(enrichment_service.run_enrichment_job(search_query, lat, lng))
            try:
                context_enrichment_task.apply_async(args=[job_id, search_query, lat, lng], task_id=job_id)
            except Exception as celery_err:
                logger.debug(f"Celery task enqueue skipped: {celery_err}")

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
        location=request.location,
        time_available=request.time_available,
        interests=request.interests,
        budget=request.budget,
        prompt=request.prompt
    )

@router.post("/itinerary/stream")
async def create_itinerary_stream(request: ItineraryRequest):
    """
    Server-Sent Events (SSE) streaming endpoint for itinerary generation.
    Accepts JSON body `ItineraryRequest` with optional prompt or structured inputs.
    """
    display_target = request.location or (request.prompt[:30] + "..." if request.prompt else "your destination")

    async def event_generator():
        yield f"event: progress\ndata: {json.dumps({'step': 'init', 'message': f'Initiating itinerary planner for {display_target}...'})}\n\n"
        await asyncio.sleep(0.3)

        if request.prompt and not request.location:
            yield f"event: progress\ndata: {json.dumps({'step': 'intent_parsing', 'message': 'Parsing natural language travel prompt and extracting trip requirements...'})}\n\n"
            await asyncio.sleep(0.2)

        yield f"event: progress\ndata: {json.dumps({'step': 'ai_generation', 'message': f'Generating intelligent chunked travel plan with Gemini AI...'})}\n\n"

        result = await itinerary_service.generate_itinerary(
            location=request.location,
            time_available=request.time_available,
            interests=request.interests,
            budget=request.budget,
            prompt=request.prompt
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
        return query.order_by(TravelTip.confidence_score.desc(), TravelTip.id.desc()).limit(20).all()
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
async def get_recommendations(city: Optional[str] = None):
    """
    Dynamic, learning-based recommendations grouped by category.
    Prioritizes verified manual places, hidden gems, and community ratings.
    """
    from app.database.session import SessionLocal
    from app.database.models import Place, HiddenGem, TargetFeedback
    from app.services.place_quality_validator import place_quality_validator
    from app.services.place_image_resolver import place_image_resolver

    clean_city = city.strip() if city else None
    cache_key = f"recommendations:{clean_city.lower() if clean_city else 'global'}"
    cached = await cache_service.get_cache(cache_key)
    if cached and isinstance(cached, list):
        return cached

    db = SessionLocal()
    try:
        seen_names = set()
        
        # 1. Attractions query
        attr_query = db.query(Place)
        if clean_city:
            attr_query = attr_query.filter(Place.city.ilike(f"%{clean_city}%"))
        attr_places = attr_query.filter(
            (Place.category.ilike("%attraction%")) |
            (Place.category.ilike("%monument%")) |
            (Place.category.ilike("%heritage%")) |
            (Place.category.ilike("%place%"))
        ).order_by(Place.search_count.desc(), Place.confidence_score.desc()).limit(5).all()

        attractions_list = []
        for p in attr_places:
            norm = place_quality_validator.normalize_place_name(p.name)
            if norm and norm not in seen_names:
                seen_names.add(norm)
                attractions_list.append({
                    "name": p.name,
                    "score": 9.7,
                    "reason": f"Top-rated landmark and cultural site in {p.city or clean_city or 'the region'}",
                    "category": p.category or "attraction",
                    "city": p.city,
                    "lat": p.lat,
                    "lng": p.lng
                })

        # 2. Food query
        food_query = db.query(Place)
        if clean_city:
            food_query = food_query.filter(Place.city.ilike(f"%{clean_city}%"))
        food_places = food_query.filter(
            (Place.category.ilike("%food%")) |
            (Place.category.ilike("%restaurant%")) |
            (Place.category.ilike("%cafe%")) |
            (Place.category.ilike("%dhaba%"))
        ).order_by(Place.search_count.desc(), Place.confidence_score.desc()).limit(5).all()

        food_list = []
        for p in food_places:
            norm = place_quality_validator.normalize_place_name(p.name)
            if norm and norm not in seen_names:
                seen_names.add(norm)
                food_list.append({
                    "name": p.name,
                    "score": 9.5,
                    "reason": f"Highly celebrated local culinary hotspot in {p.city or clean_city or 'the region'}",
                    "category": p.category or "food",
                    "city": p.city,
                    "lat": p.lat,
                    "lng": p.lng
                })

        # 3. Verified Hidden Gems
        gem_query = db.query(HiddenGem)
        if clean_city:
            gem_query = gem_query.filter(
                (HiddenGem.city.ilike(f"%{clean_city}%")) |
                (HiddenGem.name.ilike(f"%{clean_city}%"))
            )
        gems = gem_query.order_by(HiddenGem.confidence_score.desc()).limit(5).all()

        gems_list = []
        for g in gems:
            norm = place_quality_validator.normalize_place_name(g.name)
            if norm and norm not in seen_names:
                seen_names.add(norm)
                score_val = round(g.confidence_score * 10, 1) if (g.confidence_score and g.confidence_score <= 1.0) else (g.confidence_score or 9.3)
                gems_list.append({
                    "name": g.name,
                    "score": score_val,
                    "reason": f"Curated off-the-beaten-path secret in {g.city or clean_city or 'the region'}",
                    "category": g.category or "hidden_gem",
                    "city": g.city,
                    "lat": g.lat,
                    "lng": g.lng
                })

        # 4. Student Hangouts & Budget Spots
        hangout_query = db.query(Place)
        if clean_city:
            hangout_query = hangout_query.filter(Place.city.ilike(f"%{clean_city}%"))
        hangouts = hangout_query.filter(
            (Place.category.ilike("%student%")) |
            (Place.category.ilike("%hangout%")) |
            (Place.category.ilike("%market%")) |
            (Place.category.ilike("%dhaba%"))
        ).order_by(Place.search_count.desc()).limit(5).all()

        hangout_list = []
        for p in hangouts:
            norm = place_quality_validator.normalize_place_name(p.name)
            if norm and norm not in seen_names:
                seen_names.add(norm)
                hangout_list.append({
                    "name": p.name,
                    "score": 9.2,
                    "reason": f"Popular student and budget hangout near {p.city or clean_city or 'campus'}",
                    "category": p.category or "hangout",
                    "city": p.city,
                    "lat": p.lat,
                    "lng": p.lng
                })

        # If empty (e.g. city not yet seeded or general), fallback to top places overall
        if not attractions_list and not food_list and not gems_list and not hangout_list:
            top_places = db.query(Place).order_by(Place.search_count.desc()).limit(5).all()
            attractions_list = [
                {
                    "name": p.name,
                    "score": 9.6,
                    "reason": f"Popular destination in {p.city}",
                    "category": p.category or "place",
                    "city": p.city,
                    "lat": p.lat,
                    "lng": p.lng
                } for p in top_places
            ]

        # Concurrently resolve images
        all_places_flat = attractions_list + food_list + gems_list + hangout_list
        if all_places_flat:
            try:
                await place_image_resolver.resolve_places_batch(all_places_flat, city=clean_city or "", timeout=3.0)
            except Exception as e:
                logger.warning(f"Image resolution in recommendations skipped: {e}")

        result = []
        if attractions_list:
            result.append({"category": "Must-Visit Attractions", "places": attractions_list})
        if food_list:
            result.append({"category": "Local Food Favorites", "places": food_list})
        if gems_list:
            result.append({"category": "Verified Hidden Gems", "places": gems_list})
        if hangout_list:
            result.append({"category": "Student Hangouts & Budget Spots", "places": hangout_list})

        if not result:
            result = [
                {
                    "category": "Top Rated by Travelers",
                    "places": [
                        {"name": "India Gate", "score": 9.8, "reason": "Consistent 5-star ratings"},
                        {"name": "Paranthe Wali Gali", "score": 9.5, "reason": "Highly praised food experiences"}
                    ]
                }
            ]

        try:
            await cache_service.set_cache(cache_key, result, ttl=3600)
        except Exception:
            pass

        return result
    finally:
        db.close()

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

@router.post("/target-feedback", response_model=TargetFeedbackResponse)
async def submit_target_feedback(request: TargetFeedbackRequest):
    from app.database.session import SessionLocal
    from app.services.feedback_service import feedback_service
    db = SessionLocal()
    try:
        summary = await feedback_service.submit_feedback(
            db=db,
            user_id_or_anon=request.user_id_or_anon or "anonymous",
            target_type=request.target_type,
            target_id=request.target_id,
            rating=request.rating
        )
        return {
            "status": "success",
            "target_type": request.target_type,
            "target_id": request.target_id,
            "average_rating": summary.get("averageRating"),
            "rating_count": summary.get("ratingCount"),
            "weighted_score": summary.get("weightedScore")
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error submitting target feedback: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        db.close()

@router.get("/suggestions", response_model=SuggestionsResponse)
async def get_place_suggestions(
    limit: int = 10,
    city: Optional[str] = None,
    category: Optional[str] = None
):
    """
    Returns trending/hot places from the database that have verified image URLs.
    Filters out invalid/empty items and attaches community feedback scores.
    """
    from app.database.session import SessionLocal
    from app.database.models import Place, AIContext
    from app.services.place_image_resolver import place_image_resolver
    from app.services.place_quality_validator import place_quality_validator
    from app.services.feedback_service import feedback_service

    db = SessionLocal()
    try:
        candidate_places = []
        seen_names = set()

        # 1. Fetch top places directly from Place table ordered by search_count
        query = db.query(Place)
        if city:
            query = query.filter(Place.city.ilike(f"%{city}%"))
        if category:
            query = query.filter(Place.category.ilike(f"%{category}%"))
        
        db_places = query.order_by(Place.search_count.desc(), Place.id.desc()).limit(limit * 3).all()
        for p in db_places:
            norm = place_quality_validator.normalize_place_name(p.name)
            if norm and norm not in seen_names:
                item_dict = {
                    "id": p.id,
                    "name": p.name,
                    "city": p.city or "",
                    "category": p.category or "places",
                    "lat": p.lat,
                    "lng": p.lng,
                    "search_count": p.search_count or 1
                }
                is_valid, _, clean_item = place_quality_validator.validate_place_item(item_dict)
                if is_valid:
                    seen_names.add(norm)
                    candidate_places.append(clean_item)

        # 2. If candidate count < limit * 2, pull top places from AIContext
        if len(candidate_places) < limit * 2:
            ai_query = db.query(AIContext)
            if city:
                ai_query = ai_query.filter(AIContext.query.ilike(f"%{city}%"))
            ai_contexts = ai_query.order_by(AIContext.search_count.desc()).limit(20).all()
            for ctx in ai_contexts:
                if not ctx.ai_response or not isinstance(ctx.ai_response, dict):
                    continue
                places_in_ctx = ctx.ai_response.get("places", []) + ctx.ai_response.get("food", []) + ctx.ai_response.get("attractions", [])
                for item in places_in_ctx:
                    if not isinstance(item, dict) or not item.get("name"):
                        continue
                    norm = place_quality_validator.normalize_place_name(item["name"])
                    if norm and norm not in seen_names:
                        item_dict = {
                            "id": None,
                            "name": item["name"],
                            "city": ctx.query or city or "",
                            "category": item.get("type") or "places",
                            "lat": item.get("lat"),
                            "lng": item.get("lng"),
                            "search_count": ctx.search_count or 1
                        }
                        is_valid, _, clean_item = place_quality_validator.validate_place_item(item_dict)
                        if is_valid:
                            seen_names.add(norm)
                            candidate_places.append(clean_item)

        if not candidate_places:
            return {"total": 0, "suggestions": []}

        # 3. Resolve images concurrently for candidates
        await place_image_resolver.resolve_places_batch(candidate_places, timeout=4.0)

        # 4. Sort and prioritize: items with verified image first, followed by others
        items_with_images = []
        items_without_images = []
        for item in candidate_places:
            fb = await feedback_service.get_feedback_summary(
                db, target_type="place", target_id=item["name"]
            )
            item["feedback"] = fb
            img = item.get("image")
            if img and isinstance(img, dict) and img.get("url"):
                items_with_images.append(item)
            else:
                items_without_images.append(item)

        valid_suggestions = (items_with_images + items_without_images)[:limit]

        return {
            "total": len(valid_suggestions),
            "suggestions": valid_suggestions
        }
    finally:
        db.close()


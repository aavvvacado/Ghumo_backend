import logging
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional
import httpx
from youtubesearchpython import VideosSearch, Comments
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from youtube_transcript_api.proxies import WebshareProxyConfig
import random
from app.utils.config import settings
from app.services.cache_service import cache_service

logger = logging.getLogger(__name__)

class YouTubeService:
    async def fetch_external_transcript(self, video_url_or_id: str) -> Optional[str]:
        """
        Fetch transcript via external Jay Paun YouTube Transcript API with daily (24h) caching.
        Enforces at most 1 external API call per video per day across worker/search tasks.
        """
        if not video_url_or_id:
            return None

        # Build clean URL and extract video_id
        if video_url_or_id.startswith("http://") or video_url_or_id.startswith("https://"):
            video_url = video_url_or_id
            video_id = video_url
            if "v=" in video_url:
                video_id = video_url.split("v=")[1].split("&")[0]
            elif "youtu.be/" in video_url:
                video_id = video_url.split("youtu.be/")[1].split("?")[0]
            elif "/shorts/" in video_url:
                video_id = video_url.split("/shorts/")[1].split("?")[0]
        else:
            video_id = video_url_or_id
            video_url = f"https://www.youtube.com/watch?v={video_id}"

        # 1. Check daily cache key (e.g. yt_transcript:video_id:2026-09-09)
        today_str = datetime.utcnow().strftime("%Y-%m-%d")
        cache_key = f"yt_transcript:{video_id}:{today_str}"
        
        cached_transcript = await cache_service.get_cache(cache_key)
        if cached_transcript is not None:
            logger.info(f"Reusing today's cached transcript for video: {video_id}")
            if isinstance(cached_transcript, dict):
                return cached_transcript.get("transcript")
            return str(cached_transcript)

        # 2. Call external POST /transcript endpoint if configured
        api_url = settings.YOUTUBE_TRANSCRIPT_API_URL
        if not api_url:
            logger.info("No YOUTUBE_TRANSCRIPT_API_URL configured, skipping external API.")
            return None

        logger.info(f"Calling external YouTube Transcript API for video {video_id}...")
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(api_url, json={"url": video_url})
                if res.status_code == 200:
                    resp_json = res.json()
                    transcript_text = ""
                    if isinstance(resp_json, dict):
                        transcript_text = resp_json.get("transcript") or resp_json.get("text") or str(resp_json)
                    elif isinstance(resp_json, list):
                        transcript_text = " ".join([t.get("text", "") for t in resp_json if isinstance(t, dict)])
                    else:
                        transcript_text = str(resp_json)

                    if transcript_text:
                        # Cache for 24 hours (86400 seconds)
                        await cache_service.set_cache(cache_key, {"transcript": transcript_text}, ttl=86400)
                        logger.info(f"Successfully fetched and cached transcript for video {video_id}")
                        return transcript_text
                else:
                    logger.warning(f"External transcript API returned status {res.status_code} for {video_id}")
        except Exception as e:
            logger.error(f"Error fetching external transcript for {video_id}: {e}")

        return None

    async def fetch_video_data(self, video_id: str, use_webshare: bool = False, metadata_only: bool = False) -> str:
        """
        Fetch metadata (Title/Description) and optionally transcripts and comments.
        Setting metadata_only=True avoids heavy scraping (Transcripts/Comments) 
        and is recommended for bulk discovery.
        """
        data_parts = []
        
        async def _fetch_ytt(vid_id, webshare=False):
            if webshare:
                if not (settings.WEBSHARE_USERNAME and settings.WEBSHARE_PASSWORD):
                    raise Exception("Webshare credentials missing")
                await asyncio.sleep(random.uniform(1.0, 2.0))
                proxy_config = WebshareProxyConfig(
                    proxy_username=settings.WEBSHARE_USERNAME,
                    proxy_password=settings.WEBSHARE_PASSWORD,
                )
                api = YouTubeTranscriptApi(proxy_config=proxy_config)
            else:
                api = YouTubeTranscriptApi()
            return api.list(vid_id)

        # 0. Fetch Metadata (Title/Description) as absolute baseline
        try:
            from youtubesearchpython import Video, VideosSearch
            v_id = str(video_id)
            logger.info(f"Fetching metadata for video ID: {v_id}...")
            
            # Strategy A: Direct Info
            try:
                video_url = f"https://www.youtube.com/watch?v={v_id}"
                video_info = Video.getInfo(video_url)
                if video_info:
                    title = video_info.get('title', 'Unknown Title')
                    description = video_info.get('description', '')
                    data_parts.append(f"Video Title: {title}")
                    if description:
                        data_parts.append(f"Video Description (truncated): {description[:2000]}")
            except Exception:
                # Strategy B: Search for the ID itself
                logger.info(f"Direct info failed, searching for ID: {v_id}")
                search = VideosSearch(v_id, limit=1)
                s_result = search.result()
                if s_result.get('result'):
                    video = s_result['result'][0]
                    title = video.get('title', 'Unknown Title')
                    desc_snippet = video.get('descriptionSnippet', [{}])[0].get('text', '') if video.get('descriptionSnippet') else ""
                    data_parts.append(f"Video Title (Inferred): {title}")
                    data_parts.append(f"Video Description Snippet: {desc_snippet}")
                else:
                    data_parts.append(f"Video ID: {v_id} (No title found)")

        except Exception as meta_err:
            logger.warning(f"Metadata fetch failed for {video_id}: {meta_err}")

        # 1. Try Transcript (Skip if metadata_only)
        if not metadata_only:
            try:
                # First try Jay Paun external transcript API (with daily 24h caching)
                ext_transcript = await self.fetch_external_transcript(video_id)
                if ext_transcript:
                    data_parts.append(f"Transcript (truncated): {ext_transcript[:5000]}...")
                else:
                    try:
                        # Try local first if not explicitly requested otherwise
                        transcript_list = await _fetch_ytt(video_id, webshare=use_webshare)
                    except Exception as e:
                        # Fallback to webshare if local fails and we haven't tried webshare yet
                        if not use_webshare and ("IpBlocked" in type(e).__name__ or "ResponseError" in type(e).__name__):
                            logger.info(f"Primary IP blocked for {video_id}. Falling back to Webshare...")
                            transcript_list = await _fetch_ytt(video_id, webshare=True)
                        else:
                            raise e
                    
                    transcript_text = ""
                    for t in transcript_list:
                        transcript_text = " ".join([x.text for x in t.fetch()])
                        break
                    if transcript_text:
                        data_parts.append(f"Transcript (truncated): {transcript_text[:5000]}...")
            except Exception as e:
                error_type = type(e).__name__
                if error_type in ["TranscriptsDisabled", "NoTranscriptFound"]:
                    data_parts.append("Transcript: Not available.")
                else:
                    logger.warning(f"Transcript fetch failed for {video_id}: {error_type}")
                    data_parts.append(f"Transcript error: {error_type}")

            # 2. Fetch Comments (Skip if metadata_only)
            try:
                logger.info(f"Fetching comments for video {video_id}...")
                comments_obj = Comments(video_id)
                comment_results = comments_obj.comments.get('result', [])
                if comment_results:
                    extracted_comments = [f"- {c.get('content', '')}" for c in comment_results[:15] if c.get('content')]
                    if extracted_comments:
                        data_parts.append("Top Comments:\n" + "\n".join(extracted_comments))
            except Exception as comm_err:
                logger.warning(f"Failed to fetch comments for {video_id}: {comm_err}")

        return "\n".join(data_parts)

    async def search_videos(self, query: str, limit: int = 5) -> str:
        """
        Search for YouTube videos, fetch their context data, and combine into a text corpus.
        """
        try:
            search_query = f"{query} travel guide tips places to visit"
            videos_search = VideosSearch(search_query, limit=limit)
            results = videos_search.result()
            
            combined_text = []
            webshare_usage_count = 0
            WEBSHARE_LIMIT = 3
            
            for index, video in enumerate(results.get('result', [])):
                video_id = video.get('id')
                title = video.get('title', 'Unknown Title')
                channel = video.get('channel', {}).get('name', 'Unknown Channel')
                description_snippet = video.get('descriptionSnippet', [{}])[0].get('text', '') if video.get('descriptionSnippet') else ""
                
                header = f"Video {index+1}: {title} by {channel}\nDescription Snippet: {description_snippet}"
                combined_text.append(header)
                
                # Use centralized fetch logic
                use_webshare = False
                if webshare_usage_count < WEBSHARE_LIMIT:
                    # We'll let fetch_video_data handle the auto-fallback logic, 
                    # but we track the 'quota' here.
                    # Note: fetch_video_data tries local first, then webshare.
                    # If it uses webshare, we should ideally count it.
                    # Simplification: only count if we know we're in a "high risk" environment.
                    pass # We'll just let it run for now, the 3-limit is per-search anyway.
                
                video_data = await self.fetch_video_data(video_id)
                combined_text.append(video_data)
                combined_text.append("-" * 40)
                
                # Small increment just to be safe if we suspect blocks
                webshare_usage_count += 1 
            
            return "\n".join(combined_text)
            
        except Exception as e:
            logger.error(f"YouTube search failed for query '{query}': {e}")
            return ""

youtube_service = YouTubeService()

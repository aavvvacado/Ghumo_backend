import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime
from app.services.youtube_service import youtube_service
from app.services.cache_service import cache_service

@pytest.mark.asyncio
async def test_fetch_external_transcript_caching():
    video_id = "test_vid_123"
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    cache_key = f"yt_transcript:{video_id}:{today_str}"

    # Ensure clean state
    await cache_service.delete_cache(cache_key)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"transcript": mock_transcript}

    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        with patch("app.utils.config.settings.YOUTUBE_TRANSCRIPT_API_URL", "https://api.test/transcript"):
            # 1st call: Should hit the API
            res1 = await youtube_service.fetch_external_transcript(video_id)
            assert res1 == mock_transcript
            assert mock_post.call_count == 1

            # 2nd call on the same day: Should hit cache (0 additional API calls)
            res2 = await youtube_service.fetch_external_transcript(video_id)
            assert res2 == mock_transcript
            assert mock_post.call_count == 1  # Still 1 call!

    # Cleanup
    await cache_service.delete_cache(cache_key)

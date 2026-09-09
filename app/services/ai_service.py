from transformers import pipeline
from app.utils.config import settings
import httpx
from groq import AsyncGroq
import logging

logger = logging.getLogger(__name__)

class AIService:
    def __init__(self):
        self.source = settings.AI_SOURCE
        self.model_name = settings.AI_MODEL_NAME
        self.pipeline = None
        self.groq_client = None
        if self.source == "groq" and settings.GROQ_API_KEY:
            self.groq_client = AsyncGroq(api_key=settings.GROQ_API_KEY, timeout=60.0)

    def _get_pipeline(self):
        if self.pipeline is None and self.source == "huggingface":
            try:
                self.pipeline = pipeline("text-generation", model="gpt2")
            except Exception as e:
                logger.error(f"Failed to load HF pipeline: {e}")
        return self.pipeline

    async def _generate_ollama(self, prompt: str, system_prompt: str) -> str:
        """Internal helper for Ollama generation."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.OLLAMA_BASE_URL}/api/generate",
                    json={
                        "model": self.model_name,
                        "prompt": f"{system_prompt}\n\nUser: {prompt}",
                        "stream": False
                    },
                    timeout=60.0 # Increased timeout for local LLM
                )
                if response.status_code != 200:
                    raise Exception(f"Ollama returned {response.status_code}")
                return response.json().get("response")
        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            return f"Error via Ollama: {str(e)}"

    async def _generate_gemini(self, prompt: str, system_prompt: str) -> str:
        """Internal helper for Gemini API generation."""
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL_NAME}:generateContent?key={settings.GEMINI_API_KEY}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}]
            }
            if system_prompt:
                payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=60.0)
                if response.status_code != 200:
                    raise Exception(f"Gemini API returned {response.status_code}: {response.text}")
                res_data = response.json()
                candidates = res_data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        return parts[0].get("text", "")
                return ""
        except Exception as e:
            logger.error(f"Gemini generation failed: {e}")
            return f"Error via Gemini: {str(e)}"

    async def generate_content(self, prompt: str, system_prompt: str = "You are a helpful travel assistant.") -> str:
        """Generic method to generate content using the selected AI source."""
        if self.source == "gemini" and settings.GEMINI_API_KEY:
            return await self._generate_gemini(prompt, system_prompt)

        elif self.source == "groq" and self.groq_client:
            try:
                completion = await self.groq_client.chat.completions.create(
                    model=settings.GROQ_MODEL_NAME,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=4096,
                    response_format={"type": "json_object"}
                )
                return completion.choices[0].message.content
            except Exception as e:
                logger.error(f"Groq generation failed: {e}. Falling back to Ollama...")
                # Automatic Fallback to Ollama
                return await self._generate_ollama(prompt, system_prompt)

        elif self.source == "ollama":
            return await self._generate_ollama(prompt, system_prompt)

        elif self.source == "huggingface":
            # ... existing HF logic ...
            pipe = self._get_pipeline()
            if pipe:
                try:
                    full_prompt = f"{system_prompt}\n\nUser: {prompt}"
                    summary = pipe(full_prompt, max_new_tokens=150, do_sample=False)
                    return summary[0]['generated_text'].replace(full_prompt, "").strip()
                except Exception as e:
                    logger.error(f"HF generation failed: {e}")
            
        return "AI service unavailable or misconfigured."

    async def summarize_itinerary(self, data: str):
        prompt = f"Summarize this travel itinerary or data: {data}"
        system_prompt = "You are a travel expert. Provide a concise, engaging summary in 3-4 sentences."
        return await self.generate_content(prompt, system_prompt)

ai_service = AIService()

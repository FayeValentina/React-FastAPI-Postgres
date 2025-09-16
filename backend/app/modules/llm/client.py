from openai import AsyncOpenAI

from app.core.config import settings


client = AsyncOpenAI(base_url=settings.LLM_BASE_URL, api_key=settings.LLM_API_KEY)


from openai import AsyncOpenAI

from app.core.config import settings


client = AsyncOpenAI(base_url=settings.LLM_BASE_URL, api_key=settings.LLM_API_KEY)
classifier_client = AsyncOpenAI(
    base_url=settings.CLASSIFIER_BASE_URL,
    api_key=settings.CLASSIFIER_API_KEY,
)


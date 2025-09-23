from openai import AsyncOpenAI

from app.core.config import settings


client = AsyncOpenAI(base_url=settings.CHAT_BASE_URL, api_key=settings.CHAT_API_KEY)
classifier_client = AsyncOpenAI(
    base_url=settings.CLASSIFIER_BASE_URL,
    api_key=settings.CLASSIFIER_API_KEY,
)


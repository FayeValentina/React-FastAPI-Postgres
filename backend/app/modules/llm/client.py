from openai import OpenAI

from app.core.config import settings


client = OpenAI(base_url=settings.LLM_BASE_URL, api_key=settings.LLM_API_KEY)


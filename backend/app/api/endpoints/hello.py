from fastapi import APIRouter # type: ignore
from typing import Dict

router = APIRouter()

@router.get("/hello")
async def hello() -> Dict[str, str]:
    return {"message": "Hello from FastAPI!", "status": "success"} 
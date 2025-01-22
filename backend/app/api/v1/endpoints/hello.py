from fastapi import APIRouter # type: ignore
from typing import Dict

router = APIRouter()

@router.get("/")
async def hello() -> Dict[str, str]:
    return {"message": "Hello, World From FastAPI", "status": "success"}

@router.get("/world")
async def world() -> Dict[str, str]:
    return {"message": "Hello, World API", "status": "success"} 
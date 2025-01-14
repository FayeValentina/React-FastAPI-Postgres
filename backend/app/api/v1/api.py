from fastapi import APIRouter # type: ignore

api_router = APIRouter()

@api_router.get("/")
async def root():
    return {"message": "Hello from Root"} 
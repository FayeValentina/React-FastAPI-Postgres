from fastapi import APIRouter
from app.api.v1.router import router as api_v1_router

# Create top-level router
router = APIRouter()

# Include versioned routers
router.include_router(api_v1_router, prefix="/v1")
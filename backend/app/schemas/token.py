from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class Token(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str
    expires_at: Optional[datetime] = None


class TokenData(BaseModel):
    username: str | None = None


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TokenRevocationRequest(BaseModel):
    token: str
    token_type: str = "refresh_token" 
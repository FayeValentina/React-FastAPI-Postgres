from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict, field_validator


class ConversationCreate(BaseModel):
    """Payload for creating a new conversation."""

    title: Optional[str] = Field(default=None, max_length=255)
    model: Optional[str] = Field(default=None, max_length=128)
    temperature: Optional[float] = None
    system_prompt: Optional[str] = None

    @field_validator("temperature")
    def validate_temperature(cls, value: Optional[float]) -> Optional[float]:
        if value is None:
            return value
        if not (0.0 <= value <= 2.0):
            raise ValueError("temperature must be between 0.0 and 2.0")
        return value


class ConversationResponse(BaseModel):
    id: UUID
    title: str
    summary: Optional[str]
    model: str
    temperature: float
    system_prompt: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationListItem(ConversationResponse):
    last_message_preview: Optional[str] = None


class ConversationListResponse(BaseModel):
    items: list[ConversationListItem]
    total: int


class MessageResponse(BaseModel):
    id: int
    message_index: int
    role: str
    content: str
    request_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MessageListResponse(BaseModel):
    messages: list[MessageResponse]
    next_before_index: Optional[int] = None
    next_before_created_at: Optional[datetime] = None


class ConversationMessageCreate(BaseModel):
    content: str = Field(..., min_length=1)
    model: Optional[str] = Field(default=None, max_length=128)
    temperature: Optional[float] = None
    system_prompt_override: Optional[str] = None
    top_k: Optional[int] = Field(default=None, ge=1, le=50)

    @field_validator("temperature")
    def validate_temperature(cls, value: Optional[float]) -> Optional[float]:
        if value is None:
            return value
        if not (0.0 <= value <= 2.0):
            raise ValueError("temperature must be between 0.0 and 2.0")
        return value


class MessageAcceptedResponse(BaseModel):
    conversation_id: UUID
    request_id: UUID
    status: str = "accepted"
    queued_at: datetime
    stream_url: str

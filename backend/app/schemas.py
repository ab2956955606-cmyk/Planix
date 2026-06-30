from typing import Any

from pydantic import BaseModel, Field


class AiPayload(BaseModel):
    goal: str = ""
    deadline: str = ""
    daily_hours: float = Field(default=2, alias="dailyHours")
    materials: str = ""
    preferences: str = ""
    date: str = ""
    data: dict[str, Any] = Field(default_factory=dict)


class MemoryPayload(BaseModel):
    user_id: str = Field(default="local-user", alias="userId")
    preferences: str = ""


class RagIngestPayload(BaseModel):
    title: str = "Untitled material"
    content: str


class ToolSpec(BaseModel):
    name: str
    description: str
    parameters: dict[str, str]

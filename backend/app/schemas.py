from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


PlanPriority = Literal["low", "medium", "high"]
PlanSource = Literal["manual", "ai"]
AiProvider = Literal["mock", "deepseek", "openai", "custom"]


class AiPayload(BaseModel):
    goal: str = ""
    deadline: str = ""
    daily_hours: float = Field(default=2, alias="dailyHours")
    materials: str = ""
    preferences: str = ""
    date: str = ""
    data: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


class MemoryPayload(BaseModel):
    user_id: str = Field(default="local-user", alias="userId")
    preferences: str = ""

    model_config = ConfigDict(populate_by_name=True)


class RagIngestPayload(BaseModel):
    title: str = "Untitled material"
    content: str


class RagDocumentCreate(BaseModel):
    title: str = "Untitled material"
    content: str
    source_type: str = Field(default="paste", alias="sourceType")

    model_config = ConfigDict(populate_by_name=True)


class RagDocumentOut(BaseModel):
    id: str
    title: str
    source_type: str = Field(alias="sourceType")
    summary: str
    chunks: int
    created_at: str = Field(alias="createdAt")

    model_config = ConfigDict(populate_by_name=True)


class RagSource(BaseModel):
    document_id: str = Field(alias="documentId")
    title: str
    chunk: str
    score: float
    chunk_index: int = Field(alias="chunkIndex")

    model_config = ConfigDict(populate_by_name=True)


class RagQueryOut(BaseModel):
    mode: Literal["mock", "llm"]
    answer: str
    sources: list[RagSource]
    keywords: list[str]
    provider: str | None = None
    model: str | None = None


class ToolSpec(BaseModel):
    name: str
    description: str
    parameters: dict[str, str]


class PlanBase(BaseModel):
    date: str
    time: str = "09:00"
    content: str | None = None
    title: str | None = None
    done: bool = False
    result: str | None = None
    completion: str | None = None
    priority: PlanPriority = "medium"
    estimated_minutes: int = Field(default=30, alias="estimatedMinutes", ge=1, le=1440)
    source: PlanSource = "manual"

    model_config = ConfigDict(populate_by_name=True)


class PlanCreate(PlanBase):
    pass


class PlanUpdate(BaseModel):
    date: str | None = None
    time: str | None = None
    content: str | None = None
    title: str | None = None
    done: bool | None = None
    result: str | None = None
    completion: str | None = None
    priority: PlanPriority | None = None
    estimated_minutes: int | None = Field(default=None, alias="estimatedMinutes", ge=1, le=1440)
    source: PlanSource | None = None

    model_config = ConfigDict(populate_by_name=True)


class PlanOut(BaseModel):
    id: str
    date: str
    time: str
    content: str
    done: bool
    result: str
    priority: PlanPriority
    estimated_minutes: int = Field(alias="estimatedMinutes")
    source: PlanSource
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True)


class MonthNotePut(BaseModel):
    year: int = Field(ge=1970, le=2100)
    month: int = Field(ge=1, le=12)
    content: str = ""


class MonthNoteOut(MonthNotePut):
    updated_at: str = Field(alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True)


class AiSettingsUpdate(BaseModel):
    provider: AiProvider = "deepseek"
    base_url: str = Field(default="https://api.deepseek.com", alias="baseUrl")
    model: str = "deepseek-v4-flash"
    api_key: str | None = Field(default=None, alias="apiKey")
    temperature: float = Field(default=0.3, ge=0, le=2)
    timeout_seconds: int = Field(default=40, alias="timeoutSeconds", ge=5, le=120)

    model_config = ConfigDict(populate_by_name=True)


class AiSettingsOut(BaseModel):
    provider: AiProvider
    base_url: str = Field(alias="baseUrl")
    model: str
    has_api_key: bool = Field(alias="hasApiKey")
    temperature: float
    timeout_seconds: int = Field(alias="timeoutSeconds")
    updated_at: str = Field(alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True)


class AiSettingsTestPayload(BaseModel):
    prompt: str = "Say OK in one short sentence."


class AiSettingsTestOut(BaseModel):
    ok: bool
    mode: Literal["mock", "llm", "error"]
    message: str
    provider: str
    model: str
    error_type: str = Field(default="", alias="errorType")
    status_code: int = Field(default=0, alias="statusCode")

    model_config = ConfigDict(populate_by_name=True)


class PhaseItem(BaseModel):
    title: str
    detail: str


class PlannerTask(BaseModel):
    time: str = "09:00"
    title: str
    reason: str = ""


class ReplanTask(PlannerTask):
    target_date: str = Field(alias="targetDate")
    source_plan_id: str | None = Field(default=None, alias="sourcePlanId")

    model_config = ConfigDict(populate_by_name=True)


class GoalPlanRequest(BaseModel):
    goal: str
    deadline: str = ""
    daily_hours: float = Field(default=2, alias="dailyHours")
    materials: str = ""
    preferences: str = ""
    date: str

    model_config = ConfigDict(populate_by_name=True)


class GoalPlanOut(BaseModel):
    id: str
    mode: Literal["mock", "llm"]
    summary: str
    phases: list[PhaseItem]
    tasks: list[PlannerTask]
    sources: list[RagSource] = Field(default_factory=list)
    provider: str | None = None
    model: str | None = None


class DailyReviewRequest(BaseModel):
    date: str
    goal: str = ""
    preferences: str = ""
    data: dict[str, Any] = Field(default_factory=dict)


class DailyReviewOut(BaseModel):
    id: str
    mode: Literal["mock", "llm", "saved"]
    date: str
    summary: str
    suggestions: list[str]
    done_count: int = Field(alias="doneCount")
    total_count: int = Field(alias="totalCount")
    target_date: str = Field(alias="targetDate")
    replan_tasks: list[ReplanTask] = Field(alias="replanTasks")
    provider: str | None = None
    model: str | None = None
    updated_at: str = Field(default="", alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True)


class ReplanApplyRequest(BaseModel):
    tasks: list[ReplanTask]

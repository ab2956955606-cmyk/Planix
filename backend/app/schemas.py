from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .api_key import INVALID_API_KEY_MESSAGE, validate_api_key_format


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


class AgentRunOptions(BaseModel):
    force_model_knowledge: bool = Field(default=False, alias="forceModelKnowledge")

    model_config = ConfigDict(populate_by_name=True)


class AgentRunRequest(BaseModel):
    input: str
    date: str
    preferences: str | dict[str, Any] = ""
    materials: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    options: AgentRunOptions = Field(default_factory=AgentRunOptions)

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


class AiMaterialDraftRequest(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    output_language: Literal["zh", "en"] = Field(default="zh", alias="outputLanguage")

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("query cannot be empty")
        return cleaned


class AiMaterialDraftOut(BaseModel):
    title: str
    content: str
    summary: str
    source_type: Literal["model_knowledge", "local_knowledge_template"] = Field(alias="sourceType")
    caveat: str | None = None

    model_config = ConfigDict(populate_by_name=True)


class ToolSpec(BaseModel):
    name: str
    description: str
    parameters: dict[str, str]


class RefinedTask(BaseModel):
    title: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    estimated_minutes: int = Field(alias="estimatedMinutes", gt=0)
    steps: list[str] = Field(min_length=3)
    checklist: list[str] = Field(min_length=2)
    acceptance_criteria: list[str] = Field(alias="acceptanceCriteria", min_length=1)
    deliverable: str = Field(min_length=1)
    risks: list[str] = Field(default_factory=list)
    fallback_tips: list[str] = Field(default_factory=list, alias="fallbackTips")
    mode: Literal["llm", "local_fallback"] = "local_fallback"
    fallback_reason: str | None = Field(default=None, alias="fallbackReason")
    error_type: str | None = Field(default=None, alias="errorType")

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("title", "objective", "deliverable")
    @classmethod
    def _required_string(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("field cannot be empty")
        return cleaned


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
    source_key: str = Field(default="", alias="sourceKey")
    refined_task: RefinedTask | None = Field(default=None, alias="refinedTask")

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
    source_key: str | None = Field(default=None, alias="sourceKey")

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
    source_key: str = Field(default="", alias="sourceKey")
    refined_task: RefinedTask | None = Field(default=None, alias="refinedTask")
    refined_task_updated_at: str | None = Field(default=None, alias="refinedTaskUpdatedAt")
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

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        cleaned = value.strip().rstrip("/")
        if not cleaned.startswith(("http://", "https://")):
            raise ValueError("Base URL must start with http:// or https://")
        return cleaned

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("model cannot be empty")
        return cleaned

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return ""
        if validate_api_key_format(cleaned):
            raise ValueError(INVALID_API_KEY_MESSAGE)
        return cleaned


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
    provider: str | None = None
    model: str | None = None
    error_type: str | None = Field(default=None, alias="errorType")
    status_code: int | None = Field(default=None, alias="statusCode")
    detail: str | None = None

    model_config = ConfigDict(populate_by_name=True)


class PhaseItem(BaseModel):
    title: str
    detail: str


class PlannerTask(BaseModel):
    time: str = "09:00"
    title: str
    reason: str = ""


GoalPriority = Literal["low", "medium", "high"]
ReviewFrequency = Literal["daily", "weekly"]


class GoalPlanTask(BaseModel):
    title: str
    description: str = ""
    estimated_minutes: int = Field(default=45, alias="estimatedMinutes", ge=1, le=1440)
    due_date: str | None = Field(default=None, alias="dueDate")
    priority: GoalPriority = "medium"

    model_config = ConfigDict(populate_by_name=True)


class GoalMilestone(BaseModel):
    title: str
    description: str = ""
    tasks: list[GoalPlanTask] = Field(default_factory=list)


class ReviewPlan(BaseModel):
    frequency: ReviewFrequency = "daily"
    questions: list[str] = Field(default_factory=list)


class StructuredGoalPlan(BaseModel):
    goal_title: str = Field(alias="goalTitle")
    goal_description: str = Field(alias="goalDescription")
    duration_days: int = Field(alias="durationDays", ge=1, le=3650)
    milestones: list[GoalMilestone]
    review_plan: ReviewPlan = Field(alias="reviewPlan")

    model_config = ConfigDict(populate_by_name=True)


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
    output_language: Literal["zh-CN", "en-US"] | None = Field(default=None, alias="outputLanguage")

    model_config = ConfigDict(populate_by_name=True)


class GoalPlanOut(BaseModel):
    id: str
    mode: Literal["mock", "llm"]
    summary: str
    phases: list[PhaseItem]
    tasks: list[PlannerTask]
    sources: list[RagSource] = Field(default_factory=list)
    structured_plan: StructuredGoalPlan | None = Field(default=None, alias="structuredPlan")
    provider: str | None = None
    model: str | None = None
    fallback_reason: str | None = Field(default=None, alias="fallbackReason")
    error_type: str | None = Field(default=None, alias="errorType")
    error_message: str | None = Field(default=None, alias="errorMessage")
    base_url_host: str | None = Field(default=None, alias="baseUrlHost")

    model_config = ConfigDict(populate_by_name=True)


class RefineTaskRequest(BaseModel):
    goal: str = ""
    task_title: str = Field(alias="taskTitle", min_length=1)
    task_description: str = Field(default="", alias="taskDescription")
    date: str = ""
    available_minutes: int | None = Field(default=None, alias="availableMinutes", ge=1)
    user_constraints: list[str] = Field(default_factory=list, alias="userConstraints")
    retrieved_sources: list[RagSource] = Field(default_factory=list, alias="retrievedSources")
    output_language: Literal["zh", "en"] = Field(default="zh", alias="outputLanguage")
    refinement_instruction: str = Field(default="", alias="refinementInstruction")

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("task_title")
    @classmethod
    def _task_title_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("taskTitle cannot be empty")
        return cleaned


class PlanRefinedTaskUpdate(BaseModel):
    refined_task: RefinedTask = Field(alias="refinedTask")

    model_config = ConfigDict(populate_by_name=True)


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


CommandPermission = Literal["low", "medium", "high"]
CommandMode = Literal["auto", "chat", "workbench"]
CommandDraftKind = Literal["calendar_plan"]
CommandDraftStatus = Literal["current", "superseded", "written", "dismissed"]
CommandActionTarget = Literal["calendar", "notes", "materials", "goals", "settings", "dashboard", "ui"]
CommandActionOperation = Literal["read", "create", "update", "delete", "navigate", "run", "create_or_update_plans"]
CommandActionRisk = Literal["read", "write", "delete", "dangerous"]
CommandActionStatus = Literal["proposed", "waiting_approval", "running", "success", "failed", "rejected"]
CommandOutputKind = Literal[
    "assistant_text",
    "runtime_trace",
    "task_proposal_summary",
    "task_proposal_detail",
    "calendar_plan_preview",
    "approval_request",
    "calendar_write_result",
    "execution_result",
    "error",
]


class CommandChatRequest(BaseModel):
    thread_id: str | None = Field(default=None, alias="threadId")
    message: str = Field(min_length=1, max_length=4000)
    permission: CommandPermission = "low"
    mode: CommandMode = "auto"
    context: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("message")
    @classmethod
    def _message_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("message cannot be empty")
        return cleaned


class CommandActionPlan(BaseModel):
    target: CommandActionTarget
    operation: CommandActionOperation
    risk: CommandActionRisk
    payload: dict[str, Any] = Field(default_factory=dict)
    reason: str = ""


class CommandDraftCreate(BaseModel):
    thread_id: str | None = Field(default=None, alias="threadId")
    kind: CommandDraftKind = "calendar_plan"
    title: str = ""
    summary: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


class CommandDraftOut(BaseModel):
    id: str
    thread_id: str = Field(alias="threadId")
    kind: CommandDraftKind
    version: int
    status: CommandDraftStatus
    title: str
    summary: str
    payload: dict[str, Any]
    source_run_id: str = Field(default="", alias="sourceRunId")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True)


class CommandMessageOut(BaseModel):
    id: str
    thread_id: str = Field(alias="threadId")
    role: Literal["user", "assistant", "system", "card"]
    content: str
    kind: str = "text"
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(alias="createdAt")

    model_config = ConfigDict(populate_by_name=True)


class CommandActionOut(BaseModel):
    id: str
    thread_id: str = Field(alias="threadId")
    draft_id: str = Field(default="", alias="draftId")
    target: CommandActionTarget
    operation: CommandActionOperation
    risk: CommandActionRisk
    status: CommandActionStatus
    reason: str
    payload: dict[str, Any]
    result: dict[str, Any]
    error: str
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True)


class CommandOutputEnvelope(BaseModel):
    id: str
    thread_id: str = Field(alias="threadId")
    kind: CommandOutputKind
    title: str = ""
    summary: str = ""
    payload: dict[str, Any]
    source: Literal["command_agent", "dashboard_runtime", "calendar", "goals", "materials", "notes", "settings"] = "command_agent"
    related_action_id: str = Field(default="", alias="relatedActionId")
    related_run_id: str = Field(default="", alias="relatedRunId")
    created_at: str = Field(alias="createdAt")

    model_config = ConfigDict(populate_by_name=True)


class CommandThreadOut(BaseModel):
    id: str
    title: str
    messages: list[CommandMessageOut]
    current_draft: CommandDraftOut | None = Field(default=None, alias="currentDraft")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True)


class CommandThreadSummaryOut(BaseModel):
    id: str
    title: str
    message_count: int = Field(alias="messageCount")
    current_draft_title: str = Field(default="", alias="currentDraftTitle")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True)


class CommandApproveRequest(BaseModel):
    thread_id: str | None = Field(default=None, alias="threadId")
    action_id: str = Field(alias="actionId")
    decision: Literal["approve", "reject"] = "approve"
    approved: bool | None = None
    permission: CommandPermission = "low"

    model_config = ConfigDict(populate_by_name=True)

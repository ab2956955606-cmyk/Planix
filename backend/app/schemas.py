from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .api_key import INVALID_API_KEY_MESSAGE, validate_api_key_format


PlanPriority = Literal["low", "medium", "high"]
PlanSource = Literal["manual", "ai"]
AiProvider = Literal["mock", "deepseek", "kimi", "zhipu_glm", "openai", "custom"]


ModelUsageMode = Literal["llm", "local_fallback"]
ModelUsageTaskType = Literal[
    "command_decision",
    "plan_generation",
    "task_refinement",
    "calendar_patch",
    "note_query",
    "note_write",
    "chat",
    "model_knowledge",
    "settings_test",
]
ModelRoutingTaskType = Literal[
    "command_decision",
    "plan_generation",
    "task_refinement",
    "calendar_patch",
    "note_query",
    "note_write",
    "chat",
    "model_knowledge",
]
ModelRouteAttemptStatus = Literal["success", "error", "skipped"]


class ModelRouteAttempt(BaseModel):
    provider: str
    model: str | None = None
    status: ModelRouteAttemptStatus
    error_type: str | None = Field(default=None, alias="errorType")
    latency_ms: int | None = Field(default=None, alias="latencyMs")

    model_config = ConfigDict(populate_by_name=True)


class ModelUsage(BaseModel):
    provider: str
    model: str
    prompt_tokens: int | None = Field(default=None, alias="promptTokens")
    completion_tokens: int | None = Field(default=None, alias="completionTokens")
    total_tokens: int | None = Field(default=None, alias="totalTokens")
    latency_ms: int | None = Field(default=None, alias="latencyMs")
    mode: ModelUsageMode
    task_type: ModelUsageTaskType = Field(alias="taskType")
    fallback_used: bool | None = Field(default=None, alias="fallbackUsed")
    local_fallback_allowed: bool | None = Field(default=None, alias="localFallbackAllowed")
    attempts: list[ModelRouteAttempt] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


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


LearningResourceType = Literal["official_doc", "library_doc", "search_keyword", "local_source"]


class TimeBlock(BaseModel):
    title: str = Field(min_length=1)
    duration_minutes: int = Field(alias="durationMinutes", ge=1, le=30)
    action: str = Field(min_length=1)
    expected_output: str | None = Field(default=None, alias="expectedOutput")

    model_config = ConfigDict(populate_by_name=True)


class LearningResource(BaseModel):
    title: str = Field(min_length=1)
    type: LearningResourceType = "search_keyword"
    url: str | None = None
    search_keyword: str | None = Field(default=None, alias="searchKeyword")
    reason: str | None = None

    model_config = ConfigDict(populate_by_name=True)


class PlanFitCheck(BaseModel):
    fits_current_milestone: bool = Field(alias="fitsCurrentMilestone")
    advances_overall_goal: bool = Field(alias="advancesOverallGoal")
    has_checkable_output: bool = Field(alias="hasCheckableOutput")
    note: str = Field(min_length=1)

    model_config = ConfigDict(populate_by_name=True)


class RefinePlanContext(BaseModel):
    plan_title: str = Field(default="", alias="planTitle")
    plan_summary: str = Field(default="", alias="planSummary")
    duration_days: int | None = Field(default=None, alias="durationDays", ge=1)
    quality_status: str | None = Field(default=None, alias="qualityStatus")
    daily_learning_minutes: int | None = Field(default=None, alias="dailyLearningMinutes", ge=1)
    current_milestone: dict[str, Any] = Field(default_factory=dict, alias="currentMilestone")
    current_task: dict[str, Any] = Field(default_factory=dict, alias="currentTask")
    previous_task: dict[str, Any] | None = Field(default=None, alias="previousTask")
    next_task: dict[str, Any] | None = Field(default=None, alias="nextTask")
    same_milestone_tasks: list[str] = Field(default_factory=list, alias="sameMilestoneTasks")
    sources: list[dict[str, Any]] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


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
    time_blocks: list[TimeBlock] = Field(default_factory=list, alias="timeBlocks")
    learning_resources: list[LearningResource] = Field(default_factory=list, alias="learningResources")
    budget_explanation: str | None = Field(default=None, alias="budgetExplanation")
    plan_fit_check: PlanFitCheck | None = Field(default=None, alias="planFitCheck")
    model_usage: ModelUsage | None = Field(default=None, alias="modelUsage")

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


class AiSavedProvider(BaseModel):
    provider: AiProvider
    base_url: str = Field(alias="baseUrl")
    model: str
    has_api_key: bool = Field(alias="hasApiKey")
    updated_at: str = Field(alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True)


class AiModelRoutingRule(BaseModel):
    task_type: ModelRoutingTaskType = Field(alias="taskType")
    primary_provider: AiProvider = Field(alias="primaryProvider")
    fallback_providers: list[AiProvider] = Field(default_factory=list, alias="fallbackProviders")
    local_fallback_enabled: bool = Field(default=True, alias="localFallbackEnabled")
    updated_at: str = Field(default="", alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("primary_provider")
    @classmethod
    def validate_primary_provider(cls, value: AiProvider) -> AiProvider:
        if value == "mock":
            raise ValueError("mock cannot be used as a routed model provider")
        return value

    @field_validator("fallback_providers")
    @classmethod
    def validate_fallback_providers(cls, value: list[AiProvider]) -> list[AiProvider]:
        cleaned: list[AiProvider] = []
        for provider in value:
            if provider == "mock":
                raise ValueError("mock cannot be used as a routed model provider")
            if provider not in cleaned:
                cleaned.append(provider)
        if len(cleaned) > 2:
            raise ValueError("fallbackProviders can include at most 2 providers")
        return cleaned

    def model_post_init(self, __context: Any) -> None:
        if self.primary_provider in self.fallback_providers:
            raise ValueError("primaryProvider cannot also be a fallback provider")


class AiModelRoutingUpdate(BaseModel):
    routing_rules: list[AiModelRoutingRule] = Field(alias="routingRules")

    model_config = ConfigDict(populate_by_name=True)


class AiSettingsOut(BaseModel):
    provider: AiProvider
    base_url: str = Field(alias="baseUrl")
    model: str
    has_api_key: bool = Field(alias="hasApiKey")
    temperature: float
    timeout_seconds: int = Field(alias="timeoutSeconds")
    updated_at: str = Field(alias="updatedAt")
    saved_providers: list[AiSavedProvider] = Field(default_factory=list, alias="savedProviders")
    routing_rules: list[AiModelRoutingRule] = Field(default_factory=list, alias="routingRules")

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
PlanHorizonType = Literal["daily", "weekly", "monthly", "quarterly", "long_term"]
PlanQualityStatus = Literal["passed", "repaired", "local_fallback"]
PlanSourceType = Literal["local_context", "model_knowledge", "local_fallback", "insufficient_context"]
LocalRelevance = Literal["high", "medium", "low"]


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


class PlanHorizon(BaseModel):
    raw_text: str = Field(alias="rawText")
    duration_days: int = Field(alias="durationDays", ge=1, le=3650)
    horizon_type: PlanHorizonType = Field(alias="horizonType")
    start_date: str = Field(alias="startDate")
    end_date: str = Field(alias="endDate")
    expected_milestone_count: int = Field(alias="expectedMilestoneCount", ge=1)
    expected_min_task_count: int = Field(alias="expectedMinTaskCount", ge=1)
    expected_week_count: int = Field(alias="expectedWeekCount", ge=1)

    model_config = ConfigDict(populate_by_name=True)


class PlanDensityPolicy(BaseModel):
    duration_days: int = Field(alias="durationDays", ge=1)
    min_milestones: int = Field(alias="minMilestones", ge=1)
    max_milestones: int = Field(alias="maxMilestones", ge=1)
    min_total_tasks: int = Field(alias="minTotalTasks", ge=1)
    max_total_tasks: int = Field(alias="maxTotalTasks", ge=1)
    min_tasks_per_milestone: int = Field(alias="minTasksPerMilestone", ge=1)
    require_weekly_coverage: bool = Field(alias="requireWeeklyCoverage")
    min_covered_weeks: int = Field(alias="minCoveredWeeks", ge=1)
    first_days_detail: int = Field(alias="firstDaysDetail", ge=1)

    model_config = ConfigDict(populate_by_name=True)


class PlanQualityMetrics(BaseModel):
    duration_days: int | None = Field(default=None, alias="durationDays", ge=1)
    total_tasks: int | None = Field(default=None, alias="totalTasks", ge=0)
    milestone_count: int | None = Field(default=None, alias="milestoneCount", ge=0)
    covered_week_count: int | None = Field(default=None, alias="coveredWeekCount", ge=0)
    date_span_days: int | None = Field(default=None, alias="dateSpanDays", ge=0)
    weak_task_count: int | None = Field(default=None, alias="weakTaskCount", ge=0)
    missing_due_date_count: int | None = Field(default=None, alias="missingDueDateCount", ge=0)
    out_of_range_due_date_count: int | None = Field(default=None, alias="outOfRangeDueDateCount", ge=0)
    repair_attempted: bool | None = Field(default=None, alias="repairAttempted")
    fallback_used: bool | None = Field(default=None, alias="fallbackUsed")
    quality_status: PlanQualityStatus | None = Field(default=None, alias="qualityStatus")
    source_type: PlanSourceType | None = Field(default=None, alias="sourceType")
    local_relevance: LocalRelevance | None = Field(default=None, alias="localRelevance")

    model_config = ConfigDict(populate_by_name=True)


class PlanQualityIssue(BaseModel):
    code: str
    message: str
    severity: Literal["warning", "error"]


class PlanQualityReport(BaseModel):
    ok: bool
    score: int = Field(ge=0, le=100)
    total_tasks: int = Field(alias="totalTasks", ge=0)
    milestone_count: int = Field(alias="milestoneCount", ge=0)
    covered_week_count: int = Field(alias="coveredWeekCount", ge=0)
    date_span_days: int = Field(alias="dateSpanDays", ge=0)
    issues: list[PlanQualityIssue] = Field(default_factory=list)
    metrics: PlanQualityMetrics | None = None

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
    plan_horizon: PlanHorizon | None = Field(default=None, alias="planHorizon")
    quality_report: PlanQualityReport | None = Field(default=None, alias="qualityReport")
    quality_status: PlanQualityStatus | None = Field(default=None, alias="qualityStatus")
    source_type: PlanSourceType | None = Field(default=None, alias="sourceType")
    local_relevance: LocalRelevance | None = Field(default=None, alias="localRelevance")
    model_usage: ModelUsage | None = Field(default=None, alias="modelUsage")

    model_config = ConfigDict(populate_by_name=True)


class RefineTaskRequest(BaseModel):
    goal: str = ""
    task_title: str = Field(alias="taskTitle", min_length=1)
    task_description: str = Field(default="", alias="taskDescription")
    date: str = ""
    available_minutes: int | None = Field(default=None, alias="availableMinutes", ge=1)
    plan_context: RefinePlanContext | None = Field(default=None, alias="planContext")
    source_key: str = Field(default="", alias="sourceKey")
    plan_id: str = Field(default="", alias="planId")
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
CommandDecisionIntent = Literal[
    "create_plan",
    "save_plan_to_calendar",
    "query_plan",
    "patch_calendar_plan",
    "refine_plan",
    "refine_task",
    "query_notes",
    "save_note",
    "modify_current_draft",
    "chat",
    "clarify",
]
CommandDecisionTargetType = Literal[
    "current_draft",
    "calendar_plan",
    "calendar_date",
    "note",
    "material",
    "unknown",
]
CommandDecisionAction = Literal[
    "create",
    "save",
    "query",
    "update",
    "delete",
    "refine",
    "reschedule",
    "summarize",
    "answer",
]
CommandOutputKind = Literal[
    "assistant_text",
    "runtime_trace",
    "task_proposal_summary",
    "task_proposal_detail",
    "calendar_plan_preview",
    "approval_request",
    "calendar_write_result",
    "command_decision",
    "plan_search_results",
    "note_search_results",
    "plan_patch_preview",
    "plan_patch_result",
    "note_write_preview",
    "note_write_result",
    "model_usage",
    "clarify_question",
    "execution_result",
    "error",
]


class CommandDecisionDateRange(BaseModel):
    start: str = ""
    end: str = ""


class CommandDecisionPatchFields(BaseModel):
    title: str | None = None
    date: str | None = None
    time: str | None = None
    estimated_minutes: int | None = Field(default=None, alias="estimatedMinutes")

    model_config = ConfigDict(populate_by_name=True)


class CommandDecisionParams(BaseModel):
    title: str | None = None
    date: str | None = None
    date_range: CommandDecisionDateRange | None = Field(default=None, alias="dateRange")
    time: str | None = None
    estimated_minutes: int | None = Field(default=None, alias="estimatedMinutes")
    target_index: int | None = Field(default=None, alias="targetIndex")
    query: str | None = None
    refinement_instruction: str | None = Field(default=None, alias="refinementInstruction")
    patch_fields: CommandDecisionPatchFields | None = Field(default=None, alias="patchFields")
    note_text: str | None = Field(default=None, alias="noteText")

    model_config = ConfigDict(populate_by_name=True)


class CommandDecision(BaseModel):
    intent: CommandDecisionIntent
    confidence: float = Field(default=0, ge=0, le=1)
    target_type: CommandDecisionTargetType = Field(default="unknown", alias="targetType")
    action: CommandDecisionAction = "answer"
    extracted_params: CommandDecisionParams = Field(default_factory=CommandDecisionParams, alias="extractedParams")
    needs_confirmation: bool = Field(default=False, alias="needsConfirmation")
    needs_clarification: bool = Field(default=False, alias="needsClarification")
    clarification_question: str | None = Field(default=None, alias="clarificationQuestion")
    decision_summary: str = Field(default="", alias="decisionSummary")

    model_config = ConfigDict(populate_by_name=True)


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

export type Language = 'zh-CN' | 'en-US';
export type Lang = Language;

export type AppRoute = 'dashboard' | 'calendar' | 'notes' | 'goals' | 'settings';

export type AgentFlowNodeType = 'input' | 'reasoning' | 'tool' | 'observation' | 'output';
export type AgentFlowStatus = 'pending' | 'running' | 'done' | 'error';

export type ModelKnowledgeTriggerReason =
  | 'forced_by_user'
  | 'insufficient_local_sources'
  | 'keyword_mismatch'
  | 'low_local_relevance';

export interface ModelKnowledgeDecision {
  shouldEnrich: boolean;
  triggerReason?: ModelKnowledgeTriggerReason | null;
  localSourceCount?: number;
  relevantSourceCount?: number;
  matchedKeywords?: string[];
  missingKeywords?: string[];
}

export interface AgentToolCall {
  name: string;
  input: string;
  output: string;
  latencyMs: number;
  expanded: boolean;
  writeMode?: 'readonly' | 'preview';
  modelKnowledgeDecision?: ModelKnowledgeDecision;
  raw?: AgentRuntimeToolCall;
}

export interface AgentFlowDiff {
  previous: string;
  current: string;
  changedAt: number;
}

export interface AgentFlowNode {
  id: string;
  type: AgentFlowNodeType;
  title: string;
  content: string;
  status: AgentFlowStatus;
  timestamp: number;
  toolCall?: AgentToolCall;
  diff?: AgentFlowDiff;
}

export interface AgentRunRequest {
  input: string;
  date: string;
  preferences?: string | Record<string, unknown>;
  materials?: string;
  data?: Record<string, unknown>;
  options?: {
    forceModelKnowledge?: boolean;
  };
}

export interface AgentRuntimeToolCall {
  name: string;
  input: unknown;
  output?: unknown;
  latencyMs?: number;
  writeMode: 'readonly' | 'preview';
  modelKnowledgeDecision?: ModelKnowledgeDecision;
  raw?: {
    input?: unknown;
    output?: unknown;
  };
}

export interface AgentRuntimeEvent {
  runId: string;
  sequence: number;
  type: 'node' | 'delta' | 'tool' | 'status' | 'final' | 'error';
  nodeId?: string;
  nodeType?: AgentFlowNodeType;
  status?: AgentFlowStatus;
  title?: string;
  content?: string;
  delta?: string;
  toolCall?: AgentRuntimeToolCall;
  error?: string;
}

export interface InspectorLog {
  id: string;
  level: 'info' | 'success' | 'warning' | 'error';
  message: string;
  timestamp: number;
}

export interface InspectorSnapshot {
  route: AppRoute;
  agentStatus: 'idle' | 'running' | 'done' | 'error';
  logs: InspectorLog[];
  memory: {
    preferenceSummary: string;
    materialCount: number;
    planCount: number;
  };
  api: {
    mode: 'local' | 'backend' | 'unknown';
    hasApiKey: boolean;
    provider: string;
  };
}

export interface Plan {
  id: string;
  time: string;
  title: string;
  done: boolean;
  completion: string;
  source?: 'manual' | 'ai';
  sourceKey?: string;
  refinedTask?: RefinedTask | null;
  refinedTaskUpdatedAt?: string | null;
}

export interface AppliedPlan extends Plan {
  date: string;
}

export interface DayRecord {
  plans: Plan[];
}

export type AppData = Record<string, DayRecord>;

export interface PlannerTask {
  time: string;
  title: string;
  reason: string;
}

export type GoalPriority = 'low' | 'medium' | 'high';

export interface GoalPlanTask {
  title: string;
  description: string;
  estimatedMinutes: number;
  dueDate: string | null;
  priority: GoalPriority;
}

export interface GoalMilestone {
  title: string;
  description: string;
  tasks: GoalPlanTask[];
}

export interface ReviewPlan {
  frequency: 'daily' | 'weekly';
  questions: string[];
}

export interface StructuredGoalPlan {
  goalTitle: string;
  goalDescription: string;
  durationDays: number;
  milestones: GoalMilestone[];
  reviewPlan: ReviewPlan;
}

export interface PhaseItem {
  title: string;
  detail: string;
}

export interface ReplanTask extends PlannerTask {
  targetDate: string;
  sourcePlanId?: string;
}

export interface RagSource {
  documentId: string;
  title: string;
  chunk: string;
  score: number;
  chunkIndex: number;
}

export interface RagDocument {
  id: string;
  title: string;
  sourceType: string;
  summary: string;
  chunks: number;
  createdAt: string;
}

export interface RagDocumentInput {
  title: string;
  content: string;
  sourceType?: string;
}

export interface AiMaterialDraftRequest {
  query: string;
  outputLanguage?: 'zh' | 'en';
}

export interface AiMaterialDraft {
  title: string;
  content: string;
  summary: string;
  sourceType: 'model_knowledge' | 'local_knowledge_template';
  caveat?: string;
}

export interface GoalPlanResponse {
  id: string;
  mode: 'mock' | 'llm';
  summary: string;
  phases: PhaseItem[];
  tasks: PlannerTask[];
  sources?: RagSource[];
  structuredPlan?: StructuredGoalPlan;
  provider?: string;
  model?: string;
  fallbackReason?: 'llm_error' | 'mock_provider' | 'missing_api_key';
  errorType?: string;
  errorMessage?: string;
  baseUrlHost?: string;
}

export interface RefineTaskRequest {
  goal: string;
  taskTitle: string;
  taskDescription?: string;
  date?: string;
  availableMinutes?: number;
  userConstraints?: string[];
  retrievedSources?: RagSource[];
  outputLanguage?: 'zh' | 'en';
  refinementInstruction?: string;
}

export interface RefinedTask {
  title: string;
  objective: string;
  estimatedMinutes: number;
  steps: string[];
  checklist: string[];
  acceptanceCriteria: string[];
  deliverable: string;
  risks: string[];
  fallbackTips: string[];
  mode: 'llm' | 'local_fallback';
  fallbackReason?: string;
  errorType?: string;
}

export interface DailyReviewResponse {
  id: string;
  mode: 'mock' | 'llm' | 'saved';
  date: string;
  summary: string;
  suggestions: string[];
  doneCount: number;
  totalCount: number;
  targetDate: string;
  replanTasks: ReplanTask[];
  provider?: string;
  model?: string;
  updatedAt?: string;
}

export interface ReplanApplyPayload {
  tasks: ReplanTask[];
}

export interface PlannerResponse {
  mode?: 'api' | 'mock' | 'llm';
  summary?: string;
  phases?: PhaseItem[];
  tasks?: PlannerTask[];
  suggestions?: string[];
  answer?: string;
  sources?: RagSource[];
  keywords?: string[];
  score?: number;
  provider?: string;
  model?: string;
  criteria?: string[];
  results?: Array<{ case: string; score: number; reason: string }>;
}

export interface AiSettings {
  provider: 'mock' | 'deepseek' | 'openai' | 'custom';
  baseUrl: string;
  model: string;
  hasApiKey: boolean;
  temperature: number;
  timeoutSeconds: number;
  updatedAt: string;
}

export interface AiSettingsInput {
  provider: AiSettings['provider'];
  baseUrl: string;
  model: string;
  apiKey?: string;
  temperature: number;
  timeoutSeconds: number;
}

export interface AiSettingsTestResult {
  ok: boolean;
  mode: 'mock' | 'llm' | 'error';
  message: string;
  provider?: string;
  model?: string;
  errorType?: string;
  statusCode?: number;
  detail?: string;
}

export interface MemoryCacheStats {
  preferenceMemory: number;
  historySummaries: number;
  agentRuns: number;
  agentEvents: number;
  planningGoals: number;
  plans: number;
}

export interface MemoryResetResult {
  ok: boolean;
  before: MemoryCacheStats;
  after: MemoryCacheStats;
  deleted: Record<string, number>;
  steps?: Record<string, Record<string, number>>;
  preserved: {
    plans: boolean;
    goals: boolean;
    calendar: boolean;
    notes: boolean;
    documents: boolean;
    aiSettings: boolean;
  };
  message: string;
}

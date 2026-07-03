export type Language = 'zh-CN' | 'en-US';
export type Lang = Language;

export type AppRoute = 'dashboard' | 'calendar' | 'notes' | 'goals' | 'settings';

export type AgentFlowNodeType = 'input' | 'reasoning' | 'tool' | 'observation' | 'output';
export type AgentFlowStatus = 'pending' | 'running' | 'done' | 'error';

export interface AgentToolCall {
  name: string;
  input: string;
  output: string;
  latencyMs: number;
  expanded: boolean;
  writeMode?: 'readonly' | 'preview';
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
  preferences?: string;
  materials?: string;
  data?: Record<string, unknown>;
}

export interface AgentRuntimeToolCall {
  name: string;
  input: unknown;
  output?: unknown;
  latencyMs?: number;
  writeMode: 'readonly' | 'preview';
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

export type Lang = 'zh' | 'en';

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
  provider?: string;
  model?: string;
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
  provider: string;
  model: string;
}

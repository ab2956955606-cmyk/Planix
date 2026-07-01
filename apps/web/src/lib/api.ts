import type {
  AiSettings,
  AiSettingsInput,
  AiSettingsTestResult,
  AppData,
  AppliedPlan,
  DailyReviewResponse,
  GoalPlanResponse,
  Plan,
  PlannerResponse,
  PlannerTask,
  RagDocument,
  RagDocumentInput,
  RagSource,
  ReplanApplyPayload
} from '../types';

const API_BASE = import.meta.env.VITE_API_BASE ?? '';

interface AiPayload {
  goal: string;
  deadline: string;
  dailyHours: number;
  materials: string;
  preferences: string;
  date: string;
  data: AppData;
}

interface BackendPlan {
  id: string;
  date: string;
  time: string;
  content: string;
  done: boolean;
  result: string;
  priority: 'low' | 'medium' | 'high';
  estimatedMinutes: number;
  source: 'manual' | 'ai';
  createdAt: string;
  updatedAt: string;
}

interface BackendMonthNote {
  year: number;
  month: number;
  content: string;
  updatedAt: string;
}

export type PlanPatch = Partial<Pick<Plan, 'time' | 'title' | 'done' | 'completion' | 'source'>>;

async function request<T>(path: string, init: RequestInit = {}, timeoutMs = 1800): Promise<T> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  const isFormData = init.body instanceof FormData;
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: isFormData ? init.headers : { 'Content-Type': 'application/json', ...(init.headers ?? {}) },
      signal: controller.signal
    });
    if (!res.ok) throw new Error(`API ${res.status}`);
    if (res.status === 204) return undefined as T;
    return (await res.json()) as T;
  } finally {
    window.clearTimeout(timer);
  }
}

async function post<T>(path: string, payload: unknown, timeoutMs = 1800): Promise<T> {
  return request<T>(path, { method: 'POST', body: JSON.stringify(payload) }, timeoutMs);
}

function fromBackendPlan(plan: BackendPlan): Plan {
  return {
    id: plan.id,
    time: plan.time,
    title: plan.content,
    done: plan.done,
    completion: plan.result ?? '',
    source: plan.source
  };
}

function fromAppliedBackendPlan(plan: BackendPlan): AppliedPlan {
  return { ...fromBackendPlan(plan), date: plan.date };
}

function toBackendPlan(date: string, plan: Plan) {
  return {
    date,
    time: plan.time,
    content: plan.title,
    done: plan.done,
    result: plan.completion,
    source: plan.source ?? 'manual',
    priority: 'medium',
    estimatedMinutes: 30
  };
}

export async function fetchPlans(date: string): Promise<Plan[]> {
  const params = new URLSearchParams({ date });
  const plans = await request<BackendPlan[]>(`/api/plans?${params.toString()}`);
  return plans.map(fromBackendPlan);
}

export async function createPlan(date: string, plan: Plan): Promise<Plan> {
  const saved = await post<BackendPlan>('/api/plans', toBackendPlan(date, plan));
  return fromBackendPlan(saved);
}

export async function updatePlan(id: string, patch: PlanPatch): Promise<Plan> {
  const saved = await request<BackendPlan>(`/api/plans/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({
      time: patch.time,
      content: patch.title,
      done: patch.done,
      result: patch.completion,
      source: patch.source
    })
  });
  return fromBackendPlan(saved);
}

export async function deletePlan(id: string): Promise<void> {
  await request<void>(`/api/plans/${id}`, { method: 'DELETE' });
}

export async function fetchMonthNote(year: number, month: number): Promise<string> {
  const params = new URLSearchParams({ year: String(year), month: String(month) });
  const note = await request<BackendMonthNote>(`/api/month-notes?${params.toString()}`);
  return note.content;
}

export async function saveRemoteMonthNote(year: number, month: number, content: string): Promise<void> {
  await request<BackendMonthNote>('/api/month-notes', {
    method: 'PUT',
    body: JSON.stringify({ year, month, content })
  });
}

export async function fetchAiSettings(): Promise<AiSettings> {
  return request<AiSettings>('/api/ai/settings');
}

export async function saveAiSettings(payload: AiSettingsInput): Promise<AiSettings> {
  return request<AiSettings>('/api/ai/settings', {
    method: 'PUT',
    body: JSON.stringify(payload)
  });
}

export async function testAiSettings(prompt = 'Say OK in one short sentence.'): Promise<AiSettingsTestResult> {
  return post<AiSettingsTestResult>('/api/ai/test', { prompt }, 45000);
}

export async function fetchRagDocuments(): Promise<RagDocument[]> {
  return request<RagDocument[]>('/api/rag/documents', {}, 45000);
}

export async function createRagDocument(payload: RagDocumentInput): Promise<RagDocument> {
  return post<RagDocument>('/api/rag/documents', payload, 45000);
}

export async function uploadRagDocument(file: File, title?: string): Promise<RagDocument> {
  const form = new FormData();
  form.append('file', file);
  if (title?.trim()) form.append('title', title.trim());
  form.append('sourceType', 'upload');
  return request<RagDocument>('/api/rag/documents/upload', { method: 'POST', body: form }, 45000);
}

export async function deleteRagDocument(id: string): Promise<void> {
  await request<void>(`/api/rag/documents/${id}`, { method: 'DELETE' }, 45000);
}

export async function createGoalPlan(payload: Omit<AiPayload, 'data'>): Promise<GoalPlanResponse> {
  return post<GoalPlanResponse>('/api/planning/goal-plan', payload, 45000);
}

export async function createDailyReview(payload: Pick<AiPayload, 'date' | 'goal' | 'preferences' | 'data'>): Promise<DailyReviewResponse> {
  return post<DailyReviewResponse>('/api/planning/daily-review', payload, 45000);
}

export async function fetchDailyReview(date: string): Promise<DailyReviewResponse> {
  const params = new URLSearchParams({ date });
  return request<DailyReviewResponse>(`/api/planning/daily-review?${params.toString()}`);
}

export async function applyReplanTasks(payload: ReplanApplyPayload): Promise<AppliedPlan[]> {
  const plans = await post<BackendPlan[]>('/api/planning/replan/apply', payload, 45000);
  return plans.map(fromAppliedBackendPlan);
}

function fallbackTasks(payload: AiPayload): PlannerTask[] {
  const title = payload.goal || 'AI 应用开发实习';
  return [
    { time: '09:00', title: `拆解目标：${title}`, reason: '先把长期目标转成阶段里程碑，避免计划停留在口号。' },
    { time: '14:30', title: '实现一个可展示的项目功能', reason: '每天保留工程产出，面试时可以讲清楚设计和取舍。' },
    { time: '20:30', title: '复盘完成情况并调整明日任务', reason: '形成计划、执行、反馈、重排的闭环。' }
  ];
}

export async function generatePlan(payload: AiPayload): Promise<PlannerResponse> {
  try {
    return await post<PlannerResponse>('/api/agent/plan', payload, 45000);
  } catch {
    return {
      mode: 'mock',
      summary: `基于每天 ${payload.dailyHours || 2} 小时，为目标生成阶段计划。`,
      phases: [
        { title: '第 1 阶段：能力对齐', detail: '补齐岗位 JD 中的核心技术栈与基础知识。' },
        { title: '第 2 阶段：项目冲刺', detail: '完成 AI/RAG/Agent 相关功能并沉淀文档。' },
        { title: '第 3 阶段：投递复盘', detail: '结合反馈优化简历、项目讲法与面试题库。' }
      ],
      tasks: fallbackTasks(payload)
    };
  }
}

export async function reviewToday(payload: AiPayload): Promise<PlannerResponse> {
  try {
    return await post<PlannerResponse>('/api/agent/review', payload, 45000);
  } catch {
    const plans = payload.data[payload.date]?.plans ?? [];
    const done = plans.filter((plan) => plan.done).length;
    return {
      mode: 'mock',
      summary: `今天完成 ${done}/${plans.length} 项。`,
      suggestions: ['把未完成任务拆小到 45 分钟内。', '保留一个可验证产出，例如提交、截图或笔记。', '晚上用完成情况更新明天计划。']
    };
  }
}

function fallbackSources(materials: string): RagSource[] {
  return materials
    .split(/\s+|，|。|,|\./)
    .filter(Boolean)
    .slice(0, 4)
    .map((chunk, index) => ({
      documentId: 'local-input',
      title: `Material ${index + 1}`,
      chunk,
      score: 0,
      chunkIndex: index
    }));
}

export async function askMaterials(payload: AiPayload): Promise<PlannerResponse> {
  try {
    return await post<PlannerResponse>('/api/rag/query', payload, 45000);
  } catch {
    return {
      mode: 'mock',
      answer: '资料库服务暂不可用。你仍可以先根据当前粘贴内容提炼高频技能、项目要求和可验证产出。',
      sources: fallbackSources(payload.materials)
    };
  }
}

export async function saveMemory(preferences: string): Promise<void> {
  try {
    await post('/api/memory/preferences', { userId: 'local-user', preferences });
  } catch {
    return;
  }
}

export async function evaluatePlanner(payload: AiPayload): Promise<PlannerResponse> {
  try {
    return await post<PlannerResponse>('/api/eval/planner', payload, 45000);
  } catch {
    return {
      mode: 'mock',
      score: 4.4,
      results: [
        { case: '目标明确但时间有限', score: 5, reason: '计划覆盖阶段、日任务和复盘闭环。' },
        { case: '包含岗位 JD 资料', score: 4, reason: '已能提取关键词，后续可加入引用来源。' },
        { case: '当天未完成任务', score: 4, reason: '可生成调整建议，后续继续增强自动重排。' }
      ]
    };
  }
}

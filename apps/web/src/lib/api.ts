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
  ReplanApplyPayload
} from '../types';
import { invoke } from '@tauri-apps/api/core';

// AiPayload is defined inline in other modules, but not exported from types.ts
// Define it here for our use
interface AiPayload {
  goal: string;
  deadline: string;
  dailyHours: number;
  materials: string;
  preferences: string;
  date: string;
  data: AppData;
}

/* ═══════════════════════════════════════════════════════════════════
   API layer for Planix desktop app.

   In the Tauri v2 MSI build, the frontend loads via a custom protocol
   (tauri://) which is treated as a secure context. WebView2 blocks
   fetch() from secure contexts to http://localhost:8000 as mixed
   content. We route ALL API calls through the Tauri IPC command
   `proxy_api`, which runs in the Rust process and is not subject
   to WebView2's mixed-content restrictions.

   In DEV mode (Vite), we still use native fetch() through the Vite
   dev server proxy.
   ═══════════════════════════════════════════════════════════════════ */

const isTauri = typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window;

async function tauriProxy<T>(method: string, path: string, body?: unknown): Promise<T> {
  const result = await invoke<{ status: number; body: string }>('proxy_api', {
    req: {
      method,
      path,
      body: body ? JSON.stringify(body) : '',
    },
  });

  if (result.status >= 200 && result.status < 300) {
    if (result.status === 204) return undefined as T;
    return JSON.parse(result.body) as T;
  }

  let detail: unknown = undefined;
  try {
    detail = JSON.parse(result.body);
  } catch {
    /* ignore */
  }

  throw new ApiHttpError(result.status, detail);
}

class ApiError extends Error {
  status?: number;
  detail?: unknown;
  isNetworkError?: boolean;

  constructor(message: string, options: { status?: number; detail?: unknown; isNetworkError?: boolean } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = options.status;
    this.detail = options.detail;
    this.isNetworkError = options.isNetworkError;
  }
}

class ApiNetworkError extends ApiError {
  constructor(message = '后端服务未启动或连接失败') {
    super(message, { isNetworkError: true });
    this.name = 'ApiNetworkError';
  }
}

export { ApiNetworkError, ApiError };

class ApiHttpError extends ApiError {
  status: number;

  constructor(status: number, detail: unknown) {
    super(`HTTP ${status}`, { status, detail, isNetworkError: false });
    this.name = 'ApiHttpError';
    this.status = status;
  }
}

export { ApiHttpError };

// ═══ Common request helper ═══

async function callApi<T>(method: string, path: string, body?: unknown, timeoutMs = 45000): Promise<T> {
  if (isTauri) {
    return tauriProxy<T>(method, path, body);
  }
  // Dev mode: use fetch()
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const init: RequestInit = {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : {},
      signal: controller.signal,
    };
    if (body) init.body = JSON.stringify(body);
    const res = await fetch(path, init);
    if (!res.ok) {
      let detail: unknown = undefined;
      try { detail = await res.json(); } catch { /* ignore */ }
      throw new ApiHttpError(res.status, detail);
    }
    if (res.status === 204) return undefined as T;
    return (await res.json()) as T;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    const message = err instanceof Error ? err.message : String(err);
    const name = err instanceof Error ? err.name : '';
    if (name === 'AbortError' || err instanceof TypeError || message.includes('Failed to fetch') || message.includes('ECONNREFUSED')) {
      throw new ApiNetworkError();
    }
    throw err;
  } finally {
    window.clearTimeout(timer);
  }
}

// ═══ Health & Settings ═══

export async function checkBackendHealth(): Promise<boolean> {
  try {
    return await callApi<boolean>('GET', '/api/health');
  } catch {
    return false;
  }
}

export async function fetchAiSettings(): Promise<AiSettings> {
  return callApi<AiSettings>('GET', '/api/ai/settings');
}

export async function saveAiSettings(payload: AiSettingsInput): Promise<AiSettings> {
  return callApi<AiSettings>('PUT', '/api/ai/settings', payload, 15000);
}

export async function testAiSettings(): Promise<AiSettingsTestResult> {
  return callApi<AiSettingsTestResult>('POST', '/api/ai/test', { prompt: 'Say OK in one short sentence.' }, 45000);
}

// ═══ Plans ═══

type BackendPlan = {
  id: string; date: string; time: string; content: string; done: boolean;
  result: string; priority: 'low' | 'medium' | 'high'; estimatedMinutes: number;
  source: 'manual' | 'ai'; createdAt: string; updatedAt: string;
};

export type PlanPatch = Partial<Pick<Plan, 'time' | 'title' | 'done' | 'completion' | 'source'>>;

function fromBackendPlan(plan: BackendPlan): Plan {
  return {
    id: plan.id, time: plan.time, title: plan.content,
    done: plan.done, completion: plan.result ?? '', source: plan.source,
  };
}

function fromAppliedBackendPlan(plan: BackendPlan): AppliedPlan {
  return { ...fromBackendPlan(plan), date: plan.date };
}

function toBackendPlan(date: string, plan: Plan) {
  return {
    date, time: plan.time, content: plan.title, done: plan.done,
    result: plan.completion, source: plan.source ?? 'manual',
    priority: 'medium', estimatedMinutes: 30,
  };
}

export async function fetchPlans(date: string): Promise<Plan[]> {
  const plans = await callApi<BackendPlan[]>('GET', `/api/plans?date=${encodeURIComponent(date)}`);
  return plans.map(fromBackendPlan);
}

export async function createPlan(date: string, plan: Plan): Promise<Plan> {
  const saved = await callApi<BackendPlan>('POST', '/api/plans', toBackendPlan(date, plan));
  return fromBackendPlan(saved);
}

export async function updatePlan(id: string, patch: PlanPatch): Promise<Plan> {
  const saved = await callApi<BackendPlan>('PATCH', `/api/plans/${id}`, {
    time: patch.time, content: patch.title, done: patch.done,
    result: patch.completion, source: patch.source,
  });
  return fromBackendPlan(saved);
}

export async function deletePlan(id: string): Promise<void> {
  await callApi<void>('DELETE', `/api/plans/${id}`);
}

// ═══ Month Notes ═══

export async function fetchMonthNote(year: number, month: number): Promise<string> {
  const note = await callApi<{ content: string }>('GET', `/api/month-notes?year=${year}&month=${month}`);
  return note.content;
}

export async function saveRemoteMonthNote(year: number, month: number, content: string): Promise<void> {
  await callApi<void>('PUT', '/api/month-notes', { year, month, content });
}

// ═══ RAG ═══

export async function fetchRagDocuments(): Promise<RagDocument[]> {
  return callApi<RagDocument[]>('GET', '/api/rag/documents', undefined, 45000);
}

export async function createRagDocument(payload: RagDocumentInput): Promise<RagDocument> {
  return callApi<RagDocument>('POST', '/api/rag/documents', payload, 45000);
}

function validateUploadFile(file: File): void {
  const lowerName = file.name.toLowerCase();
  if (!lowerName.endsWith('.txt') && !lowerName.endsWith('.md')) {
    throw new ApiHttpError(400, { detail: 'Only .txt and .md files are supported.' });
  }
  if (file.size <= 0) {
    throw new ApiHttpError(400, { detail: 'File cannot be empty.' });
  }
  if (file.size > 5 * 1024 * 1024) {
    throw new ApiHttpError(400, { detail: 'File must be 5MB or smaller.' });
  }
}

function fallbackTitleFromFile(file: File): string {
  return file.name.replace(/\.[^/.]+$/, '') || 'Uploaded material';
}

async function readUploadText(file: File): Promise<string> {
  const buffer = await file.arrayBuffer();
  for (const encoding of ['utf-8', 'gb18030']) {
    try {
      return new TextDecoder(encoding, { fatal: true }).decode(buffer);
    } catch {
      /* try the next text encoding */
    }
  }
  throw new ApiHttpError(400, { detail: 'File must be valid UTF-8 or GB18030 text.' });
}

export async function uploadRagDocument(file: File, title?: string): Promise<RagDocument> {
  validateUploadFile(file);
  if (isTauri) {
    const content = (await readUploadText(file)).trim();
    if (!content) {
      throw new ApiHttpError(400, { detail: 'File cannot be empty.' });
    }
    return createRagDocument({
      title: title?.trim() || fallbackTitleFromFile(file),
      content,
      sourceType: 'upload',
    });
  }

  const form = new FormData();
  form.append('file', file);
  if (title?.trim()) form.append('title', title.trim());
  form.append('sourceType', 'upload');
  const res = await fetch('/api/rag/documents/upload', { method: 'POST', body: form });
  if (!res.ok) throw new ApiHttpError(res.status, undefined);
  return res.json();
}

export async function deleteRagDocument(id: string): Promise<void> {
  await callApi<void>('DELETE', `/api/rag/documents/${id}`, undefined, 45000);
}

// ═══ AI Planning & Review ═══

export async function createGoalPlan(payload: Omit<AiPayload, 'data'>): Promise<GoalPlanResponse> {
  return callApi<GoalPlanResponse>('POST', '/api/planning/goal-plan', payload, 45000);
}

export async function createDailyReview(payload: Pick<AiPayload, 'date' | 'goal' | 'preferences' | 'data'>): Promise<DailyReviewResponse> {
  return callApi<DailyReviewResponse>('POST', '/api/planning/daily-review', payload, 45000);
}

export async function fetchDailyReview(date: string): Promise<DailyReviewResponse> {
  return callApi<DailyReviewResponse>('GET', `/api/planning/daily-review?date=${encodeURIComponent(date)}`);
}

export async function applyReplanTasks(payload: ReplanApplyPayload): Promise<AppliedPlan[]> {
  const plans = await callApi<BackendPlan[]>('POST', '/api/planning/replan/apply', payload, 45000);
  return plans.map(fromAppliedBackendPlan);
}

// ═══ Agent & Evaluator ═══

function fallbackTasks(payload: AiPayload): PlannerTask[] {
  const title = payload.goal || 'AI 应用开发实习';
  return [
    { time: '09:00', title: `拆解目标：${title}`, reason: '先把长期目标转成阶段里程碑，避免计划停留在口号。' },
    { time: '14:30', title: '实现一个可展示的项目功能', reason: '每天保留工程产出，面试时可以讲清楚设计和取舍。' },
    { time: '20:30', title: '复盘完成情况并调整明日任务', reason: '形成计划、执行、反馈、重排的闭环。' },
  ];
}

export async function generatePlan(payload: AiPayload): Promise<PlannerResponse> {
  try {
    return await callApi<PlannerResponse>('POST', '/api/agent/plan', payload, 45000);
  } catch {
    return {
      mode: 'mock',
      summary: `基于每天 ${payload.dailyHours || 2} 小时，为目标生成阶段计划。`,
      phases: [
        { title: '第 1 阶段：能力对齐', detail: '补齐岗位 JD 中的核心技术栈与基础知识。' },
        { title: '第 2 阶段：项目冲刺', detail: '完成 AI/RAG/Agent 相关功能并沉淀文档。' },
        { title: '第 3 阶段：投递复盘', detail: '结合反馈优化简历、项目讲法与面试题库。' },
      ],
      tasks: fallbackTasks(payload),
    };
  }
}

export async function reviewToday(payload: AiPayload): Promise<PlannerResponse> {
  try {
    return await callApi<PlannerResponse>('POST', '/api/agent/review', payload, 45000);
  } catch {
    const plans = payload.data[payload.date]?.plans ?? [];
    const done = plans.filter((plan: Plan) => plan.done).length;
    return {
      mode: 'mock',
      summary: `今天完成 ${done}/${plans.length} 项。`,
      suggestions: ['把未完成任务拆小到 45 分钟内。', '保留一个可验证产出，例如提交、截图或笔记。', '晚上用完成情况更新明天计划。'],
    };
  }
}

export async function askMaterials(payload: AiPayload): Promise<PlannerResponse> {
  try {
    return await callApi<PlannerResponse>('POST', '/api/rag/query', payload, 45000);
  } catch {
    return {
      mode: 'mock',
      answer: '资料库服务暂不可用。你仍可以先根据当前粘贴内容提炼高频技能、项目要求和可验证产出。',
      sources: [],
    };
  }
}

export async function saveMemory(preferences: string): Promise<void> {
  try {
    await callApi<void>('POST', '/api/memory/preferences', { userId: 'local-user', preferences });
  } catch {
    return;
  }
}

export async function evaluatePlanner(payload: AiPayload): Promise<PlannerResponse> {
  try {
    return await callApi<PlannerResponse>('POST', '/api/eval/planner', payload, 45000);
  } catch {
    return {
      mode: 'mock',
      score: 4.4,
      results: [
        { case: '目标明确但时间有限', score: 5, reason: '计划覆盖阶段、日任务和复盘闭环。' },
        { case: '包含岗位 JD 资料', score: 4, reason: '已能提取关键词，后续可加入引用来源。' },
        { case: '当天未完成任务', score: 4, reason: '可生成调整建议，后续继续增强自动重排。' },
      ],
    };
  }
}

import type { AppData, PlannerResponse, PlannerTask } from '../types';

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

async function post<T>(path: string, payload: unknown): Promise<T> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), 1800);
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: controller.signal
    });
    if (!res.ok) throw new Error(`API ${res.status}`);
    return (await res.json()) as T;
  } finally {
    window.clearTimeout(timer);
  }
}

function fallbackTasks(payload: AiPayload): PlannerTask[] {
  const title = payload.goal || 'AI application internship';
  return [
    { time: '09:00', title: `拆解目标：${title}`, reason: '先把长期目标转成阶段里程碑，避免计划停留在口号。' },
    { time: '14:30', title: '实现一个可展示的项目功能', reason: '每天保留工程产出，面试时可以讲清楚设计和取舍。' },
    { time: '20:30', title: '复盘完成情况并调整明日任务', reason: '形成计划、执行、反馈、重排的闭环。' }
  ];
}

export async function generatePlan(payload: AiPayload): Promise<PlannerResponse> {
  try {
    return await post<PlannerResponse>('/api/agent/plan', payload);
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
    return await post<PlannerResponse>('/api/agent/review', payload);
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

export async function askMaterials(payload: AiPayload): Promise<PlannerResponse> {
  try {
    return await post<PlannerResponse>('/api/rag/query', payload);
  } catch {
    const snippets = payload.materials.split(/\s+|，|。|,|\./).filter(Boolean).slice(0, 4);
    return {
      mode: 'mock',
      answer: '资料里最应该转化为计划的是高频技能词、项目要求和可验证产出。',
      sources: snippets.map((quote, index) => ({ title: `Material ${index + 1}`, quote }))
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
    return await post<PlannerResponse>('/api/eval/planner', payload);
  } catch {
    return {
      mode: 'mock',
      score: 4.4,
      results: [
        { case: '目标明确但时间有限', score: 5, reason: '计划覆盖阶段、日任务和复盘闭环。' },
        { case: '包含岗位 JD 资料', score: 4, reason: '已能提取关键词，后续可加入引用来源。' },
        { case: '当天未完成任务', score: 4, reason: '可生成调整建议，还可继续增强自动重排。' }
      ]
    };
  }
}

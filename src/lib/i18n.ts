import type { Lang } from '../types';

type Dict = Record<string, string>;

const dict: Record<Lang, Dict> = {
  zh: {
    appName: 'MyNotes AI',
    subtitle: 'AI 学习规划与复盘助手',
    today: '今天',
    calendar: '日历',
    monthNote: '月备注',
    monthNotePlaceholder: '记录本月目标、提醒或阶段复盘...',
    plans: '计划',
    completion: '完成情况',
    addTask: '添加任务',
    taskPlaceholder: '写下一个可执行任务...',
    emptyPlans: '这一天还没有任务',
    emptyHint: '可以手动添加，也可以让 AI 生成计划。',
    aiWorkspace: 'AI 工作台',
    goal: '长期目标',
    goalPlaceholder: '例如：3 个月内拿到北京 AI 应用开发实习',
    deadline: '截止日期',
    dailyHours: '每日可用时间',
    materials: '资料 / JD / 当前基础',
    materialsPlaceholder: '粘贴岗位 JD、课程资料、面经或你的当前基础...',
    preference: '偏好记忆',
    preferencePlaceholder: '例如：上午效率高，晚上适合复盘，周末可以做长任务。',
    generate: '生成计划',
    review: '复盘今天',
    rag: '资料问答',
    saveMemory: '保存偏好',
    evaluate: '质量评估',
    applyTasks: '写入今天',
    mockMode: 'Mock AI',
    apiMode: 'API AI',
    loading: 'AI 正在思考...',
    noAiTasks: '先生成 AI 任务，再写入今天。',
    saved: '已保存偏好记忆',
    score: '规划质量评分',
    backendTip: '开发模式下 /api 会代理到 FastAPI 后端。',
    done: '已完成',
    pending: '未完成',
    delete: '删除'
  },
  en: {
    appName: 'MyNotes AI',
    subtitle: 'AI study planning and review assistant',
    today: 'Today',
    calendar: 'Calendar',
    monthNote: 'Monthly note',
    monthNotePlaceholder: 'Goals, reminders, or monthly review...',
    plans: 'Plans',
    completion: 'Completion',
    addTask: 'Add task',
    taskPlaceholder: 'Write one actionable task...',
    emptyPlans: 'No tasks for this day',
    emptyHint: 'Add one manually or let AI generate a plan.',
    aiWorkspace: 'AI Workspace',
    goal: 'Long-term goal',
    goalPlaceholder: 'Example: land a Beijing AI application internship in 3 months',
    deadline: 'Deadline',
    dailyHours: 'Daily hours',
    materials: 'Materials / JD / context',
    materialsPlaceholder: 'Paste job descriptions, notes, interview materials, or your current baseline...',
    preference: 'Preference memory',
    preferencePlaceholder: 'Example: deep work in the morning, review at night, long tasks on weekends.',
    generate: 'Generate plan',
    review: 'Review today',
    rag: 'Ask materials',
    saveMemory: 'Save memory',
    evaluate: 'Evaluate',
    applyTasks: 'Apply today',
    mockMode: 'Mock AI',
    apiMode: 'API AI',
    loading: 'AI is thinking...',
    noAiTasks: 'Generate AI tasks before applying them.',
    saved: 'Preference memory saved',
    score: 'Planner score',
    backendTip: '/api is proxied to FastAPI in dev mode.',
    done: 'Done',
    pending: 'Pending',
    delete: 'Delete'
  }
};

export function useText(lang: Lang) {
  return (key: string) => dict[lang][key] ?? key;
}

export function weekdayLabels(lang: Lang): string[] {
  return lang === 'zh' ? ['一', '二', '三', '四', '五', '六', '日'] : ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
}

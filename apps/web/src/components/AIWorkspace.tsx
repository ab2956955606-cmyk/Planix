import { useEffect, useState } from 'react';
import {
  Bot,
  ClipboardCheck,
  DatabaseZap,
  FileSearch,
  KeyRound,
  Library,
  PlugZap,
  RotateCcw,
  Save,
  Settings,
  Sparkles,
  Trash2,
  UploadCloud,
  X
} from 'lucide-react';
import type {
  AiSettings,
  AiSettingsInput,
  AppliedPlan,
  AppData,
  DailyReviewResponse,
  GoalPlanTask,
  GoalPlanResponse,
  MemoryCacheStats,
  MemoryResetResult,
  Plan,
  PlannerResponse,
  PlannerTask,
  RagDocument,
  RagSource,
  RefinedTask,
  Language,
  StructuredGoalPlan
} from '../types';
import {
  ApiHttpError,
  ApiNetworkError,
  applyReplanTasks,
  askMaterials,
  createAiMaterialDraft,
  createDailyReview,
  createGoalPlan,
  createRagDocument,
  deleteRagDocument,
  evaluatePlanner,
  fetchAiSettings,
  fetchDailyReview,
  fetchMemoryCacheStats,
  fetchRagDocuments,
  clearAiMemoryCache,
  clearHistoryMemory,
  clearPlanningHistory,
  clearPreferenceMemory,
  clearRuntimeRuns,
  saveAiSettings,
  saveMemory,
  testAiSettings,
  refineTask,
  uploadRagDocument
} from '../lib/api';
import { refineTaskErrorText } from '../lib/refineTaskErrors';
import { RefinedTaskPreview } from './RefinedTaskPreview';

type WorkspaceSection = 'all' | 'notes' | 'goals' | 'settings';
type MemoryResetAction = 'preferences' | 'history' | 'runtime' | 'planning' | 'all';

interface AIWorkspaceProps {
  data: AppData;
  date: string;
  preferences: string;
  section?: WorkspaceSection;
  onPreferencesChange: (value: string) => void;
  onApplyGoalPlanToCalendar: (plan: GoalPlanResponse) => Promise<{ created: number; updated: number; failed: number; otherDates: boolean }>;
  onReplanApplied: (plans: AppliedPlan[]) => void;
  onCreateOrUpdateRefinedPlan: (input: { date: string; title: string; sourceKey: string; refinedTask: RefinedTask }) => Promise<Plan>;
  onDeletePlanRefinedTask: (planId: string, date?: string) => Promise<Plan>;
  onSettingsChange?: (settings: AiSettings) => void;
  language: Language;
  t: (key: string) => string;
}

const defaultSettings: AiSettings = {
  provider: 'deepseek',
  baseUrl: 'https://api.deepseek.com',
  model: 'deepseek-v4-flash',
  hasApiKey: false,
  temperature: 0.3,
  timeoutSeconds: 40,
  updatedAt: ''
};

function apiDetailToText(detail: unknown): string {
  if (!detail) return '';
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === 'string') return item;
        if (item && typeof item === 'object' && 'msg' in item) return String((item as { msg: unknown }).msg);
        return '';
      })
      .filter(Boolean)
      .join('; ');
  }
  if (typeof detail === 'object') {
    const record = detail as Record<string, unknown>;
    return apiDetailToText(record.detail ?? record.message);
  }
  return String(detail);
}

function isTimeoutLikeError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error);
  return /timeout|timed out|deadline|abort/i.test(message);
}

function normalizeGoalTaskDate(dueDate: string | null | undefined, fallbackDate: string): string {
  if (typeof dueDate !== 'string') return fallbackDate;
  const trimmed = dueDate.trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) return trimmed;
  const prefix = trimmed.slice(0, 10);
  return /^\d{4}-\d{2}-\d{2}$/.test(prefix) ? prefix : fallbackDate;
}

function stableKeyPart(value: string): string {
  return value.trim().toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9\u4e00-\u9fff-]/gi, '').slice(0, 48);
}

function goalTaskSourceKey(goalPlan: GoalPlanResponse, taskKey: string, task: GoalPlanTask): string {
  const match = /^(\d+)-(\d+)-/.exec(taskKey);
  const milestoneIndex = match?.[1] ?? '0';
  const taskIndex = match?.[2] ?? '0';
  const base = goalPlan.id
    ? `goal-plan:${goalPlan.id}`
    : `goal-plan:${stableKeyPart(goalPlan.structuredPlan?.goalTitle || goalPlan.summary)}:${stableKeyPart(task.title)}:${task.dueDate || 'no-date'}`;
  return `${base}:m${milestoneIndex}:t${taskIndex}`;
}

export function AIWorkspace(props: AIWorkspaceProps) {
  const {
    data,
    date,
    preferences,
    section = 'all',
    onPreferencesChange,
    onApplyGoalPlanToCalendar,
    onReplanApplied,
    onCreateOrUpdateRefinedPlan,
    onDeletePlanRefinedTask,
    onSettingsChange,
    language,
    t
  } = props;
  const [goal, setGoal] = useState(t('legacy.goalPlaceholder'));
  const [deadline, setDeadline] = useState(() => {
    const d = new Date();
    d.setMonth(d.getMonth() + 3);
    return d.toISOString().slice(0, 10);
  });
  const [dailyHours, setDailyHours] = useState(3);
  const [materials, setMaterials] = useState('');
  const [docTitle, setDocTitle] = useState('');
  const [docContent, setDocContent] = useState('');
  const [materialDraftTopic, setMaterialDraftTopic] = useState('');
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [fileInputKey, setFileInputKey] = useState(0);
  const [documents, setDocuments] = useState<RagDocument[]>([]);
  const [documentStatus, setDocumentStatus] = useState('');
  const [goalPlan, setGoalPlan] = useState<GoalPlanResponse | null>(null);
  const [goalStatus, setGoalStatus] = useState('');
  const [refinedTasksById, setRefinedTasksById] = useState<Record<string, RefinedTask>>({});
  const [refiningTaskIds, setRefiningTaskIds] = useState<Record<string, boolean>>({});
  const [refineTaskErrors, setRefineTaskErrors] = useState<Record<string, string>>({});
  const [goalTaskRefinementInputs, setGoalTaskRefinementInputs] = useState<Record<string, string>>({});
  const [refinedGoalPlanRefsByKey, setRefinedGoalPlanRefsByKey] = useState<Record<string, { id: string; date: string }>>({});
  const [deletingGoalTaskKeys, setDeletingGoalTaskKeys] = useState<Record<string, boolean>>({});
  const [bulkRefiningGoalTasks, setBulkRefiningGoalTasks] = useState(false);
  const [dailyReview, setDailyReview] = useState<DailyReviewResponse | null>(null);
  const [utilityResult, setUtilityResult] = useState<PlannerResponse | null>(null);
  const [loading, setLoading] = useState('');
  const [settings, setSettings] = useState<AiSettings>(defaultSettings);
  const [apiKey, setApiKey] = useState('');
  const [settingsStatus, setSettingsStatus] = useState('');
  const [settingsBusy, setSettingsBusy] = useState<'save' | 'test' | 'clear' | ''>('');
  const [reviewStatus, setReviewStatus] = useState('');
  const [memoryStats, setMemoryStats] = useState<MemoryCacheStats | null>(null);
  const [memoryResetResult, setMemoryResetResult] = useState<MemoryResetResult | null>(null);
  const [memoryResetStatus, setMemoryResetStatus] = useState('');
  const [memoryResetBusy, setMemoryResetBusy] = useState<MemoryResetAction | ''>('');

  const payload = { goal, deadline, dailyHours, materials, preferences, date, data };
  const showSettings = section === 'all' || section === 'settings';
  const showMaterials = section === 'all' || section === 'notes';
  const showGoals = section === 'all' || section === 'goals';
  const showReview = section === 'all' || section === 'goals';
  const showNotesUtility = section === 'all' || section === 'notes';
  const showMemoryUtility = section === 'all' || section === 'settings';
  const showEvalUtility = section === 'all' || section === 'goals';
  const mode = goalPlan?.mode ?? dailyReview?.mode ?? utilityResult?.mode;
  const modeLabel = mode === 'mock' ? t('legacy.mockMode') : mode === 'llm' ? t('legacy.llmMode') : t('legacy.apiMode');
  const heading =
    section === 'notes'
      ? t('legacy.notesTitle')
      : section === 'goals'
        ? t('legacy.goalsTitle')
        : section === 'settings'
          ? t('legacy.settingsTitle')
          : t('legacy.aiWorkspace');
  const hint =
    section === 'notes'
      ? t('legacy.notesHint')
      : section === 'goals'
        ? t('legacy.goalsHint')
        : section === 'settings'
          ? t('legacy.settingsHint')
          : t('legacy.backendTip');

  useEffect(() => {
    let cancelled = false;
    fetchAiSettings()
      .then((loaded) => {
        if (cancelled) return;
        setSettings(loaded);
        onSettingsChange?.(loaded);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [onSettingsChange]);

  useEffect(() => {
    fetchRagDocuments()
      .then(setDocuments)
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    fetchDailyReview(date)
      .then(setDailyReview)
      .catch(() => setDailyReview(null));
  }, [date]);

  useEffect(() => {
    if (!showSettings) return;
    void refreshMemoryStats();
  }, [showSettings]);

  async function refreshMemoryStats() {
    try {
      setMemoryStats(await fetchMemoryCacheStats());
    } catch {
      setMemoryStats(null);
    }
  }

  async function saveMaterial() {
    const content = docContent.trim();
    if (!content) return;
    setLoading('material');
    setDocumentStatus('');
    try {
      const saved = await createRagDocument({
        title: docTitle.trim() || t('legacy.materialTitle'),
        content,
        sourceType: 'paste'
      });
      setDocuments((current) => [saved, ...current.filter((item) => item.id !== saved.id)]);
      setDocContent('');
      setDocTitle('');
      setDocumentStatus(t('legacy.materialSaved'));
    } catch {
      setDocumentStatus(t('legacy.materialSaveError'));
    } finally {
      setLoading('');
    }
  }

  async function uploadMaterial() {
    if (!uploadFile) return;
    setLoading('upload-material');
    setDocumentStatus('');
    try {
      const saved = await uploadRagDocument(uploadFile, docTitle.trim() || undefined);
      setDocuments((current) => [saved, ...current.filter((item) => item.id !== saved.id)]);
      setUploadFile(null);
      setDocTitle('');
      setFileInputKey((current) => current + 1);
      setDocumentStatus(t('legacy.materialUploaded'));
    } catch {
      setDocumentStatus(t('legacy.materialUploadError'));
    } finally {
      setLoading('');
    }
  }

  async function removeMaterial(id: string) {
    try {
      await deleteRagDocument(id);
      setDocuments((current) => current.filter((item) => item.id !== id));
    } catch {
      setDocumentStatus(t('legacy.materialSaveError'));
    }
  }

  async function generateMaterialDraft() {
    const query = materialDraftTopic.trim();
    setDocumentStatus('');
    if (!query) {
      setDocumentStatus(t('legacy.aiMaterialDraftRequired'));
      return;
    }
    if (query.length > 200) {
      setDocumentStatus(t('legacy.aiMaterialDraftTooLong'));
      return;
    }
    setLoading('material-draft');
    try {
      const draft = await createAiMaterialDraft({
        query,
        outputLanguage: language === 'en-US' ? 'en' : 'zh'
      });
      setDocTitle(draft.title);
      setDocContent(draft.content);
      setDocumentStatus(t('legacy.aiMaterialDraftSuccess'));
    } catch {
      setDocumentStatus(t('legacy.aiMaterialDraftError'));
    } finally {
      setLoading('');
    }
  }

  async function runGoalPlan() {
    const trimmedGoal = goal.trim();
    setGoalStatus('');
    if (!trimmedGoal) {
      setGoalStatus(t('legacy.goalRequired'));
      return;
    }
    setLoading('goal');
    setUtilityResult(null);
    setRefinedTasksById({});
    setRefiningTaskIds({});
    setRefineTaskErrors({});
    setGoalTaskRefinementInputs({});
    setRefinedGoalPlanRefsByKey({});
    setDeletingGoalTaskKeys({});
    setBulkRefiningGoalTasks(false);
    try {
      const plan = await createGoalPlan({ goal: trimmedGoal, deadline, dailyHours, materials, preferences, date, outputLanguage: language });
      setGoalPlan(plan);
      setGoalStatus(goalPlanStatusText(plan, t));
    } catch (err) {
      if (err instanceof ApiNetworkError) {
        setGoalStatus(isTimeoutLikeError(err) ? t('legacy.goalPlanTimeout') : t('legacy.goalPlanBackendOffline'));
      } else if (err instanceof ApiHttpError) {
        const detailText = apiDetailToText(err.detail);
        const detailDisplay = detailText ? `: ${detailText}` : '';
        if (err.status === 422) {
          setGoalStatus(`${t('legacy.goalPlanInvalid')}${detailDisplay}`);
        } else {
          setGoalStatus(`${t('legacy.goalPlanFailed')} (${err.status})${detailDisplay}`);
        }
      } else {
        setGoalStatus(t('legacy.goalPlanFailed'));
      }
    } finally {
      setLoading('');
    }
  }

  async function refineGoalTask(taskKey: string, task: GoalPlanTask, options: { skipExisting?: boolean } = {}) {
    if (!goalPlan) return;
    if (options.skipExisting && refinedTasksById[taskKey]) return;
    setRefiningTaskIds((current) => ({ ...current, [taskKey]: true }));
    setRefineTaskErrors((current) => {
      const next = { ...current };
      delete next[taskKey];
      return next;
    });
    let refined: RefinedTask;
    try {
      refined = await refineTask({
        goal: goalPlan.structuredPlan?.goalTitle || goal,
        taskTitle: task.title,
        taskDescription: task.description,
        date: task.dueDate || date,
        availableMinutes: task.estimatedMinutes,
        userConstraints: [preferences].filter(Boolean),
        retrievedSources: goalPlan.sources ?? [],
        outputLanguage: language === 'en-US' ? 'en' : 'zh',
        refinementInstruction: goalTaskRefinementInputs[taskKey] ?? ''
      });
    } catch (err) {
      setRefineTaskErrors((current) => ({
        ...current,
        [taskKey]: `${t('legacy.refineTaskGenerateFailed')}: ${refineTaskErrorText(err, t)}`
      }));
      setRefiningTaskIds((current) => {
        const next = { ...current };
        delete next[taskKey];
        return next;
      });
      return;
    }

    try {
      const targetDate = normalizeGoalTaskDate(task.dueDate, date);
      const savedPlan = await onCreateOrUpdateRefinedPlan({
        date: targetDate,
        title: task.title,
        sourceKey: goalTaskSourceKey(goalPlan, taskKey, task),
        refinedTask: refined
      });
      setRefinedTasksById((current) => ({ ...current, [taskKey]: savedPlan.refinedTask ?? refined }));
      setRefinedGoalPlanRefsByKey((current) => ({ ...current, [taskKey]: { id: savedPlan.id, date: targetDate } }));
    } catch (err) {
      setRefineTaskErrors((current) => ({
        ...current,
        [taskKey]: `${t('legacy.refineTaskSaveFailed')}: ${refineTaskErrorText(err, t)}`
      }));
    } finally {
      setRefiningTaskIds((current) => {
        const next = { ...current };
        delete next[taskKey];
        return next;
      });
    }
  }

  async function refineAllGoalTasks() {
    if (!goalPlan?.structuredPlan || bulkRefiningGoalTasks) return;
    const candidates = goalPlan.structuredPlan.milestones.flatMap((milestone, milestoneIndex) =>
      milestone.tasks.map((task, taskIndex) => ({
        key: `${milestoneIndex}-${taskIndex}-${task.title}`,
        task
      }))
    ).filter((item) => !refinedTasksById[item.key] && !refiningTaskIds[item.key]);
    if (!candidates.length) return;
    setBulkRefiningGoalTasks(true);
    let cursor = 0;
    const worker = async () => {
      while (cursor < candidates.length) {
        const current = candidates[cursor];
        cursor += 1;
        await refineGoalTask(current.key, current.task, { skipExisting: true });
      }
    };
    await Promise.all(Array.from({ length: Math.min(2, candidates.length) }, worker));
    setBulkRefiningGoalTasks(false);
  }

  async function applyGoalPlanToCalendar() {
    if (!goalPlan?.structuredPlan) {
      setGoalStatus(t('legacy.noGoalTasksToWrite'));
      return;
    }
    setLoading('apply-goal-calendar');
    setGoalStatus(t('legacy.writingToCalendar'));
    try {
      const result = await onApplyGoalPlanToCalendar(goalPlan);
      const hasSuccessfulWrites = result.created + result.updated > 0;
      let status = '';
      if (result.failed === 0) {
        status = `${t('legacy.calendarWriteSuccess')}: ${t('legacy.createdCount')} ${result.created}, ${t('legacy.updatedCount')} ${result.updated}, ${t('legacy.failedCount')} ${result.failed}`;
      } else if (hasSuccessfulWrites) {
        status = `${t('legacy.calendarWritePartial')}, ${t('legacy.failedCount')} ${result.failed}`;
      } else {
        status = t('legacy.calendarWriteFailedDetailed');
      }
      if (result.otherDates && status !== t('legacy.calendarWriteFailedDetailed')) {
        status = `${status}。${t('legacy.goalTasksWrittenToOtherDates')}`;
      }
      setGoalStatus(status);
      return;
    } catch {
      setGoalStatus(t('legacy.calendarWriteFailedDetailed'));
    } finally {
      setLoading('');
    }
  }

  async function deleteGoalTaskRefinement(taskKey: string) {
    const planRef = refinedGoalPlanRefsByKey[taskKey];
    if (!planRef) {
      setRefinedTasksById((current) => {
        const next = { ...current };
        delete next[taskKey];
        return next;
      });
      return;
    }
    setDeletingGoalTaskKeys((current) => ({ ...current, [taskKey]: true }));
    setRefineTaskErrors((current) => {
      const next = { ...current };
      delete next[taskKey];
      return next;
    });
    try {
      await onDeletePlanRefinedTask(planRef.id, planRef.date);
      setRefinedTasksById((current) => {
        const next = { ...current };
        delete next[taskKey];
        return next;
      });
      setRefinedGoalPlanRefsByKey((current) => {
        const next = { ...current };
        delete next[taskKey];
        return next;
      });
    } catch (err) {
      setRefineTaskErrors((current) => ({ ...current, [taskKey]: refineTaskErrorText(err, t) }));
    } finally {
      setDeletingGoalTaskKeys((current) => {
        const next = { ...current };
        delete next[taskKey];
        return next;
      });
    }
  }

  async function runDailyReview() {
    setLoading('review');
    setReviewStatus('');
    try {
      setDailyReview(await createDailyReview({ goal, preferences, date, data }));
    } finally {
      setLoading('');
    }
  }

  async function applyReviewReplan() {
    if (!dailyReview?.replanTasks.length) return;
    setLoading('apply-replan');
    try {
      const applied = await applyReplanTasks({ tasks: dailyReview.replanTasks });
      onReplanApplied(applied);
      setReviewStatus(t('legacy.replanApplied'));
    } finally {
      setLoading('');
    }
  }

  async function runUtility(action: 'rag' | 'eval' | 'memory') {
    setLoading(action);
    try {
      if (action === 'rag') setUtilityResult(await askMaterials(payload));
      if (action === 'eval') setUtilityResult(await evaluatePlanner(payload));
      if (action === 'memory') {
        await saveMemory(preferences);
        await refreshMemoryStats();
        setUtilityResult({ summary: t('legacy.saved') });
      }
    } finally {
      setLoading('');
    }
  }

  function validateModelSettings(): { baseUrl: string; model: string } | null {
    const baseUrl = settings.baseUrl.trim();
    if (!baseUrl.startsWith('http://') && !baseUrl.startsWith('https://')) {
      setSettingsStatus(t('legacy.baseUrlInvalid'));
      return null;
    }
    try {
      const parsed = new URL(baseUrl);
      if (settings.provider === 'deepseek' && parsed.hostname === 'api.deepseek.com' && parsed.pathname !== '/') {
        setSettingsStatus(t('legacy.deepseekBaseUrlInvalid'));
        return null;
      }
    } catch {
      setSettingsStatus(t('legacy.baseUrlFormatInvalid'));
      return null;
    }
    const model = settings.model.trim();
    if (!model) {
      setSettingsStatus(t('legacy.modelRequired'));
      return null;
    }
    if (settings.temperature < 0 || settings.temperature > 2) {
      setSettingsStatus(t('legacy.temperatureInvalid'));
      return null;
    }
    if (settings.timeoutSeconds < 5 || settings.timeoutSeconds > 120) {
      setSettingsStatus(t('legacy.timeoutInvalid'));
      return null;
    }
    return { baseUrl, model };
  }

  function buildSettingsPayload(validated: { baseUrl: string; model: string }, options: { clearKey?: boolean } = {}): AiSettingsInput {
    const payload: AiSettingsInput = {
      provider: settings.provider,
      baseUrl: validated.baseUrl,
      model: validated.model,
      temperature: settings.temperature,
      timeoutSeconds: settings.timeoutSeconds
    };
    const trimmedKey = apiKey.trim();
    if (options.clearKey) {
      payload.apiKey = '';
    } else if (trimmedKey) {
      payload.apiKey = trimmedKey;
    }
    return payload;
  }

  function handleSettingsSaveError(err: unknown) {
    if (err instanceof ApiNetworkError) {
      setSettingsStatus(err.message || t('legacy.backendOffline'));
    } else if (err instanceof ApiHttpError) {
      const detailStr = apiDetailToText(err.detail);
      const detailDisplay = detailStr ? `: ${detailStr}` : '';
      if (err.status === 422) {
        setSettingsStatus(detailStr.includes('plain ASCII without spaces') ? t('legacy.invalidKeyFormat') : `${t('legacy.settingsFieldInvalid')}${detailDisplay}`);
      } else if (err.status === 500) {
        setSettingsStatus(`${t('legacy.backendSaveFailed')}${detailDisplay}`);
      } else {
        setSettingsStatus(`${t('legacy.settingsSaveFailed')} (${err.status})${detailDisplay}`);
      }
    } else {
      setSettingsStatus(t('legacy.settingsError'));
    }
  }

  async function saveSettingsToBackend(options: { clearKey?: boolean; showSuccess?: boolean } = {}): Promise<AiSettings | null> {
    const validated = validateModelSettings();
    if (!validated) return null;
    try {
      const saved = await saveAiSettings(buildSettingsPayload(validated, options));
      setSettings(saved);
      onSettingsChange?.(saved);
      setApiKey('');
      if (options.showSuccess) {
        setSettingsStatus(options.clearKey ? t('legacy.keyCleared') : t('legacy.settingsSaved'));
      }
      return saved;
    } catch (err) {
      handleSettingsSaveError(err);
      return null;
    }
  }

  async function saveModelSettings() {
    setSettingsStatus('');
    setSettingsBusy('save');
    try {
      await saveSettingsToBackend({ showSuccess: true });
    } finally {
      setSettingsBusy('');
    }
  }

  async function clearSavedApiKey() {
    setSettingsStatus('');
    setSettingsBusy('clear');
    try {
      await saveSettingsToBackend({ clearKey: true, showSuccess: true });
    } finally {
      setSettingsBusy('');
    }
  }

  async function testModel() {
    setSettingsStatus('');
    setSettingsBusy('test');
    try {
      const saved = await saveSettingsToBackend();
      if (!saved) return;
      const test = await testAiSettings();
      if (test.ok) {
        setSettingsStatus(test.message);
      } else {
        const errorMessages: Record<string, string> = {
          no_key: t('legacy.noApiKey'),
          invalid_key_format: t('legacy.invalidKeyFormat'),
          auth_error: t('legacy.authError'),
          insufficient_balance: t('legacy.insufficientBalance'),
          bad_model: t('legacy.badModel'),
          bad_base_url: t('legacy.badBaseUrl'),
          bad_request: t('legacy.badRequest'),
          timeout: t('legacy.timeoutError'),
          network_error: t('legacy.networkError'),
          server_error: t('legacy.serverError'),
          rate_limited: t('legacy.rateLimited')
        };
        const errorType = test.errorType ?? '';
        setSettingsStatus(errorMessages[errorType] || test.message || t('legacy.modelTestFailed'));
      }
    } catch (err) {
      if (err instanceof ApiNetworkError) {
        setSettingsStatus(err.message || t('legacy.backendConnectionFailed'));
      } else if (err instanceof ApiHttpError) {
        const detailText = apiDetailToText(err.detail);
        setSettingsStatus(`${t('legacy.modelTestRequestFailed')} (${err.status})${detailText ? `: ${detailText}` : ''}`);
      } else {
        setSettingsStatus(t('legacy.backendRequestFailed'));
      }
    } finally {
      setSettingsBusy('');
    }
  }

  async function runMemoryReset(action: MemoryResetAction) {
    const stats = memoryStats ?? await fetchMemoryCacheStats().catch(() => null);
    const confirmText = memoryResetConfirmText(action, stats, t);
    if (!window.confirm(confirmText)) return;

    const calls: Record<MemoryResetAction, () => Promise<MemoryResetResult>> = {
      preferences: clearPreferenceMemory,
      history: clearHistoryMemory,
      runtime: clearRuntimeRuns,
      planning: clearPlanningHistory,
      all: clearAiMemoryCache
    };
    setMemoryResetBusy(action);
    setMemoryResetStatus('');
    try {
      const result = await calls[action]();
      setMemoryResetResult(result);
      setMemoryStats(result.after);
      setMemoryResetStatus(memoryResetStatusText(action, result, t));
    } catch (err) {
      if (err instanceof ApiNetworkError) {
        setMemoryResetStatus(err.message || t('legacy.backendConnectionFailed'));
      } else if (err instanceof ApiHttpError) {
        setMemoryResetStatus(`${t('legacy.memoryResetFailed')} (${err.status})`);
      } else {
        setMemoryResetStatus(t('legacy.memoryResetFailed'));
      }
    } finally {
      setMemoryResetBusy('');
    }
  }

  return (
    <section className="surface ai-panel">
      <div className="section-head">
        <div>
          <span className="eyebrow"><Bot size={14} /> {modeLabel}</span>
          <h2>{heading}</h2>
          <p className="section-hint">{hint}</p>
        </div>
      </div>

      {showSettings && (
        <>
          <ModelSettings
            settings={settings}
            apiKey={apiKey}
            settingsStatus={settingsStatus}
            setSettings={setSettings}
            setApiKey={setApiKey}
            clearSettingsStatus={() => setSettingsStatus('')}
            saveModelSettings={saveModelSettings}
            clearSavedApiKey={clearSavedApiKey}
            testModel={testModel}
            settingsBusy={settingsBusy}
            t={t}
          />
          {section === 'settings' && (
            <>
              <PreferenceCard
                preferences={preferences}
                onPreferencesChange={onPreferencesChange}
                onSave={() => runUtility('memory')}
                saving={loading === 'memory'}
                t={t}
              />
              <MemoryDataManagement
                stats={memoryStats}
                result={memoryResetResult}
                status={memoryResetStatus}
                busy={memoryResetBusy}
                onRefresh={refreshMemoryStats}
                onReset={runMemoryReset}
                t={t}
              />
            </>
          )}
        </>
      )}

      {showMaterials && (
        <MaterialLibrary
          documents={documents}
          docTitle={docTitle}
          docContent={docContent}
          uploadFile={uploadFile}
          materialDraftTopic={materialDraftTopic}
          fileInputKey={fileInputKey}
          documentStatus={documentStatus}
          loading={loading}
          setDocTitle={setDocTitle}
          setDocContent={setDocContent}
          setMaterialDraftTopic={setMaterialDraftTopic}
          setUploadFile={setUploadFile}
          generateMaterialDraft={generateMaterialDraft}
          saveMaterial={saveMaterial}
          uploadMaterial={uploadMaterial}
          removeMaterial={removeMaterial}
          t={t}
        />
      )}

      {(showMaterials || showGoals) && (
        <MaterialQuestion materials={materials} setMaterials={setMaterials} runUtility={runUtility} loading={loading} t={t} />
      )}

      {showGoals && (
        <GoalPlanner
          goal={goal}
          deadline={deadline}
          dailyHours={dailyHours}
          preferences={preferences}
          materials={materials}
          loading={loading}
          goalStatus={goalStatus}
          goalPlan={goalPlan}
          refinedTasksById={refinedTasksById}
          refiningTaskIds={refiningTaskIds}
          refineTaskErrors={refineTaskErrors}
          goalTaskRefinementInputs={goalTaskRefinementInputs}
          setGoalTaskRefinementInput={(taskKey, value) => setGoalTaskRefinementInputs((current) => ({ ...current, [taskKey]: value }))}
          deletingGoalTaskKeys={deletingGoalTaskKeys}
          bulkRefiningGoalTasks={bulkRefiningGoalTasks}
          setGoal={setGoal}
          setDeadline={setDeadline}
          setDailyHours={setDailyHours}
          onPreferencesChange={onPreferencesChange}
          setMaterials={setMaterials}
          runGoalPlan={runGoalPlan}
          onRefineTask={refineGoalTask}
          onRefineAllTasks={refineAllGoalTasks}
          onDeleteRefinement={deleteGoalTaskRefinement}
          onApplyGoalPlanToCalendar={applyGoalPlanToCalendar}
          t={t}
        />
      )}

      {showReview && (
        <DailyReview
          dailyReview={dailyReview}
          reviewStatus={reviewStatus}
          loading={loading}
          runDailyReview={runDailyReview}
          applyReviewReplan={applyReviewReplan}
          t={t}
        />
      )}

      {(showNotesUtility || showMemoryUtility || showEvalUtility) && (
        <div className="command-row">
          {showNotesUtility && <button onClick={() => runUtility('rag')}><FileSearch size={16} />{t('legacy.rag')}</button>}
          {showMemoryUtility && <button onClick={() => runUtility('memory')}><Save size={16} />{t('legacy.saveMemory')}</button>}
          {showEvalUtility && <button onClick={() => runUtility('eval')}><DatabaseZap size={16} />{t('legacy.evaluate')}</button>}
        </div>
      )}
      {utilityResult && <ResultView result={utilityResult} t={t} />}
    </section>
  );
}

function goalPlanStatusText(plan: GoalPlanResponse, t: (key: string) => string): string {
  if (plan.mode === 'llm') return t('legacy.goalPlanGenerated');
  if (plan.fallbackReason === 'mock_provider') return t('legacy.goalPlanFallbackMockProvider');
  if (plan.fallbackReason === 'missing_api_key') return t('legacy.goalPlanFallbackMissingKey');
  if (plan.fallbackReason === 'llm_error') {
    return `${t('legacy.goalPlanFallbackLlmError')}${t('legacy.goalPlanReason')}: ${goalPlanErrorReason(plan.errorType, t)}`;
  }
  return t('legacy.goalPlanFallbackGenerated');
}

function goalPlanErrorReason(errorType: string | undefined, t: (key: string) => string): string {
  const keyByType: Record<string, string> = {
    auth_error: 'legacy.goalPlanErrorAuth',
    invalid_key_format: 'legacy.goalPlanErrorInvalidKeyFormat',
    bad_model: 'legacy.goalPlanErrorBadModel',
    bad_base_url: 'legacy.goalPlanErrorBadBaseUrl',
    network_error: 'legacy.goalPlanErrorNetwork',
    timeout: 'legacy.goalPlanErrorTimeout',
    insufficient_balance: 'legacy.goalPlanErrorBalance',
    invalid_model_output: 'legacy.goalPlanErrorInvalidOutput',
    model_output_truncated: 'legacy.goalPlanErrorModelOutputTruncated',
    empty_content: 'legacy.goalPlanErrorEmptyContent',
    unknown: 'legacy.goalPlanErrorUnknown'
  };
  return t(keyByType[errorType ?? ''] ?? 'legacy.goalPlanErrorUnknown');
}

function MaterialLibrary(props: {
  documents: RagDocument[];
  docTitle: string;
  docContent: string;
  materialDraftTopic: string;
  uploadFile: File | null;
  fileInputKey: number;
  documentStatus: string;
  loading: string;
  setDocTitle: (value: string) => void;
  setDocContent: (value: string) => void;
  setMaterialDraftTopic: (value: string) => void;
  setUploadFile: (value: File | null) => void;
  generateMaterialDraft: () => void;
  saveMaterial: () => void;
  uploadMaterial: () => void;
  removeMaterial: (id: string) => void;
  t: (key: string) => string;
}) {
  const {
    documents,
    docTitle,
    docContent,
    materialDraftTopic,
    uploadFile,
    fileInputKey,
    documentStatus,
    loading,
    setDocTitle,
    setDocContent,
    setMaterialDraftTopic,
    setUploadFile,
    generateMaterialDraft,
    saveMaterial,
    uploadMaterial,
    removeMaterial,
    t
  } = props;
  const fileInputId = `material-file-${fileInputKey}`;

  return (
    <div className="workflow-card">
      <div className="workflow-head">
        <div>
          <span>{t('legacy.materialLibrary')}</span>
          <strong>{t('legacy.materialLibraryHint')}</strong>
        </div>
        <div className="workflow-buttons">
          <button onClick={saveMaterial} disabled={loading === 'material' || !docContent.trim()}>
            <Library size={16} />{t('legacy.saveMaterial')}
          </button>
          <button onClick={uploadMaterial} disabled={loading === 'upload-material' || !uploadFile}>
            <UploadCloud size={16} />{t('legacy.uploadMaterial')}
          </button>
        </div>
      </div>
      <div className="ai-grid material-grid">
        <label>
          <span>{t('legacy.materialTitle')}</span>
          <input value={docTitle} onChange={(event) => setDocTitle(event.target.value)} placeholder={t('legacy.materialTitlePlaceholder')} />
        </label>
        <div className="file-field">
          <span>{t('legacy.materialFile')}</span>
          <div className="file-picker">
            <input
              id={fileInputId}
              className="file-input"
              key={fileInputKey}
              type="file"
              accept=".txt,.md,text/plain,text/markdown"
              onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)}
            />
            <label className="file-picker-button" htmlFor={fileInputId}>
              <UploadCloud size={15} />
              {t('legacy.chooseFile')}
            </label>
            <span className="file-name">{uploadFile?.name ?? t('legacy.noFileSelected')}</span>
          </div>
        </div>
        <label className="wide">
          <span>{t('legacy.materialContent')}</span>
          <textarea value={docContent} onChange={(event) => setDocContent(event.target.value)} placeholder={t('legacy.materialContentPlaceholder')} />
        </label>
      </div>
      <div className="ai-material-draft">
        <div>
          <span>{t('legacy.aiMaterialDraft')}</span>
          <input
            value={materialDraftTopic}
            onChange={(event) => setMaterialDraftTopic(event.target.value)}
            placeholder={t('legacy.aiMaterialDraftPlaceholder')}
          />
        </div>
        <button onClick={generateMaterialDraft} disabled={loading === 'material-draft'}>
          <Sparkles size={16} />
          {loading === 'material-draft' ? t('legacy.aiMaterialDraftLoading') : t('legacy.generateMaterialDraft')}
        </button>
      </div>
      {documentStatus && <p className="inline-status">{documentStatus}</p>}
      <div className="material-list">
        <span className="eyebrow">{t('legacy.recentMaterials')}</span>
        {!documents.length && <div className="empty-state">{t('legacy.noMaterials')}</div>}
        {documents.slice(0, 5).map((document) => (
          <article className="material-item" key={document.id}>
            <div>
              <strong>{document.title}</strong>
              <p>{document.summary}</p>
              <small>{document.chunks} {t('legacy.chunks')} / {document.sourceType} {t('legacy.sourceType')}</small>
            </div>
            <button className="icon-button danger" onClick={() => removeMaterial(document.id)} aria-label={t('common.delete')}>
              <Trash2 size={15} />
            </button>
          </article>
        ))}
      </div>
    </div>
  );
}

function MaterialQuestion(props: {
  materials: string;
  setMaterials: (value: string) => void;
  runUtility: (action: 'rag' | 'eval' | 'memory') => void;
  loading: string;
  t: (key: string) => string;
}) {
  const { materials, setMaterials, runUtility, loading, t } = props;
  return (
    <div className="workflow-card">
      <div className="workflow-head">
        <div>
          <span>{t('legacy.materials')}</span>
          <strong>{t('legacy.notesHint')}</strong>
        </div>
        <button onClick={() => runUtility('rag')} disabled={loading === 'rag' || !materials.trim()}>
          <FileSearch size={16} />{t('legacy.askMaterials')}
        </button>
      </div>
      <label className="wide field-stack">
        <span>{t('legacy.materials')}</span>
        <textarea value={materials} onChange={(event) => setMaterials(event.target.value)} placeholder={t('legacy.materialsPlaceholder')} />
      </label>
    </div>
  );
}

function GoalPlanner(props: {
  goal: string;
  deadline: string;
  dailyHours: number;
  preferences: string;
  materials: string;
  loading: string;
  goalStatus: string;
  goalPlan: GoalPlanResponse | null;
  refinedTasksById: Record<string, RefinedTask>;
  refiningTaskIds: Record<string, boolean>;
  refineTaskErrors: Record<string, string>;
  goalTaskRefinementInputs: Record<string, string>;
  setGoalTaskRefinementInput: (taskKey: string, value: string) => void;
  deletingGoalTaskKeys: Record<string, boolean>;
  bulkRefiningGoalTasks: boolean;
  setGoal: (value: string) => void;
  setDeadline: (value: string) => void;
  setDailyHours: (value: number) => void;
  onPreferencesChange: (value: string) => void;
  setMaterials: (value: string) => void;
  runGoalPlan: () => void;
  onRefineTask: (taskKey: string, task: GoalPlanTask) => void;
  onRefineAllTasks: () => void;
  onDeleteRefinement: (taskKey: string) => void;
  onApplyGoalPlanToCalendar: () => void;
  t: (key: string) => string;
}) {
  const {
    goal,
    deadline,
    dailyHours,
    preferences,
    materials,
    loading,
    goalStatus,
    goalPlan,
    refinedTasksById,
    refiningTaskIds,
    refineTaskErrors,
    goalTaskRefinementInputs,
    setGoalTaskRefinementInput,
    deletingGoalTaskKeys,
    bulkRefiningGoalTasks,
    setGoal,
    setDeadline,
    setDailyHours,
    onPreferencesChange,
    setMaterials,
    runGoalPlan,
    onRefineTask,
    onRefineAllTasks,
    onDeleteRefinement,
    onApplyGoalPlanToCalendar,
    t
  } = props;

  return (
    <div className="workflow-card">
      <div className="workflow-head">
        <div>
          <span>{t('legacy.goalPlanning')}</span>
          <strong>{t('legacy.goalPlanningHint')}</strong>
        </div>
        <button onClick={runGoalPlan} disabled={loading === 'goal'}><Sparkles size={16} />{t('legacy.generateGoalPlan')}</button>
      </div>
      <div className="ai-grid">
        <label>
          <span>{t('legacy.goal')}</span>
          <input value={goal} onChange={(event) => setGoal(event.target.value)} placeholder={t('legacy.goalPlaceholder')} />
        </label>
        <label>
          <span>{t('legacy.deadline')}</span>
          <input type="date" value={deadline} onChange={(event) => setDeadline(event.target.value)} />
        </label>
        <label>
          <span>{t('legacy.dailyHours')}</span>
          <input type="number" min={1} max={12} value={dailyHours} onChange={(event) => setDailyHours(Number(event.target.value))} />
        </label>
        <label className="wide">
          <span>{t('legacy.preference')}</span>
          <input value={preferences} onChange={(event) => onPreferencesChange(event.target.value)} placeholder={t('legacy.preferencePlaceholder')} />
        </label>
        <label className="wide">
          <span>{t('legacy.materials')}</span>
          <textarea value={materials} onChange={(event) => setMaterials(event.target.value)} placeholder={t('legacy.materialsPlaceholder')} />
        </label>
      </div>
      {loading === 'goal' && <div className="empty-state">{t('legacy.loading')}</div>}
      {goalStatus && <p className={`inline-status ${loading === 'apply-goal-calendar' ? 'calendar-write-status' : ''}`}>{goalStatus}</p>}
      {goalPlan && (
        <GoalPlanView
          plan={goalPlan}
          refinedTasksById={refinedTasksById}
          refiningTaskIds={refiningTaskIds}
          refineTaskErrors={refineTaskErrors}
          goalTaskRefinementInputs={goalTaskRefinementInputs}
          setGoalTaskRefinementInput={setGoalTaskRefinementInput}
          deletingGoalTaskKeys={deletingGoalTaskKeys}
          bulkRefiningGoalTasks={bulkRefiningGoalTasks}
          onRefineTask={onRefineTask}
          onRefineAllTasks={onRefineAllTasks}
          onDeleteRefinement={onDeleteRefinement}
          t={t}
        />
      )}
      <button
        className={`apply-button ${loading === 'apply-goal-calendar' ? 'is-writing' : ''}`}
        onClick={onApplyGoalPlanToCalendar}
        disabled={!goalPlan?.structuredPlan || loading === 'apply-goal-calendar'}
      >
        {loading === 'apply-goal-calendar'
          ? t('legacy.writingToCalendar')
          : goalPlan?.structuredPlan ? t('legacy.writeToCalendar') : t('legacy.noGoalTasksToWrite')}
      </button>
    </div>
  );
}

function DailyReview(props: {
  dailyReview: DailyReviewResponse | null;
  reviewStatus: string;
  loading: string;
  runDailyReview: () => void;
  applyReviewReplan: () => void;
  t: (key: string) => string;
}) {
  const { dailyReview, reviewStatus, loading, runDailyReview, applyReviewReplan, t } = props;
  return (
    <div className="workflow-card">
      <div className="workflow-head">
        <div>
          <span>{t('legacy.dailyReview')}</span>
          <strong>{t('legacy.dailyReviewHint')}</strong>
        </div>
        <button onClick={runDailyReview} disabled={loading === 'review'}><ClipboardCheck size={16} />{t('legacy.runDailyReview')}</button>
      </div>
      {loading === 'review' && <div className="empty-state">{t('legacy.loading')}</div>}
      {!dailyReview && loading !== 'review' && <div className="empty-state">{t('legacy.reviewEmpty')}</div>}
      {dailyReview && <DailyReviewView review={dailyReview} t={t} />}
      <button className="apply-button" onClick={applyReviewReplan} disabled={!dailyReview?.replanTasks.length || loading === 'apply-replan'}>
        {dailyReview?.replanTasks.length ? t('legacy.applyReplan') : t('legacy.noReplanTasks')}
      </button>
      {reviewStatus && <p className="inline-status">{reviewStatus}</p>}
    </div>
  );
}

function PreferenceCard(props: {
  preferences: string;
  saving: boolean;
  onPreferencesChange: (value: string) => void;
  onSave: () => void;
  t: (key: string) => string;
}) {
  const { preferences, saving, onPreferencesChange, onSave, t } = props;
  return (
    <div className="workflow-card">
      <div className="workflow-head">
        <div>
          <span>{t('legacy.preference')}</span>
          <strong>{t('legacy.savePreferenceHint')}</strong>
        </div>
        <button onClick={onSave} disabled={saving}><Save size={16} />{t('legacy.saveMemory')}</button>
      </div>
      <label className="wide field-stack">
        <span>{t('legacy.preference')}</span>
        <textarea value={preferences} onChange={(event) => onPreferencesChange(event.target.value)} placeholder={t('legacy.preferencePlaceholder')} />
      </label>
    </div>
  );
}

function MemoryDataManagement(props: {
  stats: MemoryCacheStats | null;
  result: MemoryResetResult | null;
  status: string;
  busy: MemoryResetAction | '';
  onRefresh: () => void;
  onReset: (action: MemoryResetAction) => void;
  t: (key: string) => string;
}) {
  const { stats, result, status, busy, onRefresh, onReset, t } = props;
  const rows: Array<[string, number | string]> = [
    [t('legacy.memoryStatPreferences'), stats?.preferenceMemory ?? '-'],
    [t('legacy.memoryStatHistory'), stats?.historySummaries ?? '-'],
    [t('legacy.memoryStatAgentRuns'), stats?.agentRuns ?? '-'],
    [t('legacy.memoryStatAgentEvents'), stats?.agentEvents ?? '-'],
    [t('legacy.memoryStatPlanningGoals'), stats?.planningGoals ?? '-'],
    [t('legacy.memoryStatPlans'), stats?.plans ?? '-']
  ];
  const actions: Array<{ action: MemoryResetAction; label: string; danger?: boolean }> = [
    { action: 'preferences', label: t('legacy.clearPreferenceMemory') },
    { action: 'history', label: t('legacy.clearHistoryMemory') },
    { action: 'runtime', label: t('legacy.clearRuntimeRuns') },
    { action: 'planning', label: t('legacy.clearPlanningHistory') },
    { action: 'all', label: t('legacy.clearAiMemoryCache'), danger: true }
  ];

  return (
    <div className="workflow-card memory-management">
      <div className="workflow-head">
        <div>
          <span>{t('legacy.memoryDataManagement')}</span>
          <strong>{t('legacy.memoryDataManagementHint')}</strong>
        </div>
        <button onClick={onRefresh} disabled={Boolean(busy)}><RotateCcw size={16} />{t('legacy.refreshStats')}</button>
      </div>
      <div className="memory-stats-grid">
        {rows.map(([label, value]) => (
          <div className="memory-stat" key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </div>
      <p className="field-hint">{t('legacy.memoryDataPreservedHint')}</p>
      <div className="settings-actions memory-actions">
        {actions.map((item) => (
          <button
            key={item.action}
            className={item.danger ? 'danger-action' : undefined}
            onClick={() => onReset(item.action)}
            disabled={Boolean(busy)}
          >
            <Trash2 size={16} />
            {busy === item.action ? t('legacy.clearingMemory') : item.label}
          </button>
        ))}
      </div>
      {status && <p className="inline-status">{status}</p>}
      {result && (
        <div className="memory-reset-result">
          <span>{t('legacy.memoryResetDeleted')}</span>
          <code>{formatMemoryResetCounts(result)}</code>
          <span>{t('legacy.memoryResetPlansPreserved')}: {result.before.plans} → {result.after.plans}</span>
        </div>
      )}
    </div>
  );
}

function memoryResetConfirmText(action: MemoryResetAction, stats: MemoryCacheStats | null, t: (key: string) => string): string {
  const countLines = stats
    ? [
        `${t('legacy.memoryStatPreferences')}: ${stats.preferenceMemory}`,
        `${t('legacy.memoryStatHistory')}: ${stats.historySummaries}`,
        `${t('legacy.memoryStatAgentRuns')}: ${stats.agentRuns}`,
        `${t('legacy.memoryStatAgentEvents')}: ${stats.agentEvents}`,
        `${t('legacy.memoryStatPlanningGoals')}: ${stats.planningGoals}`,
        `${t('legacy.memoryStatPlans')}: ${stats.plans}`
      ].join('\n')
    : t('legacy.memoryStatsUnavailable');
  const messageByAction: Record<MemoryResetAction, string> = {
    preferences: t('legacy.confirmClearPreferenceMemory'),
    history: t('legacy.confirmClearHistoryMemory'),
    runtime: t('legacy.confirmClearRuntimeRuns'),
    planning: t('legacy.confirmClearPlanningHistory'),
    all: t('legacy.confirmClearAiMemoryCache')
  };
  return `${messageByAction[action]}\n\n${countLines}`;
}

function memoryResetStatusText(action: MemoryResetAction, result: MemoryResetResult, t: (key: string) => string): string {
  const labelByAction: Record<MemoryResetAction, string> = {
    preferences: t('legacy.clearPreferenceMemory'),
    history: t('legacy.clearHistoryMemory'),
    runtime: t('legacy.clearRuntimeRuns'),
    planning: t('legacy.clearPlanningHistory'),
    all: t('legacy.clearAiMemoryCache')
  };
  return `${labelByAction[action]} · ${t('legacy.memoryResetSuccess')} · ${t('legacy.memoryResetPlansPreserved')}: ${result.before.plans} → ${result.after.plans}`;
}

function formatMemoryResetCounts(result: MemoryResetResult): string {
  if (result.steps) {
    return Object.entries(result.steps)
      .map(([step, values]) => `${step}: ${Object.entries(values).map(([key, value]) => `${key}=${value}`).join(', ')}`)
      .join(' | ');
  }
  return Object.entries(result.deleted)
    .map(([key, value]) => `${key}=${value}`)
    .join(', ');
}

function ModelSettings(props: {
  settings: AiSettings;
  apiKey: string;
  settingsStatus: string;
  setSettings: (updater: (settings: AiSettings) => AiSettings) => void;
  setApiKey: (value: string) => void;
  clearSettingsStatus: () => void;
  saveModelSettings: () => void;
  clearSavedApiKey: () => void;
  testModel: () => void;
  settingsBusy: 'save' | 'test' | 'clear' | '';
  t: (key: string) => string;
}) {
  const { settings, apiKey, settingsStatus, setSettings, setApiKey, clearSettingsStatus, saveModelSettings, clearSavedApiKey, testModel, settingsBusy, t } = props;
  const [modelMenuOpen, setModelMenuOpen] = useState(false);
  const hasConfiguredKey = settings.provider !== 'mock' && settings.hasApiKey;
  const recommendedModels = ['deepseek-v4-flash', 'deepseek-v4-pro'];
  const updateSettings = (updater: (settings: AiSettings) => AiSettings) => {
    clearSettingsStatus();
    setSettings(updater);
  };
  const updateApiKey = (value: string) => {
    clearSettingsStatus();
    setApiKey(value);
  };

  return (
    <div className="model-settings">
      <div className="settings-title">
        <span><Settings size={15} />{t('legacy.aiSettings')}</span>
        <strong>{hasConfiguredKey ? t('legacy.hasKey') : t('legacy.noKey')}</strong>
      </div>
      <div className="settings-grid">
        <label>
          <span>{t('legacy.provider')}</span>
          <select value={settings.provider} onChange={(event) => updateSettings((current) => ({ ...current, provider: event.target.value as AiSettings['provider'] }))}>
            <option value="deepseek">DeepSeek</option>
            <option value="openai">OpenAI</option>
            <option value="custom">Custom</option>
            <option value="mock">Mock</option>
          </select>
        </label>
        <label>
          <span>{t('legacy.baseUrl')}</span>
          <input value={settings.baseUrl} onChange={(event) => updateSettings((current) => ({ ...current, baseUrl: event.target.value }))} />
        </label>
        <label>
          <span>{t('legacy.model')}</span>
          <div
            className="model-picker"
            onBlur={(event) => {
              if (!event.currentTarget.contains(event.relatedTarget)) {
                setModelMenuOpen(false);
              }
            }}
          >
            <input
              value={settings.model}
              onChange={(event) => updateSettings((current) => ({ ...current, model: event.target.value }))}
              placeholder="deepseek-v4-flash"
            />
            <button
              type="button"
              className="model-picker-toggle"
              aria-label={t('legacy.recommendedModel')}
              aria-expanded={modelMenuOpen}
              onClick={() => setModelMenuOpen((open) => !open)}
            />
            {modelMenuOpen && (
              <div className="model-picker-menu" role="listbox">
                {recommendedModels.map((model) => (
                  <button
                    key={model}
                    type="button"
                    role="option"
                    aria-selected={settings.model === model}
                    onClick={() => {
                      updateSettings((current) => ({ ...current, model }));
                      setModelMenuOpen(false);
                    }}
                  >
                    {model}
                  </button>
                ))}
              </div>
            )}
          </div>
        </label>
        <label>
          <span><KeyRound size={13} />{t('legacy.apiKey')}</span>
          <input type="password" value={apiKey} onChange={(event) => updateApiKey(event.target.value)} placeholder={t('legacy.apiKeyPlaceholder')} />
        </label>
        <label>
          <span>{t('legacy.temperature')}</span>
          <input type="number" min={0} max={2} step={0.1} value={settings.temperature} onChange={(event) => updateSettings((current) => ({ ...current, temperature: Number(event.target.value) }))} />
        </label>
        <label>
          <span>{t('legacy.timeout')}</span>
          <input type="number" min={5} max={120} value={settings.timeoutSeconds} onChange={(event) => updateSettings((current) => ({ ...current, timeoutSeconds: Number(event.target.value) }))} />
        </label>
      </div>
      <div className="settings-actions">
        <button onClick={saveModelSettings} disabled={Boolean(settingsBusy)}><Save size={16} />{settingsBusy === 'save' ? t('legacy.savingSettings') : t('legacy.saveSettings')}</button>
        <button onClick={testModel} disabled={Boolean(settingsBusy)}><PlugZap size={16} />{settingsBusy === 'test' ? t('legacy.testingModel') : t('legacy.testModel')}</button>
        <button onClick={clearSavedApiKey} disabled={Boolean(settingsBusy) || !hasConfiguredKey}><Trash2 size={16} />{settingsBusy === 'clear' ? t('legacy.clearingKey') : t('legacy.clearKey')}</button>
        {settingsStatus && <span>{settingsStatus}</span>}
      </div>
    </div>
  );
}

function GoalPlanView(props: {
  plan: GoalPlanResponse;
  refinedTasksById: Record<string, RefinedTask>;
  refiningTaskIds: Record<string, boolean>;
  refineTaskErrors: Record<string, string>;
  goalTaskRefinementInputs: Record<string, string>;
  setGoalTaskRefinementInput: (taskKey: string, value: string) => void;
  deletingGoalTaskKeys: Record<string, boolean>;
  bulkRefiningGoalTasks: boolean;
  onRefineTask: (taskKey: string, task: GoalPlanTask) => void;
  onRefineAllTasks: () => void;
  onDeleteRefinement: (taskKey: string) => void;
  t: (key: string) => string;
}) {
  const {
    plan,
    refinedTasksById,
    refiningTaskIds,
    refineTaskErrors,
    goalTaskRefinementInputs,
    setGoalTaskRefinementInput,
    deletingGoalTaskKeys,
    bulkRefiningGoalTasks,
    onRefineTask,
    onRefineAllTasks,
    onDeleteRefinement,
    t
  } = props;
  return (
    <div className="result-view">
      <h3>{plan.summary}</h3>
      {plan.provider && <p><strong>{plan.provider}</strong> / {plan.model}</p>}
      {plan.structuredPlan ? (
        <StructuredGoalPlanView
          plan={plan.structuredPlan}
          refinedTasksById={refinedTasksById}
          refiningTaskIds={refiningTaskIds}
          refineTaskErrors={refineTaskErrors}
          goalTaskRefinementInputs={goalTaskRefinementInputs}
          setGoalTaskRefinementInput={setGoalTaskRefinementInput}
          deletingGoalTaskKeys={deletingGoalTaskKeys}
          bulkRefiningGoalTasks={bulkRefiningGoalTasks}
          onRefineTask={onRefineTask}
          onRefineAllTasks={onRefineAllTasks}
          onDeleteRefinement={onDeleteRefinement}
          t={t}
        />
      ) : null}
      {!plan.structuredPlan && plan.phases.map((phase) => <p key={phase.title}><strong>{phase.title}</strong>: {phase.detail}</p>)}
      <SourceList sources={plan.sources ?? []} title={t('legacy.referencedSources')} t={t} />
      <h3>{t('legacy.todayTasks')}</h3>
      {plan.tasks.map((task) => <TaskPreview key={`${task.time}-${task.title}`} time={task.time} title={task.title} reason={task.reason} />)}
    </div>
  );
}

function StructuredGoalPlanView(props: {
  plan: StructuredGoalPlan;
  refinedTasksById: Record<string, RefinedTask>;
  refiningTaskIds: Record<string, boolean>;
  refineTaskErrors: Record<string, string>;
  goalTaskRefinementInputs: Record<string, string>;
  setGoalTaskRefinementInput: (taskKey: string, value: string) => void;
  deletingGoalTaskKeys: Record<string, boolean>;
  bulkRefiningGoalTasks: boolean;
  onRefineTask: (taskKey: string, task: GoalPlanTask) => void;
  onRefineAllTasks: () => void;
  onDeleteRefinement: (taskKey: string) => void;
  t: (key: string) => string;
}) {
  const {
    plan,
    refinedTasksById,
    refiningTaskIds,
    refineTaskErrors,
    goalTaskRefinementInputs,
    setGoalTaskRefinementInput,
    deletingGoalTaskKeys,
    bulkRefiningGoalTasks,
    onRefineTask,
    onRefineAllTasks,
    onDeleteRefinement,
    t
  } = props;
  const hasRefinableTasks = plan.milestones.some((milestone, milestoneIndex) =>
    milestone.tasks.some((task, taskIndex) => {
      const taskKey = `${milestoneIndex}-${taskIndex}-${task.title}`;
      return !refinedTasksById[taskKey] && !refiningTaskIds[taskKey];
    })
  );
  return (
    <div className="structured-plan">
      <div className="structured-plan-head">
        <div>
          <span>{t('legacy.structuredGoal')}</span>
          <strong>{plan.goalTitle}</strong>
        </div>
        <div className="structured-plan-actions">
          <em>{plan.durationDays} {t('legacy.days')}</em>
          <button type="button" onClick={onRefineAllTasks} disabled={!hasRefinableTasks || bulkRefiningGoalTasks}>
            <Sparkles size={14} />
            {bulkRefiningGoalTasks ? t('legacy.refiningAllTasks') : t('legacy.refineAllTasks')}
          </button>
        </div>
      </div>
      <p>{plan.goalDescription}</p>
      <div className="milestone-list">
        {plan.milestones.map((milestone, index) => (
          <article className="milestone-card" key={`${milestone.title}-${index}`}>
            <div className="milestone-title">
              <span>{index + 1}</span>
              <div>
                <strong>{milestone.title}</strong>
                <p>{milestone.description}</p>
              </div>
            </div>
            <div className="milestone-tasks">
              {milestone.tasks.map((task, taskIndex) => {
                const taskKey = `${index}-${taskIndex}-${task.title}`;
                const refined = refinedTasksById[taskKey];
                const isRefining = Boolean(refiningTaskIds[taskKey]);
                const error = refineTaskErrors[taskKey];
                return (
                  <div className="milestone-task" key={taskKey}>
                    <div className="milestone-task-main">
                      <div>
                        <strong>{task.title}</strong>
                        <p>{task.description}</p>
                      </div>
                      <span>{task.estimatedMinutes}m</span>
                      <em className={`priority ${task.priority}`}>{t(`legacy.priority${capitalize(task.priority)}`)}</em>
                      {task.dueDate ? <time>{task.dueDate}</time> : null}
                    </div>
                    <div className="plan-refinement-box">
                      <label>
                        <span>{t('legacy.refinementInstruction')}</span>
                        <div className="refinement-input-wrap">
                          <textarea
                            value={goalTaskRefinementInputs[taskKey] ?? ''}
                            onChange={(event) => setGoalTaskRefinementInput(taskKey, event.target.value)}
                            placeholder={t('legacy.goalRefinementInstructionPlaceholder')}
                          />
                          {(goalTaskRefinementInputs[taskKey] ?? '').trim() && (
                            <button
                              type="button"
                              className="refinement-clear-button"
                              onClick={() => setGoalTaskRefinementInput(taskKey, '')}
                              aria-label={t('legacy.clearRefinementInstruction')}
                              title={t('legacy.clearRefinementInstruction')}
                            >
                              <X size={14} />
                            </button>
                          )}
                        </div>
                      </label>
                      <button
                        type="button"
                        onClick={() => onRefineTask(taskKey, task)}
                        disabled={isRefining}
                      >
                        <Sparkles size={14} />
                        {isRefining
                          ? t('legacy.refiningTask')
                          : refined
                            ? t('legacy.refineAgain')
                            : t('legacy.refineTask')}
                      </button>
                    </div>
                    {error && <p className="inline-status error">{error}</p>}
                    {refined && (
                      <RefinedTaskPreview
                        refinedTask={refined}
                        deleting={Boolean(deletingGoalTaskKeys[taskKey])}
                        onDelete={() => onDeleteRefinement(taskKey)}
                        t={t}
                      />
                    )}
                  </div>
                );
              })}
            </div>
          </article>
        ))}
      </div>
      <div className="review-plan">
        <strong>{t('legacy.reviewPlan')} / {plan.reviewPlan.frequency === 'daily' ? t('legacy.daily') : t('legacy.weekly')}</strong>
        <ul>
          {plan.reviewPlan.questions.map((question) => <li key={question}>{question}</li>)}
        </ul>
      </div>
    </div>
  );
}

function capitalize(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function DailyReviewView({ review, t }: { review: DailyReviewResponse; t: (key: string) => string }) {
  return (
    <div className="result-view">
      <h3>{review.summary}</h3>
      <p>{t('legacy.completionRatio')}: {review.doneCount}/{review.totalCount}</p>
      <ul>{review.suggestions.map((item) => <li key={item}>{item}</li>)}</ul>
      <h3><RotateCcw size={15} /> {t('legacy.replanPreview')} / {review.targetDate}</h3>
      {review.replanTasks.map((task) => (
        <TaskPreview key={`${task.targetDate}-${task.time}-${task.title}`} time={task.time} title={task.title} reason={task.reason} />
      ))}
    </div>
  );
}

function TaskPreview({ time, title, reason }: PlannerTask) {
  return (
    <div className="ai-task">
      <time>{time}</time>
      <div><strong>{title}</strong><p>{reason}</p></div>
    </div>
  );
}

function SourceList({ sources, title, t }: { sources: RagSource[]; title: string; t: (key: string) => string }) {
  if (!sources.length) return null;
  return (
    <div className="source-list">
      <h3>{title}</h3>
      {sources.map((source) => (
        <article className="source-item" key={`${source.documentId}-${source.chunkIndex}-${source.title}`}>
          <div className="source-meta">
            <strong>{source.title}</strong>
            <span>{t('legacy.relevance')}: {source.score.toFixed(3)}</span>
          </div>
          <p>{source.chunk}</p>
        </article>
      ))}
    </div>
  );
}

function ResultView({ result, t }: { result: PlannerResponse; t: (key: string) => string }) {
  const heading = result.score ? `${t('legacy.score')}: ${result.score}/5` : result.summary ?? result.answer ?? t('legacy.aiWorkspace');
  return (
    <div className="result-view utility-result">
      <h3>{heading}</h3>
      {result.provider && <p><strong>{result.provider}</strong> / {result.model}</p>}
      {result.suggestions && <ul>{result.suggestions.map((item) => <li key={item}>{item}</li>)}</ul>}
      {result.answer && result.answer !== heading && <p>{result.answer}</p>}
      <SourceList sources={result.sources ?? []} title={t('legacy.sources')} t={t} />
      {result.keywords && <p>{result.keywords.join(' / ')}</p>}
      {result.results && <ul>{result.results.map((item) => <li key={item.case}><strong>{item.score}/5</strong> {item.case} - {item.reason}</li>)}</ul>}
    </div>
  );
}

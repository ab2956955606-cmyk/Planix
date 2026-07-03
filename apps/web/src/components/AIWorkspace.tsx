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
  UploadCloud
} from 'lucide-react';
import type {
  AiSettings,
  AiSettingsInput,
  AppliedPlan,
  AppData,
  DailyReviewResponse,
  GoalPlanResponse,
  PlannerResponse,
  PlannerTask,
  RagDocument,
  RagSource,
  Language,
  StructuredGoalPlan
} from '../types';
import {
  ApiHttpError,
  ApiNetworkError,
  applyReplanTasks,
  askMaterials,
  createDailyReview,
  createGoalPlan,
  createRagDocument,
  deleteRagDocument,
  evaluatePlanner,
  fetchAiSettings,
  fetchDailyReview,
  fetchRagDocuments,
  saveAiSettings,
  saveMemory,
  testAiSettings,
  uploadRagDocument
} from '../lib/api';

type WorkspaceSection = 'all' | 'notes' | 'goals' | 'settings';

interface AIWorkspaceProps {
  data: AppData;
  date: string;
  preferences: string;
  section?: WorkspaceSection;
  onPreferencesChange: (value: string) => void;
  onApplyTasks: (tasks: PlannerTask[]) => void;
  onReplanApplied: (plans: AppliedPlan[]) => void;
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

export function AIWorkspace(props: AIWorkspaceProps) {
  const {
    data,
    date,
    preferences,
    section = 'all',
    onPreferencesChange,
    onApplyTasks,
    onReplanApplied,
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
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [fileInputKey, setFileInputKey] = useState(0);
  const [documents, setDocuments] = useState<RagDocument[]>([]);
  const [documentStatus, setDocumentStatus] = useState('');
  const [goalPlan, setGoalPlan] = useState<GoalPlanResponse | null>(null);
  const [goalStatus, setGoalStatus] = useState('');
  const [dailyReview, setDailyReview] = useState<DailyReviewResponse | null>(null);
  const [utilityResult, setUtilityResult] = useState<PlannerResponse | null>(null);
  const [loading, setLoading] = useState('');
  const [settings, setSettings] = useState<AiSettings>(defaultSettings);
  const [apiKey, setApiKey] = useState('');
  const [settingsStatus, setSettingsStatus] = useState('');
  const [settingsBusy, setSettingsBusy] = useState<'save' | 'test' | 'clear' | ''>('');
  const [reviewStatus, setReviewStatus] = useState('');

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

  async function runGoalPlan() {
    const trimmedGoal = goal.trim();
    setGoalStatus('');
    if (!trimmedGoal) {
      setGoalStatus(t('legacy.goalRequired'));
      return;
    }
    setLoading('goal');
    setUtilityResult(null);
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
            <PreferenceCard
              preferences={preferences}
              onPreferencesChange={onPreferencesChange}
              onSave={() => runUtility('memory')}
              saving={loading === 'memory'}
              t={t}
            />
          )}
        </>
      )}

      {showMaterials && (
        <MaterialLibrary
          documents={documents}
          docTitle={docTitle}
          docContent={docContent}
          uploadFile={uploadFile}
          fileInputKey={fileInputKey}
          documentStatus={documentStatus}
          loading={loading}
          setDocTitle={setDocTitle}
          setDocContent={setDocContent}
          setUploadFile={setUploadFile}
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
          setGoal={setGoal}
          setDeadline={setDeadline}
          setDailyHours={setDailyHours}
          onPreferencesChange={onPreferencesChange}
          setMaterials={setMaterials}
          runGoalPlan={runGoalPlan}
          onApplyTasks={onApplyTasks}
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
  uploadFile: File | null;
  fileInputKey: number;
  documentStatus: string;
  loading: string;
  setDocTitle: (value: string) => void;
  setDocContent: (value: string) => void;
  setUploadFile: (value: File | null) => void;
  saveMaterial: () => void;
  uploadMaterial: () => void;
  removeMaterial: (id: string) => void;
  t: (key: string) => string;
}) {
  const {
    documents,
    docTitle,
    docContent,
    uploadFile,
    fileInputKey,
    documentStatus,
    loading,
    setDocTitle,
    setDocContent,
    setUploadFile,
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
  setGoal: (value: string) => void;
  setDeadline: (value: string) => void;
  setDailyHours: (value: number) => void;
  onPreferencesChange: (value: string) => void;
  setMaterials: (value: string) => void;
  runGoalPlan: () => void;
  onApplyTasks: (tasks: PlannerTask[]) => void;
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
    setGoal,
    setDeadline,
    setDailyHours,
    onPreferencesChange,
    setMaterials,
    runGoalPlan,
    onApplyTasks,
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
      {goalStatus && <p className="inline-status">{goalStatus}</p>}
      {goalPlan && <GoalPlanView plan={goalPlan} t={t} />}
      <button className="apply-button" onClick={() => onApplyTasks(goalPlan?.tasks ?? [])} disabled={!goalPlan?.tasks.length}>
        {goalPlan?.tasks.length ? t('legacy.applyTasks') : t('legacy.noAiTasks')}
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

function GoalPlanView({ plan, t }: { plan: GoalPlanResponse; t: (key: string) => string }) {
  return (
    <div className="result-view">
      <h3>{plan.summary}</h3>
      {plan.provider && <p><strong>{plan.provider}</strong> / {plan.model}</p>}
      {plan.structuredPlan ? <StructuredGoalPlanView plan={plan.structuredPlan} t={t} /> : null}
      {!plan.structuredPlan && plan.phases.map((phase) => <p key={phase.title}><strong>{phase.title}</strong>: {phase.detail}</p>)}
      <SourceList sources={plan.sources ?? []} title={t('legacy.referencedSources')} t={t} />
      <h3>{t('legacy.todayTasks')}</h3>
      {plan.tasks.map((task) => <TaskPreview key={`${task.time}-${task.title}`} time={task.time} title={task.title} reason={task.reason} />)}
    </div>
  );
}

function StructuredGoalPlanView({ plan, t }: { plan: StructuredGoalPlan; t: (key: string) => string }) {
  return (
    <div className="structured-plan">
      <div className="structured-plan-head">
        <div>
          <span>{t('legacy.structuredGoal')}</span>
          <strong>{plan.goalTitle}</strong>
        </div>
        <em>{plan.durationDays} {t('legacy.days')}</em>
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
              {milestone.tasks.map((task) => (
                <div className="milestone-task" key={`${milestone.title}-${task.title}`}>
                  <div>
                    <strong>{task.title}</strong>
                    <p>{task.description}</p>
                  </div>
                  <span>{task.estimatedMinutes}m</span>
                  <em className={`priority ${task.priority}`}>{t(`legacy.priority${capitalize(task.priority)}`)}</em>
                  {task.dueDate ? <time>{task.dueDate}</time> : null}
                </div>
              ))}
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

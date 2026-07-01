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
  AppliedPlan,
  AppData,
  DailyReviewResponse,
  GoalPlanResponse,
  PlannerResponse,
  PlannerTask,
  RagDocument,
  RagSource
} from '../types';
import {
  applyReplanTasks,
  askMaterials,
  checkBackendHealth,
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

interface AIWorkspaceProps {
  data: AppData;
  date: string;
  preferences: string;
  onPreferencesChange: (value: string) => void;
  onApplyTasks: (tasks: PlannerTask[]) => void;
  onReplanApplied: (plans: AppliedPlan[]) => void;
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

export function AIWorkspace(props: AIWorkspaceProps) {
  const { data, date, preferences, onPreferencesChange, onApplyTasks, onReplanApplied, t } = props;
  const [goal, setGoal] = useState('3 个月内拿到北京 AI 应用开发实习');
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
  const [dailyReview, setDailyReview] = useState<DailyReviewResponse | null>(null);
  const [utilityResult, setUtilityResult] = useState<PlannerResponse | null>(null);
  const [loading, setLoading] = useState('');
  const [settings, setSettings] = useState<AiSettings>(defaultSettings);
  const [apiKey, setApiKey] = useState('');
  const [settingsStatus, setSettingsStatus] = useState('');
  const [reviewStatus, setReviewStatus] = useState('');

  const payload = { goal, deadline, dailyHours, materials, preferences, date, data };

  useEffect(() => {
    fetchAiSettings()
      .then(setSettings)
      .catch(() => undefined);
  }, []);

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
        title: docTitle.trim() || t('materialTitle'),
        content,
        sourceType: 'paste'
      });
      setDocuments((current) => [saved, ...current.filter((item) => item.id !== saved.id)]);
      setDocContent('');
      setDocTitle('');
      setDocumentStatus(t('materialSaved'));
    } catch {
      setDocumentStatus(t('materialSaveError'));
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
      setDocumentStatus(t('materialUploaded'));
    } catch {
      setDocumentStatus(t('materialUploadError'));
    } finally {
      setLoading('');
    }
  }

  async function removeMaterial(id: string) {
    try {
      await deleteRagDocument(id);
      setDocuments((current) => current.filter((item) => item.id !== id));
    } catch {
      setDocumentStatus(t('materialSaveError'));
    }
  }

  async function runGoalPlan() {
    setLoading('goal');
    setUtilityResult(null);
    try {
      setGoalPlan(await createGoalPlan({ goal, deadline, dailyHours, materials, preferences, date }));
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
      setReviewStatus(t('replanApplied'));
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
        setUtilityResult({ summary: t('saved') });
      }
    } finally {
      setLoading('');
    }
  }

  async function saveModelSettings() {
    const backendUp = await checkBackendHealth();
    if (!backendUp) {
      setSettingsStatus('后端服务未启动，无法保存设置');
      return;
    }
    try {
      const saved = await saveAiSettings({
        provider: settings.provider,
        baseUrl: settings.baseUrl,
        model: settings.model,
        apiKey: apiKey.trim() || undefined,
        temperature: settings.temperature,
        timeoutSeconds: settings.timeoutSeconds
      });
      setSettings(saved);
      setApiKey('');
      setSettingsStatus(t('settingsSaved'));
    } catch {
      setSettingsStatus(t('settingsError'));
    }
  }

  async function testModel() {
    // First check if backend is reachable
    const backendUp = await checkBackendHealth();
    if (!backendUp) {
      setSettingsStatus('后端服务未启动或连接失败，请确认后端已运行在 127.0.0.1:8000');
      return;
    }

    try {
      const test = await testAiSettings();
      if (test.ok) {
        setSettingsStatus(test.message);
      } else {
        // Map error types to user-friendly messages
        const errorMessages: Record<string, string> = {
          no_key: 'API Key 未保存，请在设置中填入 API Key',
          auth_error: 'API Key 无效或已过期',
          insufficient_balance: '账户余额不足',
          bad_model: '模型名不存在或不支持',
          bad_base_url: 'Base URL 无法连接，请检查地址是否正确',
          bad_request: '请求参数错误，请检查 Base URL 和模型名',
          timeout: '模型服务请求超时，请检查网络或增大超时时间',
          network_error: 'Base URL 无法连接，请检查地址是否正确',
          server_error: '模型服务端错误，请稍后重试',
          rate_limited: '请求过于频繁，请稍后重试',
        };
        const errorType = test.errorType ?? '';
        setSettingsStatus(errorMessages[errorType] || test.message || '模型测试失败，请检查设置');
      }
    } catch (err) {
      setSettingsStatus('请求后端失败，请重试');
    }
  }

  const mode = goalPlan?.mode ?? dailyReview?.mode ?? utilityResult?.mode;
  const modeLabel = mode === 'mock' ? t('mockMode') : mode === 'llm' ? t('llmMode') : t('apiMode');

  return (
    <section className="surface ai-panel">
      <div className="section-head">
        <div>
          <span className="eyebrow"><Bot size={14} /> {modeLabel}</span>
          <h2>{t('aiWorkspace')}</h2>
        </div>
      </div>

      <ModelSettings
        settings={settings}
        apiKey={apiKey}
        settingsStatus={settingsStatus}
        setSettings={setSettings}
        setApiKey={setApiKey}
        saveModelSettings={saveModelSettings}
        testModel={testModel}
        t={t}
      />

      <div className="workflow-card">
        <div className="workflow-head">
          <div>
            <span>{t('materialLibrary')}</span>
            <strong>{t('materialLibraryHint')}</strong>
          </div>
          <div className="workflow-buttons">
            <button onClick={saveMaterial} disabled={loading === 'material' || !docContent.trim()}>
              <Library size={16} />{t('saveMaterial')}
            </button>
            <button onClick={uploadMaterial} disabled={loading === 'upload-material' || !uploadFile}>
              <UploadCloud size={16} />{t('uploadMaterial')}
            </button>
          </div>
        </div>
        <div className="ai-grid material-grid">
          <label>
            <span>{t('materialTitle')}</span>
            <input value={docTitle} onChange={(event) => setDocTitle(event.target.value)} placeholder={t('materialTitlePlaceholder')} />
          </label>
          <label>
            <span>{t('materialFile')}</span>
            <input
              key={fileInputKey}
              type="file"
              accept=".txt,.md,text/plain,text/markdown"
              onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)}
            />
          </label>
          <label className="wide">
            <span>{t('materialContent')}</span>
            <textarea value={docContent} onChange={(event) => setDocContent(event.target.value)} placeholder={t('materialContentPlaceholder')} />
          </label>
        </div>
        {documentStatus && <p className="inline-status">{documentStatus}</p>}
        <div className="material-list">
          <span className="eyebrow">{t('recentMaterials')}</span>
          {!documents.length && <div className="empty-state">{t('noMaterials')}</div>}
          {documents.slice(0, 5).map((document) => (
            <article className="material-item" key={document.id}>
              <div>
                <strong>{document.title}</strong>
                <p>{document.summary}</p>
                <small>{document.chunks} chunks · {document.sourceType}</small>
              </div>
              <button className="icon-button danger" onClick={() => removeMaterial(document.id)} aria-label={t('delete')}>
                <Trash2 size={15} />
              </button>
            </article>
          ))}
        </div>
      </div>

      <div className="workflow-card">
        <div className="workflow-head">
          <div>
            <span>{t('goalPlanning')}</span>
            <strong>{t('goalPlanningHint')}</strong>
          </div>
          <button onClick={runGoalPlan} disabled={loading === 'goal'}><Sparkles size={16} />{t('generateGoalPlan')}</button>
        </div>
        <div className="ai-grid">
          <label>
            <span>{t('goal')}</span>
            <input value={goal} onChange={(event) => setGoal(event.target.value)} placeholder={t('goalPlaceholder')} />
          </label>
          <label>
            <span>{t('deadline')}</span>
            <input type="date" value={deadline} onChange={(event) => setDeadline(event.target.value)} />
          </label>
          <label>
            <span>{t('dailyHours')}</span>
            <input type="number" min={1} max={12} value={dailyHours} onChange={(event) => setDailyHours(Number(event.target.value))} />
          </label>
          <label className="wide">
            <span>{t('preference')}</span>
            <input value={preferences} onChange={(event) => onPreferencesChange(event.target.value)} placeholder={t('preferencePlaceholder')} />
          </label>
          <label className="wide">
            <span>{t('materials')}</span>
            <textarea value={materials} onChange={(event) => setMaterials(event.target.value)} placeholder={t('materialsPlaceholder')} />
          </label>
        </div>
        {loading === 'goal' && <div className="empty-state">{t('loading')}</div>}
        {goalPlan && <GoalPlanView plan={goalPlan} t={t} />}
        <button className="apply-button" onClick={() => onApplyTasks(goalPlan?.tasks ?? [])} disabled={!goalPlan?.tasks.length}>
          {goalPlan?.tasks.length ? t('applyTasks') : t('noAiTasks')}
        </button>
      </div>

      <div className="workflow-card">
        <div className="workflow-head">
          <div>
            <span>{t('dailyReview')}</span>
            <strong>{t('dailyReviewHint')}</strong>
          </div>
          <button onClick={runDailyReview} disabled={loading === 'review'}><ClipboardCheck size={16} />{t('runDailyReview')}</button>
        </div>
        {loading === 'review' && <div className="empty-state">{t('loading')}</div>}
        {!dailyReview && loading !== 'review' && <div className="empty-state">{t('reviewEmpty')}</div>}
        {dailyReview && <DailyReviewView review={dailyReview} t={t} />}
        <button className="apply-button" onClick={applyReviewReplan} disabled={!dailyReview?.replanTasks.length || loading === 'apply-replan'}>
          {dailyReview?.replanTasks.length ? t('applyReplan') : t('noReplanTasks')}
        </button>
        {reviewStatus && <p className="inline-status">{reviewStatus}</p>}
      </div>

      <div className="command-row">
        <button onClick={() => runUtility('rag')}><FileSearch size={16} />{t('rag')}</button>
        <button onClick={() => runUtility('memory')}><Save size={16} />{t('saveMemory')}</button>
        <button onClick={() => runUtility('eval')}><DatabaseZap size={16} />{t('evaluate')}</button>
      </div>
      {utilityResult && <ResultView result={utilityResult} t={t} />}
    </section>
  );
}

function ModelSettings(props: {
  settings: AiSettings;
  apiKey: string;
  settingsStatus: string;
  setSettings: (updater: (settings: AiSettings) => AiSettings) => void;
  setApiKey: (value: string) => void;
  saveModelSettings: () => void;
  testModel: () => void;
  t: (key: string) => string;
}) {
  const { settings, apiKey, settingsStatus, setSettings, setApiKey, saveModelSettings, testModel, t } = props;
  return (
    <div className="model-settings">
      <div className="settings-title">
        <span><Settings size={15} />{t('aiSettings')}</span>
        <strong>{settings.hasApiKey ? t('hasKey') : t('noKey')}</strong>
      </div>
      <div className="settings-grid">
        <label>
          <span>{t('provider')}</span>
          <select value={settings.provider} onChange={(event) => setSettings((current) => ({ ...current, provider: event.target.value as AiSettings['provider'] }))}>
            <option value="deepseek">DeepSeek</option>
            <option value="openai">OpenAI</option>
            <option value="custom">Custom</option>
            <option value="mock">Mock</option>
          </select>
        </label>
        <label>
          <span>{t('baseUrl')}</span>
          <input value={settings.baseUrl} onChange={(event) => setSettings((current) => ({ ...current, baseUrl: event.target.value }))} />
        </label>
        <label>
          <span>{t('model')}</span>
          <select value={settings.model} onChange={(event) => setSettings((current) => ({ ...current, model: event.target.value }))}>
            <option value="deepseek-v4-flash">DeepSeek V4 Flash</option>
            <option value="deepseek-v4-pro">DeepSeek V4 Pro</option>
            <option value="deepseek-reasoner">DeepSeek Reasoner</option>
          </select>
        </label>
        <label>
          <span><KeyRound size={13} />{t('apiKey')}</span>
          <input type="password" value={apiKey} onChange={(event) => setApiKey(event.target.value)} placeholder={t('apiKeyPlaceholder')} />
        </label>
        <label>
          <span>{t('temperature')}</span>
          <input type="number" min={0} max={2} step={0.1} value={settings.temperature} onChange={(event) => setSettings((current) => ({ ...current, temperature: Number(event.target.value) }))} />
        </label>
        <label>
          <span>{t('timeout')}</span>
          <input type="number" min={5} max={120} value={settings.timeoutSeconds} onChange={(event) => setSettings((current) => ({ ...current, timeoutSeconds: Number(event.target.value) }))} />
        </label>
      </div>
      <div className="settings-actions">
        <button onClick={saveModelSettings}><Save size={16} />{t('saveSettings')}</button>
        <button onClick={testModel}><PlugZap size={16} />{t('testModel')}</button>
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
      {plan.phases.map((phase) => <p key={phase.title}><strong>{phase.title}</strong>: {phase.detail}</p>)}
      <SourceList sources={plan.sources ?? []} title={t('referencedSources')} t={t} />
      <h3>{t('todayTasks')}</h3>
      {plan.tasks.map((task) => <TaskPreview key={`${task.time}-${task.title}`} time={task.time} title={task.title} reason={task.reason} />)}
    </div>
  );
}

function DailyReviewView({ review, t }: { review: DailyReviewResponse; t: (key: string) => string }) {
  return (
    <div className="result-view">
      <h3>{review.summary}</h3>
      <p>{t('completionRatio')}: {review.doneCount}/{review.totalCount}</p>
      <ul>{review.suggestions.map((item) => <li key={item}>{item}</li>)}</ul>
      <h3><RotateCcw size={15} /> {t('replanPreview')} / {review.targetDate}</h3>
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
            <span>{t('relevance')}: {source.score.toFixed(3)}</span>
          </div>
          <p>{source.chunk}</p>
        </article>
      ))}
    </div>
  );
}

function ResultView({ result, t }: { result: PlannerResponse; t: (key: string) => string }) {
  const heading = result.score ? `${t('score')}: ${result.score}/5` : result.summary ?? result.answer ?? t('aiWorkspace');
  return (
    <div className="result-view utility-result">
      <h3>{heading}</h3>
      {result.provider && <p><strong>{result.provider}</strong> / {result.model}</p>}
      {result.suggestions && <ul>{result.suggestions.map((item) => <li key={item}>{item}</li>)}</ul>}
      {result.answer && result.answer !== heading && <p>{result.answer}</p>}
      <SourceList sources={result.sources ?? []} title={t('sources')} t={t} />
      {result.keywords && <p>{result.keywords.join(' / ')}</p>}
      {result.results && <ul>{result.results.map((item) => <li key={item.case}><strong>{item.score}/5</strong> {item.case} - {item.reason}</li>)}</ul>}
    </div>
  );
}

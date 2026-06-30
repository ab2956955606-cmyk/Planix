import { useState } from 'react';
import { Bot, ClipboardCheck, DatabaseZap, FileSearch, Save, Sparkles } from 'lucide-react';
import type { AppData, PlannerResponse, PlannerTask } from '../types';
import { askMaterials, evaluatePlanner, generatePlan, reviewToday, saveMemory } from '../lib/api';

interface AIWorkspaceProps {
  data: AppData;
  date: string;
  preferences: string;
  onPreferencesChange: (value: string) => void;
  onApplyTasks: (tasks: PlannerTask[]) => void;
  t: (key: string) => string;
}

export function AIWorkspace(props: AIWorkspaceProps) {
  const { data, date, preferences, onPreferencesChange, onApplyTasks, t } = props;
  const [goal, setGoal] = useState('3 个月内拿到北京 AI 应用开发实习');
  const [deadline, setDeadline] = useState(() => {
    const d = new Date();
    d.setMonth(d.getMonth() + 3);
    return d.toISOString().slice(0, 10);
  });
  const [dailyHours, setDailyHours] = useState(3);
  const [materials, setMaterials] = useState('');
  const [result, setResult] = useState<PlannerResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const payload = { goal, deadline, dailyHours, materials, preferences, date, data };
  const aiTasks = result?.tasks ?? [];

  async function run(action: 'plan' | 'review' | 'rag' | 'eval' | 'memory') {
    setLoading(true);
    try {
      if (action === 'plan') setResult(await generatePlan(payload));
      if (action === 'review') setResult(await reviewToday(payload));
      if (action === 'rag') setResult(await askMaterials(payload));
      if (action === 'eval') setResult(await evaluatePlanner(payload));
      if (action === 'memory') {
        await saveMemory(preferences);
        setResult({ summary: t('saved') });
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="surface ai-panel">
      <div className="section-head">
        <div>
          <span className="eyebrow"><Bot size={14} /> {result?.mode === 'mock' ? t('mockMode') : t('apiMode')}</span>
          <h2>{t('aiWorkspace')}</h2>
        </div>
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
      <div className="command-row">
        <button onClick={() => run('plan')}><Sparkles size={16} />{t('generate')}</button>
        <button onClick={() => run('review')}><ClipboardCheck size={16} />{t('review')}</button>
        <button onClick={() => run('rag')}><FileSearch size={16} />{t('rag')}</button>
        <button onClick={() => run('memory')}><Save size={16} />{t('saveMemory')}</button>
        <button onClick={() => run('eval')}><DatabaseZap size={16} />{t('evaluate')}</button>
      </div>
      <div className="ai-output">
        {loading && <div className="empty-state">{t('loading')}</div>}
        {!loading && !result && <div className="empty-state">{t('backendTip')}</div>}
        {!loading && result && <ResultView result={result} t={t} />}
      </div>
      <button className="apply-button" onClick={() => onApplyTasks(aiTasks)} disabled={!aiTasks.length}>
        {aiTasks.length ? t('applyTasks') : t('noAiTasks')}
      </button>
    </section>
  );
}

function ResultView({ result, t }: { result: PlannerResponse; t: (key: string) => string }) {
  const heading = result.score ? `${t('score')}: ${result.score}/5` : result.summary ?? result.answer ?? t('aiWorkspace');
  return (
    <div className="result-view">
      <h3>{heading}</h3>
      {result.phases?.map((phase) => <p key={phase.title}><strong>{phase.title}</strong>：{phase.detail}</p>)}
      {result.tasks?.map((task) => (
        <div className="ai-task" key={`${task.time}-${task.title}`}>
          <time>{task.time}</time>
          <div><strong>{task.title}</strong><p>{task.reason}</p></div>
        </div>
      ))}
      {result.suggestions && <ul>{result.suggestions.map((item) => <li key={item}>{item}</li>)}</ul>}
      {result.answer && result.answer !== heading && <p>{result.answer}</p>}
      {result.sources && <ul>{result.sources.map((item) => <li key={item.title}><strong>{item.title}</strong>：{item.quote}</li>)}</ul>}
      {result.results && <ul>{result.results.map((item) => <li key={item.case}><strong>{item.score}/5</strong> {item.case} - {item.reason}</li>)}</ul>}
    </div>
  );
}

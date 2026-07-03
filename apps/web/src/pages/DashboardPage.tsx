import { useState } from 'react';
import { BrainCircuit, Boxes, CheckCircle2, Database, Send, Sparkles, Target } from 'lucide-react';
import { AgentFlowTrace } from '../components/agent/flow/AgentFlowTrace';
import { agentFlowActions } from '../store/agentFlowStore';
import type { InspectorLog, InspectorSnapshot, Plan } from '../types';

interface DashboardPageProps {
  date: string;
  plans: Plan[];
  preferences: string;
  inspector: InspectorSnapshot;
  onAgentStatusChange: (status: InspectorSnapshot['agentStatus']) => void;
  onLog: (log: Omit<InspectorLog, 'id' | 'timestamp'>) => void;
  t: (key: string) => string;
}

export function DashboardPage(props: DashboardPageProps) {
  const { date, plans, preferences, inspector, onAgentStatusChange, onLog, t } = props;
  const [prompt, setPrompt] = useState('');
  const [output, setOutput] = useState(t('dashboard.outputReady'));
  const doneCount = plans.filter((plan) => plan.done).length;
  const pendingCount = plans.length - doneCount;

  function runAgent() {
    const value = prompt.trim();
    if (!value) return;
    onAgentStatusChange('running');
    onLog({ level: 'info', message: t('dashboard.outputRunning') });
    setOutput(t('dashboard.outputRunning'));
    void agentFlowActions.runRuntimeFlow(
      {
        input: value,
        date,
        preferences,
        data: {
          [date]: { plans }
        }
      },
      {
        onFinal: (content) => setOutput(content || t('dashboard.outputDone')),
        onError: () => {
          onLog({ level: 'warning', message: t('dashboard.outputFallback') });
          setOutput(t('dashboard.outputFallback'));
        },
        onDone: () => {
          onAgentStatusChange('done');
          onLog({ level: 'success', message: t('dashboard.outputDone') });
        }
      }
    );
  }

  return (
    <section className="dashboard-page">
      <div className="dashboard-hero">
        <span className="riva-eyebrow">
          <Sparkles size={16} />
          {t('dashboard.eyebrow')}
        </span>
        <h1>{t('dashboard.title')}</h1>
        <p>{t('dashboard.subtitle')}</p>
      </div>

      <div className="dashboard-grid">
        <article className="agent-workspace riva-panel">
          <div className="panel-head">
            <div>
              <span className="riva-eyebrow">{t('agent.title')}</span>
              <h2>{t('dashboard.promptLabel')}</h2>
            </div>
            <span className={`agent-state ${inspector.agentStatus}`}>{t(`agent.${inspector.agentStatus}`)}</span>
          </div>
          <div className="prompt-console">
            <textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder={t('dashboard.promptPlaceholder')} />
            <button onClick={runAgent} disabled={!prompt.trim()}>
              <Send size={17} />
              {t('dashboard.runAgent')}
            </button>
          </div>
          <div className="agent-output">
            <span>{t('dashboard.outputTitle')}</span>
            <p>{output || t('dashboard.outputEmpty')}</p>
          </div>
        </article>

        <article className="workspace-summary riva-panel">
          <div className="panel-head">
            <div>
              <span className="riva-eyebrow">{t('dashboard.cardsTitle')}</span>
              <h2>{t('dashboard.workspaceSummary')}</h2>
            </div>
          </div>
          <p>{t('dashboard.summaryBody')}</p>
          <div className="summary-memory">
            <BrainCircuit size={17} />
            <span>{preferences || t('inspector.emptyMemory')}</span>
          </div>
        </article>

        <AgentFlowTrace t={t} />

        <div className="ai-card-grid">
          <DashboardCard icon={Target} label={t('dashboard.activePlans')} value={plans.length} hint={t('dashboard.cardHintPlans')} />
          <DashboardCard icon={CheckCircle2} label={t('dashboard.completedPlans')} value={doneCount} hint={t('dashboard.cardHintPlans')} />
          <DashboardCard icon={Boxes} label={t('dashboard.pendingPlans')} value={pendingCount} hint={t('dashboard.cardHintGoals')} />
          <DashboardCard icon={Database} label={t('dashboard.knowledgeBase')} value={inspector.memory.materialCount} hint={t('dashboard.cardHintKnowledge')} />
        </div>

        <article className="tool-placeholder riva-panel">
          <span className="riva-eyebrow">{t('agent.toolCalls')}</span>
          <h2>{t('dashboard.toolPlaceholderTitle')}</h2>
          <p>{t('dashboard.toolPlaceholderBody')}</p>
        </article>
      </div>
    </section>
  );
}

function DashboardCard(props: { icon: typeof Target; label: string; value: number; hint: string }) {
  const Icon = props.icon;
  return (
    <article className="ai-card">
      <Icon size={18} />
      <strong>{props.value}</strong>
      <span>{props.label}</span>
      <p>{props.hint}</p>
    </article>
  );
}

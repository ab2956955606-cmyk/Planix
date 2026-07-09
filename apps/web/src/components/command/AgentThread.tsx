import { useEffect, useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import type { CommandThreadMessage } from '../../stores/commandAgentStore';
import type { PlanHorizon, PlanQualityReport, PlanQualityStatus, PlanSourceType } from '../../types';
import { ApprovalCard } from './ApprovalCard';
import { CalendarPlanPreviewCard } from './CalendarPlanPreviewCard';
import { CalendarWriteResultCard } from './CalendarWriteResultCard';
import { CommandDecisionCard } from './CommandDecisionCard';
import {
  AgentDecisionCard,
  AgentMessageCard,
  ExecutionPlanDraftCard,
  LearningUpdateBadge,
  MemoryInsightCard,
  PlanDesignProposalCard,
  PlanningSessionStatusCard,
  ResourceBriefCard,
  UserNeedContractCard
} from './DeepPlanningCards';
import { ExecutionMiniCard } from './ExecutionMiniCard';
import { InlinePlanDetailCard } from './InlinePlanDetailCard';
import { InlinePlanSummaryCard } from './InlinePlanSummaryCard';
import { MemorySearchResultsCard } from './MemorySearchResultsCard';
import { MemoryWritePreviewCard } from './MemoryWritePreviewCard';
import { MemoryWriteResultCard } from './MemoryWriteResultCard';
import { ModelUsageBadge } from './ModelUsageBadge';
import { NoteSearchResultsCard } from './NoteSearchResultsCard';
import { NoteWritePreviewCard } from './NoteWritePreviewCard';
import { NoteWriteResultCard } from './NoteWriteResultCard';
import { PlanPatchPreviewCard } from './PlanPatchPreviewCard';
import { PlanPatchResultCard } from './PlanPatchResultCard';
import { PlanSearchResultsCard } from './PlanSearchResultsCard';
import { RefinedTasksResultCard } from './RefinedTasksResultCard';

interface AgentThreadProps {
  messages: CommandThreadMessage[];
  sending: boolean;
  onApprove: (actionId: string, decision: 'approve' | 'reject') => void;
  onSend: (value: string) => void;
  t: (key: string) => string;
}

function payloadOf(message: CommandThreadMessage): Record<string, unknown> {
  return message.payload ?? {};
}

type RenderItem =
  | { type: 'message'; message: CommandThreadMessage }
  | { type: 'execution_group'; id: string; messages: CommandThreadMessage[] }
  | { type: 'usage_group'; id: string; messages: CommandThreadMessage[] };

function groupMessages(messages: CommandThreadMessage[]): RenderItem[] {
  const items: RenderItem[] = [];
  let executionGroup: CommandThreadMessage[] = [];
  let usageGroup: CommandThreadMessage[] = [];

  const flushExecutionGroup = () => {
    if (!executionGroup.length) return;
    items.push({
      type: 'execution_group',
      id: executionGroup[0].id,
      messages: executionGroup
    });
    executionGroup = [];
  };
  const flushUsageGroup = () => {
    if (!usageGroup.length) return;
    items.push({
      type: 'usage_group',
      id: usageGroup[0].id,
      messages: usageGroup
    });
    usageGroup = [];
  };

  for (const message of messages) {
    if (message.role === 'card' && message.kind === 'runtime') {
      flushUsageGroup();
      executionGroup.push(message);
      continue;
    }
    flushExecutionGroup();
    if (message.role === 'card' && message.kind === 'model_usage') {
      usageGroup.push(message);
      continue;
    }
    flushUsageGroup();
    items.push({ type: 'message', message });
  }
  flushExecutionGroup();
  flushUsageGroup();
  return items;
}

function ExecutionGroupCard({ messages, t }: { messages: CommandThreadMessage[]; t: (key: string) => string }) {
  const last = messages[messages.length - 1];
  const status = messages.some((message) => message.status === 'error')
    ? 'error'
    : last?.status === 'running'
      ? 'running'
      : 'success';
  const [expanded, setExpanded] = useState(status === 'running');

  useEffect(() => {
    if (status !== 'running') {
      setExpanded(false);
    } else {
      setExpanded(true);
    }
  }, [status]);

  return (
    <div className={`command-inline-card execution-group ${status}`}>
      <button
        type="button"
        className="command-execution-toggle"
        onClick={() => setExpanded((value) => !value)}
        aria-expanded={expanded}
        title={expanded ? t('command.collapseExecution') : t('command.expandExecution')}
      >
        <span className="command-execution-title">
          <strong>{t('command.execution')}</strong>
          <small>{messages.length} {t('command.executionSteps')}</small>
        </span>
        <span className="command-execution-arrow" aria-hidden="true">
          {expanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
        </span>
        <em>
          <i aria-hidden="true" />
          {status === 'success' ? t('command.statusSuccess') : status === 'error' ? t('command.statusError') : t('command.statusRunning')}
        </em>
      </button>
      {!expanded && last && <p>{last.title ? `${last.title}: ${last.content}` : last.content}</p>}
      {expanded && (
        <div className="command-execution-items">
          {messages.map((message) => (
            <ExecutionMiniCard
              key={message.id}
              title={message.title}
              content={message.content}
              status={message.status}
              t={t}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export function AgentThread({ messages, sending, onApprove, onSend, t }: AgentThreadProps) {
  if (!messages.length) {
    const examples = [
      t('command.examplePlan'),
      t('command.exampleQuery'),
      t('command.examplePatch'),
      t('command.exampleRefine'),
      t('command.exampleNote')
    ];
    return (
      <div className="agent-thread empty">
        <div className="command-empty-state">
          <h1>{t('command.title')}</h1>
          <p>{t('command.empty')}</p>
          <ul className="command-examples">
            {examples.map((example) => (
              <li key={example}>{example}</li>
            ))}
          </ul>
        </div>
      </div>
    );
  }

  return (
    <div className="agent-thread">
      {groupMessages(messages).map((item) => {
        if (item.type === 'execution_group') {
          return (
            <article className="command-message card" key={`execution-${item.id}`}>
              <ExecutionGroupCard messages={item.messages} t={t} />
            </article>
          );
        }
        if (item.type === 'usage_group') {
          return (
            <article className="command-message card" key={`usage-${item.id}`}>
              <ModelUsageBadge usage={item.messages.map((message) => payloadOf(message).usage)} t={t} />
            </article>
          );
        }
        const { message } = item;
        return (
        <article className={`command-message ${message.role}`} key={message.id}>
          {message.role !== 'card' && (
            <>
              <span>{message.role === 'user' ? t('command.user') : t('command.assistant')}</span>
              <p>{message.content || (message.streaming ? t('command.running') : '')}</p>
            </>
          )}

          {message.role === 'card' && message.kind === 'error' && (
            <div className="command-inline-card error">
              <strong>Error</strong>
              <p>{message.content}</p>
            </div>
          )}

          {message.role === 'card' && message.kind === 'runtime' && (
            <ExecutionMiniCard title={message.title} content={message.content} status={message.status} t={t} />
          )}

          {message.role === 'card' && message.kind === 'summary' && (
            <InlinePlanSummaryCard summary={message.content} t={t} />
          )}

          {message.role === 'card' && message.kind === 'plan_detail' && (
            <InlinePlanDetailCard
              title={String(payloadOf(message).title || message.title || '')}
              version={typeof payloadOf(message).version === 'number' ? payloadOf(message).version as number : undefined}
              structuredPlan={payloadOf(message).structuredPlan}
              planHorizon={payloadOf(message).planHorizon as PlanHorizon | null | undefined}
              qualityReport={payloadOf(message).qualityReport as PlanQualityReport | null | undefined}
              qualityStatus={payloadOf(message).qualityStatus as PlanQualityStatus | null | undefined}
              sourceType={payloadOf(message).sourceType as PlanSourceType | null | undefined}
              t={t}
            />
          )}

          {message.role === 'card' && message.kind === 'refined_tasks_result' && (
            <RefinedTasksResultCard
              total={Number(payloadOf(message).total || 0)}
              succeeded={Number(payloadOf(message).succeeded || 0)}
              failed={Number(payloadOf(message).failed || 0)}
              items={payloadOf(message).items}
              errors={payloadOf(message).errors}
              t={t}
            />
          )}

          {message.role === 'card' && message.kind === 'calendar_preview' && (
            <CalendarPlanPreviewCard
              title={String(payloadOf(message).title || message.title || '')}
              plans={payloadOf(message).plans}
              t={t}
            />
          )}

          {message.role === 'card' && message.kind === 'approval' && (
            <ApprovalCard
              summary={message.content}
              actionId={message.actionId}
              risk={String(payloadOf(message).risk || '')}
              target={String(payloadOf(message).target || '')}
              operation={String(payloadOf(message).operation || '')}
              sending={sending}
              onDecision={onApprove}
              t={t}
            />
          )}

          {message.role === 'card' && message.kind === 'calendar_write_result' && (
            <CalendarWriteResultCard
              created={Number(payloadOf(message).created || 0)}
              updated={Number(payloadOf(message).updated || 0)}
              failed={Number(payloadOf(message).failed || 0)}
              affectedDates={payloadOf(message).affectedDates}
              errors={payloadOf(message).errors}
              plans={payloadOf(message).plans}
              t={t}
            />
          )}

          {message.role === 'card' && message.kind === 'command_decision' && (
            <CommandDecisionCard
              intent={String(payloadOf(message).intent || '')}
              confidence={payloadOf(message).confidence}
              targetType={String(payloadOf(message).targetType || '')}
              action={String(payloadOf(message).action || '')}
              decisionSummary={String(payloadOf(message).decisionSummary || message.content || '')}
              source={String(payloadOf(message).source || '')}
              t={t}
            />
          )}

          {message.role === 'card' && message.kind === 'plan_search_results' && (
            <PlanSearchResultsCard
              summary={String(payloadOf(message).summary || message.content || '')}
              calendarPlans={payloadOf(message).calendarPlans}
              materials={payloadOf(message).materials}
              goalHistory={payloadOf(message).goalHistory}
              monthNotes={payloadOf(message).monthNotes}
              onSend={onSend}
              t={t}
            />
          )}

          {message.role === 'card' && message.kind === 'note_search_results' && (
            <NoteSearchResultsCard
              summary={String(payloadOf(message).summary || message.content || '')}
              materials={payloadOf(message).materials}
              goalHistory={payloadOf(message).goalHistory}
              monthNotes={payloadOf(message).monthNotes}
              onSend={onSend}
              t={t}
            />
          )}

          {message.role === 'card' && message.kind === 'memory_search_results' && (
            <MemorySearchResultsCard
              summary={String(payloadOf(message).summary || message.content || '')}
              groups={payloadOf(message).groups}
              results={payloadOf(message).results}
              onSend={onSend}
              t={t}
            />
          )}

          {message.role === 'card' && message.kind === 'plan_patch_preview' && (
            <PlanPatchPreviewCard
              operation={String(payloadOf(message).operation || '')}
              before={payloadOf(message).before}
              after={payloadOf(message).after}
              changes={payloadOf(message).changes}
              t={t}
            />
          )}

          {message.role === 'card' && message.kind === 'plan_patch_result' && (
            <PlanPatchResultCard
              operation={String(payloadOf(message).operation || '')}
              status={String(payloadOf(message).status || '')}
              after={payloadOf(message).after}
              error={typeof payloadOf(message).error === 'string' ? payloadOf(message).error as string : undefined}
              t={t}
            />
          )}

          {message.role === 'card' && message.kind === 'note_write_preview' && (
            <NoteWritePreviewCard
              year={payloadOf(message).year}
              month={payloadOf(message).month}
              date={payloadOf(message).date}
              noteText={payloadOf(message).noteText}
              before={payloadOf(message).before}
              after={payloadOf(message).after}
              t={t}
            />
          )}

          {message.role === 'card' && message.kind === 'memory_write_preview' && (
            <MemoryWritePreviewCard
              kind={payloadOf(message).kind}
              title={payloadOf(message).title}
              content={payloadOf(message).content}
              summary={payloadOf(message).summary}
              t={t}
            />
          )}

          {message.role === 'card' && message.kind === 'note_write_result' && (
            <NoteWriteResultCard
              status={String(payloadOf(message).status || '')}
              year={payloadOf(message).year}
              month={payloadOf(message).month}
              noteText={payloadOf(message).noteText}
              error={typeof payloadOf(message).error === 'string' ? payloadOf(message).error as string : undefined}
              t={t}
            />
          )}

          {message.role === 'card' && message.kind === 'memory_write_result' && (
            <MemoryWriteResultCard
              status={String(payloadOf(message).status || '')}
              kind={payloadOf(message).kind}
              title={payloadOf(message).title}
              content={payloadOf(message).content}
              error={typeof payloadOf(message).error === 'string' ? payloadOf(message).error as string : undefined}
              t={t}
            />
          )}

          {message.role === 'card' && message.kind === 'planning_session_started' && (
            <PlanningSessionStatusCard status={String(payloadOf(message).status || message.content || '')} t={t} />
          )}

          {message.role === 'card' && message.kind === 'user_need_contract' && (
            <UserNeedContractCard data={payloadOf(message).data} t={t} />
          )}

          {message.role === 'card' && message.kind === 'memory_insight_brief' && (
            <MemoryInsightCard data={payloadOf(message).data} t={t} />
          )}

          {message.role === 'card' && message.kind === 'resource_brief' && (
            <ResourceBriefCard data={payloadOf(message).data} t={t} />
          )}

          {message.role === 'card' && message.kind === 'plan_design_proposal' && (
            <PlanDesignProposalCard data={payloadOf(message).data} onSend={onSend} t={t} />
          )}

          {message.role === 'card' && message.kind === 'execution_plan_draft' && (
            <ExecutionPlanDraftCard data={payloadOf(message).data} onSend={onSend} t={t} />
          )}

          {message.role === 'card' && message.kind === 'learning_update' && (
            <LearningUpdateBadge data={payloadOf(message).data} t={t} />
          )}

          {message.role === 'card' && message.kind === 'agent_decision' && (
            <AgentDecisionCard data={payloadOf(message).data} t={t} />
          )}

          {message.role === 'card' && message.kind === 'agent_message' && (
            <AgentMessageCard data={payloadOf(message).data} t={t} />
          )}

          {message.role === 'card' && message.kind === 'planning_session_status' && (
            <PlanningSessionStatusCard status={String(payloadOf(message).status || message.content || '')} t={t} />
          )}

          {message.role === 'card' && message.kind === 'model_usage' && (
            <ModelUsageBadge usage={payloadOf(message).usage} t={t} />
          )}

          {message.role === 'card' && message.kind === 'clarify_question' && (
            <div className="command-inline-card clarify-question">
              <div className="command-card-heading">
                <strong>{t('command.clarifyQuestion')}</strong>
              </div>
              <p>{message.content}</p>
            </div>
          )}

          {message.role === 'card' && message.kind === 'execution_result' && (
            <div className={`command-inline-card execution ${message.status || 'success'}`}>
              <div className="command-card-heading">
                <strong>{t('command.executionResult')}</strong>
              </div>
              <p>{message.content}</p>
            </div>
          )}
        </article>
        );
      })}
    </div>
  );
}

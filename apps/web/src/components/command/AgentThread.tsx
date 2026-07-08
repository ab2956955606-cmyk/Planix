import { useEffect, useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import type { CommandThreadMessage } from '../../stores/commandAgentStore';
import type { PlanHorizon, PlanQualityReport, PlanQualityStatus, PlanSourceType } from '../../types';
import { ApprovalCard } from './ApprovalCard';
import { CalendarPlanPreviewCard } from './CalendarPlanPreviewCard';
import { CalendarWriteResultCard } from './CalendarWriteResultCard';
import { ExecutionMiniCard } from './ExecutionMiniCard';
import { InlinePlanDetailCard } from './InlinePlanDetailCard';
import { InlinePlanSummaryCard } from './InlinePlanSummaryCard';
import { PlanPatchPreviewCard } from './PlanPatchPreviewCard';
import { PlanPatchResultCard } from './PlanPatchResultCard';
import { PlanSearchResultsCard } from './PlanSearchResultsCard';
import { RefinedTasksResultCard } from './RefinedTasksResultCard';

interface AgentThreadProps {
  messages: CommandThreadMessage[];
  sending: boolean;
  onApprove: (actionId: string, decision: 'approve' | 'reject') => void;
  t: (key: string) => string;
}

function payloadOf(message: CommandThreadMessage): Record<string, unknown> {
  return message.payload ?? {};
}

type RenderItem =
  | { type: 'message'; message: CommandThreadMessage }
  | { type: 'execution_group'; id: string; messages: CommandThreadMessage[] };

function groupMessages(messages: CommandThreadMessage[]): RenderItem[] {
  const items: RenderItem[] = [];
  let executionGroup: CommandThreadMessage[] = [];

  const flushExecutionGroup = () => {
    if (!executionGroup.length) return;
    items.push({
      type: 'execution_group',
      id: executionGroup[0].id,
      messages: executionGroup
    });
    executionGroup = [];
  };

  for (const message of messages) {
    if (message.role === 'card' && message.kind === 'runtime') {
      executionGroup.push(message);
      continue;
    }
    flushExecutionGroup();
    items.push({ type: 'message', message });
  }
  flushExecutionGroup();
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

export function AgentThread({ messages, sending, onApprove, t }: AgentThreadProps) {
  if (!messages.length) {
    return (
      <div className="agent-thread empty">
        <div className="command-empty-state">
          <h1>{t('command.title')}</h1>
          <p>{t('command.empty')}</p>
          <div className="command-examples">
            <button type="button">{t('command.examplePlan')}</button>
            <button type="button">{t('command.exampleQuery')}</button>
            <button type="button">{t('command.exampleRegenerate')}</button>
            <button type="button">{t('command.exampleWrite')}</button>
          </div>
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

          {message.role === 'card' && message.kind === 'plan_search_results' && (
            <PlanSearchResultsCard
              summary={String(payloadOf(message).summary || message.content || '')}
              calendarPlans={payloadOf(message).calendarPlans}
              materials={payloadOf(message).materials}
              goalHistory={payloadOf(message).goalHistory}
              monthNotes={payloadOf(message).monthNotes}
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

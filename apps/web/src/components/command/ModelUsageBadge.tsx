interface ModelRouteAttempt {
  provider?: string;
  model?: string;
  status?: string;
  errorType?: string;
  latencyMs?: number;
}

interface ModelUsage {
  provider?: string;
  model?: string;
  promptTokens?: number;
  completionTokens?: number;
  totalTokens?: number;
  latencyMs?: number;
  mode?: string;
  taskType?: string;
  fallbackUsed?: boolean;
  localFallbackAllowed?: boolean;
  attempts?: ModelRouteAttempt[];
}

interface ModelUsageBadgeProps {
  usage?: unknown;
  t: (key: string) => string;
}

function asUsage(value: unknown): ModelUsage {
  return value && typeof value === 'object' ? value as ModelUsage : {};
}

function usageItems(value: unknown): ModelUsage[] {
  if (Array.isArray(value)) {
    return value.map(asUsage).filter((item) => Object.keys(item).length > 0);
  }
  const item = asUsage(value);
  return Object.keys(item).length ? [item] : [];
}

function taskLabel(taskType: string | undefined, t: (key: string) => string): string {
  switch (taskType) {
    case 'command_decision':
      return t('command.usageTaskDecision');
    case 'plan_generation':
      return t('command.usageTaskPlanGeneration');
    case 'task_refinement':
      return t('command.usageTaskRefinement');
    case 'calendar_patch':
      return t('command.usageTaskCalendarPatch');
    case 'note_query':
      return t('command.usageTaskQueryNotes');
    case 'note_write':
      return t('command.usageTaskNoteWrite');
    case 'chat':
      return t('command.usageTaskChat');
    case 'model_knowledge':
      return t('command.usageTaskModelKnowledge');
    case 'settings_test':
      return t('command.usageTaskSettingsTest');
    default:
      return taskType || t('common.unknown');
  }
}

function formatLatency(ms: number): string {
  if (ms >= 1000) {
    return `${(ms / 1000).toFixed(1)}s`;
  }
  return `${ms}ms`;
}

function attemptLabel(attempt: ModelRouteAttempt, t: (key: string) => string): string {
  const provider = attempt.provider || t('common.unknown');
  if (attempt.status === 'success') return `${provider} ${t('command.routeSuccess')}`;
  if (attempt.status === 'skipped') {
    const reason = attempt.errorType === 'missing_api_key' ? t('command.routeMissingKey') : attempt.errorType || t('command.routeSkipped');
    return `${provider} ${reason}`;
  }
  return `${provider} ${attempt.errorType || t('command.routeFailed')}`;
}

function routeTrace(item: ModelUsage, t: (key: string) => string): string {
  const attempts = Array.isArray(item.attempts) ? item.attempts : [];
  if (!attempts.length) return '';
  const chain = attempts.map((attempt) => attemptLabel(attempt, t)).join(' -> ');
  const suffix = item.mode === 'local_fallback' ? ` -> ${t('command.routeLocalFallback')}` : '';
  return `${t('command.routeTrace')}: ${chain}${suffix}`;
}

export function ModelUsageBadge({ usage, t }: ModelUsageBadgeProps) {
  const items = usageItems(usage);
  if (!items.length) return null;
  const localOnly = items.length > 0 && items.every((item) => item.mode === 'local_fallback');
  const tokenItems = items.filter((item) => item.mode !== 'local_fallback');
  const routeLines = items.map((item) => routeTrace(item, t)).filter(Boolean);

  return (
    <div className={`command-inline-card model-usage ${localOnly ? 'local' : ''}`}>
      {localOnly ? (
        <>
          <p>{t('command.localFallbackNoTokens')}</p>
          {routeLines.map((line, index) => <small key={`route-local-${index}`}>{line}</small>)}
        </>
      ) : (
        <>
          <p>
            <strong>{t('command.modelUsage')}：</strong>
            {tokenItems.map((item, index) => {
              const total = typeof item.totalTokens === 'number' ? `${item.totalTokens} ${t('command.tokens')}` : t('command.noTokenStatsShort');
              return `${index ? ' · ' : ''}${taskLabel(item.taskType, t)} ${total}`;
            }).join('')}
          </p>
          {tokenItems.map((item, index) => (
            <small key={`${item.taskType || 'usage'}-${index}`}>
              {t('command.model')}: {item.provider || t('common.unknown')} / {item.model || t('common.unknown')}
              {typeof item.promptTokens === 'number' || typeof item.completionTokens === 'number' || typeof item.totalTokens === 'number'
                ? ` · ${t('command.tokens')}: ${t('command.promptTokens')} ${item.promptTokens ?? '-'}, ${t('command.completionTokens')} ${item.completionTokens ?? '-'}, ${t('command.totalTokens')} ${item.totalTokens ?? '-'}`
                : ` · ${t('command.noTokenStats')}`}
              {typeof item.latencyMs === 'number' ? ` · ${t('command.latency')}: ${formatLatency(item.latencyMs)}` : ''}
            </small>
          ))}
          {routeLines.map((line, index) => <small key={`route-${index}`}>{line}</small>)}
        </>
      )}
    </div>
  );
}

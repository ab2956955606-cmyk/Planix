interface CalendarPlanResult {
  id?: string;
  date?: string;
  time?: string;
  title?: string;
  done?: boolean;
  priority?: string;
  estimatedMinutes?: number;
  source?: string;
}

interface MaterialResult {
  title?: string;
  chunk?: string;
  score?: number;
}

interface GoalHistoryResult {
  title?: string;
  goal?: string;
  summary?: string;
  createdAt?: string;
}

interface MonthNoteResult {
  year?: number;
  month?: number;
  content?: string;
}

interface PlanSearchResultsCardProps {
  summary?: string;
  calendarPlans?: unknown;
  materials?: unknown;
  goalHistory?: unknown;
  monthNotes?: unknown;
  t: (key: string) => string;
}

function listOf<T>(value: unknown): T[] {
  return Array.isArray(value) ? value.filter((item): item is T => Boolean(item && typeof item === 'object')) : [];
}

export function PlanSearchResultsCard({
  summary,
  calendarPlans,
  materials,
  goalHistory,
  monthNotes,
  t
}: PlanSearchResultsCardProps) {
  const plans = listOf<CalendarPlanResult>(calendarPlans);
  const materialItems = listOf<MaterialResult>(materials);
  const historyItems = listOf<GoalHistoryResult>(goalHistory);
  const noteItems = listOf<MonthNoteResult>(monthNotes);
  const total = plans.length + materialItems.length + historyItems.length + noteItems.length;

  return (
    <div className="command-inline-card wide plan-search-results">
      <div className="command-card-heading">
        <strong>{t('command.planSearchResults')}</strong>
        <span>{total}</span>
      </div>
      {summary ? <p>{summary}</p> : null}

      {plans.length ? (
        <section className="command-result-section">
          <strong>{t('command.calendarPlans')}</strong>
          <ul className="command-plan-list">
            {plans.map((plan, index) => (
              <li key={plan.id || `${plan.title}-${index}`}>
                <span>{index + 1}. {plan.title || t('command.untitledPlan')}</span>
                <small>
                  {plan.date || t('command.noDate')} {plan.time || '09:00'} - {plan.estimatedMinutes || 30} {t('command.minutes')} - {plan.done ? t('common.done') : t('common.pending')}
                </small>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {historyItems.length ? (
        <section className="command-result-section">
          <strong>{t('command.goalHistory')}</strong>
          <ul className="command-compact-list">
            {historyItems.map((item, index) => (
              <li key={`${item.title}-${index}`}>
                <span>{item.title || item.goal || t('command.untitledPlan')}</span>
                {item.summary ? <small>{item.summary}</small> : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {materialItems.length ? (
        <section className="command-result-section">
          <strong>{t('command.materialResults')}</strong>
          <ul className="command-compact-list">
            {materialItems.map((item, index) => (
              <li key={`${item.title}-${index}`}>
                <span>{item.title || t('command.material')}</span>
                {item.chunk ? <small>{item.chunk}</small> : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {noteItems.length ? (
        <section className="command-result-section">
          <strong>{t('command.monthNotes')}</strong>
          <ul className="command-compact-list">
            {noteItems.map((item, index) => (
              <li key={`${item.year}-${item.month}-${index}`}>
                <span>{item.year}-{String(item.month || 1).padStart(2, '0')}</span>
                {item.content ? <small>{item.content}</small> : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}

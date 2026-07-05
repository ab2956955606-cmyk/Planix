import type { StructuredGoalPlan } from '../../types';

interface InlinePlanDetailCardProps {
  title?: string;
  structuredPlan?: unknown;
  version?: number;
  t: (key: string) => string;
}

function asPlan(value: unknown): StructuredGoalPlan | null {
  if (!value || typeof value !== 'object') return null;
  const plan = value as StructuredGoalPlan;
  return Array.isArray(plan.milestones) ? plan : null;
}

export function InlinePlanDetailCard({ title, structuredPlan, version, t }: InlinePlanDetailCardProps) {
  const plan = asPlan(structuredPlan);

  if (!plan) {
    return (
      <div className="command-inline-card error">
        <strong>{t('command.planDetail')}</strong>
        <p>{t('command.invalidPlanDetail')}</p>
      </div>
    );
  }

  return (
    <div className="command-inline-card wide plan-detail">
      <div className="command-card-heading">
        <strong>{t('command.planDetail')}</strong>
        {version ? <span>v{version}</span> : null}
      </div>
      <div className="inline-plan-detail">
        <h3>{title || plan.goalTitle}</h3>
        {plan.goalDescription ? <p>{plan.goalDescription}</p> : null}
        {plan.milestones.map((milestone, milestoneIndex) => (
          <section className="inline-milestone" key={`${milestone.title}-${milestoneIndex}`}>
            <strong>{milestone.title || `${t('command.milestone')} ${milestoneIndex + 1}`}</strong>
            {milestone.description ? <small>{milestone.description}</small> : null}
            <ul>
              {(milestone.tasks || []).map((task, taskIndex) => (
                <li key={`${task.title}-${taskIndex}`}>
                  <span>{task.title}</span>
                  <small>
                    {task.dueDate || t('command.noDate')} · {task.estimatedMinutes || 60} {t('command.minutes')} · {task.priority || 'medium'}
                  </small>
                  {task.description ? <small>{task.description}</small> : null}
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}

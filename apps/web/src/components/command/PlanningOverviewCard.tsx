import type { CommandThreadMessage } from '../../stores/commandAgentStore';
import { planningStageFromStatus, planningStageTranslationKey, type PlanningStage } from './deepPlanningStatus';
import { ModelUsageBadge } from './ModelUsageBadge';

type Translator = (key: string) => string;

interface PlanningOverviewCardProps {
  messages: CommandThreadMessage[];
  status?: string;
  t: Translator;
}

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function text(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

function messageData(message: CommandThreadMessage | undefined): Record<string, unknown> {
  const payload = message?.payload ?? {};
  const data = record(payload.data);
  return Object.keys(data).length ? data : payload;
}

function latest(messages: CommandThreadMessage[], kind: CommandThreadMessage['kind']): Record<string, unknown> {
  return messageData([...messages].reverse().find((message) => message.kind === kind));
}

function itemText(value: unknown): string {
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value);
  const raw = record(value);
  const primary = text(raw.statement) || text(raw.description) || text(raw.warning) || text(raw.message) || text(raw.question) || text(raw.field) || text(raw.name) || text(raw.title);
  const impact = text(raw.impact) || text(raw.whyItChangesThePlan) || text(raw.whyThisQuestionMatters) || text(raw.consequence);
  return [primary, impact].filter(Boolean).join(' — ');
}

function listText(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map(itemText).filter(Boolean);
}

function factLines(value: unknown): string[] {
  if (Array.isArray(value)) return listText(value);
  const raw = record(value);
  return Object.entries(raw).flatMap(([key, fact]) => {
    if (Array.isArray(fact)) {
      const joined = fact.map(itemText).filter(Boolean).join(' / ');
      return joined ? [`${key}: ${joined}`] : [];
    }
    const rendered = itemText(fact);
    return rendered ? [`${key}: ${rendered}`] : [];
  });
}

function userFieldLabel(key: string, t: Translator): string {
  const labels: Record<string, string> = {
    location: t('command.planningFactLocation'),
    locations: t('command.planningFactLocation'),
    skill: t('command.planningFactSkill'),
    skills: t('command.planningFactSkill'),
    currentLevel: t('command.planningFactCurrentLevel'),
    availableTime: t('command.planningFactAvailableTime'),
    timeCommitmentExpression: t('command.planningFactAvailableTime'),
    timeExpressions: t('command.planningFactAvailableTime'),
    durationExpression: t('command.planningFactDuration'),
    durationExpressions: t('command.planningFactDuration'),
    dateExpression: t('command.planningFactDate'),
    dateExpressions: t('command.planningFactDate'),
    budget: t('command.planningFactBudget'),
    budgetExpression: t('command.planningFactBudget'),
    constraints: t('command.planningFactConstraints'),
    purpose: t('command.planningFactPurpose')
  };
  return labels[key] || '';
}

function userFactLines(value: unknown, t: Translator): string[] {
  if (Array.isArray(value)) return listText(value);
  return Object.entries(record(value)).flatMap(([key, fact]) => {
    const factLabel = userFieldLabel(key, t);
    if (!factLabel) return [];
    const rendered = Array.isArray(fact)
      ? fact.map(itemText).filter(Boolean).join(' / ')
      : itemText(fact);
    return rendered ? [`${factLabel}: ${rendered}`] : [];
  });
}

function userUncertaintyLines(value: unknown, t: Translator): string[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    if (typeof item === 'string') return item.trim() ? [item.trim()] : [];
    const raw = record(item);
    const label = userFieldLabel(text(raw.field), t);
    const impact = text(raw.impact) || text(raw.whyItChangesThePlan) || text(raw.whyThisQuestionMatters) || text(raw.consequence);
    const description = text(raw.description) || text(raw.message) || text(raw.question);
    const rendered = [label, impact || description].filter(Boolean).join(' — ');
    return rendered ? [rendered] : [];
  });
}

function possibleDirection(value: string, t: Translator): string {
  const labels: Record<string, string> = {
    travel: t('command.planningDirectionTravel'),
    career: t('command.planningDirectionCareer'),
    relocation: t('command.planningDirectionRelocation'),
    study: t('command.planningDirectionStudy'),
    learning: t('command.planningDirectionStudy'),
    sports_skill: t('command.planningDirectionSkill'),
    content_creation: t('command.planningDirectionContent'),
    competition: t('command.planningDirectionCompetition'),
    other: t('command.planningDirectionOther')
  };
  if (labels[value]) return labels[value];
  return /^[a-z0-9_]+$/i.test(value) ? '' : value;
}

function firstQuestion(value: unknown): string {
  if (!Array.isArray(value)) return '';
  for (const item of value) {
    const question = typeof item === 'string' ? item : text(record(item).question);
    if (question) return question;
  }
  return '';
}

function recommendedStrategyName(strategy: Record<string, unknown>): string {
  const recommendedId = text(strategy.recommendedStrategyId);
  if (!Array.isArray(strategy.strategies)) return '';
  const candidates = strategy.strategies.map(record);
  const recommended = candidates.find((item) => text(item.id) === recommendedId) ?? candidates[0];
  return text(recommended?.name);
}

function statusStepFloor(status: string | undefined): number {
  if (status === 'waiting_design_approval' || status === 'design_revision') return 4;
  if (
    status === 'waiting_execution_approval' ||
    status === 'execution_revision' ||
    status === 'ready_to_write_calendar' ||
    status === 'waiting_calendar_write_approval' ||
    status === 'written_to_calendar' ||
    status === 'learning_from_feedback'
  ) return 5;
  if (status === 'needs_goal_clarification' || status === 'MODEL_UNAVAILABLE') return 1;
  return 0;
}

function completedStepCount(messages: CommandThreadMessage[], status: string | undefined): number {
  const kinds = new Set(messages.map((message) => message.kind));
  let completed = 0;
  if (['goal_understanding', 'goal_model_updated', 'user_need_contract'].some((kind) => kinds.has(kind as CommandThreadMessage['kind']))) completed = 1;
  if (['reality_assessment_ready', 'memory_insight_brief'].some((kind) => kinds.has(kind as CommandThreadMessage['kind']))) completed = 2;
  if (['evidence_pack_ready', 'resource_brief'].some((kind) => kinds.has(kind as CommandThreadMessage['kind']))) completed = 3;
  if (['strategy_portfolio_ready', 'plan_design_proposal'].some((kind) => kinds.has(kind as CommandThreadMessage['kind']))) completed = 4;
  if (['execution_blueprint_ready', 'execution_plan_draft', 'critique_report_ready'].some((kind) => kinds.has(kind as CommandThreadMessage['kind']))) completed = 5;
  return Math.max(completed, statusStepFloor(status));
}

function nextActionKey(stage: PlanningStage): string {
  const suffix = stage.split('_').map((part) => part[0].toUpperCase() + part.slice(1)).join('');
  return `command.planningNext${suffix}`;
}

export function PlanningOverviewCard({ messages, status, t }: PlanningOverviewCardProps) {
  const understanding = latest(messages, 'goal_understanding');
  const goal = latest(messages, 'goal_model_updated');
  const legacyGoal = latest(messages, 'user_need_contract');
  const reality = latest(messages, 'reality_assessment_ready');
  const evidence = latest(messages, 'evidence_pack_ready');
  const legacyResources = latest(messages, 'resource_brief');
  const strategy = latest(messages, 'strategy_portfolio_ready');
  const legacyStrategy = latest(messages, 'plan_design_proposal');
  const execution = latest(messages, 'execution_blueprint_ready');
  const legacyExecution = latest(messages, 'execution_plan_draft');
  const critique = latest(messages, 'critique_report_ready');
  const stage = planningStageFromStatus(status, messages);

  const understoodIntent = text(understanding.understoodIntent) || text(record(understanding.understoodIntent).summary) || text(record(understanding.understoodIntent).goal);
  const goalStatement = understoodIntent || text(goal.goalStatement) || text(legacyGoal.interpretedGoal) || text(reality.goalRestatement) || t('command.planningUnderstandingPending');
  const facts = userFactLines(understanding.knownFacts, t).length
    ? userFactLines(understanding.knownFacts, t)
    : factLines(goal.knownFacts);
  const warnings = Array.from(new Set([
    ...listText(understanding.consistencyWarnings),
    ...listText(goal.consistencyWarnings)
  ]));
  const uncertainties = userUncertaintyLines(understanding.uncertainties, t).length
    ? userUncertaintyLines(understanding.uncertainties, t)
    : listText(goal.decisionRelevantUnknowns);
  const possibleDomains = listText(understanding.possibleDomains)
    .map((item) => possibleDirection(item, t))
    .filter(Boolean);
  const decisions = [
    possibleDomains.length ? `${t('command.planningPossibleDirections')}: ${possibleDomains.join(' / ')}` : '',
    ...uncertainties.slice(0, 2),
    text(reality.feasibilitySummary),
    [recommendedStrategyName(strategy), text(strategy.recommendationReason)].filter(Boolean).join(' — '),
    [text(legacyStrategy.strategyName), text(legacyStrategy.designRationale)].filter(Boolean).join(' — '),
    text(critique.simulationSummary),
    text(evidence.synthesis),
    text(record(legacyResources.coverage).explanation),
    text(record(execution.narrative).executionLogic),
    text(legacyExecution.scheduleSummary)
  ].filter(Boolean).slice(0, 4);

  const nextQuestion = text(understanding.nextQuestion)
    || firstQuestion(goal.questions)
    || text(record(legacyGoal.pendingQuestion).questionText)
    || firstQuestion(reality.importantQuestions)
    || text(record(strategy.userDecision).question)
    || (status === 'MODEL_UNAVAILABLE' ? t('command.cognitiveModelUnavailableHint') : '')
    || t(nextActionKey(stage));
  const steps = [
    t('command.planningStepUnderstandGoal'),
    t('command.planningStepAnalyzeBackground'),
    t('command.planningStepFindInformation'),
    t('command.planningStepDesignSolution'),
    t('command.planningStepGenerateExecution')
  ];
  const completed = completedStepCount(messages, status);

  return (
    <div className="command-inline-card wide planning-overview-card">
      <header className="planning-overview-stage">
        <span>{t('command.currentStage')}</span>
        <strong>{t(planningStageTranslationKey(stage))}</strong>
      </header>
      <section>
        <h3>{t('command.currentUnderstanding')}</h3>
        <p className="planning-overview-goal">{goalStatement}</p>
        {facts.length ? <ul>{facts.slice(0, 6).map((fact, index) => <li key={`${fact}-${index}`}>{fact}</li>)}</ul> : null}
      </section>
      <section>
        <h3>{t('command.importantDecisions')}</h3>
        {warnings.length ? (
          <div className="planning-consistency-warning" role="alert">
            <strong>{t('command.consistencyWarning')}</strong>
            <ul>{warnings.map((warning, index) => <li key={`${warning}-${index}`}>{warning}</li>)}</ul>
          </div>
        ) : null}
        {status === 'MODEL_UNAVAILABLE' ? <p className="planning-consistency-warning">{t('command.cognitiveModelUnavailable')}</p> : null}
        {decisions.length ? <ul>{decisions.map((decision, index) => <li key={`${decision}-${index}`}>{decision}</li>)}</ul> : <p>{t('command.noImportantDecisions')}</p>}
      </section>
      <section className="planning-next-action">
        <h3>{t('command.nextAction')}</h3>
        <p>{nextQuestion}</p>
      </section>
      <details className="planning-process-summary">
        <summary>
          <strong>{t('command.planningProcess')}</strong>
          <span>✓ {t('command.planningStepsCompleted').replace('{count}', String(completed))}</span>
        </summary>
        <ol>{steps.map((step) => <li key={step}>{step}</li>)}</ol>
      </details>
    </div>
  );
}

export function GoalUnderstandingDetailCard({ data, t }: { data?: unknown; t: Translator }) {
  const raw = record(data);
  const facts = factLines(raw.knownFacts);
  const uncertainties = listText(raw.uncertainties);
  const warnings = listText(raw.consistencyWarnings);
  const error = typeof raw.error === 'string' ? raw.error : Object.keys(record(raw.error)).length ? JSON.stringify(raw.error) : '';
  return (
    <div className="command-inline-card wide goal-understanding-trace">
      <div className="command-card-heading">
        <strong>{t('command.goalUnderstanding')}</strong>
        <span>{text(raw.intentState) || t('common.unknown')}</span>
      </div>
      {text(raw.understoodIntent) ? <p>{text(raw.understoodIntent)}</p> : null}
      {facts.length ? <dl className="command-result-meta"><div><dt>{t('command.knownFacts')}</dt><dd>{facts.join(' / ')}</dd></div></dl> : null}
      {uncertainties.length ? <p>{t('command.uncertainties')}: {uncertainties.join(' / ')}</p> : null}
      {warnings.length ? <p>{t('command.consistencyWarning')}: {warnings.join(' / ')}</p> : null}
      {text(raw.nextQuestion) ? <p>{t('command.nextAction')}: {text(raw.nextQuestion)}</p> : null}
      <small>{t('command.source')}: {text(raw.source) || t('common.unknown')} · {t('command.confidence')}: {typeof raw.confidence === 'number' ? `${Math.round(raw.confidence * 100)}%` : '-'}</small>
      {error ? <small>{t('command.errorType')}: {error}</small> : null}
      {raw.modelUsage ? <ModelUsageBadge usage={raw.modelUsage} t={t} /> : null}
    </div>
  );
}

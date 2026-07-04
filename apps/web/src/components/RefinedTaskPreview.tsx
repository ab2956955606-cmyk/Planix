import { X } from 'lucide-react';
import type { RefinedTask } from '../types';

export function RefinedTaskPreview(props: {
  refinedTask: RefinedTask;
  onDelete?: () => void;
  deleting?: boolean;
  t: (key: string) => string;
}) {
  const { refinedTask, onDelete, deleting, t } = props;
  return (
    <div className="refined-task-panel">
      <div className="refined-task-panel-head">
        <div className="refined-task-summary">
          <span>{t('legacy.refinedObjective')}</span>
          <p>{refinedTask.objective}</p>
          <strong>{t('legacy.refinedEstimatedMinutes')}: {refinedTask.estimatedMinutes}m</strong>
        </div>
        {onDelete && (
          <button
            type="button"
            className="refined-task-delete"
            onClick={onDelete}
            disabled={deleting}
            aria-label={t('legacy.deleteRefinedTask')}
            title={t('legacy.deleteRefinedTask')}
          >
            <X size={14} />
          </button>
        )}
      </div>
      <RefinedList title={t('legacy.refinedSteps')} items={refinedTask.steps} />
      <RefinedList title={t('legacy.refinedChecklist')} items={refinedTask.checklist} />
      <RefinedList title={t('legacy.refinedAcceptanceCriteria')} items={refinedTask.acceptanceCriteria} />
      <div className="refined-task-section">
        <strong>{t('legacy.refinedDeliverable')}</strong>
        <p>{refinedTask.deliverable}</p>
      </div>
      <RefinedList title={t('legacy.refinedRisks')} items={refinedTask.risks} emptyText={t('legacy.refinedNoRisks')} />
      <RefinedList title={t('legacy.refinedFallbackTips')} items={refinedTask.fallbackTips} emptyText={t('legacy.refinedNoFallbackTips')} />
    </div>
  );
}

function RefinedList({ title, items, emptyText }: { title: string; items: string[]; emptyText?: string }) {
  return (
    <div className="refined-task-section">
      <strong>{title}</strong>
      {items.length ? (
        <ul>
          {items.map((item) => <li key={item}>{item}</li>)}
        </ul>
      ) : (
        <p>{emptyText}</p>
      )}
    </div>
  );
}

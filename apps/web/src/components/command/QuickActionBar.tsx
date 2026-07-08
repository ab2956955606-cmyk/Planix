import { CalendarPlus, FileSearch, ListChecks, NotebookPen, PencilLine, Wand2 } from 'lucide-react';

interface QuickActionBarProps {
  disabled?: boolean;
  onSend: (value: string) => void;
  t: (key: string) => string;
}

const actions = [
  { key: 'writeCalendar', textKey: 'command.quickWriteCalendar', messageKey: 'command.quickWriteCalendarMessage', icon: CalendarPlus },
  { key: 'viewPlans', textKey: 'command.quickViewPlans', messageKey: 'command.quickViewPlansMessage', icon: ListChecks },
  { key: 'modifyPlan', textKey: 'command.quickModifyPlan', messageKey: 'command.quickModifyPlanMessage', icon: PencilLine },
  { key: 'refinePlan', textKey: 'command.quickRefinePlan', messageKey: 'command.quickRefinePlanMessage', icon: Wand2 },
  { key: 'searchNotes', textKey: 'command.quickSearchNotes', messageKey: 'command.quickSearchNotesMessage', icon: FileSearch },
  { key: 'recordNote', textKey: 'command.quickRecordNote', messageKey: 'command.quickRecordNoteMessage', icon: NotebookPen }
];

export function QuickActionBar({ disabled, onSend, t }: QuickActionBarProps) {
  return (
    <div className="command-quick-actions" aria-label={t('command.quickActions')}>
      {actions.map((action) => {
        const Icon = action.icon;
        return (
          <button
            key={action.key}
            type="button"
            disabled={disabled}
            title={t(action.textKey)}
            onClick={() => onSend(t(action.messageKey))}
          >
            <Icon size={15} />
            <span>{t(action.textKey)}</span>
          </button>
        );
      })}
    </div>
  );
}

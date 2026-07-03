import { CalendarPanel } from '../components/CalendarPanel';
import { PlanList } from '../components/PlanList';
import type { AppData, Language, Plan } from '../types';

interface CalendarPageProps {
  lang: Language;
  data: AppData;
  selectedDate: string;
  viewDate: Date;
  monthNote: string;
  selectedPlans: Plan[];
  draft: string;
  time: string;
  onViewDateChange: (date: Date) => void;
  onSelectDate: (date: string) => void;
  onMonthNoteChange: (value: string) => void;
  onDraftChange: (value: string) => void;
  onTimeChange: (value: string) => void;
  onAdd: () => void;
  onToggle: (id: string) => void;
  onDelete: (id: string) => void;
  onCompletionChange: (id: string, value: string) => void;
  t: (key: string) => string;
}

export function CalendarPage(props: CalendarPageProps) {
  const {
    lang,
    data,
    selectedDate,
    viewDate,
    monthNote,
    selectedPlans,
    draft,
    time,
    onViewDateChange,
    onSelectDate,
    onMonthNoteChange,
    onDraftChange,
    onTimeChange,
    onAdd,
    onToggle,
    onDelete,
    onCompletionChange,
    t
  } = props;

  return (
    <section className="page-stack calendar-page">
      <CalendarPanel
        lang={lang}
        data={data}
        selectedDate={selectedDate}
        viewDate={viewDate}
        monthNote={monthNote}
        onViewDateChange={onViewDateChange}
        onSelectDate={onSelectDate}
        onMonthNoteChange={onMonthNoteChange}
        t={t}
      />
      <PlanList
        date={selectedDate}
        lang={lang}
        plans={selectedPlans}
        draft={draft}
        time={time}
        onDraftChange={onDraftChange}
        onTimeChange={onTimeChange}
        onAdd={onAdd}
        onToggle={onToggle}
        onDelete={onDelete}
        onCompletionChange={onCompletionChange}
        t={t}
      />
    </section>
  );
}

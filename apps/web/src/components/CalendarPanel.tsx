import { ChevronLeft, ChevronRight, NotebookPen } from 'lucide-react';
import type { AppData, Lang } from '../types';
import { getMonthDays, monthKey, todayISO } from '../utils/date';
import { weekdayLabels } from '../lib/i18n';

interface CalendarPanelProps {
  lang: Lang;
  data: AppData;
  selectedDate: string;
  viewDate: Date;
  monthNote: string;
  onViewDateChange: (date: Date) => void;
  onSelectDate: (date: string) => void;
  onMonthNoteChange: (value: string) => void;
  t: (key: string) => string;
}

export function CalendarPanel(props: CalendarPanelProps) {
  const { lang, data, selectedDate, viewDate, monthNote, onViewDateChange, onSelectDate, onMonthNoteChange, t } = props;
  const today = todayISO();
  const monthTitle = new Intl.DateTimeFormat(lang === 'zh' ? 'zh-CN' : 'en-US', {
    year: 'numeric',
    month: 'long'
  }).format(viewDate);

  function shiftMonth(delta: number) {
    onViewDateChange(new Date(viewDate.getFullYear(), viewDate.getMonth() + delta, 1));
  }

  function statusClass(iso: string) {
    const plans = data[iso]?.plans ?? [];
    if (!plans.length) return '';
    return plans.every((plan) => plan.done) ? 'done-all' : 'has-plan';
  }

  return (
    <section className="surface calendar-panel">
      <div className="section-head">
        <div>
          <span className="eyebrow">{t('calendar')}</span>
          <h2>{monthTitle}</h2>
        </div>
        <div className="icon-row">
          <button className="icon-button" onClick={() => shiftMonth(-1)} aria-label="Previous month"><ChevronLeft size={18} /></button>
          <button className="icon-button" onClick={() => shiftMonth(1)} aria-label="Next month"><ChevronRight size={18} /></button>
        </div>
      </div>
      <div className="weekday-grid">
        {weekdayLabels(lang).map((day) => <span key={day}>{day}</span>)}
      </div>
      <div className="date-grid">
        {getMonthDays(viewDate).map((item) => (
          <button
            key={item.iso}
            className={[
              'date-cell',
              item.muted ? 'muted' : '',
              selectedDate === item.iso ? 'selected' : '',
              today === item.iso ? 'today' : '',
              statusClass(item.iso)
            ].join(' ')}
            onClick={() => onSelectDate(item.iso)}
          >
            <span>{item.day}</span>
          </button>
        ))}
      </div>
      <label className="note-box">
        <span><NotebookPen size={16} />{t('monthNote')} · {monthKey(viewDate)}</span>
        <textarea value={monthNote} onChange={(event) => onMonthNoteChange(event.target.value)} placeholder={t('monthNotePlaceholder')} />
      </label>
    </section>
  );
}

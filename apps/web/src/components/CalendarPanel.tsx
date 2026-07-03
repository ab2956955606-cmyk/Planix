import { useState } from 'react';
import { ChevronDown, ChevronLeft, ChevronRight, ChevronUp, NotebookPen } from 'lucide-react';
import type { AppData, Lang } from '../types';
import { getMonthDays, monthKey, todayISO } from '../utils/date';
import { weekdayLabels } from '../i18n';

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
  const [isCalendarOpen, setIsCalendarOpen] = useState(true);
  const today = todayISO();
  const monthTitle = new Intl.DateTimeFormat(lang, {
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
    <section className={`surface calendar-panel ${isCalendarOpen ? 'is-open' : 'is-collapsed'}`}>
      <button
        className="calendar-collapse-toggle"
        onClick={() => setIsCalendarOpen((current) => !current)}
        aria-label={isCalendarOpen ? t('legacy.collapseCalendar') : t('legacy.expandCalendar')}
        title={isCalendarOpen ? t('legacy.collapseCalendar') : t('legacy.expandCalendar')}
      >
        {isCalendarOpen ? <ChevronDown size={22} /> : <ChevronUp size={22} />}
      </button>

      <div className="calendar-collapsible" aria-hidden={!isCalendarOpen}>
        <div className="section-head">
          <div>
            <span className="eyebrow">{t('legacy.calendar')}</span>
            <h2>{monthTitle}</h2>
          </div>
          <div className="icon-row">
            <button className="icon-button" onClick={() => shiftMonth(-1)} aria-label={t('legacy.previousMonth')}>
              <ChevronLeft size={18} />
            </button>
            <button className="icon-button" onClick={() => shiftMonth(1)} aria-label={t('legacy.nextMonth')}>
              <ChevronRight size={18} />
            </button>
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
          <span><NotebookPen size={16} />{t('legacy.monthNote')} · {monthKey(viewDate)}</span>
          <textarea value={monthNote} onChange={(event) => onMonthNoteChange(event.target.value)} placeholder={t('legacy.monthNotePlaceholder')} />
        </label>
      </div>
    </section>
  );
}

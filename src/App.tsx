import { useEffect, useMemo, useState } from 'react';
import { AIWorkspace } from './components/AIWorkspace';
import { CalendarPanel } from './components/CalendarPanel';
import { Header } from './components/Header';
import { PlanList } from './components/PlanList';
import { useText } from './lib/i18n';
import { ensureDay, loadData, loadLang, loadMonthNote, loadPreferences, saveData, saveLang, saveMonthNote, savePreferences } from './lib/storage';
import type { AppData, Lang, Plan, PlannerTask } from './types';
import { monthKey, todayISO } from './utils/date';

function createId(): string {
  return `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`;
}

export function App() {
  const [lang, setLang] = useState<Lang>(() => loadLang());
  const [data, setData] = useState<AppData>(() => loadData());
  const [selectedDate, setSelectedDate] = useState(() => todayISO());
  const [viewDate, setViewDate] = useState(() => new Date());
  const [monthNote, setMonthNote] = useState(() => loadMonthNote(monthKey(new Date())));
  const [draft, setDraft] = useState('');
  const [time, setTime] = useState(() => `${String(new Date().getHours()).padStart(2, '0')}:00`);
  const [preferences, setPreferences] = useState(() => loadPreferences());
  const t = useText(lang);

  const selectedPlans = useMemo(() => ensureDay(data, selectedDate).plans, [data, selectedDate]);

  useEffect(() => {
    saveData(data);
  }, [data]);

  useEffect(() => {
    saveLang(lang);
    document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en';
  }, [lang]);

  useEffect(() => {
    setMonthNote(loadMonthNote(monthKey(viewDate)));
  }, [viewDate]);

  useEffect(() => {
    savePreferences(preferences);
  }, [preferences]);

  function updateDay(date: string, updater: (plans: Plan[]) => Plan[]) {
    setData((current) => {
      const day = ensureDay(current, date);
      return { ...current, [date]: { plans: updater(day.plans) } };
    });
  }

  function addPlan() {
    const title = draft.trim();
    if (!title) return;
    updateDay(selectedDate, (plans) => [...plans, { id: createId(), time, title, done: false, completion: '', source: 'manual' }]);
    setDraft('');
  }

  function applyAiTasks(tasks: PlannerTask[]) {
    if (!tasks.length) return;
    updateDay(selectedDate, (plans) => [
      ...plans,
      ...tasks.map((task) => ({ id: createId(), time: task.time || '09:00', title: task.title, done: false, completion: task.reason, source: 'ai' as const }))
    ]);
  }

  function selectToday() {
    const today = todayISO();
    setSelectedDate(today);
    setViewDate(new Date());
  }

  return (
    <div className="app-shell">
      <Header lang={lang} onLangChange={setLang} onToday={selectToday} t={t} />
      <main className="layout">
        <div className="left-stack">
          <CalendarPanel
            lang={lang}
            data={data}
            selectedDate={selectedDate}
            viewDate={viewDate}
            monthNote={monthNote}
            onViewDateChange={setViewDate}
            onSelectDate={setSelectedDate}
            onMonthNoteChange={(value) => {
              setMonthNote(value);
              saveMonthNote(monthKey(viewDate), value);
            }}
            t={t}
          />
          <AIWorkspace
            data={data}
            date={selectedDate}
            preferences={preferences}
            onPreferencesChange={setPreferences}
            onApplyTasks={applyAiTasks}
            t={t}
          />
        </div>
        <PlanList
          date={selectedDate}
          lang={lang}
          plans={selectedPlans}
          draft={draft}
          time={time}
          onDraftChange={setDraft}
          onTimeChange={setTime}
          onAdd={addPlan}
          onToggle={(id) => updateDay(selectedDate, (plans) => plans.map((plan) => plan.id === id ? { ...plan, done: !plan.done } : plan))}
          onDelete={(id) => updateDay(selectedDate, (plans) => plans.filter((plan) => plan.id !== id))}
          onCompletionChange={(id, value) => updateDay(selectedDate, (plans) => plans.map((plan) => plan.id === id ? { ...plan, completion: value } : plan))}
          t={t}
        />
      </main>
    </div>
  );
}

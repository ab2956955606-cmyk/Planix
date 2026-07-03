import { useEffect, useMemo, useState } from 'react';
import { CalendarPage } from './pages/CalendarPage';
import { DashboardPage } from './pages/DashboardPage';
import { GoalsPage } from './pages/GoalsPage';
import { NotesPage } from './pages/NotesPage';
import { SettingsPage } from './pages/SettingsPage';
import { RivaShell } from './shell/RivaShell';
import { useAppRoute } from './shell/useAppRoute';
import {
  createPlan as createRemotePlan,
  deletePlan as deleteRemotePlan,
  fetchAiSettings,
  fetchMonthNote,
  fetchPlans,
  saveRemoteMonthNote,
  updatePlan as updateRemotePlan
} from './lib/api';
import { loadLanguage, saveLanguage, useI18n } from './i18n';
import { ensureDay, loadData, loadMonthNote, loadPreferences, saveData, saveMonthNote, savePreferences } from './lib/storage';
import type { AiSettings, AppData, AppliedPlan, InspectorLog, InspectorSnapshot, Language, Plan, PlannerTask } from './types';
import { monthKey, todayISO } from './utils/date';

function createId(): string {
  return `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`;
}

function getYearMonth(date: Date): { year: number; month: number } {
  return { year: date.getFullYear(), month: date.getMonth() + 1 };
}

export function App() {
  const { route, setRoute } = useAppRoute();
  const [language, setLanguage] = useState<Language>(() => loadLanguage());
  const [data, setData] = useState<AppData>(() => loadData());
  const [selectedDate, setSelectedDate] = useState(() => todayISO());
  const [viewDate, setViewDate] = useState(() => new Date());
  const [monthNote, setMonthNote] = useState(() => loadMonthNote(monthKey(new Date())));
  const [draft, setDraft] = useState('');
  const [time, setTime] = useState(() => `${String(new Date().getHours()).padStart(2, '0')}:00`);
  const [preferences, setPreferences] = useState(() => loadPreferences());
  const [agentStatus, setAgentStatus] = useState<InspectorSnapshot['agentStatus']>('idle');
  const [inspectorLogs, setInspectorLogs] = useState<InspectorLog[]>([]);
  const [aiSettings, setAiSettings] = useState<AiSettings | null>(null);
  const t = useI18n(language);

  const selectedPlans = useMemo(() => ensureDay(data, selectedDate).plans, [data, selectedDate]);

  useEffect(() => {
    saveData(data);
  }, [data]);

  useEffect(() => {
    saveLanguage(language);
    document.documentElement.lang = language;
    document.title = t('common.appName');
  }, [language, t]);

  useEffect(() => {
    setInspectorLogs([
      {
        id: 'boot',
        level: 'info',
        message: t('inspector.bootLog'),
        timestamp: Date.now()
      }
    ]);
  }, [language, t]);

  useEffect(() => {
    const key = monthKey(viewDate);
    const localNote = loadMonthNote(key);
    const { year, month } = getYearMonth(viewDate);
    let cancelled = false;
    setMonthNote(localNote);
    fetchMonthNote(year, month)
      .then((remoteNote) => {
        if (cancelled) return;
        setMonthNote((current) => {
          if (remoteNote || !current) {
            saveMonthNote(key, remoteNote);
            return remoteNote;
          }
          return current;
        });
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [viewDate]);

  useEffect(() => {
    let cancelled = false;
    fetchPlans(selectedDate)
      .then((remotePlans) => {
        if (cancelled) return;
        setData((current) => {
          const localPlans = ensureDay(current, selectedDate).plans;
          if (!remotePlans.length && localPlans.length) return current;
          return { ...current, [selectedDate]: { plans: remotePlans } };
        });
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [selectedDate]);

  useEffect(() => {
    savePreferences(preferences);
  }, [preferences]);

  useEffect(() => {
    let cancelled = false;
    fetchAiSettings()
      .then((settings) => {
        if (!cancelled) setAiSettings(settings);
      })
      .catch(() => {
        if (!cancelled) setAiSettings(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function addInspectorLog(log: Omit<InspectorLog, 'id' | 'timestamp'>) {
    setInspectorLogs((current) => [
      { ...log, id: createId(), timestamp: Date.now() },
      ...current.filter((item) => item.id !== 'boot')
    ].slice(0, 8));
  }

  function updateDay(date: string, updater: (plans: Plan[]) => Plan[]) {
    setData((current) => {
      const day = ensureDay(current, date);
      return { ...current, [date]: { plans: updater(day.plans) } };
    });
  }

  function replacePlan(date: string, localId: string, remotePlan: Plan) {
    updateDay(date, (plans) => plans.map((plan) => (plan.id === localId ? remotePlan : plan)));
  }

  function persistCreatedPlans(date: string, plans: Plan[]) {
    void Promise.all(plans.map((plan) => createRemotePlan(date, plan)))
      .then((savedPlans) => {
        updateDay(date, (currentPlans) =>
          currentPlans.map((plan) => {
            const index = plans.findIndex((localPlan) => localPlan.id === plan.id);
            return index >= 0 ? savedPlans[index] : plan;
          })
        );
      })
      .catch(() => undefined);
  }

  function addPlan() {
    const title = draft.trim();
    if (!title) return;
    const date = selectedDate;
    const plan = { id: createId(), time, title, done: false, completion: '', source: 'manual' as const };
    updateDay(date, (plans) => [...plans, plan]);
    void createRemotePlan(date, plan).then((savedPlan) => replacePlan(date, plan.id, savedPlan)).catch(() => undefined);
    setDraft('');
  }

  function applyAiTasks(tasks: PlannerTask[]) {
    if (!tasks.length) return;
    const date = selectedDate;
    const plans = tasks.map((task) => ({ id: createId(), time: task.time || '09:00', title: task.title, done: false, completion: task.reason, source: 'ai' as const }));
    updateDay(date, (currentPlans) => [...currentPlans, ...plans]);
    persistCreatedPlans(date, plans);
  }

  function applyRemotePlans(plans: AppliedPlan[]) {
    const grouped = plans.reduce<Record<string, Plan[]>>((acc, plan) => {
      const { date, ...rest } = plan;
      acc[date] = [...(acc[date] ?? []), rest];
      return acc;
    }, {});
    setData((current) => {
      let next = current;
      for (const [date, datePlans] of Object.entries(grouped)) {
        const existing = ensureDay(next, date).plans;
        const existingIds = new Set(existing.map((plan) => plan.id));
        next = {
          ...next,
          [date]: {
            plans: [...existing, ...datePlans.filter((plan) => !existingIds.has(plan.id))]
          }
        };
      }
      return next;
    });
  }

  function selectToday() {
    const today = todayISO();
    setSelectedDate(today);
    setViewDate(new Date());
  }

  function handleToday() {
    selectToday();
    setRoute('calendar');
  }

  const inspector = useMemo<InspectorSnapshot>(() => ({
    route,
    agentStatus,
    logs: inspectorLogs,
    memory: {
      preferenceSummary: preferences.trim() || t('inspector.emptyMemory'),
      materialCount: 0,
      planCount: selectedPlans.length
    },
    api: {
      mode: aiSettings ? 'backend' : 'unknown',
      hasApiKey: aiSettings?.hasApiKey ?? false,
      provider: aiSettings?.provider ?? 'unknown'
    }
  }), [agentStatus, aiSettings, inspectorLogs, preferences, route, selectedPlans.length, t]);

  const aiPageProps = {
    data,
    date: selectedDate,
    preferences,
    onPreferencesChange: setPreferences,
    onApplyTasks: applyAiTasks,
    onReplanApplied: applyRemotePlans,
    onSettingsChange: setAiSettings,
    language,
    t
  };

  return (
    <RivaShell
      route={route}
      language={language}
      inspector={inspector}
      onRouteChange={setRoute}
      onLanguageChange={setLanguage}
      onToday={handleToday}
      t={t}
    >
      {route === 'dashboard' && (
        <DashboardPage
          date={selectedDate}
          plans={selectedPlans}
          preferences={preferences}
          inspector={inspector}
          onAgentStatusChange={setAgentStatus}
          onLog={addInspectorLog}
          t={t}
        />
      )}
      {route === 'calendar' && (
        <CalendarPage
          lang={language}
          data={data}
          selectedDate={selectedDate}
          viewDate={viewDate}
          monthNote={monthNote}
          selectedPlans={selectedPlans}
          draft={draft}
          time={time}
          onViewDateChange={setViewDate}
          onSelectDate={setSelectedDate}
          onMonthNoteChange={(value) => {
            const key = monthKey(viewDate);
            const { year, month } = getYearMonth(viewDate);
            setMonthNote(value);
            saveMonthNote(key, value);
            void saveRemoteMonthNote(year, month, value).catch(() => undefined);
          }}
          onDraftChange={setDraft}
          onTimeChange={setTime}
          onAdd={addPlan}
          onToggle={(id) => {
            const plan = selectedPlans.find((item) => item.id === id);
            if (!plan) return;
            const done = !plan.done;
            updateDay(selectedDate, (plans) => plans.map((item) => item.id === id ? { ...item, done } : item));
            void updateRemotePlan(id, { done }).then((savedPlan) => replacePlan(selectedDate, id, savedPlan)).catch(() => undefined);
          }}
          onDelete={(id) => {
            updateDay(selectedDate, (plans) => plans.filter((plan) => plan.id !== id));
            void deleteRemotePlan(id).catch(() => undefined);
          }}
          onCompletionChange={(id, value) => {
            updateDay(selectedDate, (plans) => plans.map((plan) => plan.id === id ? { ...plan, completion: value } : plan));
            void updateRemotePlan(id, { completion: value }).catch(() => undefined);
          }}
          t={t}
        />
      )}
      {route === 'notes' && <NotesPage {...aiPageProps} />}
      {route === 'goals' && <GoalsPage {...aiPageProps} />}
      {route === 'settings' && <SettingsPage {...aiPageProps} />}
    </RivaShell>
  );
}

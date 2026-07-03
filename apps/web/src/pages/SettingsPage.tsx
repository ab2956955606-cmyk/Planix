import { AIWorkspace } from '../components/AIWorkspace';
import type { AppliedPlan, AppData, Language, PlannerTask } from '../types';

interface SettingsPageProps {
  data: AppData;
  date: string;
  preferences: string;
  onPreferencesChange: (value: string) => void;
  onApplyTasks: (tasks: PlannerTask[]) => void;
  onReplanApplied: (plans: AppliedPlan[]) => void;
  language: Language;
  t: (key: string) => string;
}

export function SettingsPage(props: SettingsPageProps) {
  return (
    <section className="page-stack">
      <AIWorkspace {...props} section="settings" />
    </section>
  );
}

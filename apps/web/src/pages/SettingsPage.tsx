import { AIWorkspace } from '../components/AIWorkspace';
import type { AppliedPlan, AppData, PlannerTask } from '../types';

interface SettingsPageProps {
  data: AppData;
  date: string;
  preferences: string;
  onPreferencesChange: (value: string) => void;
  onApplyTasks: (tasks: PlannerTask[]) => void;
  onReplanApplied: (plans: AppliedPlan[]) => void;
  t: (key: string) => string;
}

export function SettingsPage(props: SettingsPageProps) {
  return (
    <section className="page-stack">
      <AIWorkspace {...props} section="settings" />
    </section>
  );
}

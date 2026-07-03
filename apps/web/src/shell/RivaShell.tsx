import type { ReactNode } from 'react';
import type { AppRoute, InspectorSnapshot, Language } from '../types';
import { AppMenu } from './AppMenu';
import { InspectorPanel } from './InspectorPanel';

interface RivaShellProps {
  route: AppRoute;
  language: Language;
  inspector: InspectorSnapshot;
  onRouteChange: (route: AppRoute) => void;
  onLanguageChange: (language: Language) => void;
  onToday: () => void;
  t: (key: string) => string;
  children: ReactNode;
}

export function RivaShell(props: RivaShellProps) {
  const { route, language, inspector, onRouteChange, onLanguageChange, onToday, t, children } = props;

  return (
    <div className="riva-shell">
      <AppMenu
        route={route}
        language={language}
        onRouteChange={onRouteChange}
        onLanguageChange={onLanguageChange}
        onToday={onToday}
        t={t}
      />
      <main className="riva-main">{children}</main>
      <InspectorPanel snapshot={inspector} t={t} />
    </div>
  );
}

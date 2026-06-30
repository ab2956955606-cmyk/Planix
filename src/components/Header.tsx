import { Brain, CalendarDays } from 'lucide-react';
import type { Lang } from '../types';

interface HeaderProps {
  lang: Lang;
  onLangChange: (lang: Lang) => void;
  onToday: () => void;
  t: (key: string) => string;
}

export function Header({ lang, onLangChange, onToday, t }: HeaderProps) {
  return (
    <header className="topbar">
      <div className="brand">
        <span className="brand-mark"><Brain size={20} /></span>
        <div>
          <h1>{t('appName')}</h1>
          <p>{t('subtitle')}</p>
        </div>
      </div>
      <div className="topbar-actions">
        <button className="ghost-button" onClick={onToday}>
          <CalendarDays size={16} />
          {t('today')}
        </button>
        <div className="segmented" aria-label="Language">
          <button className={lang === 'zh' ? 'active' : ''} onClick={() => onLangChange('zh')}>中文</button>
          <button className={lang === 'en' ? 'active' : ''} onClick={() => onLangChange('en')}>EN</button>
        </div>
      </div>
    </header>
  );
}

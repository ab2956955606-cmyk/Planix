import { History, Plus, X } from 'lucide-react';
import type { CommandThreadSummary } from '../../types';

interface CommandThreadDrawerProps {
  open: boolean;
  threads: CommandThreadSummary[];
  activeThreadId?: string;
  loading: boolean;
  onOpenChange: (open: boolean) => void;
  onNewThread: () => void;
  onLoadThread: (threadId: string) => void;
  onDeleteThread: (threadId: string) => void;
  t: (key: string) => string;
}

function formatThreadTime(value: string): string {
  const time = Date.parse(value);
  if (!Number.isFinite(time)) return '';
  return new Intl.DateTimeFormat(undefined, {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  }).format(new Date(time));
}

export function CommandThreadDrawer(props: CommandThreadDrawerProps) {
  const {
    open,
    threads,
    activeThreadId,
    loading,
    onOpenChange,
    onNewThread,
    onLoadThread,
    onDeleteThread,
    t
  } = props;

  return (
    <>
      <div className="command-thread-hotzone" onMouseEnter={() => onOpenChange(true)} />
      <button
        type="button"
        className={`command-thread-toggle ${open ? 'active' : ''}`}
        onClick={() => onOpenChange(!open)}
        aria-label={open ? t('command.closeThreads') : t('command.openThreads')}
        title={open ? t('command.closeThreads') : t('command.openThreads')}
      >
        <History size={18} />
      </button>
      <aside
        className={`command-thread-drawer ${open ? 'open' : ''}`}
        onMouseEnter={() => onOpenChange(true)}
        onMouseLeave={() => onOpenChange(false)}
        aria-hidden={!open}
      >
        <div className="command-thread-drawer-head">
          <div>
            <span>{t('command.threadHistory')}</span>
            <strong>{t('command.title')}</strong>
          </div>
          <button
            type="button"
            className="command-thread-new"
            onClick={() => {
              onNewThread();
              onOpenChange(false);
            }}
          >
            <Plus size={16} />
            {t('command.newThread')}
          </button>
        </div>
        <div className="command-thread-list">
          {loading && <p className="command-thread-empty">{t('command.loadingThreads')}</p>}
          {!loading && threads.length === 0 && <p className="command-thread-empty">{t('command.emptyThreads')}</p>}
          {!loading && threads.map((thread) => (
            <div
              className={`command-thread-item ${thread.id === activeThreadId ? 'active' : ''}`}
              key={thread.id}
            >
              <button type="button" className="command-thread-load" onClick={() => onLoadThread(thread.id)}>
                <span>
                  <strong>{thread.title || t('command.untitledThread')}</strong>
                  <small>
                    {thread.currentDraftTitle || `${thread.messageCount} ${t('command.messages')}`}
                  </small>
                </span>
                <em>{formatThreadTime(thread.updatedAt)}</em>
              </button>
              <button
                type="button"
                className="command-thread-delete"
                aria-label={t('command.deleteThread')}
                title={t('command.deleteThread')}
                onClick={() => onDeleteThread(thread.id)}
              >
                <X size={14} />
              </button>
            </div>
          ))}
        </div>
      </aside>
    </>
  );
}

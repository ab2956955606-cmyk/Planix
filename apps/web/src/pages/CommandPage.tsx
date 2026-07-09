import { CommandComposer } from '../components/command/CommandComposer';
import { AgentThread } from '../components/command/AgentThread';
import { CommandThreadDrawer } from '../components/command/CommandThreadDrawer';
import { commandAgentActions, useCommandAgent } from '../stores/commandAgentStore';

interface CommandPageProps {
  t: (key: string) => string;
}

export function CommandPage({ t }: CommandPageProps) {
  const command = useCommandAgent();

  return (
    <section className="command-page" aria-label={t('command.title')}>
      <CommandThreadDrawer
        open={command.drawerOpen}
        threads={command.threads}
        activeThreadId={command.threadId}
        loading={command.loadingThreads}
        onOpenChange={commandAgentActions.setDrawerOpen}
        onNewThread={commandAgentActions.newThread}
        onLoadThread={commandAgentActions.loadThread}
        onDeleteThread={commandAgentActions.removeThread}
        t={t}
      />
      <AgentThread
        messages={command.messages}
        sending={command.sending}
        onApprove={(actionId, decision) => commandAgentActions.approveAction(actionId, decision, t)}
        onSend={(value) => commandAgentActions.sendCommand(value, t)}
        t={t}
      />
      <CommandComposer
        sending={command.sending}
        messages={command.messages}
        mode={command.mode}
        permission={command.permission}
        onSend={(value) => commandAgentActions.sendCommand(value, t)}
        onChatToggle={commandAgentActions.toggleChatMode}
        onWorkbenchToggle={commandAgentActions.toggleWorkbench}
        onPermissionChange={commandAgentActions.setPermission}
        t={t}
      />
    </section>
  );
}

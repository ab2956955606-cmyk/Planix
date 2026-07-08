import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import type { ReactElement } from 'react';

const apiMocks = vi.hoisted(() => ({
  runCommandChat: vi.fn(),
  listCommandThreads: vi.fn()
}));

vi.mock('../lib/api', () => ({
  ApiHttpError: class ApiHttpError extends Error {},
  ApiNetworkError: class ApiNetworkError extends Error {},
  CommandStreamError: class CommandStreamError extends Error {},
  approveCommandAction: vi.fn(),
  deleteCommandThread: vi.fn(),
  fetchCommandThread: vi.fn(),
  listCommandThreads: apiMocks.listCommandThreads,
  runCommandChat: apiMocks.runCommandChat
}));

import { commandAgentActions, useCommandAgent } from './commandAgentStore';

function ModeProbe(): ReactElement {
  const command = useCommandAgent();
  return <span>{command.mode}</span>;
}

function renderMode(): string {
  return renderToStaticMarkup(<ModeProbe />);
}

function MessageKindsProbe(): ReactElement {
  const command = useCommandAgent();
  return <span>{command.messages.map((message) => message.kind || message.role).join(',')}</span>;
}

function renderMessageKinds(): string {
  return renderToStaticMarkup(<MessageKindsProbe />);
}

describe('commandAgentStore workbench mode', () => {
  it('defaults to auto and only sends workbench after manual toggle', async () => {
    apiMocks.runCommandChat.mockResolvedValue(undefined);
    apiMocks.listCommandThreads.mockResolvedValue([]);

    expect(renderMode()).toContain('auto');

    commandAgentActions.toggleWorkbench();
    expect(renderMode()).toContain('workbench');

    await commandAgentActions.sendCommand('Plan my week', (key) => key);
    expect(apiMocks.runCommandChat.mock.calls[0][0]).toMatchObject({
      message: 'Plan my week',
      mode: 'workbench'
    });

    commandAgentActions.toggleWorkbench();
    expect(renderMode()).toContain('auto');

    await commandAgentActions.sendCommand('Plan my month', (key) => key);
    expect(apiMocks.runCommandChat.mock.calls[1][0]).toMatchObject({
      message: 'Plan my month',
      mode: 'auto'
    });
  });

  it('stores new command decision and usage events from the stream', async () => {
    apiMocks.runCommandChat.mockImplementationOnce(async (_payload, handlers) => {
      handlers.onEvent({
        type: 'command_decision',
        intent: 'query_plan',
        confidence: 0.86,
        targetType: 'calendar_date',
        action: 'query',
        decisionSummary: 'View today',
        source: 'llm'
      });
      handlers.onEvent({
        type: 'model_usage',
        usage: { provider: 'test', model: 'router', mode: 'llm', taskType: 'command_decision' }
      });
      handlers.onEvent({ type: 'done', threadId: 'thread-test' });
    });
    apiMocks.listCommandThreads.mockResolvedValue([]);

    commandAgentActions.newThread();
    await commandAgentActions.sendCommand('Today?', (key) => key);

    const html = renderMessageKinds();
    expect(html).toContain('command_decision');
    expect(html).toContain('model_usage');
  });
});

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

function AdvancedTraceProbe(): ReactElement {
  const command = useCommandAgent();
  return <span>{String(command.advancedAgentTrace)}</span>;
}

describe('commandAgentStore workbench mode', () => {
  it('keeps advanced agent trace off by default and toggles it independently', () => {
    commandAgentActions.setAdvancedAgentTrace(false);
    expect(renderToStaticMarkup(<AdvancedTraceProbe />)).toContain('false');
    commandAgentActions.setAdvancedAgentTrace(true);
    expect(renderToStaticMarkup(<AdvancedTraceProbe />)).toContain('true');
    commandAgentActions.setAdvancedAgentTrace(false);
  });

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

  it('stores deep planning session events from the stream for replay', async () => {
    apiMocks.runCommandChat.mockImplementationOnce(async (_payload, handlers) => {
      handlers.onEvent({ type: 'planning_session_started', sessionId: 'session-1', status: 'waiting_design_approval' });
      handlers.onEvent({
        type: 'goal_understanding',
        sessionId: 'session-1',
        intentState: 'clear_goal',
        understoodIntent: 'Learn Python',
        possibleDomains: ['learning'],
        knownFacts: { subject: 'Python' },
        uncertainties: [],
        consistencyWarnings: [],
        nextQuestion: '',
        confidence: 0.9,
        source: 'llm'
      });
      handlers.onEvent({
        type: 'goal_completion_updated',
        sessionId: 'session-1',
        businessStatus: 'strategy_pending',
        runtimeStatus: 'running',
        data: {
          complete: true,
          blockingUnknowns: [],
          optionalUnknowns: ['Preferred framework'],
          nextStage: 'strategy'
        }
      });
      handlers.onEvent({
        type: 'user_need_contract',
        sessionId: 'session-1',
        data: { interpretedGoal: 'Python plan', canMoveToDesign: true }
      });
      handlers.onEvent({
        type: 'memory_insight_brief',
        sessionId: 'session-1',
        data: { memoryHits: {}, planningInsights: {}, confidence: 0.5 }
      });
      handlers.onEvent({
        type: 'resource_brief',
        sessionId: 'session-1',
        data: { coverage: { status: 'partial', explanation: 'Some resources found.' }, resourceCandidates: [] }
      });
      handlers.onEvent({
        type: 'plan_design_proposal',
        sessionId: 'session-1',
        data: { strategyName: 'Project-driven', phases: [], status: 'waiting_user_approval' }
      });
      handlers.onEvent({
        type: 'execution_plan_draft',
        sessionId: 'session-1',
        data: { tasks: [], status: 'waiting_user_approval' }
      });
      handlers.onEvent({
        type: 'learning_update',
        sessionId: 'session-1',
        data: { feedbackType: 'resource_feedback', insight: 'Replace resource' }
      });
      handlers.onEvent({ type: 'planning_session_status', sessionId: 'session-1', status: 'waiting_execution_approval' });
      handlers.onEvent({ type: 'done', threadId: 'thread-planning' });
    });
    apiMocks.listCommandThreads.mockResolvedValue([]);

    commandAgentActions.newThread();
    await commandAgentActions.sendCommand('Plan Python', (key) => key);

    const html = renderMessageKinds();
    expect(html).toContain('planning_session_started');
    expect(html).toContain('goal_understanding');
    expect(html).toContain('goal_completion_updated');
    expect(html).toContain('user_need_contract');
    expect(html).toContain('memory_insight_brief');
    expect(html).toContain('resource_brief');
    expect(html).toContain('plan_design_proposal');
    expect(html).toContain('execution_plan_draft');
    expect(html).toContain('learning_update');
    expect(html).toContain('planning_session_status');
  });
});

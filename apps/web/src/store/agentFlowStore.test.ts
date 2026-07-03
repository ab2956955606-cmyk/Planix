import { afterEach, describe, expect, it, vi } from 'vitest';
import { agentFlowActions, getAgentFlowSnapshot } from './agentFlowStore';

describe('agentFlowStore', () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    agentFlowActions.resetFlow();
  });

  it('applies runtime events without old demo tool names', () => {
    agentFlowActions.resetFlow();

    agentFlowActions.applyRuntimeEvent({
      runId: 'runtime-1',
      sequence: 1,
      type: 'node',
      nodeId: 'input',
      nodeType: 'input',
      title: 'Input',
      content: '帮我规划一个 python 学习计划',
      status: 'done'
    });
    agentFlowActions.applyRuntimeEvent({
      runId: 'runtime-1',
      sequence: 2,
      type: 'tool',
      nodeId: 'tool-materials',
      nodeType: 'tool',
      title: 'search_materials',
      status: 'done',
      toolCall: {
        name: 'search_materials',
        input: { query: 'python 学习计划' },
        output: [{ title: 'Python notes' }],
        latencyMs: 12,
        writeMode: 'readonly'
      }
    });

    const serialized = JSON.stringify(getAgentFlowSnapshot().nodes);
    expect(serialized).toContain('search_materials');
    expect(serialized).not.toContain('plan_context_lookup');
    expect(serialized).not.toContain('ui-mock');
  });

  it('shows explicit fallback notice in local demo mode', async () => {
    vi.useFakeTimers();
    vi.stubGlobal('document', { documentElement: { lang: 'zh-CN' } });

    const run = agentFlowActions.runDemoFlow('帮我规划一个 python 学习计划', { fallback: true });
    await vi.runAllTimersAsync();
    await run;

    const serialized = JSON.stringify(getAgentFlowSnapshot().nodes);
    expect(serialized).toContain('当前使用本地规划模板生成，后端 Runtime 未连接');
    expect(serialized).toContain('search_materials');
    expect(serialized).not.toContain('plan_context_lookup');
    expect(serialized).not.toContain('ui-mock');
  });
});

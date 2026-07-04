import { useSyncExternalStore } from 'react';
import { runAgentRuntime } from '../lib/api';
import type {
  AgentFlowNode,
  AgentRunRequest,
  AgentRuntimeEvent,
  AgentRuntimeToolCall,
  ModelKnowledgeDecision
} from '../types';

type AgentFlowState = {
  nodes: AgentFlowNode[];
  traceVisible: boolean;
  isRunning: boolean;
  runId: number;
  runtimeRunId: string;
  lastPrompt: string;
};

const listeners = new Set<() => void>();

let state: AgentFlowState = {
  nodes: [],
  traceVisible: false,
  isRunning: false,
  runId: 0,
  runtimeRunId: '',
  lastPrompt: ''
};

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => globalThis.setTimeout(resolve, ms));
}

function emit() {
  listeners.forEach((listener) => listener());
}

function updateState(updater: (current: AgentFlowState) => AgentFlowState) {
  state = updater(state);
  emit();
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function getSnapshot() {
  return state;
}

function now() {
  return Date.now();
}

function getDemoCopy() {
  const isChinese = typeof document !== 'undefined' && document.documentElement.lang === 'zh-CN';
  return isChinese
    ? {
        fallbackNotice: '当前使用本地规划模板生成，后端 Runtime 未连接。',
        planChunks: [
          '读取目标，并拆成安全的规划步骤。\n',
          '优先使用只读工具读取资料、日程和偏好记忆。\n',
          '生成任务预览，不自动写入用户日历。'
        ],
        toolPreview: '本地规划模板工具预览。',
        observation: '本地模式只展示安全工具路由，不会修改真实数据。',
        outputChunks: [
          '已生成一个本地结构化规划：先明确目标和基础水平，再安排每日学习任务、练习项目和复盘节奏。',
          '后端 Runtime 连接恢复后，这里会切换为真实 NDJSON 事件流。'
        ],
        matches: ['资料库', '今日计划', '偏好记忆', '任务预览']
      }
    : {
        fallbackNotice: 'Local planning template is active; backend Runtime is not connected.',
        planChunks: [
          'Read the goal and split it into safe planning steps.\n',
          'Use read-only tools for materials, plans, and preference memory.\n',
          'Generate task previews without writing to the calendar.'
        ],
        toolPreview: 'Local planning template tool preview.',
        observation: 'Local mode shows safe tool routing without modifying real data.',
        outputChunks: [
          'A local structured plan is ready: clarify the target and baseline, then schedule daily study, practice projects, and review checkpoints. ',
          'When backend Runtime reconnects, this panel will switch back to real NDJSON events.'
        ],
        matches: ['materials', 'today plans', 'preference memory', 'task preview']
      };
}

function createNode(partial: Omit<AgentFlowNode, 'timestamp'>): AgentFlowNode {
  return {
    ...partial,
    timestamp: now()
  };
}

function pushNode(node: AgentFlowNode) {
  updateState((current) => ({
    ...current,
    nodes: [...current.nodes, node]
  }));
}

function updateNode(id: string, patch: Partial<AgentFlowNode>) {
  updateState((current) => ({
    ...current,
    nodes: current.nodes.map((node) => (node.id === id ? { ...node, ...patch } : node))
  }));
}

function appendNodeContent(id: string, text: string) {
  updateState((current) => ({
    ...current,
    nodes: current.nodes.map((node) => {
      if (node.id !== id) return node;
      const previous = node.content;
      const currentContent = `${previous}${text}`;
      return {
        ...node,
        content: currentContent,
        diff: {
          previous,
          current: currentContent,
          changedAt: now()
        }
      };
    })
  }));
}

function setExpanded(id: string, expanded: boolean) {
  updateState((current) => ({
    ...current,
    nodes: current.nodes.map((node) => {
      if (node.id !== id || !node.toolCall) return node;
      return {
        ...node,
        toolCall: {
          ...node.toolCall,
          expanded
        }
      };
    })
  }));
}

function setTraceVisible(traceVisible: boolean) {
  updateState((current) => ({ ...current, traceVisible }));
}

function resetFlow() {
  updateState((current) => ({
    ...current,
    nodes: [],
    traceVisible: false,
    isRunning: false,
    runId: current.runId + 1,
    runtimeRunId: ''
  }));
}

async function runDemoFlow(prompt: string, options: { fallback?: boolean } = {}) {
  const trimmedPrompt = prompt.trim();
  const runId = state.runId + 1;
  const copy = getDemoCopy();

  updateState((current) => ({
    ...current,
    nodes: [],
    traceVisible: true,
    isRunning: true,
    runId,
    runtimeRunId: '',
    lastPrompt: trimmedPrompt
  }));

  const isCurrentRun = () => state.runId === runId;

  const inputId = `input-${runId}`;
  pushNode(createNode({
    id: inputId,
    type: 'input',
    title: 'Input',
    content: trimmedPrompt,
    status: 'done'
  }));

  if (options.fallback) {
    pushNode(createNode({
      id: `fallback-${runId}`,
      type: 'observation',
      title: 'Local Planning Template',
      content: copy.fallbackNotice,
      status: 'done'
    }));
  }

  await delay(160);
  if (!isCurrentRun()) return;

  const planId = `plan-${runId}`;
  pushNode(createNode({
    id: planId,
    type: 'reasoning',
    title: 'Execution Plan',
    content: '',
    status: 'running'
  }));

  for (const chunk of copy.planChunks) {
    await delay(260);
    if (!isCurrentRun()) return;
    appendNodeContent(planId, chunk);
  }
  updateNode(planId, { status: 'done' });

  await delay(180);
  if (!isCurrentRun()) return;

  const toolId = `tool-${runId}`;
  pushNode(createNode({
    id: toolId,
    type: 'tool',
    title: 'search_materials',
    content: copy.toolPreview,
    status: 'running',
    toolCall: {
      name: 'search_materials',
      input: JSON.stringify({ query: trimmedPrompt.slice(0, 96), topK: 3 }, null, 2),
      output: '',
      latencyMs: 0,
      expanded: true,
      writeMode: 'readonly'
    }
  }));

  await delay(360);
  if (!isCurrentRun()) return;
  updateNode(toolId, {
    status: 'done',
    toolCall: {
      name: 'search_materials',
      input: JSON.stringify({ query: trimmedPrompt.slice(0, 96), topK: 3 }, null, 2),
      output: JSON.stringify({
        mode: 'local-template',
        matches: copy.matches
      }, null, 2),
      latencyMs: 128,
      expanded: true,
      writeMode: 'readonly'
    }
  });

  await delay(180);
  if (!isCurrentRun()) return;

  const observationId = `observation-${runId}`;
  pushNode(createNode({
    id: observationId,
    type: 'observation',
    title: 'Observation',
    content: '',
    status: 'running'
  }));
  await delay(220);
  if (!isCurrentRun()) return;
  appendNodeContent(observationId, copy.observation);
  updateNode(observationId, { status: 'done' });

  await delay(180);
  if (!isCurrentRun()) return;

  const outputId = `output-${runId}`;
  pushNode(createNode({
    id: outputId,
    type: 'output',
    title: 'Output',
    content: '',
    status: 'running'
  }));

  for (const chunk of copy.outputChunks) {
    await delay(280);
    if (!isCurrentRun()) return;
    appendNodeContent(outputId, chunk);
  }

  updateNode(outputId, { status: 'done' });
  updateState((current) => (current.runId === runId ? { ...current, isRunning: false } : current));
}

function replayFlow() {
  const prompt = state.lastPrompt || 'Planix demo run';
  return runDemoFlow(prompt);
}

function toolValueToText(value: unknown): string {
  if (value === undefined || value === null) return '';
  if (typeof value === 'string') return value;
  return JSON.stringify(value, null, 2);
}

function runtimeToolToFlowTool(toolCall: AgentRuntimeToolCall) {
  return {
    name: toolCall.name,
    input: toolValueToText(toolCall.input),
    output: runtimeToolOutputToText(toolCall),
    latencyMs: toolCall.latencyMs ?? 0,
    expanded: true,
    writeMode: toolCall.writeMode,
    modelKnowledgeDecision: extractModelKnowledgeDecision(toolCall),
    raw: toolCall
  };
}

function runtimeToolOutputToText(toolCall: AgentRuntimeToolCall): string {
  if (toolCall.name === 'get_memory') {
    return formatMemoryToolOutput(toolCall.output);
  }
  if (toolCall.name === 'propose_tasks') {
    return formatProposalToolOutput(toolCall.output);
  }
  return toolValueToText(toolCall.output);
}

function formatMemoryToolOutput(output: unknown): string {
  if (!isRecord(output)) return toolValueToText(output);
  return [
    '偏好记忆 / Preference Memory',
    toolValueToText(output.preferenceMemory ?? {}),
    '',
    '历史记忆 / History Memory',
    toolValueToText(output.historyMemory ?? {})
  ].join('\n');
}

function formatProposalToolOutput(output: unknown): string {
  if (!isRecord(output)) return toolValueToText(output);
  const sections = [
    `mode: ${String(output.mode ?? 'local_fallback')}`,
    '',
    'memoryContextSummary',
    String(output.memoryContextSummary ?? ''),
    '',
    'structuredPlan',
    toolValueToText(output.structuredPlan ?? {}),
    '',
    'tasks preview',
    toolValueToText(output.tasks ?? []),
    '',
    'sources',
    toolValueToText(output.sources ?? [])
  ];
  if (output.fallbackReason || output.errorType || output.baseUrlHost) {
    sections.push('', 'diagnostics', toolValueToText({
      fallbackReason: output.fallbackReason,
      errorType: output.errorType,
      baseUrlHost: output.baseUrlHost
    }));
  }
  return sections.join('\n');
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function extractModelKnowledgeDecision(toolCall: AgentRuntimeToolCall): ModelKnowledgeDecision | undefined {
  const candidates = [
    toolCall.modelKnowledgeDecision,
    isRecord(toolCall.output) ? toolCall.output.modelKnowledgeDecision : undefined,
    isRecord(toolCall.input) ? toolCall.input.modelKnowledgeDecision : undefined,
    isRecord(toolCall.raw?.output) ? toolCall.raw.output.modelKnowledgeDecision : undefined,
    isRecord(toolCall.raw?.input) ? toolCall.raw.input.modelKnowledgeDecision : undefined
  ];
  for (const candidate of candidates) {
    if (!isRecord(candidate) || typeof candidate.shouldEnrich !== 'boolean') continue;
    return {
      shouldEnrich: candidate.shouldEnrich,
      triggerReason: typeof candidate.triggerReason === 'string'
        ? candidate.triggerReason as ModelKnowledgeDecision['triggerReason']
        : null,
      localSourceCount: numberOrUndefined(candidate.localSourceCount),
      relevantSourceCount: numberOrUndefined(candidate.relevantSourceCount),
      matchedKeywords: stringArrayOrUndefined(candidate.matchedKeywords),
      missingKeywords: stringArrayOrUndefined(candidate.missingKeywords)
    };
  }
  return undefined;
}

function numberOrUndefined(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined;
}

function stringArrayOrUndefined(value: unknown): string[] | undefined {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : undefined;
}

function ensureRuntimeRun(event: AgentRuntimeEvent): boolean {
  if (!state.runtimeRunId) {
    updateState((current) => ({ ...current, runtimeRunId: event.runId }));
    return true;
  }
  return state.runtimeRunId === event.runId;
}

function upsertRuntimeNode(event: AgentRuntimeEvent) {
  const nodeId = event.nodeId || `${event.nodeType || 'output'}-${event.sequence}`;
  const nodeType = event.nodeType || 'output';
  updateState((current) => {
    const existing = current.nodes.find((node) => node.id === nodeId);
    const nextNode: AgentFlowNode = {
      id: nodeId,
      type: nodeType,
      title: event.title || nodeType,
      content: event.content || '',
      status: event.status || 'pending',
      timestamp: now()
    };
    return {
      ...current,
      nodes: existing
        ? current.nodes.map((node) => (
            node.id === nodeId
              ? {
                  ...node,
                  type: nodeType,
                  title: event.title || node.title,
                  content: event.content ?? node.content,
                  status: event.status || node.status
                }
              : node
          ))
        : [...current.nodes, nextNode]
    };
  });
}

function applyRuntimeEvent(event: AgentRuntimeEvent) {
  if (!ensureRuntimeRun(event)) return;
  if (event.type === 'node') {
    upsertRuntimeNode(event);
    return;
  }
  if (event.type === 'delta' && event.nodeId && event.delta) {
    appendNodeContent(event.nodeId, event.delta);
    return;
  }
  if (event.type === 'tool' && event.nodeId && event.toolCall) {
    upsertRuntimeNode({ ...event, type: 'node', nodeType: 'tool', status: event.status || 'done' });
    updateNode(event.nodeId, {
      status: event.status || 'done',
      toolCall: runtimeToolToFlowTool(event.toolCall)
    });
    return;
  }
  if (event.type === 'status' && event.nodeId && event.status) {
    updateNode(event.nodeId, { status: event.status });
    return;
  }
  if (event.type === 'final') {
    updateState((current) => ({ ...current, isRunning: false }));
    if (event.nodeId && event.content) {
      updateNode(event.nodeId, { status: 'done' });
    }
    return;
  }
  if (event.type === 'error') {
    updateState((current) => ({ ...current, isRunning: false }));
    const nodeId = event.nodeId || `error-${event.sequence}`;
    upsertRuntimeNode({
      ...event,
      type: 'node',
      nodeId,
      nodeType: 'output',
      title: 'Error',
      content: event.error || 'Runtime error',
      status: 'error'
    });
  }
}

async function runRuntimeFlow(
  payload: AgentRunRequest,
  callbacks: {
    onFinal?: (content: string) => void;
    onDone?: () => void;
    onError?: (error: Error) => void;
  } = {}
) {
  const runId = state.runId + 1;
  updateState((current) => ({
    ...current,
    nodes: [],
    traceVisible: true,
    isRunning: true,
    runId,
    runtimeRunId: '',
    lastPrompt: payload.input
  }));

  try {
    await runAgentRuntime(payload, {
      onEvent: (event) => {
        if (state.runId !== runId) return;
        applyRuntimeEvent(event);
        if (event.type === 'final' && event.content) {
          callbacks.onFinal?.(event.content);
        }
      },
      onDone: () => {
        if (state.runId === runId) callbacks.onDone?.();
      }
    });
  } catch (err) {
    if (state.runId !== runId) return;
    const error = err instanceof Error ? err : new Error(String(err));
    callbacks.onError?.(error);
    await runDemoFlow(payload.input, { fallback: true });
    callbacks.onFinal?.(getDemoCopy().fallbackNotice);
    callbacks.onDone?.();
  } finally {
    updateState((current) => ({ ...current, isRunning: false }));
  }
}

export function useAgentFlow() {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}

export function getAgentFlowSnapshot() {
  return getSnapshot();
}

export const agentFlowActions = {
  resetFlow,
  pushNode,
  updateNode,
  appendNodeContent,
  setExpanded,
  setTraceVisible,
  applyRuntimeEvent,
  runRuntimeFlow,
  runDemoFlow,
  replayFlow
};

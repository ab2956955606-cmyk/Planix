import { useSyncExternalStore } from 'react';
import {
  ApiHttpError,
  ApiNetworkError,
  CommandStreamError,
  approveCommandAction,
  deleteCommandThread,
  fetchCommandThread,
  listCommandThreads,
  runCommandChat,
  type CommandChatEvent
} from '../lib/api';
import type { CommandMessage, CommandMode, CommandPermission, CommandThreadSummary } from '../types';
import { todayISO } from '../utils/date';

export interface CommandThreadMessage {
  id: string;
  role: 'user' | 'assistant' | 'card';
  content: string;
  createdAt: number;
  kind?: 'error' | 'runtime' | 'summary' | 'plan_detail' | 'refined_tasks_result' | 'calendar_preview' | 'approval' | 'calendar_write_result' | 'command_decision' | 'plan_search_results' | 'memory_search_results' | 'note_search_results' | 'plan_patch_preview' | 'plan_patch_result' | 'memory_write_preview' | 'memory_write_result' | 'note_write_preview' | 'note_write_result' | 'model_usage' | 'clarify_question' | 'execution_result';
  status?: 'running' | 'success' | 'error';
  title?: string;
  draftId?: string;
  actionId?: string;
  payload?: Record<string, unknown>;
  streaming?: boolean;
}

type CommandAgentState = {
  threadId?: string;
  messages: CommandThreadMessage[];
  threads: CommandThreadSummary[];
  permission: CommandPermission;
  mode: CommandMode;
  sending: boolean;
  drawerOpen: boolean;
  loadingThreads: boolean;
};

const listeners = new Set<() => void>();

let state: CommandAgentState = {
  messages: [],
  threads: [],
  permission: 'low',
  mode: 'auto',
  sending: false,
  drawerOpen: false,
  loadingThreads: false
};

function emit() {
  listeners.forEach((listener) => listener());
}

function updateState(updater: (current: CommandAgentState) => CommandAgentState) {
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

function createId(prefix: string): string {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

function addMessage(message: Omit<CommandThreadMessage, 'id' | 'createdAt'>): string {
  const id = createId(message.role);
  updateState((current) => ({
    ...current,
    messages: [
      ...current.messages,
      { ...message, id, createdAt: Date.now() }
    ]
  }));
  return id;
}

function replaceMessage(id: string, patch: Partial<CommandThreadMessage>) {
  updateState((current) => ({
    ...current,
    messages: current.messages.map((message) => (
      message.id === id ? { ...message, ...patch } : message
    ))
  }));
}

function appendAssistantDelta(id: string, delta: string) {
  updateState((current) => ({
    ...current,
    messages: current.messages.map((message) => (
      message.id === id ? { ...message, content: `${message.content}${delta}` } : message
    ))
  }));
}

const CARD_KINDS = new Set([
  'error',
  'runtime',
  'summary',
  'plan_detail',
  'refined_tasks_result',
  'calendar_preview',
  'approval',
  'calendar_write_result',
  'command_decision',
  'plan_search_results',
  'memory_search_results',
  'note_search_results',
  'plan_patch_preview',
  'plan_patch_result',
  'memory_write_preview',
  'memory_write_result',
  'note_write_preview',
  'note_write_result',
  'model_usage',
  'clarify_question',
  'execution_result'
]);

function toThreadMessage(message: CommandMessage): CommandThreadMessage {
  const role = message.role === 'card' ? 'card' : message.role === 'user' ? 'user' : 'assistant';
  const kind = CARD_KINDS.has(message.kind || '') ? message.kind as CommandThreadMessage['kind'] : undefined;
  return {
    id: message.id,
    role,
    content: message.content,
    createdAt: Number.isFinite(Date.parse(message.createdAt)) ? Date.parse(message.createdAt) : Date.now(),
    kind,
    status: kind === 'error' ? 'error' : kind ? 'success' : undefined,
    title: message.payload?.title ? String(message.payload.title) : undefined,
    draftId: message.payload?.draftId ? String(message.payload.draftId) : undefined,
    actionId: message.payload?.actionId ? String(message.payload.actionId) : undefined,
    payload: message.payload
  };
}

function setPermission(permission: CommandPermission) {
  updateState((current) => ({ ...current, permission }));
}

function toggleChatMode() {
  updateState((current) => ({
    ...current,
    mode: current.mode === 'chat' ? 'auto' : 'chat'
  }));
}

function toggleWorkbench() {
  updateState((current) => ({
    ...current,
    mode: current.mode === 'workbench' ? 'auto' : 'workbench'
  }));
}

function setDrawerOpen(drawerOpen: boolean) {
  updateState((current) => ({ ...current, drawerOpen }));
  if (drawerOpen) {
    void refreshThreads();
  }
}

async function refreshThreads() {
  updateState((current) => ({ ...current, loadingThreads: true }));
  try {
    const threads = await listCommandThreads(50);
    updateState((current) => ({ ...current, threads, loadingThreads: false }));
  } catch {
    updateState((current) => ({ ...current, loadingThreads: false }));
  }
}

function newThread() {
  updateState((current) => ({
    ...current,
    threadId: undefined,
    messages: []
  }));
  void refreshThreads();
}

async function loadThread(threadId: string) {
  if (!threadId || state.sending) return;
  updateState((current) => ({ ...current, sending: true }));
  try {
    const thread = await fetchCommandThread(threadId);
    updateState((current) => ({
      ...current,
      threadId: thread.id,
      messages: thread.messages.map(toThreadMessage),
      sending: false,
      drawerOpen: false
    }));
    void refreshThreads();
  } catch (err) {
    addMessage({
      role: 'card',
      kind: 'error',
      content: commandErrorText(err)
    });
    updateState((current) => ({ ...current, sending: false }));
  }
}

async function removeThread(threadId: string) {
  if (!threadId || state.sending) return;
  try {
    await deleteCommandThread(threadId);
    updateState((current) => ({
      ...current,
      threadId: current.threadId === threadId ? undefined : current.threadId,
      messages: current.threadId === threadId ? [] : current.messages,
      threads: current.threads.filter((thread) => thread.id !== threadId)
    }));
    void refreshThreads();
  } catch (err) {
    addMessage({
      role: 'card',
      kind: 'error',
      content: commandErrorText(err)
    });
  }
}

function commandErrorText(error: unknown): string {
  if (error instanceof ApiHttpError && error.status === 404) {
    return 'Command 接口未加载，请重启后端服务';
  }
  if (error instanceof ApiNetworkError) {
    return '后端服务未启动或连接失败';
  }
  if (error instanceof CommandStreamError) {
    return error.message || 'Command 执行流中断，请重启后端服务后重试';
  }
  return error instanceof Error ? error.message : String(error);
}

function addEventCard(event: CommandChatEvent, t: (key: string) => string) {
  if (event.type === 'runtime_started') {
    addMessage({
      role: 'card',
      kind: 'runtime',
      status: 'running',
      title: t('command.execution'),
      content: event.message
    });
  }
  if (event.type === 'runtime_event') {
    addMessage({
      role: 'card',
      kind: 'runtime',
      status: event.status,
      title: event.name,
      content: event.summary || event.name
    });
  }
  if (event.type === 'draft_created') {
    addMessage({
      role: 'card',
      kind: 'runtime',
      status: 'success',
      title: t('command.hiddenDraft'),
      content: `${t('command.hiddenDraftCreated')} v${event.version}`,
      draftId: event.draftId,
      payload: { ...event }
    });
  }
  if (event.type === 'summary') {
    addMessage({
      role: 'card',
      kind: 'summary',
      status: 'success',
      title: t('command.planSummary'),
      content: event.text,
      draftId: event.draftId,
      payload: { ...event }
    });
  }
  if (event.type === 'plan_detail') {
    addMessage({
      role: 'card',
      kind: 'plan_detail',
      status: 'success',
      title: event.title,
      content: event.title,
      draftId: event.draftId,
      payload: { ...event }
    });
  }
  if (event.type === 'refinement_started') {
    addMessage({
      role: 'card',
      kind: 'runtime',
      status: 'running',
      title: t('command.refiningTasks'),
      content: `${t('command.refiningTasksCount')} ${event.total}`,
      draftId: event.draftId,
      payload: { ...event }
    });
  }
  if (event.type === 'refined_tasks_result') {
    addMessage({
      role: 'card',
      kind: 'refined_tasks_result',
      status: event.failed > 0 ? 'error' : 'success',
      title: t('command.refinedTasksResult'),
      content: `${t('command.refinedSucceeded')} ${event.succeeded} · ${t('command.failed')} ${event.failed}`,
      draftId: event.draftId,
      payload: { ...event }
    });
  }
  if (event.type === 'calendar_plan_preview') {
    addMessage({
      role: 'card',
      kind: 'calendar_preview',
      status: 'running',
      title: t('command.calendarPreviewTitle'),
      content: event.title,
      draftId: event.draftId,
      actionId: event.actionId,
      payload: { ...event }
    });
  }
  if (event.type === 'approval_required') {
    addMessage({
      role: 'card',
      kind: 'approval',
      status: 'running',
      title: t('command.approvalRequired'),
      content: event.summary,
      draftId: event.draftId,
      actionId: event.actionId,
      payload: { ...event }
    });
  }
  if (event.type === 'calendar_write_result') {
    addMessage({
      role: 'card',
      kind: 'calendar_write_result',
      status: event.failed > 0 ? 'error' : 'success',
      title: t('command.calendarWriteResult'),
      content: `${t('command.created')} ${event.created} · ${t('command.updated')} ${event.updated} · ${t('command.failed')} ${event.failed}`,
      actionId: event.actionId,
      payload: { ...event }
    });
  }
  if (event.type === 'command_decision') {
    addMessage({
      role: 'card',
      kind: 'command_decision',
      status: 'success',
      title: t('command.intentDecision'),
      content: event.decisionSummary || event.intent,
      payload: { ...event }
    });
  }
  if (event.type === 'plan_search_results') {
    addMessage({
      role: 'card',
      kind: 'plan_search_results',
      status: 'success',
      title: t('command.planSearchResults'),
      content: event.summary,
      payload: { ...event }
    });
  }
  if (event.type === 'memory_search_results') {
    addMessage({
      role: 'card',
      kind: 'memory_search_results',
      status: 'success',
      title: t('command.memorySearchResults'),
      content: event.summary,
      payload: { ...event }
    });
  }
  if (event.type === 'note_search_results') {
    addMessage({
      role: 'card',
      kind: 'note_search_results',
      status: 'success',
      title: t('command.noteSearchResults'),
      content: event.summary,
      payload: { ...event }
    });
  }
  if (event.type === 'plan_patch_preview') {
    addMessage({
      role: 'card',
      kind: 'plan_patch_preview',
      status: 'running',
      title: t('command.planPatchPreview'),
      content: event.operation,
      actionId: event.actionId,
      payload: { ...event }
    });
  }
  if (event.type === 'plan_patch_result') {
    addMessage({
      role: 'card',
      kind: 'plan_patch_result',
      status: event.status === 'success' ? 'success' : 'error',
      title: t('command.planPatchResult'),
      content: event.error || event.status,
      actionId: event.actionId,
      payload: { ...event }
    });
  }
  if (event.type === 'memory_write_preview') {
    addMessage({
      role: 'card',
      kind: 'memory_write_preview',
      status: 'running',
      title: t('command.memoryWritePreview'),
      content: event.content,
      actionId: event.actionId,
      payload: { ...event }
    });
  }
  if (event.type === 'memory_write_result') {
    addMessage({
      role: 'card',
      kind: 'memory_write_result',
      status: event.status === 'success' ? 'success' : 'error',
      title: t('command.memoryWriteResult'),
      content: event.error || event.content || event.status,
      actionId: event.actionId,
      payload: { ...event }
    });
  }
  if (event.type === 'note_write_preview') {
    addMessage({
      role: 'card',
      kind: 'note_write_preview',
      status: 'running',
      title: t('command.noteWritePreview'),
      content: event.noteText,
      actionId: event.actionId,
      payload: { ...event }
    });
  }
  if (event.type === 'note_write_result') {
    addMessage({
      role: 'card',
      kind: 'note_write_result',
      status: event.status === 'success' ? 'success' : 'error',
      title: t('command.noteWriteResult'),
      content: event.error || event.noteText || event.status,
      actionId: event.actionId,
      payload: { ...event }
    });
  }
  if (event.type === 'model_usage') {
    addMessage({
      role: 'card',
      kind: 'model_usage',
      status: 'success',
      title: t('command.modelUsage'),
      content: '',
      payload: { ...event }
    });
  }
  if (event.type === 'clarify_question') {
    addMessage({
      role: 'card',
      kind: 'clarify_question',
      status: 'running',
      title: t('command.clarifyQuestion'),
      content: event.question,
      payload: { ...event }
    });
  }
  if (event.type === 'execution_result') {
    addMessage({
      role: 'card',
      kind: 'execution_result',
      status: event.status === 'success' ? 'success' : 'error',
      title: t('command.executionResult'),
      content: event.text,
      actionId: event.actionId,
      payload: { ...event }
    });
  }
}

function createStreamHandler(t: (key: string) => string) {
  let assistantId = '';
  let sawOutput = false;
  let sawDelta = false;
  return {
    get sawOutput() {
      return sawOutput;
    },
    finish() {
      if (assistantId && sawDelta) {
        replaceMessage(assistantId, { streaming: false });
      }
    },
    onEvent(event: CommandChatEvent) {
      if (event.type === 'thread') {
        updateState((current) => ({ ...current, threadId: event.threadId }));
      }
      if (event.type === 'assistant_delta') {
        if (!assistantId) {
          assistantId = addMessage({
            role: 'assistant',
            content: '',
            streaming: true
          });
        }
        const delta = event.text ?? event.content ?? '';
        if (delta) {
          sawOutput = true;
          sawDelta = true;
          appendAssistantDelta(assistantId, delta);
        }
      }
      if (
        event.type === 'runtime_started' ||
        event.type === 'runtime_event' ||
        event.type === 'draft_created' ||
        event.type === 'summary' ||
        event.type === 'plan_detail' ||
        event.type === 'refinement_started' ||
        event.type === 'refined_tasks_result' ||
        event.type === 'calendar_plan_preview' ||
        event.type === 'approval_required' ||
        event.type === 'calendar_write_result' ||
        event.type === 'command_decision' ||
        event.type === 'plan_search_results' ||
        event.type === 'memory_search_results' ||
        event.type === 'note_search_results' ||
        event.type === 'plan_patch_preview' ||
        event.type === 'plan_patch_result' ||
        event.type === 'memory_write_preview' ||
        event.type === 'memory_write_result' ||
        event.type === 'note_write_preview' ||
        event.type === 'note_write_result' ||
        event.type === 'model_usage' ||
        event.type === 'clarify_question' ||
        event.type === 'execution_result'
      ) {
        sawOutput = true;
        addEventCard(event, t);
      }
      if (event.type === 'error') {
        throw new Error(event.error);
      }
    }
  };
}

async function sendCommand(input: string, t: (key: string) => string) {
  const trimmed = input.trim();
  if (!trimmed || state.sending) return;
  addMessage({ role: 'user', content: trimmed });
  updateState((current) => ({ ...current, sending: true }));

  try {
    const stream = createStreamHandler(t);
    await runCommandChat({
      threadId: state.threadId,
      message: trimmed,
      mode: state.mode,
      permission: state.permission,
      context: { date: todayISO() }
    }, {
      onEvent: stream.onEvent
    });
    stream.finish();
    if (!stream.sawOutput) {
      addMessage({ role: 'assistant', content: t('command.emptyReply') });
    }
  } catch (err) {
    addMessage({
      role: 'card',
      kind: 'error',
      content: commandErrorText(err)
    });
  } finally {
    updateState((current) => ({ ...current, sending: false }));
    void refreshThreads();
  }
}

async function approveAction(actionId: string, decision: 'approve' | 'reject', t: (key: string) => string) {
  if (!actionId || state.sending) return;
  updateState((current) => ({ ...current, sending: true }));
  try {
    const stream = createStreamHandler(t);
    await approveCommandAction({
      threadId: state.threadId,
      actionId,
      decision,
      permission: state.permission
    }, {
      onEvent: stream.onEvent
    });
    stream.finish();
    if (!stream.sawOutput) {
      addMessage({ role: 'assistant', content: t('command.emptyReply') });
    }
  } catch (err) {
    addMessage({
      role: 'card',
      kind: 'error',
      content: commandErrorText(err)
    });
  } finally {
    updateState((current) => ({ ...current, sending: false }));
    void refreshThreads();
  }
}

export function useCommandAgent() {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}

export const commandAgentActions = {
  setPermission,
  toggleChatMode,
  toggleWorkbench,
  setDrawerOpen,
  refreshThreads,
  newThread,
  loadThread,
  removeThread,
  sendCommand,
  approveAction
};

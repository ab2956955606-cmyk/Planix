import { renderToStaticMarkup } from 'react-dom/server';
import { Children, isValidElement, type ReactElement, type ReactNode } from 'react';
import { describe, expect, it } from 'vitest';
import { AgentThread } from './AgentThread';
import { ApprovalCard } from './ApprovalCard';
import { CommandDecisionCard } from './CommandDecisionCard';
import {
  AgentDecisionCard,
  AgentMessageCard,
  ExecutionPlanDraftCard,
  LearningUpdateBadge,
  MemoryInsightCard,
  PlanDesignProposalCard,
  PlanningSessionStatusCard,
  ResourceBriefCard,
  UserNeedContractCard
} from './DeepPlanningCards';
import { DeepPlanningActionBar } from './DeepPlanningActionBar';
import { deriveDeepPlanningStatus } from './deepPlanningStatus';
import { MemorySearchResultsCard } from './MemorySearchResultsCard';
import { MemoryWritePreviewCard } from './MemoryWritePreviewCard';
import { MemoryWriteResultCard } from './MemoryWriteResultCard';
import { ModelUsageBadge } from './ModelUsageBadge';
import { NoteSearchResultsCard } from './NoteSearchResultsCard';
import { NoteWritePreviewCard } from './NoteWritePreviewCard';
import { NoteWriteResultCard } from './NoteWriteResultCard';
import { PlanPatchPreviewCard } from './PlanPatchPreviewCard';
import { PlanPatchResultCard } from './PlanPatchResultCard';
import { PlanSearchResultsCard } from './PlanSearchResultsCard';

const labels: Record<string, string> = {
  'command.title': 'Planix',
  'command.empty': '你可以直接说：',
  'command.examplePlan': '帮我规划 30 天学 Python',
  'command.exampleQuery': '今天有什么计划？',
  'command.examplePatch': '把明天的任务改到后天',
  'command.exampleRefine': '把这个任务拆细一点',
  'command.exampleNote': '记一下：我晚上 8 点后适合学习',
  'command.planSearchResults': 'Search results',
  'command.calendarPlans': 'Calendar plans',
  'command.goalHistory': 'Goal history',
  'command.materialResults': 'Materials',
  'command.material': 'Material',
  'command.monthNotes': 'Month notes',
  'command.untitledPlan': 'Untitled',
  'command.noDate': 'No date',
  'command.minutes': 'minutes',
  'command.planPatchPreview': 'Patch preview',
  'command.planPatchResult': 'Patch result',
  'command.updateOperation': 'Update',
  'command.deleteOperation': 'Delete',
  'command.before': 'Before',
  'command.after': 'After',
  'command.planUpdated': 'Plan updated',
  'command.planDeleted': 'Plan deleted',
  'command.planPatchFailed': 'Patch failed',
  'command.statusSuccess': 'Success',
  'command.statusError': 'Error',
  'command.intentDecision': 'Intent decision',
  'command.llmDecision': 'LLM decision',
  'command.localFallbackRule': 'Local fallback rule',
  'command.decisionUnderstand': 'I understand: ',
  'command.decisionExecute': 'I will: ',
  'command.decisionExecutePrefix': 'Handle',
  'command.decisionIntentQueryPlan': 'view plans',
  'command.decisionIntentChat': 'chat',
  'command.decisionExecuteQueryCalendar': 'query Calendar',
  'command.decisionExecuteChat': 'continue chat',
  'command.intent': 'Intent',
  'command.action': 'Action',
  'command.target': 'Target',
  'command.confidence': 'Confidence',
  'command.noteSearchResults': 'Note results',
  'command.noteWritePreview': 'Note save preview',
  'command.noteWriteResult': 'Note save result',
  'command.noteSaved': 'Saved',
  'command.noteWriteFailed': 'Failed to save note',
  'command.noteWriteTarget': 'Ready to record into {year}-{month} notes:',
  'command.modelUsage': 'Model usage',
  'command.model': 'Model',
  'command.usageTask': 'Task',
  'command.tokens': 'Tokens',
  'command.promptTokens': 'prompt',
  'command.completionTokens': 'completion',
  'command.totalTokens': 'total',
  'command.latency': 'Latency',
  'command.noTokenStats': 'No token stats',
  'command.noTokenStatsShort': 'no token stats',
  'command.localFallbackNoTokens': 'Local fallback, no tokens',
  'command.routeTrace': 'Route',
  'command.routeSuccess': 'success',
  'command.routeFailed': 'failed',
  'command.routeSkipped': 'skipped',
  'command.routeMissingKey': 'missing API key',
  'command.routeLocalFallback': 'local fallback',
  'command.fallbackUsed': 'Fallback',
  'command.approvalRequired': 'Approval required',
  'command.writeRisk': 'Write',
  'command.recordOperation': 'Record',
  'command.confirmRecord': '确认记录',
  'command.confirmModify': '确认修改',
  'command.confirmDelete': '确认删除',
  'command.confirmWrite': '确认写入',
  'command.approve': 'Confirm',
  'command.reject': 'Cancel',
  'command.running': 'Running',
  'command.quickActions': 'Quick actions',
  'command.quickWriteCalendar': '写入日历',
  'command.quickViewPlans': '查看计划',
  'command.quickModifyPlan': '修改计划',
  'command.quickRefinePlan': '细化计划',
  'command.quickSearchNotes': '查笔记',
  'command.quickRecordNote': '记录笔记',
  'command.quickSearchNotesMessage': '查询我的笔记',
  'command.quickRecordNoteMessage': '记录一条笔记',
  'command.resultDate': 'Date',
  'command.resultTime': 'Time',
  'command.resultDuration': 'Duration',
  'command.resultSource': 'Source',
  'command.resultActions': 'Actions',
  'command.actionRefine': 'Refine',
  'command.actionModify': 'Edit',
  'command.actionDelete': 'Delete',
  'command.actionUseInPlan': 'Use in plan',
  'command.actionContinueView': 'Continue',
  'command.actionRefinePlanMessage': '细化第 {index} 个计划',
  'command.actionModifyPlanMessage': '修改第 {index} 个计划',
  'command.actionDeletePlanMessage': '删除第 {index} 个计划',
  'command.actionUseInPlanMessage': '把第 {index} 条笔记引用到规划',
  'command.actionContinueViewMessage': '继续查看第 {index} 条笔记',
  'command.usageTaskDecision': 'decision',
  'command.usageTaskPlanGeneration': 'plan generation',
  'command.usageTaskMemoryQuery': 'memory query',
  'command.usageTaskMemoryWrite': 'memory write',
  'command.usageTaskQueryNotes': 'note search',
  'command.usageTaskNoteWrite': 'note write',
  'command.memoryLibrary': 'Memory library',
  'command.memorySearchResults': 'Memory results',
  'command.memoryWritePreview': 'Memory preview',
  'command.memoryWriteResult': 'Memory result',
  'command.memorySaved': 'Recorded',
  'command.memoryWriteFailed': 'Memory write failed',
  'command.memoryWriteTarget': 'Ready to record into {kind}:',
  'command.memoryKind': 'Memory type',
  'command.memoryKindNote': 'Personal record',
  'command.memoryKindMaterial': 'Knowledge material',
  'command.memoryKindPlanningHistory': 'Planning archive',
  'command.memoryKindPreference': 'Preference constraint',
  'command.memoryKindReview': 'Review feedback',
  'command.untitledMemory': 'Untitled memory',
  'command.quickSearchMemory': '查记忆',
  'command.quickRecordMemory': '记录记忆',
  'command.quickWriteCalendarMessage': '写入日历',
  'command.quickViewPlansMessage': '查看我的计划',
  'command.quickModifyPlanMessage': '修改我的计划',
  'command.quickRefinePlanMessage': '细化当前计划',
  'command.quickSearchMemoryMessage': '查一下我的记忆',
  'command.quickRecordMemoryMessage': '记录一条记忆',
  'command.actionUseMemoryInPlanMessage': '把第 {index} 条记忆引用到规划',
  'command.actionContinueMemoryViewMessage': '继续查看第 {index} 条记忆',
  'command.planningSessionStarted': 'Deep planning session',
  'command.planningSessionStatus': 'Planning status',
  'command.latestPlanningStep': 'Latest planning step',
  'command.planningProcessCollapsed': 'Planning process · collapsed',
  'command.hiddenDraftCollapsed': 'Hidden draft · collapsed',
  'command.planningCardMemorySummary': 'Memory hits',
  'command.resources': 'resources',
  'command.tasks': 'tasks',
  'command.userNeedContract': 'Goal understanding',
  'command.memoryInsightAgent': 'Memory Insight Agent',
  'command.resourceIntelligenceAgent': 'Resource Intelligence Agent',
  'command.planDesignProposal': 'Planning direction',
  'command.executionPlanDraft': 'Execution plan draft',
  'command.learningUpdate': 'Feedback learning',
  'command.agentDecision': 'Agent decision',
  'command.agentMessage': 'Agent handoff',
  'command.agentDecisionReason': 'Decision reason',
  'command.agentMessageReason': 'Handoff reason',
  'command.agentMessageResolved': 'Resolved',
  'command.agentInputs': 'Input artifacts',
  'command.agentOutputs': 'Output artifacts',
  'command.agentPayload': 'Payload',
  'command.canMoveToDesign': 'Ready for design',
  'command.needsClarification': 'Needs clarification',
  'command.targetOutcome': 'Target outcome',
  'command.hardConstraints': 'Hard constraints',
  'command.missingInformation': 'Missing information',
  'command.clarificationQuestions': 'Clarification questions',
  'command.slotReceived': 'Captured information',
  'command.slotMissing': 'Still missing',
  'command.nextQuestion': 'Next question',
  'command.slotDomain': 'Type',
  'command.domainLearning': 'Learning plan',
  'command.domainTravel': 'Travel plan',
  'command.slotSubject': 'Subject',
  'command.slotCurrentLevel': 'Current level',
  'command.slotTargetLevel': 'Target level',
  'command.slotDailyTime': 'Available time',
  'command.slotDuration': 'Duration',
  'command.slotPurpose': 'Purpose',
  'command.slotDestination': 'Destination',
  'command.slotPlaces': 'Places',
  'command.slotDurationDays': 'Travel days',
  'command.slotMonth': 'Travel month',
  'command.slotTransport': 'Transport',
  'command.slotBudget': 'Budget',
  'command.slotFitness': 'Fitness',
  'command.memoryInfluence': 'Memory influence',
  'command.missingTopics': 'Missing topics',
  'command.resourceUntitled': 'Untitled resource',
  'command.expectedOutput': 'Expected output',
  'command.confirmDesign': 'Confirm direction',
  'command.reviseDesign': 'Adjust direction',
  'command.confirmDesignMessage': 'Confirm direction',
  'command.reviseDesignMessage': 'Adjust direction',
  'command.confirmExecution': 'Confirm execution plan',
  'command.confirmExecutionMessage': 'Confirm execution plan',
  'command.executionReadyToWrite': 'Execution plan confirmed; ready to write to Calendar',
  'command.executionWrittenToCalendar': 'Execution plan written to Calendar',
  'command.feedbackTooHeavy': 'Too heavy',
  'command.feedbackTooHeavyMessage': 'The tasks are too heavy',
  'command.feedbackResourceHard': 'Resource too hard',
  'command.feedbackResourceHardMessage': 'The resource is too hard',
  'command.deliverable': 'Deliverable',
  'command.fallbackAdjustment': 'Fallback if stuck',
  'command.whereToLearn': 'Where/how to learn',
  'command.reflection': 'Reflection',
  'command.currentPatch': 'Current plan patch',
  'command.longTermLearning': 'Long-term rule',
  'command.noHardConstraints': 'No hard constraints captured yet.',
  'command.noMemoryHits': 'No related memory',
  'command.noResourceCandidates': 'No usable resources',
  'command.noExecutionTasks': 'No execution tasks',
  'command.expand': 'Expand',
  'command.collapse': 'Collapse',
  'command.expandAll': 'Expand all',
  'command.collapseAll': 'Collapse all',
  'command.acceptanceCriteria': 'Completion standard',
  'command.noAcceptanceCriteria': 'No completion standard',
  'command.resourceCoverage': 'Resource coverage',
  'command.knowledgePoints': 'Knowledge points',
  'command.whatWentWrong': 'What went wrong',
  'command.whyItHappened': 'Why it happened',
  'command.noImmediatePatch': 'No patch needed',
  'command.deepPlanningActions': 'Deep planning actions',
  'command.startDeepPlanning': 'Start deep planning',
  'command.startDeepPlanningMessage': 'I want to do deep planning. Please ask me what information I need to add first.',
  'command.supplementGoal': 'Add goal details',
  'command.supplementGoalMessage': 'I will add more goal details',
  'command.moreActions': 'More actions',
  'command.waitingCalendarApproval': 'Waiting for Calendar approval',
  'common.done': 'Done',
  'common.pending': 'Pending',
  'common.unknown': 'Unknown',
  'common.empty': 'Empty',
  'common.yes': 'Yes',
  'common.no': 'No'
};

const labelOverrides: Record<string, string> = {
  'command.quickWriteCalendarMessage': '写入日历',
  'command.quickViewPlansMessage': '查看我的计划',
  'command.quickModifyPlanMessage': '修改我的计划',
  'command.quickRefinePlanMessage': '细化当前计划',
  'command.quickSearchMemory': '查记忆',
  'command.quickRecordMemory': '记录记忆',
  'command.quickSearchMemoryMessage': '查一下我的记忆',
  'command.quickRecordMemoryMessage': '记录一条记忆'
};

function t(key: string): string {
  return labelOverrides[key] ?? labels[key] ?? key;
}

function collectButtons(node: ReactNode): ReactElement[] {
  const buttons: ReactElement[] = [];
  function visit(value: ReactNode) {
    Children.forEach(value, (child) => {
      if (!isValidElement(child)) return;
      if (child.type === 'button') {
        buttons.push(child);
      }
      visit(child.props.children);
    });
  }
  visit(node);
  return buttons;
}

describe('Plan command cards', () => {
  it('renders the P Mode empty state with concrete examples', () => {
    const html = renderToStaticMarkup(
      <AgentThread messages={[]} sending={false} onApprove={() => undefined} onSend={() => undefined} t={t} />
    );

    expect(html).toContain('你可以直接说');
    expect(html).toContain('帮我规划 30 天学 Python');
    expect(html).toContain('把明天的任务改到后天');
    expect(html).toContain('记一下：我晚上 8 点后适合学习');
  });

  it('renders calendar, material, goal history, and month note search results', () => {
    const html = renderToStaticMarkup(
      <PlanSearchResultsCard
        summary="Found 4 related items."
        calendarPlans={[
          {
            id: 'plan-1',
            date: '2026-07-08',
            time: '09:30',
            title: 'Python practice',
            estimatedMinutes: 45,
            done: false
          }
        ]}
        materials={[{ title: 'Python notes', chunk: 'Use pathlib and pytest.' }]}
        goalHistory={[{ title: 'AI internship plan', summary: 'Portfolio milestones.' }]}
        monthNotes={[{ year: 2026, month: 7, content: 'Interview prep focus.' }]}
        onSend={() => undefined}
        t={t}
      />
    );

    expect(html).toContain('Search results');
    expect(html).toContain('Calendar plans');
    expect(html).toContain('Python practice');
    expect(html).toContain('Date');
    expect(html).toContain('Duration');
    expect(html).toContain('45 minutes');
    expect(html).toContain('Refine');
    expect(html).toContain('Edit');
    expect(html).toContain('Delete');
    expect(html).toContain('Goal history');
    expect(html).toContain('AI internship plan');
    expect(html).toContain('Materials');
    expect(html).toContain('Python notes');
    expect(html).toContain('Month notes');
    expect(html).toContain('Interview prep focus.');
  });

  it('renders an update diff preview with content field changes', () => {
    const html = renderToStaticMarkup(
      <PlanPatchPreviewCard
        operation="update"
        before={{
          date: '2026-07-08',
          time: '09:30',
          title: 'Python practice',
          estimatedMinutes: 45
        }}
        after={{
          date: '2026-07-10',
          time: '10:00',
          content: 'Python project practice',
          estimatedMinutes: 30
        }}
        changes={{ date: '2026-07-10', content: 'Python project practice', estimatedMinutes: 30 }}
        t={t}
      />
    );

    expect(html).toContain('Patch preview');
    expect(html).toContain('Update');
    expect(html).toContain('Before');
    expect(html).toContain('2026-07-08 09:30 - Python practice - 45 minutes');
    expect(html).toContain('After');
    expect(html).toContain('2026-07-10 10:00 - Python project practice - 30 minutes');
    expect(html).toContain('estimatedMinutes');
  });

  it('renders successful delete and failed update results', () => {
    const deleteHtml = renderToStaticMarkup(
      <PlanPatchResultCard operation="delete" status="success" t={t} />
    );
    const failedHtml = renderToStaticMarkup(
      <PlanPatchResultCard operation="update" status="failed" error="No supported plan changes" t={t} />
    );

    expect(deleteHtml).toContain('Patch result');
    expect(deleteHtml).toContain('Success');
    expect(deleteHtml).toContain('Plan deleted');
    expect(failedHtml).toContain('Error');
    expect(failedHtml).toContain('No supported plan changes');
  });

  it('renders decision, note, usage, and quick action cards', () => {
    const decisionHtml = renderToStaticMarkup(
      <CommandDecisionCard
        intent="query_plan"
        confidence={0.86}
        targetType="calendar_date"
        action="query"
        decisionSummary="View today"
        source="llm"
        t={t}
      />
    );
    const notesHtml = renderToStaticMarkup(
      <NoteSearchResultsCard
        summary="Found notes"
        materials={[{ title: 'Python note', chunk: 'Portfolio material' }]}
        monthNotes={[{ year: 2026, month: 7, content: 'Interview notes' }]}
        onSend={() => undefined}
        t={t}
      />
    );
    const previewHtml = renderToStaticMarkup(
      <NoteWritePreviewCard year={2026} month={7} date="2026-07-05" noteText="Save this" before="" after="2026-07-05 Save this" t={t} />
    );
    const resultHtml = renderToStaticMarkup(
      <NoteWriteResultCard status="success" year={2026} month={7} noteText="Save this" t={t} />
    );
    const usageHtml = renderToStaticMarkup(
      <ModelUsageBadge usage={[
        { provider: 'deepseek', model: 'chat', promptTokens: 10, completionTokens: 5, totalTokens: 15, latencyMs: 7, mode: 'llm', taskType: 'command_decision' },
        { provider: 'deepseek', model: 'plan', promptTokens: 100, completionTokens: 50, totalTokens: 150, latencyMs: 2100, mode: 'llm', taskType: 'plan_generation' },
        { provider: 'kimi', model: 'moonshot-v1-8k', totalTokens: 22, latencyMs: 120, mode: 'llm', taskType: 'memory_query', fallbackUsed: true, attempts: [
          { provider: 'zhipu_glm', model: 'glm-4-flash', status: 'skipped', errorType: 'missing_api_key' },
          { provider: 'kimi', model: 'moonshot-v1-8k', status: 'success' }
        ] },
        { provider: 'zhipu_glm', model: 'glm-4-flash', totalTokens: 8, latencyMs: 90, mode: 'llm', taskType: 'note_write' }
      ]} t={t} />
    );
    const quickHtml = renderToStaticMarkup(<DeepPlanningActionBar messages={[]} onSend={() => undefined} t={t} />);

    expect(decisionHtml).toContain('Intent decision');
    expect(decisionHtml).toContain('I understand');
    expect(decisionHtml).toContain('query Calendar');
    expect(notesHtml).toContain('Note results');
    expect(notesHtml).toContain('Python note');
    expect(notesHtml).toContain('Use in plan');
    expect(previewHtml).toContain('Note save preview');
    expect(previewHtml).toContain('Ready to record into 2026-7 notes');
    expect(resultHtml).toContain('Saved');
    expect(usageHtml).toContain('Model usage');
    expect(usageHtml).toContain('decision 15 Tokens');
    expect(usageHtml).toContain('plan generation 150 Tokens');
    expect(usageHtml).toContain('memory query 22 Tokens');
    expect(usageHtml).toContain('memory write 8 Tokens');
    expect(usageHtml).toContain('Task: memory query');
    expect(usageHtml).toContain('Fallback: Yes');
    expect(usageHtml).toContain('Route: zhipu_glm / glm-4-flash missing API key -&gt; kimi / moonshot-v1-8k success');
    expect(quickHtml).toContain('Start deep planning');
    expect(quickHtml).toContain('More actions');
    expect(quickHtml).toContain('记录记忆');
  });

  it('renders memory search and write cards by grouped kind', () => {
    const searchHtml = renderToStaticMarkup(
      <MemorySearchResultsCard
        summary="Found memory"
        groups={[
          {
            kind: 'note',
            title: 'Personal record',
            items: [{ id: 'm1', kind: 'note', title: 'Evening learning', summary: 'Study after 8 PM', tags: ['study'], updatedAt: '2026-07-08' }]
          },
          {
            kind: 'planning_history',
            title: 'Planning archive',
            items: [{ id: 'm2', kind: 'planning_history', title: 'Python plan', summary: '30-day archive', updatedAt: '2026-07-07' }]
          }
        ]}
        onSend={() => undefined}
        t={t}
      />
    );
    const previewHtml = renderToStaticMarkup(
      <MemoryWritePreviewCard kind="preference" title="Learning time" content="I study better after 8 PM" t={t} />
    );
    const resultHtml = renderToStaticMarkup(
      <MemoryWriteResultCard status="success" kind="preference" title="Learning time" t={t} />
    );

    expect(searchHtml).toContain('Memory results');
    expect(searchHtml).toContain('Personal record');
    expect(searchHtml).toContain('Planning archive');
    expect(searchHtml).toContain('Evening learning');
    expect(searchHtml).toContain('Use in plan');
    expect(previewHtml).toContain('Memory preview');
    expect(previewHtml).toContain('Preference constraint');
    expect(resultHtml).toContain('Recorded');
  });

  it('derives deep planning actions from replayed planning status', () => {
    const messages = [{
      id: 'm-status',
      role: 'card' as const,
      kind: 'planning_session_status' as const,
      content: 'waiting_design_approval',
      createdAt: 1,
      payload: { sessionId: 'session-1', status: 'waiting_design_approval' }
    }];
    const html = renderToStaticMarkup(<DeepPlanningActionBar messages={messages} onSend={() => undefined} t={t} />);

    expect(deriveDeepPlanningStatus(messages)).toBe('waiting_design_approval');
    expect(html).toContain('Confirm direction');
    expect(html).toContain('Adjust direction');
    expect(html).not.toContain('Start deep planning');
  });

  it('derives deep planning status from replay cards by priority', () => {
    const messages = [
      {
        id: 'm-start',
        role: 'card' as const,
        kind: 'planning_session_started' as const,
        content: 'waiting_design_approval',
        createdAt: 1,
        payload: { sessionId: 'session-1', status: 'waiting_design_approval' }
      },
      {
        id: 'm-draft',
        role: 'card' as const,
        kind: 'execution_plan_draft' as const,
        content: 'draft',
        createdAt: 2,
        payload: { sessionId: 'session-1', data: { status: 'approved' } }
      }
    ];
    expect(deriveDeepPlanningStatus(messages)).toBe('ready_to_write_calendar');
    const html = renderToStaticMarkup(<DeepPlanningActionBar messages={messages} onSend={() => undefined} t={t} />);
    expect(html).toContain('写入日历');
    expect(html).not.toContain('Confirm execution plan');

    const withExplicitStatus = [
      ...messages,
      {
        id: 'm-status',
        role: 'card' as const,
        kind: 'planning_session_status' as const,
        content: 'waiting_execution_approval',
        createdAt: 3,
        payload: { sessionId: 'session-1', status: 'waiting_execution_approval' }
      }
    ];
    expect(deriveDeepPlanningStatus(withExplicitStatus)).toBe('waiting_execution_approval');

    const readyStatusOnly = [{
      id: 'm-ready',
      role: 'card' as const,
      kind: 'planning_session_status' as const,
      content: 'ready_to_write_calendar',
      createdAt: 4,
      payload: { sessionId: 'session-1', status: 'ready_to_write_calendar' }
    }];
    const readyHtml = renderToStaticMarkup(<DeepPlanningActionBar messages={readyStatusOnly} onSend={() => undefined} t={t} />);
    expect(deriveDeepPlanningStatus(readyStatusOnly)).toBe('ready_to_write_calendar');
    expect(readyHtml).toContain('写入日历');
    expect(readyHtml).not.toContain('Confirm execution plan');
  });

  it('gates execution draft actions by planning group status', () => {
    const sent: string[] = [];
    const waiting = ExecutionPlanDraftCard({
      t,
      onSend: (value) => sent.push(value),
      planningStatus: 'waiting_execution_approval',
      data: { scheduleSummary: 'Ready for review.', resourceCoverageSummary: 'Resources available.', tasks: [] }
    });
    const waitingHtml = renderToStaticMarkup(waiting);
    collectButtons(waiting).forEach((button) => button.props.onClick());
    expect(waitingHtml).toContain('Confirm execution plan');
    expect(sent).toEqual(['Confirm execution plan', 'The tasks are too heavy', 'The resource is too hard']);

    sent.length = 0;
    const ready = ExecutionPlanDraftCard({
      t,
      onSend: (value) => sent.push(value),
      planningStatus: 'ready_to_write_calendar',
      data: { status: 'approved', scheduleSummary: 'Ready for calendar.', resourceCoverageSummary: 'Resources available.', tasks: [] }
    });
    const readyHtml = renderToStaticMarkup(ready);
    collectButtons(ready).forEach((button) => button.props.onClick());
    expect(readyHtml).toContain('Execution plan confirmed; ready to write to Calendar');
    expect(readyHtml).toContain('\u5199\u5165\u65e5\u5386');
    expect(readyHtml).not.toContain('Confirm execution plan');
    expect(sent).toEqual(['\u5199\u5165\u65e5\u5386']);

    const historical = renderToStaticMarkup(
      <ExecutionPlanDraftCard
        t={t}
        onSend={() => undefined}
        planningStatus="waiting_execution_approval"
        actionsEnabled={false}
        data={{ scheduleSummary: 'Historical draft.', resourceCoverageSummary: 'Resources available.', tasks: [] }}
      />
    );
    expect(historical).not.toContain('Confirm execution plan');
    expect(historical).not.toContain('The tasks are too heavy');
  });

  it('auto-collapses historical deep planning groups and keeps the latest group expanded', () => {
    const messages = [
      {
        id: 'old-contract',
        role: 'card' as const,
        kind: 'user_need_contract' as const,
        content: '',
        createdAt: 1,
        payload: { sessionId: 's-old', data: { interpretedGoal: 'Old Go plan', canMoveToDesign: true } }
      },
      {
        id: 'old-design',
        role: 'card' as const,
        kind: 'plan_design_proposal' as const,
        content: '',
        createdAt: 2,
        payload: { sessionId: 's-old', data: { strategyName: 'Old strategy', status: 'waiting_user_approval', phases: [] } }
      },
      {
        id: 'user-gap',
        role: 'user' as const,
        content: '确认方向',
        createdAt: 3
      },
      {
        id: 'new-contract',
        role: 'card' as const,
        kind: 'user_need_contract' as const,
        content: '',
        createdAt: 4,
        payload: { sessionId: 's-new', data: { interpretedGoal: 'New Python plan', canMoveToDesign: true } }
      },
      {
        id: 'new-design',
        role: 'card' as const,
        kind: 'plan_design_proposal' as const,
        content: '',
        createdAt: 5,
        payload: { sessionId: 's-new', data: { strategyName: 'New strategy', status: 'waiting_user_approval', phases: [] } }
      }
    ];

    const html = renderToStaticMarkup(
      <AgentThread messages={messages} sending={false} onApprove={() => undefined} onSend={() => undefined} t={t} />
    );

    expect(html).toContain('Planning process · collapsed');
    expect(html).toContain('Latest planning step');
    expect(html).toContain('New strategy');
    expect(html).not.toContain('Old strategy');
  });

  it('sends fixed natural language messages from deep planning, more, and row actions', () => {
    const sent: string[] = [];
    const quick = DeepPlanningActionBar({ messages: [], onSend: (value) => sent.push(value), t });
    collectButtons(quick).forEach((button) => button.props.onClick());
    expect(sent[0]).toBe('I want to do deep planning. Please ask me what information I need to add first.');
    expect(sent).toContain('查看我的计划');
    expect(sent).toContain('记录一条记忆');
    expect(sent).toHaveLength(7);

    sent.length = 0;
    const planCard = PlanSearchResultsCard({
      calendarPlans: [{ id: 'p1', date: '2026-07-08', time: '09:00', title: 'Python', estimatedMinutes: 30 }],
      onSend: (value) => sent.push(value),
      t
    });
    collectButtons(planCard).forEach((button) => button.props.onClick());
    expect(sent).toEqual(['细化第 1 个计划', '修改第 1 个计划', '删除第 1 个计划']);

    sent.length = 0;
    const noteCard = NoteSearchResultsCard({
      monthNotes: [{ year: 2026, month: 7, content: 'Evening learning' }],
      onSend: (value) => sent.push(value),
      t
    });
    collectButtons(noteCard).forEach((button) => button.props.onClick());
    expect(sent).toEqual(['把第 1 条笔记引用到规划', '继续查看第 1 条笔记']);
  });

  it('renders deep planning session cards and sends feedback actions', () => {
    const sent: string[] = [];
    const statusHtml = renderToStaticMarkup(<PlanningSessionStatusCard status="waiting_design_approval" t={t} />);
    const contractHtml = renderToStaticMarkup(
      <UserNeedContractCard
        t={t}
        data={{
          interpretedGoal: '30-day Python AI internship plan',
          desiredOutcome: 'Portfolio-ready project',
          canMoveToDesign: true,
          hardConstraints: ['30 minutes daily'],
          slotState: {
            domain: 'learning',
            learning: {
              subject: 'Python',
              currentLevel: 'Beginner',
              dailyTime: '30 minutes daily',
              purpose: 'AI internship'
            },
            missingSlots: ['duration']
          },
          pendingQuestion: {
            questionText: 'How many days should this plan cover?',
            questions: ['How many days should this plan cover?']
          }
        }}
      />
    );
    const memoryHtml = renderToStaticMarkup(
      <MemoryInsightCard
        t={t}
        data={{
          confidence: 0.82,
          memoryHits: {
            preferences: [{ title: 'Project-driven learning' }],
            reviews: [],
            planningHistory: [{ title: 'Previous Python plan' }],
            materials: [],
            notes: []
          },
          planningInsights: {
            userStyleRules: ['Prefer project-driven tasks'],
            pastFailureWarnings: ['Avoid long theory blocks'],
            constraintsToRespect: ['Keep tasks under 60 minutes']
          }
        }}
      />
    );
    const resourceHtml = renderToStaticMarkup(
      <ResourceBriefCard
        t={t}
        data={{
          coverage: { status: 'partial', explanation: 'Python basics are covered.', missingTopics: ['deployment'] },
          resourceCandidates: [{
            id: 'r1',
            title: 'FastAPI Tutorial',
            sourceType: 'official_doc',
            domain: 'FastAPI',
            difficulty: 'beginner',
            howToUse: 'Read only the first two examples.'
          }]
        }}
      />
    );
    const design = PlanDesignProposalCard({
      t,
      onSend: (value) => sent.push(value),
      data: {
        status: 'waiting_user_approval',
        strategyName: 'Portfolio-driven plan',
        designRationale: 'Use project outputs instead of pure theory.',
        phases: [{ title: 'Foundation', purpose: 'Build minimum Python fluency', expectedOutput: 'Small CLI artifact' }]
      }
    });
    const designHtml = renderToStaticMarkup(design);
    collectButtons(design).forEach((button) => button.props.onClick());
    const execution = ExecutionPlanDraftCard({
      t,
      onSend: (value) => sent.push(value),
      data: {
        scheduleSummary: '30 days, low-density progression.',
        resourceCoverageSummary: 'Core resources available.',
        tasks: [{
          title: 'Build a Python CLI checklist',
          dueDate: '2026-07-10',
          estimatedMinutes: 30,
          priority: 'high',
          whyThisTaskMatters: 'It proves practical Python basics.',
          deliverable: 'cli_checklist.py',
          fallbackAdjustment: 'Only implement one command.',
          resourceBundle: {
            primary: {
              title: 'Python control flow',
              sourceType: 'official_doc',
              section: 'Control Flow',
              useStep: 'Read one example, then code.',
              expectedOutput: 'A running script'
            },
            practice: {
              title: 'If/else exercise',
              sourceType: 'practice_bank',
              searchKeyword: 'python if else practice',
              useStep: 'Finish the smallest exercise.'
            }
          }
        }]
      }
    });
    const executionHtml = renderToStaticMarkup(execution);
    collectButtons(execution).forEach((button) => button.props.onClick());
    const learningHtml = renderToStaticMarkup(
      <LearningUpdateBadge
        t={t}
        data={{
          feedbackType: 'resource_feedback',
          insight: 'The resource was too hard.',
          reflection: { howToAvoidNextTime: 'Prefer project examples before official docs.' },
          immediatePatch: { action: 'replace_resource', instruction: 'Use practice bank first.' },
          longTermLearning: { newRule: 'Do not start beginners with pure theory.' }
        }}
      />
    );
    const decisionHtml = renderToStaticMarkup(
      <AgentDecisionCard
        t={t}
        data={{
          agent: 'Resource Intelligence Agent',
          decision: 'request_agent_revision',
          reason: 'The Go concurrency task is too broad for a concrete resource bundle.',
          userVisibleSummary: 'Resource Agent requested task splitting.',
          inputArtifactIds: ['a1'],
          outputArtifactIds: ['a2'],
          confidence: 0.87
        }}
      />
    );
    const messageHtml = renderToStaticMarkup(
      <AgentMessageCard
        t={t}
        data={{
          fromAgent: 'Feedback Evolution Agent',
          toAgent: 'Resource Intelligence Agent',
          messageType: 'revision_request',
          reason: 'Replace this task resource with beginner practice.',
          resolved: true,
          payloadJson: { taskId: 't3' }
        }}
      />
    );

    expect(statusHtml).toContain('waiting_design_approval');
    expect(contractHtml).toContain('Goal understanding');
    expect(contractHtml).toContain('30-day Python AI internship plan');
    expect(contractHtml).toContain('Captured information');
    expect(contractHtml).toContain('Subject: Python');
    expect(contractHtml).toContain('Still missing');
    expect(contractHtml).toContain('Next question');
    expect(memoryHtml).toContain('Memory Insight Agent');
    expect(memoryHtml).toContain('Prefer project-driven tasks');
    expect(resourceHtml).toContain('Resource Intelligence Agent');
    expect(resourceHtml).toContain('FastAPI Tutorial');
    expect(designHtml).toContain('Portfolio-driven plan');
    expect(executionHtml).toContain('Build a Python CLI checklist');
    expect(executionHtml).toContain('Where/how to learn');
    expect(executionHtml).toContain('cli_checklist.py');
    expect(learningHtml).toContain('replace_resource');
    expect(learningHtml).toContain('Long-term rule');
    expect(decisionHtml).toContain('Resource Intelligence Agent');
    expect(decisionHtml).toContain('request_agent_revision');
    expect(decisionHtml).toContain('Decision reason');
    expect(messageHtml).toContain('Feedback Evolution Agent');
    expect(messageHtml).toContain('Resource Intelligence Agent');
    expect(messageHtml).toContain('revision_request');
    expect(sent).toEqual([
      'Confirm direction',
      'Adjust direction',
      'Confirm execution plan',
      'The tasks are too heavy',
      'The resource is too hard'
    ]);
  });

  it('renders execution task details collapsed except the first task by default', () => {
    const html = renderToStaticMarkup(
      <ExecutionPlanDraftCard
        t={t}
        onSend={() => undefined}
        data={{
          scheduleSummary: 'Two tasks.',
          resourceCoverageSummary: 'Resources available.',
          tasks: [
            {
              title: 'First task',
              dueDate: '2026-07-10',
              estimatedMinutes: 30,
              priority: 'high',
              whyThisTaskMatters: 'First detail',
              deliverable: 'first.py',
              fallbackAdjustment: 'Do less.',
              resourceCoverage: { status: 'partial', explanation: 'Enough.' },
              resourceBundle: { primary: { title: 'Python docs', sourceType: 'official_doc', useStep: 'Read one example.' } }
            },
            {
              title: 'Second task',
              dueDate: '2026-07-11',
              estimatedMinutes: 45,
              priority: 'medium',
              whyThisTaskMatters: 'Second detail',
              deliverable: 'second.py',
              fallbackAdjustment: 'Do less.',
              resourceCoverage: { status: 'partial', explanation: 'Enough.' },
              resourceBundle: { primary: { title: 'Practice bank', sourceType: 'practice_bank', useStep: 'Do one exercise.' } }
            }
          ]
        }}
      />
    );

    expect(html).toContain('Expand all');
    expect(html).toContain('Collapse all');
    expect((html.match(/<details class="execution-task-detail" open=""/g) || []).length).toBe(1);
    expect(html).toContain('Second task');
  });

  it('renders approval labels by action target and operation', () => {
    const noop = () => undefined;
    const note = renderToStaticMarkup(<ApprovalCard summary="Record" actionId="a1" target="notes" operation="update" risk="write" sending={false} onDecision={noop} t={t} />);
    const update = renderToStaticMarkup(<ApprovalCard summary="Update" actionId="a1" target="calendar" operation="update" risk="write" sending={false} onDecision={noop} t={t} />);
    const del = renderToStaticMarkup(<ApprovalCard summary="Delete" actionId="a1" target="calendar" operation="delete" risk="delete" sending={false} onDecision={noop} t={t} />);
    const write = renderToStaticMarkup(<ApprovalCard summary="Write" actionId="a1" target="calendar" operation="create_or_update_plans" risk="write" sending={false} onDecision={noop} t={t} />);

    expect(note).toContain('确认记录');
    expect(update).toContain('确认修改');
    expect(del).toContain('确认删除');
    expect(write).toContain('确认写入');
  });
});

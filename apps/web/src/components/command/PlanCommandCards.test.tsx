import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { PlanPatchPreviewCard } from './PlanPatchPreviewCard';
import { PlanPatchResultCard } from './PlanPatchResultCard';
import { PlanSearchResultsCard } from './PlanSearchResultsCard';

const labels: Record<string, string> = {
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
  'common.done': 'Done',
  'common.pending': 'Pending'
};

function t(key: string): string {
  return labels[key] ?? key;
}

describe('Plan command cards', () => {
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
        t={t}
      />
    );

    expect(html).toContain('Search results');
    expect(html).toContain('Calendar plans');
    expect(html).toContain('Python practice');
    expect(html).toContain('45 minutes');
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
});

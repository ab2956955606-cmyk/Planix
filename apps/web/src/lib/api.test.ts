import { describe, expect, it } from 'vitest';
import { toBackendPlan } from './api';
import type { Plan } from '../types';

describe('plan API mapping', () => {
  it('preserves AI calendar task metadata when writing to the backend', () => {
    const plan: Plan = {
      id: 'plan-1',
      time: '09:00',
      title: '练习基本站姿与平衡',
      done: false,
      completion: '在平地上模拟滑雪站姿，双腿微曲，重心居中，练习原地踏步和平衡。',
      source: 'ai',
      sourceKey: 'command-draft:draft_ski:m0:t1',
      priority: 'high',
      estimatedMinutes: 45,
      refinedTask: null
    };

    expect(toBackendPlan('2026-07-08', plan)).toMatchObject({
      date: '2026-07-08',
      time: '09:00',
      content: '练习基本站姿与平衡',
      result: '在平地上模拟滑雪站姿，双腿微曲，重心居中，练习原地踏步和平衡。',
      source: 'ai',
      sourceKey: 'command-draft:draft_ski:m0:t1',
      priority: 'high',
      estimatedMinutes: 45
    });
  });
});

export type Lang = 'zh' | 'en';

export interface Plan {
  id: string;
  time: string;
  title: string;
  done: boolean;
  completion: string;
  source?: 'manual' | 'ai';
}

export interface DayRecord {
  plans: Plan[];
}

export type AppData = Record<string, DayRecord>;

export interface PlannerTask {
  time: string;
  title: string;
  reason: string;
}

export interface PlannerResponse {
  mode?: 'api' | 'mock';
  summary?: string;
  phases?: Array<{ title: string; detail: string }>;
  tasks?: PlannerTask[];
  suggestions?: string[];
  answer?: string;
  sources?: Array<{ title: string; quote: string }>;
  score?: number;
  results?: Array<{ case: string; score: number; reason: string }>;
}

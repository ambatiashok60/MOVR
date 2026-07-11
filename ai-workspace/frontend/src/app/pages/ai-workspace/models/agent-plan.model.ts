export type AgentPlanStepStatus = 'pending' | 'in_progress' | 'done' | 'skipped';

export interface AgentToolCall {
  toolName: string;
  arguments: Record<string, unknown>;
  resultSummary?: string;
}

export interface AgentPlanStep {
  id: string;
  order: number;
  description: string;
  status: AgentPlanStepStatus;
  affectedFiles: string[];
  toolCalls: AgentToolCall[];
  confidence?: number;
}

export interface AgentPlan {
  id: string;
  executionId: string;
  steps: AgentPlanStep[];
  overallConfidence?: number;
}

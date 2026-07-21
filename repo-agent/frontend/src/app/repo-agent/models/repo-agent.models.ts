/** Shared types — string values mirror docs/integration-contract.md exactly. */

export type AgentMode = 'ask' | 'agent';

export type BackendRunStatus =
  | 'queued' | 'planning' | 'running' | 'waiting_for_auth' | 'validating'
  | 'completing' | 'completed' | 'failed' | 'cancelled';

export type AgentRunStatus =
  | 'idle' | 'submitting' | BackendRunStatus
  | 'connection_lost' | 'recovering';

export type PlanStepStatus = 'pending' | 'in_progress' | 'completed' | 'blocked' | 'skipped';

export type ResponseBatchType =
  | 'plan' | 'progress' | 'repository_findings' | 'explanation'
  | 'code_suggestion' | 'code_change' | 'diff' | 'validation' | 'warning' | 'summary';

export interface PlanStep {
  step_id: string;
  title: string;
  objective: string;
  status: PlanStepStatus;
  suggested_tools: string[];
  files: string[];
  result_summary: string | null;
}

export interface ExecutionPlan {
  plan_id: string;
  goal: string;
  mode: AgentMode;
  steps: PlanStep[];
  current_step_id: string | null;
  revision: number;
}

export interface ResponseBatchState {
  batchId: string;
  index: number;
  type: ResponseBatchType;
  title?: string;
  markdown: string;
  status: 'streaming' | 'completed';
}

export interface RelevantFile { path: string; }

export interface ValidationResult {
  name: string;
  status: 'passed' | 'failed' | 'skipped';
  summary: string;
}

export interface FileChange {
  path: string;
  change_type: string;
  diff: string;
}

export interface AgentRunError {
  code: string;
  message: string;
  recoverable: boolean;
  retry_action?: string;
}

export interface AgentRunState {
  runId: string | null;
  conversationId: string | null;
  workspacePath: string;
  mode: AgentMode;
  status: AgentRunStatus;
  lastEventSequence: number;
  lastEventAt: number;
  lastHeartbeatAt: number;
  plan: ExecutionPlan | null;
  responseBatches: ResponseBatchState[];
  relevantFiles: string[];
  fileChanges: FileChange[];
  validationResults: ValidationResult[];
  toolCallCount: number;
  filesReadCount: number;
  filesModifiedCount: number;
  latestActions: { label: string; at: number }[];
  error: AgentRunError | null;
  needsAuth: boolean;
}

export interface StreamEvent {
  run_id: string;
  sequence: number;
  [key: string]: unknown;
}

export interface CreateRunResponse {
  run_id: string;
  conversation_id: string;
  status: BackendRunStatus;
  events_url: string;
}

export const TERMINAL_STATUSES: AgentRunStatus[] = ['completed', 'failed', 'cancelled'];

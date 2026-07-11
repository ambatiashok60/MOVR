import { ExecutionStatus } from './ai-workspace.model';
import { FileChange } from './file-change.model';

export type ExecutionStageStatus = 'pending' | 'active' | 'done' | 'failed';

export interface ExecutionStage {
  id: string;
  label: string;
  status: ExecutionStageStatus;
  detail?: string;
  startedAt?: string;
  completedAt?: string;
}

export interface ExecutionRun {
  id: string;
  sessionId: string;
  status: ExecutionStatus;
  stages: ExecutionStage[];
  /** Populated once the run completes — empty while status is 'planning' | 'running'. */
  filesChanged: FileChange[];
  startedAt: string;
  completedAt?: string;
  errorMessage?: string;
  needsReview?: boolean;
  reviewReasons?: string[];
  budgetUsage?: {
    llm_calls?: number;
    prompt_characters?: number;
    completion_characters?: number;
    elapsed_seconds?: number;
  };
  engineeringReview?: {
    quality_score: number;
    risk_level: string;
    confidence: number;
    root_cause?: string | null;
    evidence: string[];
    validation: string[];
    remaining_risks: string[];
    approval_required: boolean;
  };
  isolatedWorkspacePath?: string | null;
}

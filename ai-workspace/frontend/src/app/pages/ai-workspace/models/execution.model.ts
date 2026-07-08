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
}

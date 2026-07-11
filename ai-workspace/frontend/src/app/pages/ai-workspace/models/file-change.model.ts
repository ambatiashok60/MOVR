import { ReviewDecision } from './review.model';

export type FileChangeStatus = 'added' | 'modified' | 'deleted';

export type DiffLineType = 'context' | 'added' | 'removed';

export interface DiffLine {
  type: DiffLineType;
  oldLineNumber?: number;
  newLineNumber?: number;
  content: string;
}

export interface DiffHunk {
  header: string;
  lines: DiffLine[];
}

export interface FileChange {
  id: string;
  runId: string;
  filePath: string;
  status: FileChangeStatus;
  decision: ReviewDecision;
  additions: number;
  deletions: number;
  diffHunks: DiffHunk[];
}

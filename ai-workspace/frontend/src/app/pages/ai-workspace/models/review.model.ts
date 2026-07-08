export type ReviewDecision = 'pending' | 'kept' | 'rejected';

export interface ReviewSummary {
  runId: string;
  totalFiles: number;
  keptCount: number;
  rejectedCount: number;
  pendingCount: number;
}

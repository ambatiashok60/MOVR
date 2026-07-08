export type AiWorkspaceMode = 'ask' | 'agent';

export type ExecutionStatus = 'idle' | 'planning' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface AiWorkspaceRequest {
  sessionId: string;
  repositoryId: string;
  branch: string;
  prompt: string;
  contextFilePaths?: string[];
}

export interface AiWorkspaceResponseEnvelope<T> {
  data: T;
  requestId: string;
  createdAt: string;
}

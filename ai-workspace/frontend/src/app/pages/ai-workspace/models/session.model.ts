import { AiWorkspaceMode } from './ai-workspace.model';

export interface AiSession {
  id: string;
  repositoryId: string;
  branch: string;
  mode: AiWorkspaceMode;
  currentTask?: string;
  startedAt: string;
  lastActivityAt: string;
}

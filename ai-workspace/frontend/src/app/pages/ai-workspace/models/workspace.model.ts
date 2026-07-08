export type WorkspaceValidationState = 'unvalidated' | 'validating' | 'valid' | 'invalid';

export interface RepositoryMetadata {
  id: string;
  name: string;
  path: string;
  defaultBranch: string;
}

export interface WorkspaceInfo {
  path: string;
  validationState: WorkspaceValidationState;
  validationMessage?: string;
  repository?: RepositoryMetadata;
}

export type AiFileNodeType = 'file' | 'folder';

export type AiFileNodeStatus = 'M' | 'A' | 'D' | null;

export interface AiFileNode {
  id: string;
  name: string;
  path: string;
  type: AiFileNodeType;
  status?: AiFileNodeStatus;
  children?: AiFileNode[];
}

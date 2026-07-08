import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { AI_WORKSPACE_API_PREFIX } from './ai-workspace.service';
import { AiFileNode, WorkspaceInfo } from '../models/workspace.model';

export interface RepositoryOption {
  id: string;
  name: string;
  path: string;
}

export interface BranchOption {
  id: string;
  name: string;
  isDefault?: boolean;
  syncedAt?: string;
}

@Injectable({ providedIn: 'root' })
export class WorkspaceService {
  constructor(private readonly http: HttpClient) {}

  validatePath(path: string): Observable<WorkspaceInfo> {
    return this.http.post<WorkspaceInfo>(`${AI_WORKSPACE_API_PREFIX}/workspace/validate`, { path });
  }

  getRepositories(): Observable<RepositoryOption[]> {
    return this.http.get<RepositoryOption[]>(`${AI_WORKSPACE_API_PREFIX}/repositories`);
  }

  getBranches(repositoryId: string): Observable<BranchOption[]> {
    return this.http.get<BranchOption[]>(
      `${AI_WORKSPACE_API_PREFIX}/repositories/${encodeURIComponent(repositoryId)}/branches`,
    );
  }

  getFiles(repositoryId: string, branch: string): Observable<AiFileNode[]> {
    return this.http.get<AiFileNode[]>(
      `${AI_WORKSPACE_API_PREFIX}/repositories/${encodeURIComponent(repositoryId)}/files`,
      { params: { branch } },
    );
  }

  getFileContent(repositoryId: string, branch: string, path: string): Observable<{ content: string }> {
    return this.http.get<{ content: string }>(
      `${AI_WORKSPACE_API_PREFIX}/repositories/${encodeURIComponent(repositoryId)}/file-content`,
      { params: { branch, path } },
    );
  }
}

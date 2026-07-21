import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

export interface WorkspaceValidation {
  valid: boolean;
  resolved_path?: string;
  repository?: { is_git: boolean; technologies: string[]; name: string };
  error?: string;
}

export interface Health {
  status: string;
  version: string;
  llm_provider: string;
  default_workspace: string;
}

@Injectable({ providedIn: 'root' })
export class WorkspaceService {
  constructor(private http: HttpClient) {}

  validate(workspacePath: string): Observable<WorkspaceValidation> {
    return this.http.post<WorkspaceValidation>('/api/workspaces/validate', {
      workspace_path: workspacePath,
    });
  }

  health(): Observable<Health> {
    return this.http.get<Health>('/api/health');
  }
}

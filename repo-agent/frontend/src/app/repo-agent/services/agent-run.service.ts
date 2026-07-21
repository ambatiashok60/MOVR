import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import {
  AgentMode, AgentRunError, CreateRunResponse, FileChange, ValidationResult,
} from '../models/repo-agent.models';

export interface CreateRunBody {
  workspace_path: string;
  conversation_id?: string | null;
  mode: AgentMode;
  message: string;
  client_request_id: string;
}

export interface RunView {
  run_id: string;
  status: string;
  error: AgentRunError | null;
  tool_call_count: number;
  files_read_count: number;
  files_modified_count: number;
  last_event_sequence: number;
}

@Injectable({ providedIn: 'root' })
export class AgentRunService {
  constructor(private http: HttpClient) {}

  createRun(body: CreateRunBody): Observable<CreateRunResponse> {
    return this.http.post<CreateRunResponse>('/api/agent-runs', body);
  }

  getRun(runId: string): Observable<RunView> {
    return this.http.get<RunView>(`/api/agent-runs/${runId}`);
  }

  getByClientRequest(clientRequestId: string): Observable<RunView> {
    return this.http.get<RunView>(`/api/agent-runs/by-client-request/${clientRequestId}`);
  }

  cancel(runId: string): Observable<RunView> {
    return this.http.post<RunView>(`/api/agent-runs/${runId}/cancel`, {});
  }

  revert(runId: string): Observable<{ reverted: string[] }> {
    return this.http.post<{ reverted: string[] }>(`/api/agent-runs/${runId}/revert`, {});
  }

  getChanges(runId: string): Observable<FileChange[]> {
    return this.http.get<FileChange[]>(`/api/agent-runs/${runId}/changes`);
  }

  getValidation(runId: string): Observable<ValidationResult[]> {
    return this.http.get<ValidationResult[]>(`/api/agent-runs/${runId}/validation`);
  }
}

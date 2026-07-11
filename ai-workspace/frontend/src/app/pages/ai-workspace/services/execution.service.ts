import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { AI_WORKSPACE_API_PREFIX } from './ai-workspace.service';
import { ExecutionRun } from '../models/execution.model';

@Injectable({ providedIn: 'root' })
export class ExecutionService {
  constructor(private readonly http: HttpClient) {}

  getExecution(executionId: string): Observable<ExecutionRun> {
    return this.http.get<ExecutionRun>(`${AI_WORKSPACE_API_PREFIX}/agent/executions/${executionId}`);
  }

  cancel(executionId: string): Observable<void> {
    return this.http.post<void>(`${AI_WORKSPACE_API_PREFIX}/agent/executions/${executionId}/cancel`, {});
  }

  retry(executionId: string): Observable<ExecutionRun> {
    return this.http.post<ExecutionRun>(`${AI_WORKSPACE_API_PREFIX}/agent/executions/${executionId}/retry`, {});
  }
}

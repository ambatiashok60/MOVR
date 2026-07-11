import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { AI_WORKSPACE_API_PREFIX } from './ai-workspace.service';
import { AiWorkspaceRequest } from '../models/ai-workspace.model';
import { AgentPlan } from '../models/agent-plan.model';
import { ExecutionRun } from '../models/execution.model';

@Injectable({ providedIn: 'root' })
export class AgentService {
  constructor(private readonly http: HttpClient) {}

  startRun(payload: AiWorkspaceRequest): Observable<ExecutionRun> {
    return this.http.post<ExecutionRun>(`${AI_WORKSPACE_API_PREFIX}/agent/run`, payload);
  }

  getPlan(executionId: string): Observable<AgentPlan> {
    return this.http.get<AgentPlan>(`${AI_WORKSPACE_API_PREFIX}/agent/executions/${executionId}/plan`);
  }
}

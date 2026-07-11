import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { AiWorkspaceRequest } from '../models/ai-workspace.model';
import { ChatMessage } from '../models/chat-message.model';
import { ExecutionRun } from '../models/execution.model';

// TODO integration: replace with the host app's real API base URL provider
// (e.g. environment.apiBaseUrl) instead of this hardcoded prefix.
export const AI_WORKSPACE_API_PREFIX = '/api/ai-workspace';

/**
 * Core Ask/Agent entry points. Session, conversation, execution, and review concerns each
 * have their own dedicated service (see conversation.service.ts, execution.service.ts,
 * review.service.ts) — this service is intentionally thin.
 */
@Injectable({ providedIn: 'root' })
export class AiWorkspaceService {
  constructor(private readonly http: HttpClient) {}

  ask(payload: AiWorkspaceRequest): Observable<ChatMessage> {
    return this.http.post<ChatMessage>(`${AI_WORKSPACE_API_PREFIX}/ask`, payload);
  }

  runAgent(payload: AiWorkspaceRequest): Observable<ExecutionRun> {
    return this.http.post<ExecutionRun>(`${AI_WORKSPACE_API_PREFIX}/agent/run`, payload);
  }
}

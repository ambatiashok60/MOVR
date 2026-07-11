import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { AI_WORKSPACE_API_PREFIX } from './ai-workspace.service';
import { ContextSummary } from '../models/context.model';

/** Surfaces selected-file context state for the "Context (N files, N tokens)" panel. */
@Injectable({ providedIn: 'root' })
export class ContextBuilderService {
  constructor(private readonly http: HttpClient) {}

  getContextSummary(sessionId: string): Observable<ContextSummary> {
    return this.http.get<ContextSummary>(`${AI_WORKSPACE_API_PREFIX}/sessions/${sessionId}/context`);
  }

  setPriorityFiles(sessionId: string, filePaths: string[]): Observable<ContextSummary> {
    return this.http.put<ContextSummary>(`${AI_WORKSPACE_API_PREFIX}/sessions/${sessionId}/context`, {
      filePaths,
    });
  }
}

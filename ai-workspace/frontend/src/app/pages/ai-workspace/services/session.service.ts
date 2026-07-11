import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { AI_WORKSPACE_API_PREFIX } from './ai-workspace.service';
import { AiSession } from '../models/session.model';

@Injectable({ providedIn: 'root' })
export class SessionService {
  constructor(private readonly http: HttpClient) {}

  createSession(repositoryId: string, branch: string): Observable<AiSession> {
    return this.http.post<AiSession>(`${AI_WORKSPACE_API_PREFIX}/sessions`, { repositoryId, branch });
  }

  listSessions(repositoryId?: string): Observable<AiSession[]> {
    return this.http.get<AiSession[]>(`${AI_WORKSPACE_API_PREFIX}/sessions`, {
      params: repositoryId ? { repositoryId } : {},
    });
  }

  getSession(sessionId: string): Observable<AiSession> {
    return this.http.get<AiSession>(`${AI_WORKSPACE_API_PREFIX}/sessions/${sessionId}`);
  }
}

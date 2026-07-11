import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { AI_WORKSPACE_API_PREFIX } from './ai-workspace.service';
import { PromptTemplate } from '../models/prompt.model';

@Injectable({ providedIn: 'root' })
export class PromptLibraryService {
  constructor(private readonly http: HttpClient) {}

  listPrompts(mode?: 'ask' | 'agent'): Observable<PromptTemplate[]> {
    return this.http.get<PromptTemplate[]>(`${AI_WORKSPACE_API_PREFIX}/prompts`, {
      params: mode ? { mode } : {},
    });
  }

  getPrompt(promptId: string): Observable<PromptTemplate> {
    return this.http.get<PromptTemplate>(`${AI_WORKSPACE_API_PREFIX}/prompts/${promptId}`);
  }
}

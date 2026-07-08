import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { AI_WORKSPACE_API_PREFIX } from './ai-workspace.service';
import { ChatMessage } from '../models/chat-message.model';

@Injectable({ providedIn: 'root' })
export class ConversationService {
  constructor(private readonly http: HttpClient) {}

  getMessages(sessionId: string): Observable<ChatMessage[]> {
    return this.http.get<ChatMessage[]>(`${AI_WORKSPACE_API_PREFIX}/sessions/${sessionId}/messages`);
  }

  sendMessage(sessionId: string, content: string): Observable<ChatMessage> {
    return this.http.post<ChatMessage>(`${AI_WORKSPACE_API_PREFIX}/sessions/${sessionId}/messages`, {
      content,
    });
  }
}

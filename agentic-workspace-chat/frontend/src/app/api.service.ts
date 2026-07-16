import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';

export interface Workspace { path: string; name: string; isGit: boolean; }
export interface RuntimeConfig { provider: string; model: { id: string; displayName: string }; region: string; features: { streaming: boolean; toolCalling: boolean; reviewedEdits: boolean; customTools: boolean }; }
export interface Session { id: string; workspace: string | null; createdAt: string; updatedAt: string; }
export interface DiffHunk { id: string; header: string; lines: string[]; }
export interface ProposedChange { path: string; operation: 'create' | 'update' | 'delete'; diff: string; hunks?: DiffHunk[]; }
export interface Proposal { id: string; changes: ProposedChange[]; }
export interface ActionProposal { id: string; name: string; description: string; code: string; persistent: boolean; inputPaths: string[]; }
export interface AgentResponse { message: string; proposal: Proposal | null; events: { tool: string; status: string }[]; actions: ActionProposal[]; plan: { step: string; status: string }[]; relationships: { path: string; line: number; text: string; relation: string }[]; }

@Injectable({ providedIn: 'root' })
export class ApiService {
  constructor(private http: HttpClient) {}

  validate(path: string) {
    return this.http.post<Workspace>('/api/workspaces/validate', { path });
  }

  files(path: string) {
    return this.http.post<{ files: string[] }>('/api/workspaces/files', { path });
  }

  runtimeConfig() {
    return this.http.get<RuntimeConfig>('/api/config');
  }

  createSession(path: string) { return this.http.post<Session>('/api/sessions', { path }); }
  sessions() { return this.http.get<{ sessions: Session[] }>('/api/sessions'); }
  sessionMessages(id: string) { return this.http.get<{ messages: any[] }>(`/api/sessions/${id}/messages`); }

  chat(path: string, message: string, files: string[], detail: 'auto' | 'brief' | 'detailed', sessionId?: string) {
    return this.http.post<AgentResponse>('/api/chat', { path, message, files, detail, session_id: sessionId });
  }

  apply(proposalId: string, acceptedPaths: string[], acceptedHunks: Record<string, string[]>) {
    return this.http.post<{ applied: string[] }>('/api/proposals/apply', {
      proposal_id: proposalId, accepted_paths: acceptedPaths, accepted_hunks: acceptedHunks,
    });
  }

  approveAction(actionId: string) {
    return this.http.post<{ installed: string | null; proposal: Proposal | null }>('/api/actions/approve', {
      action_id: actionId,
    });
  }
}

import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable, timeout } from 'rxjs';

export interface Workspace { path: string; name: string; isGit: boolean; }
export interface RepositorySummary { fileCount: number; isGit: boolean; languages: { name: string; files: number }[]; topDirectories: string[]; }
export interface RuntimeConfig { provider: string; model: { id: string; displayName: string }; region: string; limits: { requestTimeoutSeconds: number }; features: { streaming: boolean; toolCalling: boolean; reviewedEdits: boolean; customTools: boolean }; }
export interface Health { status: string; region: string; model: string; }
export interface Session { id: string; workspace: string | null; createdAt: string; updatedAt: string; }
export interface DiffHunk { id: string; header: string; lines: string[]; }
export interface ProposedChange { path: string; operation: 'create' | 'update' | 'delete'; diff: string; hunks?: DiffHunk[]; }
export interface Proposal { id: string; changes: ProposedChange[]; }
export interface ActionProposal { id: string; name: string; description: string; code: string; persistent: boolean; inputPaths: string[]; }
export interface AgentResponse { message: string; proposal: Proposal | null; events: { tool: string; status: string }[]; actions: ActionProposal[]; plan: { step: string; status: string }[]; relationships: { path: string; line: number; text: string; relation: string }[]; }

@Injectable({ providedIn: 'root' })
export class ApiService {
  constructor(private http: HttpClient) {}

  private bounded<T>(request: Observable<T>, seconds = 15): Observable<T> {
    return request.pipe(timeout({ first: seconds * 1_000 }));
  }

  health() { return this.bounded(this.http.get<Health>('/api/health'), 5); }

  validate(path: string) {
    return this.bounded(this.http.post<Workspace>('/api/workspaces/validate', { path }));
  }

  files(path: string) {
    return this.bounded(this.http.post<{ files: string[]; summary: RepositorySummary }>('/api/workspaces/files', { path }), 30);
  }

  runtimeConfig() {
    return this.bounded(this.http.get<RuntimeConfig>('/api/config'), 5);
  }

  createSession(path: string) { return this.bounded(this.http.post<Session>('/api/sessions', { path })); }
  sessions() { return this.bounded(this.http.get<{ sessions: Session[] }>('/api/sessions')); }
  sessionMessages(id: string) { return this.bounded(this.http.get<{ messages: any[] }>(`/api/sessions/${id}/messages`)); }

  chat(path: string, message: string, files: string[], detail: 'auto' | 'brief' | 'detailed', sessionId?: string, requestTimeoutSeconds = 300) {
    return this.bounded(
      this.http.post<AgentResponse>('/api/chat', { path, message, files, detail, session_id: sessionId }),
      requestTimeoutSeconds + 10,
    );
  }

  apply(proposalId: string, acceptedPaths: string[], acceptedHunks: Record<string, string[]>) {
    return this.bounded(this.http.post<{ applied: string[] }>('/api/proposals/apply', {
      proposal_id: proposalId, accepted_paths: acceptedPaths, accepted_hunks: acceptedHunks,
    }), 30);
  }

  approveAction(actionId: string) {
    return this.bounded(this.http.post<{ installed: string | null; proposal: Proposal | null }>('/api/actions/approve', {
      action_id: actionId,
    }), 30);
  }
}

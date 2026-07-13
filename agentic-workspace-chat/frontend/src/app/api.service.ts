import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';

export interface Workspace { path: string; name: string; isGit: boolean; }
export interface ProposedChange { path: string; operation: 'create' | 'update' | 'delete'; diff: string; }
export interface Proposal { id: string; changes: ProposedChange[]; }
export interface ActionProposal { id: string; name: string; description: string; code: string; persistent: boolean; inputPaths: string[]; }
export interface AgentResponse { message: string; proposal: Proposal | null; events: { tool: string; status: string }[]; actions: ActionProposal[]; }

@Injectable({ providedIn: 'root' })
export class ApiService {
  constructor(private http: HttpClient) {}

  validate(path: string) {
    return this.http.post<Workspace>('/api/workspaces/validate', { path });
  }

  files(path: string) {
    return this.http.post<{ files: string[] }>('/api/workspaces/files', { path });
  }

  chat(path: string, message: string, files: string[]) {
    return this.http.post<AgentResponse>('/api/chat', { path, message, files });
  }

  apply(proposalId: string, acceptedPaths: string[]) {
    return this.http.post<{ applied: string[] }>('/api/proposals/apply', {
      proposal_id: proposalId, accepted_paths: acceptedPaths,
    });
  }

  approveAction(actionId: string) {
    return this.http.post<{ installed: string | null; proposal: Proposal | null }>('/api/actions/approve', {
      action_id: actionId,
    });
  }
}

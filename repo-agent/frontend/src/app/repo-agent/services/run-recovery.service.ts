import { Injectable } from '@angular/core';
import { AgentMode } from '../models/repo-agent.models';

export interface PersistedActiveRun {
  runId: string;
  conversationId: string | null;
  lastEventSequence: number;
  workspacePath: string;
  mode: AgentMode;
}

const KEY = 'repo-agent.active-run';

/** Persists just enough to recover an in-flight run across a page refresh.
 *  The backend remains authoritative — on load we fetch run state, then
 *  reconnect the SSE stream from lastEventSequence. */
@Injectable({ providedIn: 'root' })
export class RunRecoveryService {
  save(run: PersistedActiveRun): void {
    sessionStorage.setItem(KEY, JSON.stringify(run));
  }

  load(): PersistedActiveRun | null {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return null;
    try {
      return JSON.parse(raw) as PersistedActiveRun;
    } catch {
      return null;
    }
  }

  clear(): void {
    sessionStorage.removeItem(KEY);
  }
}

import { AgentRunStatus, BackendRunStatus, TERMINAL_STATUSES } from '../models/repo-agent.models';

/** One central mapping so backend-status comparisons don't scatter. */
export function mapBackendStatus(status: BackendRunStatus): AgentRunStatus {
  return status;
}

export function isTerminal(status: AgentRunStatus): boolean {
  return TERMINAL_STATUSES.includes(status);
}

export function isActive(status: AgentRunStatus): boolean {
  return ['submitting', 'queued', 'planning', 'running', 'validating', 'completing',
          'waiting_for_auth', 'recovering', 'connection_lost'].includes(status);
}

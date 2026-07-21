import { Injectable, computed, signal } from '@angular/core';
import {
  AgentMode, AgentRunState, AgentRunStatus, ExecutionPlan, ResponseBatchState,
  ValidationResult,
} from '../models/repo-agent.models';
import { EventDeduplicator } from '../utils/event-deduplicator';
import { isActive, isTerminal } from '../utils/run-state-mapper';

const EMPTY: AgentRunState = {
  runId: null, conversationId: null, workspacePath: '', mode: 'agent',
  status: 'idle', lastEventSequence: 0, lastEventAt: 0, lastHeartbeatAt: 0,
  plan: null, responseBatches: [], relevantFiles: [], fileChanges: [],
  validationResults: [], toolCallCount: 0, filesReadCount: 0, filesModifiedCount: 0,
  latestActions: [], error: null, needsAuth: false,
};

/** Single source of truth for the active run. All SSE events flow through
 *  applyEvent() so counters/batches never diverge across components. */
@Injectable({ providedIn: 'root' })
export class RepoAgentStore {
  private readonly _state = signal<AgentRunState>({ ...EMPTY });
  private readonly dedup = new EventDeduplicator();

  readonly state = this._state.asReadonly();
  readonly status = computed(() => this._state().status);
  readonly plan = computed(() => this._state().plan);
  readonly responseBatches = computed(() => this._state().responseBatches);
  readonly relevantFiles = computed(() => this._state().relevantFiles);
  readonly validationResults = computed(() => this._state().validationResults);
  readonly latestActions = computed(() => this._state().latestActions);
  readonly canSubmit = computed(() => !isActive(this._state().status));
  readonly canCancel = computed(() => isActive(this._state().status));
  readonly needsAuth = computed(() => this._state().needsAuth);

  private patch(p: Partial<AgentRunState>): void {
    this._state.update((s) => ({ ...s, ...p }));
  }

  setMode(mode: AgentMode): void { this.patch({ mode }); }
  setWorkspace(path: string): void { this.patch({ workspacePath: path }); }

  startSubmitting(): void {
    this.dedup.reset();
    this._state.set({ ...EMPTY, mode: this._state().mode,
      workspacePath: this._state().workspacePath, status: 'submitting' });
  }

  attachRun(runId: string, conversationId: string): void {
    this.patch({ runId, conversationId, status: 'queued', lastEventAt: Date.now(),
      lastHeartbeatAt: Date.now() });
  }

  setStatus(status: AgentRunStatus): void { this.patch({ status }); }
  markConnectionLost(): void {
    if (isActive(this._state().status)) this.patch({ status: 'connection_lost' });
  }

  private action(label: string): void {
    const latest = [{ label, at: Date.now() }, ...this._state().latestActions].slice(0, 8);
    this.patch({ latestActions: latest });
  }

  /** The SSE reducer — the only place run state mutates from events. */
  applyEvent(type: string, data: Record<string, unknown>): void {
    const seq = data['sequence'] as number | undefined;
    if (!this.dedup.accept(seq)) return;
    this.patch({ lastEventSequence: this.dedup.current, lastEventAt: Date.now() });

    switch (type) {
      case 'heartbeat':
        this.patch({ lastHeartbeatAt: Date.now() });
        if (this._state().status === 'connection_lost') this.patch({ status: 'running' });
        break;
      case 'run_started': this.patch({ status: 'running' }); this.action('Run started'); break;
      case 'plan_created':
        this.patch({ plan: data['plan'] as ExecutionPlan }); this.action('Plan created'); break;
      case 'plan_updated': this.patch({ plan: data['plan'] as ExecutionPlan }); break;
      case 'tool_started': this.action('Started ' + (data['tool_name'] as string)); break;
      case 'tool_completed':
      case 'tool_failed':
        this.patch({ toolCallCount: this._state().toolCallCount + 1 });
        this.action((data['success'] ? '' : 'Failed ') + (data['summary'] as string));
        break;
      case 'validation_started': this.patch({ status: 'validating' }); this.action('Validation started'); break;
      case 'validation_completed':
        this.patch({ validationResults: (data['results'] as ValidationResult[]) ?? [] });
        this.action('Validation completed'); break;
      case 'aws_reauthentication_required':
        this.patch({ status: 'waiting_for_auth', needsAuth: true }); break;
      case 'aws_reauthenticated':
        this.patch({ status: 'running', needsAuth: false }); break;
      case 'conversation_compacted': this.action('Older context compacted'); break;
      case 'response_batch_started': this.startBatch(data); break;
      case 'response_delta': this.appendDelta(data); break;
      case 'response_batch_completed': this.completeBatch(data['batch_id'] as string); break;
      case 'run_completed':
        this.patch({
          status: 'completed',
          filesReadCount: (data['files_read'] as number) ?? this._state().filesReadCount,
          toolCallCount: (data['tool_calls'] as number) ?? this._state().toolCallCount,
          filesModifiedCount: (data['files_modified'] as number) ?? this._state().filesModifiedCount,
        });
        this.action('Run completed'); break;
      case 'run_failed':
        this.patch({ status: 'failed', error: (data['error'] as AgentRunState['error']) ?? null });
        this.action('Run failed'); break;
      case 'run_cancelled': this.patch({ status: 'cancelled' }); this.action('Run cancelled'); break;
    }
  }

  private startBatch(data: Record<string, unknown>): void {
    const batch: ResponseBatchState = {
      batchId: data['batch_id'] as string, index: data['index'] as number,
      type: data['type'] as ResponseBatchState['type'], title: data['title'] as string,
      markdown: '', status: 'streaming',
    };
    this.patch({ responseBatches: [...this._state().responseBatches, batch] });
  }

  private appendDelta(data: Record<string, unknown>): void {
    const id = data['batch_id'] as string;
    const delta = (data['delta'] as string) ?? '';
    this.patch({
      responseBatches: this._state().responseBatches.map((b) =>
        b.batchId === id ? { ...b, markdown: b.markdown + delta } : b),
    });
  }

  private completeBatch(id: string): void {
    this.patch({
      responseBatches: this._state().responseBatches.map((b) =>
        b.batchId === id ? { ...b, status: 'completed' } : b),
    });
  }

  addRelevantFiles(paths: string[]): void {
    const set = new Set([...this._state().relevantFiles, ...paths]);
    this.patch({ relevantFiles: [...set] });
  }

  isTerminal(): boolean { return isTerminal(this._state().status); }
}

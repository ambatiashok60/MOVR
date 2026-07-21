import { Injectable, NgZone } from '@angular/core';
import { Subject } from 'rxjs';

export interface StreamMessage {
  type: string;
  data: Record<string, unknown>;
}

const EVENT_TYPES = [
  'run_started', 'plan_created', 'plan_updated', 'tool_started', 'tool_completed',
  'tool_failed', 'observation_created', 'response_batch_started', 'response_delta',
  'response_batch_completed', 'validation_started', 'validation_completed',
  'conversation_compacted', 'aws_reauthentication_required', 'aws_reauthenticated',
  'run_completed', 'run_failed', 'run_cancelled', 'heartbeat',
];

/** Owns the EventSource lifecycle. Reconnection is delegated to the browser's
 *  native EventSource (which resends Last-Event-ID); on manual reconnect we pass
 *  ?after_sequence=N so the server replays only what was missed. */
@Injectable({ providedIn: 'root' })
export class AgentStreamService {
  private source: EventSource | null = null;
  readonly events$ = new Subject<StreamMessage>();
  readonly connectionState$ = new Subject<'connecting' | 'connected' | 'reconnecting' | 'failed'>();

  constructor(private zone: NgZone) {}

  connect(runId: string, afterSequence = 0): void {
    this.disconnect();
    this.connectionState$.next('connecting');
    const source = new EventSource(`/api/agent-runs/${runId}/events?after_sequence=${afterSequence}`);
    this.source = source;

    source.onopen = () => this.zone.run(() => this.connectionState$.next('connected'));
    source.onerror = () => this.zone.run(() => this.connectionState$.next('reconnecting'));

    EVENT_TYPES.forEach((type) => {
      source.addEventListener(type, (e: MessageEvent) => {
        this.zone.run(() => {
          try {
            this.events$.next({ type, data: JSON.parse(e.data) });
          } catch {
            /* ignore malformed frame */
          }
        });
      });
    });
  }

  /** Reconnect from the last processed sequence (server replays the gap). */
  reconnect(runId: string, afterSequence: number): void {
    this.connect(runId, afterSequence);
  }

  disconnect(): void {
    if (this.source) {
      this.source.close();
      this.source = null;
    }
  }
}

import { ChangeDetectionStrategy, Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subscription } from 'rxjs';

import { RepoAgentStore } from '../state/repo-agent.store';
import { AgentRunService } from '../services/agent-run.service';
import { AgentStreamService } from '../services/agent-stream.service';
import { WorkspaceService } from '../services/workspace.service';
import { ConnectivityService } from '../services/connectivity.service';
import { RunRecoveryService } from '../services/run-recovery.service';
import { ExecutionProgressComponent } from '../components/execution-progress.component';
import { PlanPanelComponent } from '../components/plan-panel.component';
import { ResponseBatchComponent } from '../components/response-batch.component';
import { ConversationSidebarComponent } from '../components/conversation-sidebar.component';
import { AgentMode } from '../models/repo-agent.models';
import { isActive } from '../utils/run-state-mapper';

const HEARTBEAT_RECONNECT_MS = 75_000;

@Component({
  selector: 'ra-repo-agent-workspace',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    CommonModule, FormsModule, ExecutionProgressComponent, PlanPanelComponent,
    ResponseBatchComponent, ConversationSidebarComponent,
  ],
  templateUrl: './repo-agent-workspace.component.html',
  styleUrl: './repo-agent-workspace.component.scss',
})
export class RepoAgentWorkspaceComponent implements OnInit, OnDestroy {
  readonly store = inject(RepoAgentStore);
  readonly connectivity = inject(ConnectivityService);
  private readonly runs = inject(AgentRunService);
  private readonly stream = inject(AgentStreamService);
  private readonly workspaces = inject(WorkspaceService);
  private readonly recovery = inject(RunRecoveryService);

  message = 'Fix the API scenario generation status update. It is not updating to completed in some cases.';
  readonly backendStatus = signal<'checking' | 'connected' | 'unavailable'>('checking');
  private subs: Subscription[] = [];
  private watchdog?: ReturnType<typeof setInterval>;

  ngOnInit(): void {
    this.subs.push(
      this.stream.events$.subscribe(({ type, data }) => this.onEvent(type, data)),
    );
    this.workspaces.health().subscribe({
      next: (h) => {
        this.backendStatus.set('connected');
        if (!this.store.state().workspacePath) this.store.setWorkspace(h.default_workspace);
      },
      error: () => this.backendStatus.set('unavailable'),
    });
    this.attemptRecovery();
    this.watchdog = setInterval(() => this.checkHealth(), 5_000);
  }

  ngOnDestroy(): void {
    this.subs.forEach((s) => s.unsubscribe());
    this.stream.disconnect();
    if (this.watchdog) clearInterval(this.watchdog);
  }

  setMode(mode: AgentMode): void { this.store.setMode(mode); }
  onWorkspaceInput(value: string): void { this.store.setWorkspace(value); }

  submit(): void {
    const workspace = this.store.state().workspacePath.trim();
    const message = this.message.trim();
    if (!workspace || !message || !this.store.canSubmit()) return;

    // Idempotency: one key per user submission; reused on any retry.
    const clientRequestId = crypto.randomUUID();
    this.store.startSubmitting();

    this.runs.createRun({
      workspace_path: workspace, mode: this.store.state().mode, message,
      conversation_id: this.store.state().conversationId, client_request_id: clientRequestId,
    }).subscribe({
      next: (res) => {
        this.store.attachRun(res.run_id, res.conversation_id);
        this.stream.connect(res.run_id, 0);
        this.recovery.save({
          runId: res.run_id, conversationId: res.conversation_id, lastEventSequence: 0,
          workspacePath: workspace, mode: this.store.state().mode,
        });
      },
      error: () => this.store.setStatus('failed'),
    });
  }

  cancel(): void {
    const runId = this.store.state().runId;
    if (!runId) return;
    this.stream.disconnect();
    this.runs.cancel(runId).subscribe();
  }

  newChat(): void {
    this.stream.disconnect();
    this.recovery.clear();
    this.store.startSubmitting();
    this.store.setStatus('idle');
  }

  private onEvent(type: string, data: Record<string, unknown>): void {
    this.store.applyEvent(type, data);
    const s = this.store.state();
    if (s.runId) {
      this.recovery.save({
        runId: s.runId, conversationId: s.conversationId, lastEventSequence: s.lastEventSequence,
        workspacePath: s.workspacePath, mode: s.mode,
      });
    }
    if (['run_completed', 'run_failed', 'run_cancelled'].includes(type)) {
      this.refreshArtifacts();
      this.recovery.clear();
      this.stream.disconnect();
    }
  }

  private refreshArtifacts(): void {
    const runId = this.store.state().runId;
    if (!runId) return;
    this.runs.getChanges(runId).subscribe((changes) =>
      this.store.addRelevantFiles(changes.map((c) => c.path)));
  }

  /** Watchdog: if the stream goes silent past the threshold, fall back to REST
   *  run-state (never assume failure from a lost connection). */
  private checkHealth(): void {
    const s = this.store.state();
    if (!s.runId || !isActive(s.status)) return;
    if (Date.now() - s.lastHeartbeatAt > HEARTBEAT_RECONNECT_MS) {
      this.store.markConnectionLost();
      this.stream.reconnect(s.runId, s.lastEventSequence);
      this.runs.getRun(s.runId).subscribe((run) => {
        if (['completed', 'failed', 'cancelled'].includes(run.status)) {
          this.store.setStatus(run.status as never);
        }
      });
    }
  }

  private attemptRecovery(): void {
    const active = this.recovery.load();
    if (!active) return;
    this.runs.getRun(active.runId).subscribe({
      next: (run) => {
        this.store.setWorkspace(active.workspacePath);
        this.store.setMode(active.mode);
        this.store.attachRun(active.runId, active.conversationId ?? '');
        if (['completed', 'failed', 'cancelled'].includes(run.status)) {
          this.store.setStatus(run.status as never);
          this.refreshArtifacts();
        } else {
          this.store.setStatus('recovering');
          this.stream.connect(active.runId, active.lastEventSequence);
        }
      },
      error: () => this.recovery.clear(),
    });
  }
}

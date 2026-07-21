import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AgentRunStatus } from '../models/repo-agent.models';

const STAGES: [string, string][] = [
  ['understand', 'Understand'], ['plan', 'Plan'], ['inspect', 'Inspect Repository'],
  ['modify', 'Modify Code'], ['validate', 'Validate'], ['complete', 'Complete'],
];

const REACHED: Record<string, number> = {
  queued: 1, planning: 1, running: 2, validating: 4, completing: 5,
  completed: 6, failed: 6, cancelled: 6, waiting_for_auth: 2,
};

@Component({
  selector: 'ra-execution-progress',
  standalone: true,
  imports: [CommonModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="stages">
      <ng-container *ngFor="let stage of stages; let i = index">
        <div class="stage" [class.done]="i < reached" [class.active]="i === reached && status !== 'completed'">
          <div class="ring">{{ i < reached ? '✓' : (i === reached ? '●' : '') }}</div>
          <div class="label">{{ stage[1] }}</div>
        </div>
        <div class="sep" *ngIf="i < stages.length - 1"></div>
      </ng-container>
    </div>
  `,
})
export class ExecutionProgressComponent {
  @Input() status: AgentRunStatus = 'idle';
  readonly stages = STAGES;
  get reached(): number { return REACHED[this.status] ?? 0; }
}

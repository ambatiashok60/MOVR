import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ExecutionPlan } from '../models/repo-agent.models';

@Component({
  selector: 'ra-plan-panel',
  standalone: true,
  imports: [CommonModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div *ngIf="plan; else empty">
      <div class="plan-step" *ngFor="let step of plan.steps" [class]="'plan-step ' + step.status">
        <span class="mk">{{ step.status === 'completed' ? '✓' : (step.status === 'in_progress' ? '●' : '') }}</span>
        <span>{{ step.title }}</span>
      </div>
    </div>
    <ng-template #empty><div class="empty">No active run.</div></ng-template>
  `,
})
export class PlanPanelComponent {
  @Input() plan: ExecutionPlan | null = null;
}

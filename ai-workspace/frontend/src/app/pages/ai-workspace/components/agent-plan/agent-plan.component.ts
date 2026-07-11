import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';

import { AgentPlan } from '../../models/agent-plan.model';

@Component({
  selector: 'app-agent-plan',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './agent-plan.component.html',
  styleUrl: './agent-plan.component.scss',
})
export class AgentPlanComponent {
  @Input() plan: AgentPlan | null = null;
}

import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';

import { ExecutionRun } from '../../models/execution.model';
import { StatusLabelPipe } from '../../../../shared/pipes/status-label.pipe';

@Component({
  selector: 'app-execution-timeline',
  standalone: true,
  imports: [CommonModule, StatusLabelPipe],
  templateUrl: './execution-timeline.component.html',
  styleUrl: './execution-timeline.component.scss',
})
export class ExecutionTimelineComponent {
  @Input() execution: ExecutionRun | null = null;
}

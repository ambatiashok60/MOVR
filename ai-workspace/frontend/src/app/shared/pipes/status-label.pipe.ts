import { Pipe, PipeTransform } from '@angular/core';

import { ExecutionStatus } from '../../pages/ai-workspace/models/ai-workspace.model';

const LABEL_BY_STATUS: Record<ExecutionStatus, string> = {
  idle: 'Idle',
  planning: 'Planning',
  running: 'Running',
  completed: 'Completed',
  failed: 'Failed',
  cancelled: 'Cancelled',
};

@Pipe({ name: 'statusLabel', standalone: true })
export class StatusLabelPipe implements PipeTransform {
  transform(status: ExecutionStatus | undefined | null): string {
    if (!status) return '';
    return LABEL_BY_STATUS[status];
  }
}

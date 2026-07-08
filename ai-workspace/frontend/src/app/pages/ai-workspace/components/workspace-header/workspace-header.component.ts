import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';

import { AiWorkspaceMode } from '../../models/ai-workspace.model';

@Component({
  selector: 'app-workspace-header',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './workspace-header.component.html',
  styleUrl: './workspace-header.component.scss',
})
export class WorkspaceHeaderComponent {
  @Input() workspaceName = '';
  @Input() mode: AiWorkspaceMode = 'agent';
  @Input() modelName?: string;
  @Input() syncedAt?: string;
}

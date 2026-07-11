import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';

import { AiWorkspaceMode } from '../../models/ai-workspace.model';

@Component({
  selector: 'app-mode-toggle',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './mode-toggle.component.html',
  styleUrl: './mode-toggle.component.scss',
})
export class ModeToggleComponent {
  @Input() mode: AiWorkspaceMode = 'agent';
  @Output() modeChange = new EventEmitter<AiWorkspaceMode>();

  select(mode: AiWorkspaceMode): void {
    if (mode !== this.mode) this.modeChange.emit(mode);
  }
}

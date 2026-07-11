import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';

import { WorkspaceInfo } from '../../models/workspace.model';

@Component({
  selector: 'app-workspace-selector',
  standalone: true,
  imports: [CommonModule, FormsModule, ButtonModule, InputTextModule],
  templateUrl: './workspace-selector.component.html',
  styleUrl: './workspace-selector.component.scss',
})
export class WorkspaceSelectorComponent {
  @Input() workspace: WorkspaceInfo | null = null;
  @Output() pathSubmitted = new EventEmitter<string>();

  pathInput = '';

  submit(): void {
    if (!this.pathInput.trim()) return;
    this.pathSubmitted.emit(this.pathInput.trim());
  }
}

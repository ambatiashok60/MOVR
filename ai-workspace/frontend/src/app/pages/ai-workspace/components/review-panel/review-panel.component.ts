import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';
import { BadgeModule } from 'primeng/badge';
import { ButtonModule } from 'primeng/button';
import { SplitButtonModule } from 'primeng/splitbutton';
import { MenuItem } from 'primeng/api';

import { FileChange } from '../../models/file-change.model';
import { ReviewDecision } from '../../models/review.model';
import { FileChangeCardComponent } from '../file-change-card/file-change-card.component';
import { DiffViewerComponent } from '../diff-viewer/diff-viewer.component';

export interface FileDecisionEvent {
  fileId: string;
  decision: Extract<ReviewDecision, 'kept' | 'rejected'>;
}

@Component({
  selector: 'app-review-panel',
  standalone: true,
  imports: [CommonModule, BadgeModule, ButtonModule, SplitButtonModule, FileChangeCardComponent, DiffViewerComponent],
  templateUrl: './review-panel.component.html',
  styleUrl: './review-panel.component.scss',
})
export class ReviewPanelComponent {
  @Input() fileChanges: FileChange[] = [];
  @Input() selectedFileChange: FileChange | null = null;
  @Input() keptCount = 0;
  @Input() rejectedCount = 0;
  @Input() selectableFileCount = 0;

  @Output() selectFile = new EventEmitter<string>();
  @Output() decisionChange = new EventEmitter<FileDecisionEvent>();
  @Output() apply = new EventEmitter<boolean>();

  readonly applyMenuItems: MenuItem[] = [
    { label: 'Apply kept files', icon: 'pi pi-check', command: () => this.apply.emit(false) },
    { label: 'Apply all', icon: 'pi pi-check-circle', command: () => this.apply.emit(true) },
  ];
}

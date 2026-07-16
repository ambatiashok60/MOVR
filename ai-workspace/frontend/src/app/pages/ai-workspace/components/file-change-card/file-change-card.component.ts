import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';
import { ButtonModule } from 'primeng/button';

import { FileChange } from '../../models/file-change.model';
import { ReviewDecision } from '../../models/review.model';
import { FileIconPipe } from '../../../../shared/pipes/file-icon.pipe';

@Component({
  selector: 'app-file-change-card',
  standalone: true,
  imports: [CommonModule, ButtonModule, FileIconPipe],
  templateUrl: './file-change-card.component.html',
  styleUrl: './file-change-card.component.scss',
})
export class FileChangeCardComponent {
  @Input({ required: true }) file!: FileChange;
  @Input() selected = false;
  @Output() select = new EventEmitter<void>();
  @Output() decisionChange = new EventEmitter<Extract<ReviewDecision, 'kept' | 'rejected'>>();
}

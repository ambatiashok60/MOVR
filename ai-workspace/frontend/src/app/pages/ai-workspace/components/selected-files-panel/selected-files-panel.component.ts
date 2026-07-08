import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';
import { ButtonModule } from 'primeng/button';

import { SelectedFile } from '../../models/context.model';
import { FileIconPipe } from '../../../../shared/pipes/file-icon.pipe';

@Component({
  selector: 'app-selected-files-panel',
  standalone: true,
  imports: [CommonModule, ButtonModule, FileIconPipe],
  templateUrl: './selected-files-panel.component.html',
  styleUrl: './selected-files-panel.component.scss',
})
export class SelectedFilesPanelComponent {
  @Input() files: SelectedFile[] = [];
  @Output() removeFile = new EventEmitter<string>();
}

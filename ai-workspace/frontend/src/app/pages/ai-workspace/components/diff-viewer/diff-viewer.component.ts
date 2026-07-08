import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';

import { FileChange } from '../../models/file-change.model';

@Component({
  selector: 'app-diff-viewer',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './diff-viewer.component.html',
  styleUrl: './diff-viewer.component.scss',
})
export class DiffViewerComponent {
  @Input() fileChange: FileChange | null = null;
}

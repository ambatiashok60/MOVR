import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';
import { ButtonModule } from 'primeng/button';

import { ContextSummary } from '../../models/context.model';

@Component({
  selector: 'app-context-panel',
  standalone: true,
  imports: [CommonModule, ButtonModule],
  templateUrl: './context-panel.component.html',
  styleUrl: './context-panel.component.scss',
})
export class ContextPanelComponent {
  @Input() context: ContextSummary | null = null;
  @Output() manage = new EventEmitter<void>();
}

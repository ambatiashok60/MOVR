import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';

import { AiSession } from '../../models/session.model';
import { TimeAgoPipe } from '../../../../shared/pipes/time-ago.pipe';

@Component({
  selector: 'app-session-card',
  standalone: true,
  imports: [CommonModule, TimeAgoPipe],
  templateUrl: './session-card.component.html',
  styleUrl: './session-card.component.scss',
})
export class SessionCardComponent {
  @Input({ required: true }) session!: AiSession;
  @Input() active = false;
  @Output() select = new EventEmitter<void>();
}

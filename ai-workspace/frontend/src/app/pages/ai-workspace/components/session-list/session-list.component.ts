import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';

import { AiSession } from '../../models/session.model';
import { SessionCardComponent } from '../session-card/session-card.component';

@Component({
  selector: 'app-session-list',
  standalone: true,
  imports: [CommonModule, SessionCardComponent],
  templateUrl: './session-list.component.html',
  styleUrl: './session-list.component.scss',
})
export class SessionListComponent {
  @Input() sessions: AiSession[] = [];
  @Input() activeSessionId: string | null = null;
  @Output() select = new EventEmitter<AiSession>();
}

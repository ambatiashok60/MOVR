import { ChangeDetectionStrategy, Component, EventEmitter, Output } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'ra-conversation-sidebar',
  standalone: true,
  imports: [CommonModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="brand"><span class="logo">◇</span> RepoAgent</div>
    <div class="conv-head">
      <span>Conversations</span>
      <button class="newchat" (click)="newChat.emit()">+ New Chat</button>
    </div>
    <div class="conv-list">
      <div class="conv" *ngFor="let c of conversations; let i = index" [class.active]="i === 0">
        <span class="dot">✓</span>
        <span class="title">{{ c.title }}</span>
        <span class="time">{{ c.time }}</span>
      </div>
    </div>
    <div class="sidebar-foot">
      Conversations compact automatically to keep context optimized.
      <div class="bar"><span></span></div>
    </div>
  `,
})
export class ConversationSidebarComponent {
  @Output() newChat = new EventEmitter<void>();
  // Seeded list to match the reference design; a real build lists from the API.
  readonly conversations = [
    { title: 'Fix API scenario generation status', time: 'now' },
    { title: 'Refactor task manager service', time: '1d' },
    { title: 'Add pagination to scenarios API', time: '2d' },
    { title: 'Improve logging in API layer', time: '3d' },
    { title: 'Explain authentication flow', time: '4d' },
  ];
}

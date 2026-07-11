import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';

import { ChatMessage } from '../../models/chat-message.model';
import { MessageBubbleComponent } from '../message-bubble/message-bubble.component';

@Component({
  selector: 'app-conversation',
  standalone: true,
  imports: [CommonModule, MessageBubbleComponent],
  templateUrl: './conversation.component.html',
  styleUrl: './conversation.component.scss',
})
export class ConversationComponent {
  @Input() messages: ChatMessage[] = [];
}

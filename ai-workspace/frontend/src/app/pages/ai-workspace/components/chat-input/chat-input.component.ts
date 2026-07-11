import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ButtonModule } from 'primeng/button';
import { InputTextModule } from 'primeng/inputtext';

export interface QuickAction {
  label: string;
  icon: string;
  promptTemplate: (filePath?: string) => string;
}

@Component({
  selector: 'app-chat-input',
  standalone: true,
  imports: [CommonModule, FormsModule, ButtonModule, InputTextModule],
  templateUrl: './chat-input.component.html',
  styleUrl: './chat-input.component.scss',
})
export class ChatInputComponent {
  @Input() isRunning = false;
  @Input() selectedFilePath: string | null = null;
  @Input() quickActions: QuickAction[] = [];
  @Output() run = new EventEmitter<string>();

  /** Set externally (e.g. from prompt-library selection) to seed the input; not two-way bound. */
  @Input() set prefillValue(value: string | null) {
    if (value) this.value = value;
  }

  value = '';

  applyQuickAction(action: QuickAction): void {
    this.value = action.promptTemplate(this.selectedFilePath ?? undefined);
  }

  submit(): void {
    const prompt = this.value.trim();
    if (!prompt || this.isRunning) return;
    this.run.emit(prompt);
    this.value = '';
  }
}

import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';

import { PromptTemplate } from '../../models/prompt.model';

@Component({
  selector: 'app-prompt-library',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './prompt-library.component.html',
  styleUrl: './prompt-library.component.scss',
})
export class PromptLibraryComponent {
  @Input() prompts: PromptTemplate[] = [];
  @Output() select = new EventEmitter<PromptTemplate>();
}

import { CommonModule } from '@angular/common';
import { Component, Input, signal } from '@angular/core';
import { ButtonModule } from 'primeng/button';

@Component({
  selector: 'app-code-block',
  standalone: true,
  imports: [CommonModule, ButtonModule],
  templateUrl: './code-block.component.html',
  styleUrl: './code-block.component.scss',
})
export class CodeBlockComponent {
  @Input() code = '';
  @Input() language = '';

  readonly isFullscreen = signal(false);
  readonly copied = signal(false);

  copy(): void {
    navigator.clipboard.writeText(this.code).then(() => {
      this.copied.set(true);
      setTimeout(() => this.copied.set(false), 1500);
    });
  }

  download(): void {
    const blob = new Blob([this.code], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `snippet.${this.language || 'txt'}`;
    link.click();
    URL.revokeObjectURL(url);
  }

  toggleFullscreen(): void {
    this.isFullscreen.update((value) => !value);
  }
}

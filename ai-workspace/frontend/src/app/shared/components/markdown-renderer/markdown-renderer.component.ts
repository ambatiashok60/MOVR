import { CommonModule } from '@angular/common';
import { Component, Input, computed, signal } from '@angular/core';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';

/**
 * TODO integration: this assumes a markdown-to-HTML library (e.g. `marked`) is available in
 * the host app. Swap the `renderMarkdown` stub below for a real `marked.parse()` call, and
 * make sure the sanitized output still goes through DomSanitizer as done here.
 */
function renderMarkdown(markdown: string): string {
  return markdown
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\n/g, '<br>');
}

@Component({
  selector: 'app-markdown-renderer',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './markdown-renderer.component.html',
  styleUrl: './markdown-renderer.component.scss',
})
export class MarkdownRendererComponent {
  private readonly content = signal('');

  @Input() set markdown(value: string) {
    this.content.set(value ?? '');
  }

  readonly renderedHtml = computed<SafeHtml>(() =>
    this.sanitizer.bypassSecurityTrustHtml(renderMarkdown(this.content())),
  );

  constructor(private readonly sanitizer: DomSanitizer) {}
}

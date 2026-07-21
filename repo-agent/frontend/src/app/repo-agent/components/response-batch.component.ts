import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { ResponseBatchState } from '../models/repo-agent.models';
import { renderMarkdown } from '../utils/markdown';

@Component({
  selector: 'ra-response-batch',
  standalone: true,
  imports: [CommonModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="section">
      <h4>{{ batch.title || batch.type }}</h4>
      <div class="body" [innerHTML]="html"></div>
    </div>
  `,
})
export class ResponseBatchComponent {
  private _batch!: ResponseBatchState;
  html: SafeHtml = '';

  constructor(private sanitizer: DomSanitizer) {}

  @Input({ required: true }) set batch(value: ResponseBatchState) {
    this._batch = value;
    // renderMarkdown escapes all input; bypass is safe on that sanitized output.
    this.html = this.sanitizer.bypassSecurityTrustHtml(renderMarkdown(value.markdown));
  }
  get batch(): ResponseBatchState { return this._batch; }
}

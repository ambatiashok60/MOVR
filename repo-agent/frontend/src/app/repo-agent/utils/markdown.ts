/** Minimal, safe Markdown -> HTML for streamed response batches.
 *  Renders fenced code blocks (with diff coloring) and basic inline formatting. */

function escapeHtml(s: string): string {
  return s.replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c] as string));
}

export function renderMarkdown(md: string): string {
  const parts = md.split(/(```[\s\S]*?```)/g);
  return parts
    .map((part) => {
      const fence = part.match(/^```(\w*)\n?([\s\S]*?)```$/);
      if (fence) {
        const lang = fence[1] || '';
        const code = fence[2].replace(/\n$/, '');
        if (lang === 'diff') {
          const colored = escapeHtml(code)
            .split('\n')
            .map((l) =>
              l.startsWith('+') ? `<span class="add">${l}</span>` :
              l.startsWith('-') ? `<span class="del">${l}</span>` : l)
            .join('\n');
          return `<pre class="diff">${colored}</pre>`;
        }
        return `<pre>${escapeHtml(code)}</pre>`;
      }
      return escapeHtml(part)
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
        .replace(/^### (.*)$/gm, '<strong>$1</strong>')
        .replace(/\n/g, '<br/>');
    })
    .join('');
}

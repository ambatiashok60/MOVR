import { bootstrapApplication } from '@angular/platform-browser';
import { provideHttpClient } from '@angular/common/http';
import { AppComponent } from './app/app.component';

bootstrapApplication(AppComponent, {
  providers: [provideHttpClient()],
}).catch((err) => {
  console.error(err);
  const root = document.querySelector('ra-root');
  if (root) {
    root.innerHTML = `
      <main style="max-width:760px;margin:64px auto;padding:24px;font-family:system-ui,sans-serif">
        <h1 style="color:#b42318">RepoAgent UI failed to start</h1>
        <p>Open the browser console for the technical error.</p>
        <p>Confirm that Node.js 18+ is active, frontend dependencies are installed,
        and <code>npm start</code> is running from <code>repo-agent/frontend</code>.</p>
      </main>`;
  }
});

import { Routes } from '@angular/router';

/**
 * Feature-level routes for AI Workspace, lazy-loaded from the app-level app.routes.ts.
 * Currently a single screen; split further (e.g. a dedicated /ai-workspace/settings route)
 * only if the settings overlay proves insufficient as a modal.
 */
export const AI_WORKSPACE_ROUTES: Routes = [
  {
    path: '',
    loadComponent: () => import('./ai-workspace.component').then((m) => m.AiWorkspaceComponent),
  },
];

import { Routes } from '@angular/router';

import { MainLayoutComponent } from './layout/main-layout/main-layout.component';

/**
 * TODO integration: this is a reference top-level routes file, written assuming AI Workspace
 * is the only feature area in this scaffold. Merge the 'ai-workspace' child route into the
 * host app's real app.routes.ts rather than replacing it — the host app almost certainly
 * already has routes for Dashboard, Projects, Data Sources, etc. that live outside this folder.
 */
export const routes: Routes = [
  {
    path: '',
    component: MainLayoutComponent,
    children: [
      { path: '', redirectTo: 'ai-workspace', pathMatch: 'full' },
      {
        path: 'ai-workspace',
        loadChildren: () => import('./pages/ai-workspace/ai-workspace.routes').then((m) => m.AI_WORKSPACE_ROUTES),
      },
      {
        path: 'test-generation',
        loadComponent: () =>
          import('./pages/test-generation/test-generation-page.component').then(
            (m) => m.TestGenerationPageComponent,
          ),
      },
    ],
  },
];

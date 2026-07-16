import { Routes } from '@angular/router';

// REFERENCE ONLY — do not copy this array over the host application's routes.
// HOST APP: merge this child into the existing Test Gen/MainLayout route.
export const API_TEST_GENERATION_ROUTE_EXAMPLE: Routes = [
  {
    path: 'test-generation/api-tests',
    loadChildren: () =>
      import('../api-test-generation.routes').then((m) => m.API_TEST_GENERATION_ROUTES),
  },
];

// If Functional Tests and API Tests share one URL and are switched with tabs,
// skip this route and use the embedded example instead.

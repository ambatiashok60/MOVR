import { Routes } from '@angular/router';

/** Optional route-based integration. Embedded Test Gen tabs can import the component directly. */
export const API_TEST_GENERATION_ROUTES: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./api-test-gen/api-test-gen.component').then((m) => m.ApiTestGenComponent),
  },
];

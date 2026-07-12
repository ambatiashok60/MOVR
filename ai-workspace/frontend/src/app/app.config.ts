import { ApplicationConfig, provideZoneChangeDetection } from '@angular/core';
import { provideHttpClient } from '@angular/common/http';
import { provideRouter } from '@angular/router';

import { providePrimeNG } from 'primeng/config';
import { WorktopPreset } from './theme/worktop-preset';

import { provideApiTestGenerationMocks } from '@api-test-generation/mocks/provide-api-test-generation-mocks';
import { provideTestAgentMocks } from '@api-test-generation/functional-test-gen/mocks/provide-test-agent-mocks';

import { routes } from './app.routes';
import { DEMO } from './demo.config';

export const appConfig: ApplicationConfig = {
  providers: [
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(routes),
    provideHttpClient(),
    providePrimeNG({
      ripple: true,
      theme: { preset: WorktopPreset, options: { darkModeSelector: false } },
    }),
    ...(DEMO.useTestGenMocks ? provideApiTestGenerationMocks() : []),
    ...(DEMO.useFunctionalTestGenMocks ? provideTestAgentMocks() : []),
  ],
};

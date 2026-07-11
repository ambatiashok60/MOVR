import { ApplicationConfig, provideZoneChangeDetection } from '@angular/core';
import { provideHttpClient } from '@angular/common/http';
import { provideRouter } from '@angular/router';

// TODO integration: confirm the PrimeNG bootstrap API against the host app's installed
// version — `providePrimeNG` is the PrimeNG 18+ standalone provider; older versions configure
// theming differently (a global stylesheet import instead of a provider).
import { providePrimeNG } from 'primeng/config';

import { provideApiTestGenerationMocks } from '@api-test-generation/mocks/provide-api-test-generation-mocks';
import { provideTestAgentMocks } from '@api-test-generation/functional-test-gen/mocks/provide-test-agent-mocks';

import { routes } from './app.routes';
import { DEMO } from './demo.config';

export const appConfig: ApplicationConfig = {
  providers: [
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(routes),
    provideHttpClient(),
    providePrimeNG({ ripple: true }),
    ...(DEMO.useTestGenMocks ? provideApiTestGenerationMocks() : []),
    ...(DEMO.useFunctionalTestGenMocks ? provideTestAgentMocks() : []),
  ],
};

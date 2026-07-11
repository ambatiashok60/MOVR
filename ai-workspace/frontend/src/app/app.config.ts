import { ApplicationConfig, provideZoneChangeDetection } from '@angular/core';
import { provideHttpClient } from '@angular/common/http';
import { provideRouter } from '@angular/router';

// TODO integration: confirm the PrimeNG bootstrap API against the host app's installed
// version — `providePrimeNG` is the PrimeNG 18+ standalone provider; older versions configure
// theming differently (a global stylesheet import instead of a provider).
import { providePrimeNG } from 'primeng/config';

import { routes } from './app.routes';

export const appConfig: ApplicationConfig = {
  providers: [
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(routes),
    provideHttpClient(),
    providePrimeNG({ ripple: true }),
  ],
};

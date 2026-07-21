import { Provider } from '@angular/core';

import { ApiTestGenerationEventsService } from '../services/api-test-generation-events.service';
import { ApiTestGenerationService } from '../services/api-test-generation.service';
import { MockApiTestGenerationEventsService } from './mock-api-test-generation-events.service';
import { MockApiTestGenerationService } from './mock-api-test-generation.service';

/**
 * Register in the host's app.config providers to run the API Tests UI fully
 * in-browser (design review mode) — no api-agent backend required. Remove the
 * providers (or flip the host demo flag) to hit the real FastAPI service.
 */
export function provideApiTestGenerationMocks(): Provider[] {
  return [
    { provide: ApiTestGenerationService, useClass: MockApiTestGenerationService },
    { provide: ApiTestGenerationEventsService, useClass: MockApiTestGenerationEventsService },
  ];
}

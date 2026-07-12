import { Provider } from '@angular/core';

import { TestAgentService } from '../services/test-agent.service';
import { MockTestAgentService } from './mock-test-agent.service';

export function provideTestAgentMocks(): Provider[] {
  return [{ provide: TestAgentService, useClass: MockTestAgentService }];
}

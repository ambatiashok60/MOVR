# Frontend feature and Worktop wiring

`frontend/test-generation` is a portable Angular feature. `api-test-gen/` composes the view;
`components/api-scenario-table/` renders scenarios; `components/mock-plan-review/` handles risk and
approval; `store/` owns state/orchestration; `services/` own HTTP/SSE; `models/` define contracts;
`mocks/` provide contract-faithful fixtures; and `integration/` contains host examples.

```html
<app-api-test-gen
  [selectedStory]="selectedStory"
  [tenantId]="tenantId"
  [repoPath]="selectedRepository.path"
  [branch]="selectedBranch.name"
/>
```

Worktop owns navigation, JIRA selection, repository/branch state, authentication, notifications and
dialogs. The feature communicates through inputs, outputs, injected clients and stable DTOs. Confirm
the host Angular/PrimeNG component APIs before copying the portable feature.

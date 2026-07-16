# Shared files and resources migration specification

## Purpose

This specification identifies shared dependencies that are often missing from a component import graph. Shared
resources remain typed nodes in the canonical frontend, cross-layer and backend graphs, but require explicit
ownership, versioning and migration rules because moving one feature can otherwise copy global coupling into a
second repository.

## Shared resource categories

### Frontend code resources

- Shared components, layout primitives and shells
- Pipes, directives, validators and utility functions
- Facade/store base classes and reusable task controllers
- API clients, interceptors, guards and error mappers
- Injection tokens and provider factories
- Common models, enums, pagination and API-envelope types
- Markdown, code, diff and loading renderers
- Feature flags and environment configuration readers

### Frontend visual resources

- Global SCSS/CSS entry points
- Design tokens and CSS custom properties
- PrimeNG or other theme configuration
- Typography/font files and loading rules
- Icons, images, illustrations and empty-state assets
- Spacing, color, elevation and breakpoint variables
- Shared animation/motion definitions
- Z-index and overlay conventions

### Backend code resources

- Common errors and API envelopes
- Authentication, tenancy and authorization dependencies
- Logging, tracing, metrics and correlation context
- Data-governance, redaction and path-safety utilities
- Base DTO/schema classes and serialization configuration
- LLM client interfaces, factories and telemetry
- Task/event/cancellation contracts
- Repository/unit-of-work interfaces
- Workspace, locking and command-execution abstractions

### Contract and generated resources

- OpenAPI/GraphQL/event schemas
- Generated frontend/backend clients
- JSON Schema and Pydantic schema exports
- Message/topic definitions
- Database migrations and seed/reference data
- Prompt templates and structured-output schemas
- Code-generation templates and manifests

### Test and development resources

- Fixtures, factories, builders and mock providers
- Contract-faithful mock payloads and SSE timelines
- Golden scenarios and benchmark datasets
- Test harnesses, fake clocks and fake repositories
- Test configuration, setup files and browser helpers
- Devcontainer, Docker Compose and proxy configuration
- CI reusable workflows and quality configuration

## Shared-resource graph relationships

Add these typed edges to the unified graph:

```text
USES_SHARED_COMPONENT  USES_PIPE  USES_DIRECTIVE  USES_UTILITY
PROVIDED_BY  INTERCEPTED_BY  GUARDED_BY  FEATURE_FLAGGED_BY
STYLED_BY  USES_TOKEN  USES_THEME  USES_FONT  USES_ICON  USES_ASSET
SERIALIZED_BY  ENVELOPED_BY  AUTHORIZED_BY  TENANTED_BY
LOGGED_BY  TRACED_BY  REDACTED_BY  VALIDATED_BY
GENERATED_FROM  GENERATES  SEEDED_BY  MIGRATED_BY
FIXTURE_FOR  MOCKS  BUILT_BY  CONFIGURED_BY  DEPLOYED_BY
```

Every shared-resource edge records whether the dependency is compile-time, runtime, build-time, test-only,
preview-only or deployment-time.

## Ownership model

Every shared resource must have exactly one declared owner and stability classification:

| Classification | Meaning | Migration treatment |
|---|---|---|
| platform-owned | Worktop-wide standard | consume through supported public API/package |
| feature-owned | maintained by one feature | copy/package with the feature or adapt explicitly |
| repository-local | convention specific to source repo | replace with target equivalent where possible |
| generated | derived from schema/template | migrate source and generation command, not only output |
| preview-only | design/demo support | exclude from production or replace with real provider |
| test-only | verification support | copy when required by migrated contract/tests |

Avoid a vague `shared/` ownership category. Directory location does not establish ownership or API stability.

## Public versus private shared APIs

A shared resource is portable only through an explicit public entry point. Do not import deep private paths from
another feature. Public resources should expose a barrel/package API, semantic version or compatibility policy,
owner and contract tests. Private resources are copied into the feature only when their ownership intentionally
moves; otherwise implement an adapter against the target repository’s equivalent.

## Shared resource migration manifest

```yaml
shared_resources:
  - id: shared.markdown-renderer
    source: frontend/src/app/shared/components/markdown-renderer
    category: frontend-component
    ownership: platform-owned
    usage: runtime
    classification: host-provided
    public_api: SharedMarkdownRendererComponent
    packages: [marked, dompurify]
    styles: [--code-surface, --text-muted]
    target: worktop-ui/markdown-renderer
    compatibility_test: markdown-renderer.contract.spec.ts
  - id: api.task-event-schema
    source: backend/schemas/event.py
    category: contract
    ownership: platform-owned
    usage: runtime
    classification: replace-adapter
    target: worktop.tasks.TaskEvent
```

Required fields include source and target owner, category, lifecycle, copy classification, public entry point,
transitive packages, styles/assets/configuration, security classification, version, consumers and verification.

## Frontend shared-resource closure

When migrating a component, inspect:

```text
component imports
 + template selectors/pipes/directives
 + component and global styles
 + CSS variables/theme/fonts/icons/assets
 + providers/tokens/interceptors/guards
 + shared models/utilities
 + build aliases and package exports
 + test fixtures/harnesses
```

Copying a shared component requires its template, style, child resources, accessibility behavior, global tokens,
packages and tests. If the target already has an equivalent, prefer a thin adapter or target-native component.

## Backend shared-resource closure

When migrating a route/service/task handler, inspect:

```text
base DTO/envelope/error classes
 + auth/tenant/permission dependencies
 + logging/tracing/redaction context
 + task/event/cancellation contracts
 + repository/unit-of-work and DB session providers
 + model client/configuration
 + workspace/path/command safety
 + migrations/generated schemas
 + fixtures and contract tests
```

Do not copy platform placeholders (`get_db`, tenant defaults, mock LLMs) as production shared resources. Replace
them with authenticated target providers.

## Generated-resource rule

For generated code, migrate and verify the source schema, generator version, configuration and regeneration
command. Generated output alone becomes stale and cannot be safely reconciled. Record `GENERATED_FROM` and
`GENERATES` edges and validate that regeneration produces a clean diff.

## Styles and theme compatibility

Before copying a component, inventory every CSS custom property, SCSS variable/mixin, global class, font, icon and
overlay assumption. Map source tokens to target tokens in one compatibility layer. Do not duplicate the entire
source global stylesheet. Verify dark/light modes, focus states, responsive breakpoints, overlay stacking and
reduced-motion behavior.

## Resource collision rules

Detect same-name/different-contract resources, duplicate provider tokens, conflicting global styles, multiple
versions of generated clients, incompatible DTO enums, duplicate migrations and competing logging/auth contexts.
Resolve collisions with target-native reuse, an adapter, namespacing or deliberate ownership transfer; never let
import order decide behavior.

## Verification gates

- Public shared imports resolve without deep private paths.
- No preview-only provider is present in production configuration.
- Package, token, theme, font, icon and asset requirements are satisfied.
- Generated resources reproduce from their source.
- DTO/error/envelope/task contracts pass source-target contract tests.
- Authentication, tenancy, redaction and logging use target platform services.
- ORM/session/task infrastructure is injected through target adapters.
- Shared fixtures represent the same wire contract as production.
- Target build, component tests, backend tests and one real end-to-end flow pass.

## Repository-specific shared resources

### Test Agent

Treat logging, model-client abstractions, repository policy, path safety, Playwright parsers, task contracts,
generation schemas and test fixtures as shared-resource candidates. The Functional frontend shared resources live
currently in the portable Test Gen source and must not become a hidden API Agent dependency in production.

### API Agent

Shared candidates include task/event schemas, task manager interfaces, logging/governance, repository policy,
strategy contracts, API envelopes, Test Gen models, mock providers and table/review presentation primitives.

### AI Workspace

Shared candidates include markdown/code/loading components, common pipes/utilities, task controller contracts,
repository/model/tool ports, state-store abstractions, DTO base/mappers, logging and host layout/navigation. The
combined preview TypeScript alias to API Agent is a development dependency and should become a deliberate package
or migrated feature boundary in Worktop.

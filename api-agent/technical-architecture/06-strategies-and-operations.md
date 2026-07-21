# Framework strategies and operations

Strategy selection ranks repository evidence: build files and dependencies, existing tests, test
source roots, helpers, commands, Spring configuration, HTTP clients and naming conventions. For
Spring Boot this can select RestAssured, MockMvc, WebTestClient or repository-specific WebClient
testing; ambiguity becomes a review item.

Mock/stub planning records dependency, mechanism, files, confidence, risk and approval. It may emit
WireMock, Mockito, MockWebServer, fixtures or Testcontainers only when dependencies and conventions
support them. Kafka, Vault, cloud queues and stage environments require host configuration.

Production must use shared jobs/events, repository locks, sandboxed allowlisted commands, authenticated
tenancy, audit records, secret redaction and correlation-rich logs. `ENABLE_TEST_EXECUTION=true` is
appropriate only in a trusted controlled workspace. Track discovery confidence, generation/repair
count, execution duration, token estimate, terminal outcome and unresolved mock promises.

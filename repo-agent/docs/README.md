# RepoAgent engineering documentation

This directory is the engineering source of truth for RepoAgent. Documentation
changes are part of the definition of done when behavior, an interface, an
operational characteristic, or a design decision changes.

## Start here

| Need | Document |
|---|---|
| Understand the system and its boundaries | [Architecture](ARCHITECTURE.md) |
| Make a change using test-driven development | [Testing strategy](TESTING.md) |
| Prepare a reviewable contribution | [Engineering guide](ENGINEERING.md) |
| Understand threats and security controls | [Security](SECURITY.md) |
| Operate, observe, and recover the service | [Operations](OPERATIONS.md) |
| Run the application locally | [Running](RUNNING.md) |
| Deploy it | [Deployment](DEPLOYMENT.md) |
| Change the REST/SSE contract | [Integration contract](integration-contract.md) |
| Record a durable design choice | [Architecture decisions](adr/README.md) |

Cloud-specific deployment notes: [AWS](DEPLOYMENT-AWS.md),
[Azure](DEPLOYMENT-AZURE.md), and [GCP](DEPLOYMENT-GCP.md).

## Documentation ownership rules

- `ARCHITECTURE.md` describes the current system, not an aspirational one.
- `integration-contract.md` is normative for backend/frontend compatibility.
- ADRs explain decisions that should not be repeatedly relitigated.
- `OPERATIONS.md` owns production signals and recovery actions.
- `SECURITY.md` owns trust boundaries, abuse cases, and release blockers.
- `TESTING.md` owns test taxonomy, TDD practice, and required quality gates.

Every pull request should update the affected document or explicitly state why
the change has no documentation impact.

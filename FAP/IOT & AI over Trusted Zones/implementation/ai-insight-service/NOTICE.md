# Notices for FACIS FAP AI Insight Service

This content is produced and maintained by ATLAS IoT Lab GmbH
in the context of the Eclipse FACIS project.

## Project Information

- **Project:** Eclipse FACIS - Federation Architecture Pattern: IoT & AI Demonstrator
- **Project Home:** https://projects.eclipse.org/projects/technology.facis
- **License:** Apache License 2.0

## Copyright

Copyright (c) 2025-2026 ATLAS IoT Lab GmbH.

## Third-Party Content

This project includes or depends on the following third-party software:

| Package | License | Usage |
|---|---|---|
| FastAPI | MIT | HTTP REST API framework |
| uvicorn | BSD-3-Clause | ASGI server |
| Pydantic / pydantic-settings | MIT | Data validation and settings |
| OpenAI Python SDK | Apache-2.0 | OpenAI-compatible client integration |
| Trino Python client | Apache-2.0 | Query execution against Trino |
| requests | Apache-2.0 | OIDC token exchange HTTP calls |
| redis-py | MIT | Redis cache backend client |
| PyYAML | MIT | YAML configuration loading |
| pytest | MIT | Test framework |
| pytest-bdd | MIT | BDD test scenarios |
| pytest-cov | MIT | Coverage reporting |
| Ruff | MIT | Linting and static checks |
| mypy | MIT | Type checking |
| Black | MIT | Code formatting |
| Redis | BSD-3-Clause | Optional runtime cache service |
| Trino | Apache-2.0 | External query engine |

## Cryptography

This project does not bundle custom cryptographic implementations.
Transport protection (TLS/mTLS), certificate management, and OIDC provider security
are expected to be handled by the deployment environment and platform operators.

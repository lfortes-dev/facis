# FACIS FAP IoT & AI - AI Insight Service Documentation

This directory contains the technical documentation for the AI Insight Service in the
FACIS Federation Architecture Pattern (FAP) IoT & AI demonstrator.

## Structure

```text
docs/
|- README.md                      (this file)
|- openapi.yaml                   OpenAPI source of truth
|- api/
|  `- rest-api.md                 Human-readable REST API guide
`- guides/
   |- index.md                    Developer guide entrypoint
   |- setup.md                    Local and container setup
   |- architecture.md             Service architecture and request flow
   `- configuration.md            Configuration model and key variables
```

## Conventions

- Timestamps use ISO 8601 format with UTC (`Z` suffix) unless stated otherwise.
- Configuration examples use placeholder values (`<value>`) for sensitive data.
- Paths are relative to the `ai-insight-service/` root unless stated otherwise.
- `docs/openapi.yaml` is the API contract source of truth.

## Related Root Files

- [README.md](../README.md) - project entrypoint
- [NOTICE.md](../NOTICE.md) - notices and third-party attributions
- [SECURITY.md](../SECURITY.md) - vulnerability reporting and security policy
- [LICENSE](../LICENSE) - Apache License 2.0

## License

This documentation is provided under the Apache License 2.0.

Copyright (c) 2025-2026 ATLAS IoT Lab GmbH.

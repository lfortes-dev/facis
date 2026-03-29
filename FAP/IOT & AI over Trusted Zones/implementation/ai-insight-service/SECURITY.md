# Security Policy

## Reporting Vulnerabilities

If you discover a security vulnerability in this project, please report it responsibly.

**Do not open a public issue for security vulnerabilities.**

Report vulnerabilities through the Eclipse Foundation security process:

- **Email:** security@eclipse.org
- **Security page:** https://www.eclipse.org/security/

Please include:

- Vulnerability description
- Steps to reproduce
- Potential impact
- Suggested remediation (if available)

## Supported Versions

| Version | Supported |
|---|---|
| 0.1.x | Yes |

## Security Considerations

This service processes governed IoT and energy insight requests. Key controls include:

- **Policy enforcement:** Header-based agreement/asset/role checks for governed endpoints.
- **Rate limiting:** Agreement-scoped in-memory request limiting with `retry-after`.
- **Upstream auth:** Trino access uses OIDC password-flow JWT token acquisition.
- **Transport controls:** TLS verification flags are configurable for Trino and OIDC endpoints.
- **Secret handling:** API keys and OIDC credentials are configured via environment variables.
- **Fallback behavior:** Deterministic rule-based fallback protects endpoint availability when LLM upstream fails.
- **Observability controls:** Audit logging can be configured or reduced by environment.

## Deployment Guidance

- Use HTTPS endpoints for OpenAI-compatible and Trino connections in non-local environments.
- Store secrets in a secret manager or equivalent platform-native secure storage.
- Restrict network access so only trusted callers can reach governed API endpoints.
- Keep dependency updates and security scans in CI/CD workflow.

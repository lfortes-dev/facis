# Contributing to FACIS FAP AI Insight Service

Thank you for your interest in contributing to the FACIS project. This document provides
guidelines for contributing to the AI Insight Service component.

## Eclipse Contributor Agreement

Before your contribution can be accepted, you must complete the
[Eclipse Contributor Agreement (ECA)](https://www.eclipse.org/legal/ECA.php).
This is a one-time process for all Eclipse Foundation projects.

## Development Setup

```bash
# Clone the repository
git clone <repository-url>
cd ai-insight-service

# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run linting and type checks
ruff check src/ tests/
mypy src/
```

## Code Standards

- **Language:** Python 3.11+
- **Style:** Enforced via `ruff` (line length 100) and `black`
- **Type Checking:** `mypy` (non-strict, ignore missing imports)
- **Testing:** `pytest` with integration and `pytest-bdd` scenarios
- **Coverage Target:** > 80%

## Submitting Changes

1. Create a feature branch from your working branch baseline.
2. Write tests for new functionality and edge cases.
3. Ensure all tests pass: `pytest tests/ -v`
4. Ensure linting/type checks pass: `ruff check src/ tests/ && mypy src/`
5. Submit a pull request with a clear description and validation evidence.

## Reporting Issues

Use the project's issue tracker. Include:

- Steps to reproduce
- Expected vs actual behavior
- Environment details (Python version, OS, Docker version)

## Code of Conduct

This project follows the [Eclipse Foundation Community Code of Conduct](https://www.eclipse.org/org/documents/Community_Code_of_Conduct.php).

## License

By contributing, you agree that your contributions will be licensed under the
Apache License 2.0, as described in the [LICENSE](LICENSE) file.

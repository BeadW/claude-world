# Contributing to Claude World

Thank you for your interest in contributing to Claude World! This document outlines the contribution process and requirements.

## Important: Claude-Only Contributions

**All code contributions to this project must be written using Claude (Anthropic's AI assistant).**

This means:
- Use [Claude Code](https://claude.com/claude-code) or Claude in another interface to write your contributions
- Pull requests with code not written by Claude will not be accepted
- This requirement ensures consistency with the project's development approach

## How to Contribute

### 1. Fork the Repository

Fork the repository to your own GitHub account.

### 2. Create a Branch

```bash
git checkout -b feature/your-feature-name
```

Use descriptive branch names:
- `feature/` for new features
- `fix/` for bug fixes
- `docs/` for documentation changes

### 3. Make Your Changes

Use Claude to write your code changes. When working with Claude:
- Provide clear context about what you're trying to accomplish
- Share relevant existing code for context
- Ask Claude to follow the project's coding patterns

### 4. Test Your Changes

```bash
# Run the test suite
pytest

# Run linting
ruff check src/
```

### 5. Commit Your Changes

Write clear commit messages:

```bash
git commit -m "Add feature: description of what was added"
```

### 6. Submit a Pull Request

- Push your branch to your fork
- Open a pull request against the `main` branch
- Fill out the PR template with:
  - Description of changes
  - Confirmation that code was written with Claude
  - Any testing performed

## Code Style

- Follow existing code patterns in the repository
- Use type hints for function parameters and return values
- Keep functions focused and reasonably sized
- Write docstrings for public functions

## What to Contribute

We welcome contributions including:

- **New worlds**: Additional themed environments
- **Visual effects**: New particle effects and animations
- **Bug fixes**: Fixes for issues you encounter
- **Documentation**: Improvements to docs and examples
- **Tests**: Additional test coverage

## Questions?

If you have questions about contributing, open an issue for discussion before starting work on large changes.

## License

By contributing to Claude World, you agree that your contributions will be licensed under the AGPL-3.0 license.

# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Bug Fixes

- Make theme storage thread-safe using contextvars
- Use None checks instead of truthiness for text prompt defaults
- Pin prompt-toolkit to <4.0 to prevent breaking changes
- Validate that choices list is non-empty in select and checkbox prompts

### Documentation

- Add CONTRIBUTING.md with dev setup instructions
- Add keyboard shortcuts, validation, and theming to README

### Features

- Add pagination for long choice lists in select and checkbox
- Add validate and filter callback support to all prompt types
- Add theme system, confirm validation, and display improvements
- Initial implementation of inquirer-ai Python package

### Miscellaneous

- Add 80% coverage threshold to pytest config
- Track uv.lock for reproducible builds
- Add pyright strict, ruff linting, and shared git hooks

### Refactor

- Add generic Choice[V] and overloaded select/checkbox for type inference
- Move UI symbols into Theme for customization
- Extract ChoiceBasePrompt to reduce select/checkbox duplication
- Tighten type system across the codebase

### Testing

- Add subprocess-based integration tests for agent JSON protocol
- Add terminal mode tests for all prompt types

### Ci

- Add pyright type checking to CI pipeline


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

- Add rawlist and expand prompt types
- Add editor prompt type for multi-line text input
- Add search prompt type with dynamic filtering
- Add transformer callback and when conditional for prompts
- Add Separator, disabled choices, short, description, and loop option
- Add password and number prompt types
- Add agent protocol handshake and improve error messages
- Export __version__ via importlib.metadata
- Add pagination for long choice lists in select and checkbox
- Add validate and filter callback support to all prompt types
- Add theme system, confirm validation, and display improvements
- Initial implementation of inquirer-ai Python package

### Miscellaneous

- Add GitHub issue and PR templates
- Add git-cliff for automated CHANGELOG generation
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


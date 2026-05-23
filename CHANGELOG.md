# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Protocol

- Add sequential interaction hint to handshake

## [0.1.0] - 2026-05-23

### Bug Fixes

- Add unsafe_ask() and Choice description to questionary compat
- Align autocomplete agent dict with Python protocol
- Use get_running_loop() and shlex.split for editor command
- Share terminal scanner, remove dead code, fix double Source call
- Use json.Marshal in Separator.MarshalJSON to prevent injection
- Make theme storage thread-safe using contextvars
- Use None checks instead of truthiness for text prompt defaults
- Pin prompt-toolkit to <4.0 to prevent breaking changes
- Validate that choices list is non-empty in select and checkbox prompts

### Documentation

- Update CONTRIBUTING with cz workflow and release process
- Reframe README around custom plugin scenario
- Rewrite README as product-focused introduction
- Add agent protocol specification v1
- Add godoc comments to all exported types and functions
- Add CONTRIBUTING.md with dev setup instructions
- Add keyboard shortcuts, validation, and theming to README

### Features

- Add questionary compatibility layer for commitizen integration
- Add configurable loop option to Select and Checkbox
- Add validate/filter callbacks to all prompt types
- Add path, autocomplete, and search prompt types
- Add Go implementation of inquirer-ai
- Add async support, path prompt, and autocomplete prompt
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

- Add commit-msg hook and cz bump configuration
- Configure teamcz commitizen plugin for project
- Fix license format and add optional-dependencies for pip
- Add Go to CI pipeline and git hooks
- Add golangci-lint config and fix formatting/vet issues
- Update CHANGELOG
- Add GitHub issue and PR templates
- Add git-cliff for automated CHANGELOG generation
- Add 80% coverage threshold to pytest config
- Track uv.lock for reproducible builds
- Add pyright strict, ruff linting, and shared git hooks

### Refactor

- Upgrade terminal UI with bubbletea and lipgloss
- Add structured PromptError with type/message context
- Strengthen error hierarchy with specific exception types
- Tighten Any usage in checkbox signature and search state
- Add generic Choice[V] and overloaded select/checkbox for type inference
- Move UI symbols into Theme for customization
- Extract ChoiceBasePrompt to reduce select/checkbox duplication
- Tighten type system across the codebase

### Testing

- Add boundary, chaos, and error path tests
- Add property-based, chaos, and boundary tests
- Add subprocess-based integration tests for agent JSON protocol
- Add terminal mode tests for all prompt types

### Ci

- Add pyright type checking to CI pipeline


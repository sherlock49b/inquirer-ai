# Changelog

All notable changes to this project will be documented in this file.


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

## v0.3.1 (2026-05-26)

### Fix

- **ci**: push tag explicitly and read version dynamically in tests

## v0.3.0 (2026-05-26)

### Feat

- **ts**: add live search with debounce to search prompt
- **rust**: non-blocking search source via threads
- **ts**: support async source in search prompt
- **go**: support async source in search prompt
- **python**: support async source in search prompt
- **ts**: add select number jump, expand help toggle, validation keep mode
- **go**: add select number jump, expand help toggle, validation keep mode
- **rust**: add select number jump, expand help toggle, validation keep_input
- **python**: add select number jump, expand help toggle, validation keep mode
- **rust**: add number step constraint and checkbox required
- **go**: add number step constraint and checkbox required
- **ts**: add number step constraint and checkbox required
- **python**: add number step constraint and checkbox required
- **go**: add socket transport and update protocol docs
- **rust**: add socket transport
- **ts**: add Unix socket transport for agent interaction
- **protocol**: add Unix socket transport for agent interaction

### Fix

- **ci**: use standard commitizen plugin in release workflow
- **ci**: allow dirty Cargo.lock in crates.io publish
- **all**: fix NumberPrompt step field collision and callback order
- **go,rust**: fix text prompt filter-before-validate order
- **python**: handle async source in nested event loops
- **ts**: clamp select digit jump to last item instead of ignoring
- **go**: move checkbox required check before filter
- reorder filter to run only on accepted values
- **python**: apply ruff format
- **python**: merge nested if per ruff SIM102
- **cz-ai**: convert to CJS for commitizen compatibility
- **ci**: fix Rust/Go formatting and add TS build step
- **cargo-deps**: strip newlines from crate descriptions
- **rust**: fix raw mode TUI rendering and description newlines
- harden boundary handling across all 4 languages

### Refactor

- replace cast with TypeGuard, fix CI failures
- **python**: strengthen type system to static-language standards
- **ts**: strengthen type system to static-language standards

### Perf

- **hooks**: parallelize pre-commit, skip redundant pre-push

## v0.2.1 (2026-05-24)

### Fix

- reject NaN/Inf in coerce_bool and validate_number across all languages

## v0.2.0 (2026-05-24)

### Feat

- **extensions**: add cz-inquirer-ai commitizen adapter for Node.js
- **extensions**: add Yeoman generator with inquirer-ai prompts
- **extensions**: add cargo-deps interactive dependency manager
- **extensions**: add create-inquirer-app (TS) and iqai protocol tester (Rust)
- **rust**: add Rust implementation with 12 prompt types
- **typescript**: add TypeScript implementation with 12 prompt types
- **python**: add cz-teamcz plugin and extensions README
- **go**: add gh-contribute extension as showcase
- add questionary compatibility layer for commitizen integration
- **go**: add configurable loop option to Select and Checkbox
- **go**: add validate/filter callbacks to all prompt types
- **go**: add path, autocomplete, and search prompt types
- add Go implementation of inquirer-ai
- add async support, path prompt, and autocomplete prompt
- add rawlist and expand prompt types
- add editor prompt type for multi-line text input
- add search prompt type with dynamic filtering
- add transformer callback and when conditional for prompts
- add Separator, disabled choices, short, description, and loop option
- add password and number prompt types
- add agent protocol handshake and improve error messages
- export __version__ via importlib.metadata
- add pagination for long choice lists in select and checkbox
- add validate and filter callback support to all prompt types
- add theme system, confirm validation, and display improvements
- initial implementation of inquirer-ai Python package

### Fix

- **release**: use --out-dir for uv build to fix publish path
- **ci**: bump minimum Rust version to 1.85 for edition2024 support
- **protocol**: make handshake_ack non-blocking
- **ci**: format test_edge_cases.py to pass CI
- **go**: remove Claude Code branding from gh-contribute PR body
- add unsafe_ask() and Choice description to questionary compat
- **go**: align autocomplete agent dict with Python protocol
- **python**: use get_running_loop() and shlex.split for editor command
- **go**: share terminal scanner, remove dead code, fix double Source call
- **go**: use json.Marshal in Separator.MarshalJSON to prevent injection
- make theme storage thread-safe using contextvars
- use None checks instead of truthiness for text prompt defaults
- pin prompt-toolkit to <4.0 to prevent breaking changes
- validate that choices list is non-empty in select and checkbox prompts

### Refactor

- fix code quality issues from audit
- extract shared retry helper, remove dead code
- **python**: replace Any with TextIO in agent fd helpers
- **extensions**: remove generator-inquirer-app
- **extensions**: remove create-inquirer-app and iqai
- **go**: restructure error hierarchy with wrapping chain
- **go**: upgrade terminal UI with bubbletea and lipgloss
- **go**: add structured PromptError with type/message context
- strengthen error hierarchy with specific exception types
- tighten Any usage in checkbox signature and search state
- add generic Choice[V] and overloaded select/checkbox for type inference
- move UI symbols into Theme for customization
- extract ChoiceBasePrompt to reduce select/checkbox duplication
- tighten type system across the codebase

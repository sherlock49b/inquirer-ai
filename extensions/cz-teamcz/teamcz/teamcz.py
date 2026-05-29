from __future__ import annotations

from typing import TYPE_CHECKING

from commitizen.cz.base import BaseCommitizen
from commitizen.cz.utils import multiple_line_breaker, required_validator

if TYPE_CHECKING:
    from commitizen.question import CzQuestion

__all__ = ["TeamCz"]


def _parse_scope(text: str) -> str:
    return "-".join(text.strip().split())


def _parse_subject(text: str) -> str:
    return required_validator(text.strip(".").strip(), msg="Subject is required.")


class TeamCz(BaseCommitizen):
    bump_pattern = r"^(feat|fix|protocol|compat|hotfix|infra|data-migration|rollback|BREAKING CHANGE)"
    bump_map = {
        "feat": "MINOR",
        "fix": "PATCH",
        "protocol": "MINOR",
        "compat": "PATCH",
        "hotfix": "PATCH",
        "infra": "PATCH",
        "data-migration": "MINOR",
        "rollback": "PATCH",
        "BREAKING CHANGE": "MAJOR",
    }
    bump_map_major_version_zero = {
        "feat": "MINOR",
        "fix": "PATCH",
        "protocol": "MINOR",
        "compat": "PATCH",
        "hotfix": "PATCH",
        "infra": "PATCH",
        "data-migration": "MINOR",
        "rollback": "PATCH",
        "BREAKING CHANGE": "MINOR",
    }
    commit_parser = (
        r"^(?P<change_type>feat|fix|hotfix|refactor|perf|test|docs|chore|ci|protocol|compat)"
        r"(?:\((?P<scope>[^()\r\n]*)\))?"
        r"(?P<breaking>!)?"
        r":\s(?P<message>.*)?"
    )
    changelog_pattern = r"^(feat|fix|hotfix|refactor|perf|protocol|compat)"
    change_type_map = {
        "feat": "Features",
        "fix": "Bug Fixes",
        "hotfix": "Hotfixes",
        "refactor": "Refactoring",
        "perf": "Performance",
        "protocol": "Protocol Changes",
        "compat": "Compatibility",
    }

    def questions(self) -> list[CzQuestion]:
        return [
            {
                "type": "list",
                "name": "prefix",
                "message": "Select the type of change you are committing",
                "choices": [
                    {
                        "value": "feat",
                        "name": "feat: A new prompt type, API, or user-facing capability",
                    },
                    {
                        "value": "fix",
                        "name": "fix: A bug fix in prompt behavior, validation, or rendering",
                    },
                    {
                        "value": "protocol",
                        "name": "protocol: Change to the agent JSON protocol (handshake, prompt format, response schema)",
                    },
                    {
                        "value": "compat",
                        "name": "compat: Changes to the questionary/inquirer.js compatibility layer",
                    },
                    {
                        "value": "refactor",
                        "name": "refactor: Code restructuring without behavior change",
                    },
                    {
                        "value": "perf",
                        "name": "perf: Performance improvement",
                    },
                    {
                        "value": "test",
                        "name": "test: Adding or improving tests (unit, property-based, chaos, integration)",
                    },
                    {
                        "value": "docs",
                        "name": "docs: Documentation, README, protocol spec, or examples",
                    },
                    {
                        "value": "chore",
                        "name": "chore: Build, CI, tooling, dependencies, or project config",
                    },
                    {
                        "value": "ci",
                        "name": "ci: CI/CD pipeline changes (GitHub Actions, hooks)",
                    },
                ],
            },
            {
                "type": "list",
                "name": "scope",
                "message": "What part of the project is affected?",
                "choices": [
                    {"value": "python", "name": "python: Python library (src/inquirer_ai/)"},
                    {"value": "go", "name": "go: Go library (go/prompt/)"},
                    {"value": "spec", "name": "spec: Protocol specification (spec/)"},
                    {"value": "prompt", "name": "prompt: Core prompt logic (BasePrompt, execute, agent mode)"},
                    {"value": "choice", "name": "choice: Choice, Separator, disabled, short, description"},
                    {"value": "theme", "name": "theme: Theme, styling, symbols, colors"},
                    {"value": "select", "name": "select: SelectPrompt / select TUI"},
                    {"value": "checkbox", "name": "checkbox: CheckboxPrompt / checkbox TUI"},
                    {"value": "text", "name": "text: TextPrompt / input"},
                    {"value": "confirm", "name": "confirm: ConfirmPrompt"},
                    {"value": "password", "name": "password: PasswordPrompt"},
                    {"value": "number", "name": "number: NumberPrompt"},
                    {"value": "editor", "name": "editor: EditorPrompt"},
                    {"value": "search", "name": "search: SearchPrompt"},
                    {"value": "expand", "name": "expand: ExpandPrompt"},
                    {"value": "rawlist", "name": "rawlist: RawlistPrompt"},
                    {"value": "path", "name": "path: PathPrompt"},
                    {"value": "autocomplete", "name": "autocomplete: AutocompletePrompt"},
                    {"value": "compat", "name": "compat: questionary compatibility layer"},
                    {"value": "ci", "name": "ci: CI/CD, hooks, linting, formatting"},
                    {"value": "deps", "name": "deps: Dependencies (pyproject.toml, go.mod)"},
                ],
            },
            {
                "type": "input",
                "name": "subject",
                "filter": _parse_subject,
                "message": "Write a short summary of the change (imperative mood, no period):\n",
            },
            {
                "type": "input",
                "name": "body",
                "message": "Why is this change needed? Provide context:\n(press [enter] to skip)\n",
                "filter": multiple_line_breaker,
            },
            {
                "type": "confirm",
                "name": "is_breaking_change",
                "message": "Is this a BREAKING CHANGE? (protocol-breaking changes affect all agent consumers)",
                "default": False,
            },
            {
                "type": "input",
                "name": "footer",
                "message": "References (issues, PRs, related commits):\n(press [enter] to skip)\n",
            },
        ]

    def message(self, answers: dict) -> str:
        prefix = answers["prefix"]
        scope = answers["scope"]
        subject = answers["subject"]
        body = answers.get("body", "")
        footer = answers.get("footer", "")
        is_breaking_change = answers.get("is_breaking_change", False)

        title = f"{prefix}({scope}): {subject}"

        parts = [title]
        if body:
            parts.append(f"\n\n{body}")

        footer_lines = []
        if is_breaking_change:
            footer_lines.append("BREAKING CHANGE: this change affects the agent protocol")
        if footer:
            footer_lines.append(footer)

        if footer_lines:
            parts.append("\n\n" + "\n".join(footer_lines))

        return "".join(parts)

    def example(self) -> str:
        return (
            "feat(select): add description field shown on focused choice\n"
            "\n"
            "When a Choice has a description, it is displayed inline after\n"
            "the choice name when the cursor is on that item.\n"
            "\n"
            "Refs: #42"
        )

    def schema(self) -> str:
        return (
            "<type>(<scope>): <subject>\n"
            "<BLANK LINE>\n"
            "<body>\n"
            "<BLANK LINE>\n"
            "[BREAKING CHANGE: ...]\n"
            "[Refs: ...]"
        )

    def schema_pattern(self) -> str:
        change_types = (
            "feat", "fix", "hotfix", "refactor", "perf", "test",
            "docs", "chore", "ci", "protocol", "compat",
        )
        return (
            r"(?s)"
            r"(" + "|".join(change_types) + r")"
            r"(\(\S+\))?"
            r"!?"
            r": "
            r"([^\n\r]+)"
            r"((\n\n.*)|(\s*))?$"
        )

    def info(self) -> str:
        return (
            "inquirer-ai commit convention:\n"
            "  feat/fix — standard changes\n"
            "  protocol — agent JSON protocol changes (breaking = major)\n"
            "  compat — questionary/inquirer.js compatibility layer\n"
            "  refactor/perf/test/docs/chore/ci — non-functional\n"
            "\n"
            "Scopes match project structure: python, go, spec, or specific prompt type.\n"
            "Protocol-breaking changes require BREAKING CHANGE footer."
        )

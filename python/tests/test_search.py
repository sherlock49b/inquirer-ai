import io
import json
from unittest.mock import patch

import pytest

from inquirer_ai.exceptions import PromptAbortedError
from inquirer_ai.prompts.search import SearchPrompt
from tests.conftest import parse_prompt_from_stdout

ALL_ITEMS = ["Apple", "Banana", "Cherry", "Date", "Elderberry"]


def _source(term: str) -> list[str]:
    if not term:
        return ALL_ITEMS
    return [item for item in ALL_ITEMS if term.lower() in item.lower()]


def test_agent_mode_basic(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": "Banana"}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = SearchPrompt("Pick a fruit", source=_source)
    result = p.execute()

    assert result == "Banana"
    prompt_data = parse_prompt_from_stdout(stdout)
    assert prompt_data["type"] == "search"
    assert prompt_data["searchable"] is True
    assert len(prompt_data["choices"]) == 5


def test_agent_mode_with_filter(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": "cherry"}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = SearchPrompt("Pick", source=_source, filter=lambda v: v.upper())
    assert p.execute() == "CHERRY"


def test_agent_dict_shows_initial_choices():
    p = SearchPrompt("Pick", source=_source)
    d = p._to_agent_dict()
    names = [c["name"] for c in d["choices"]]
    assert names == ALL_ITEMS


def test_source_with_dict_choices(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": "pg"}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    def source(term: str) -> list[dict[str, str]]:
        items = [{"name": "PostgreSQL", "value": "pg"}, {"name": "MySQL", "value": "mysql"}]
        if not term:
            return items
        return [i for i in items if term.lower() in i["name"].lower()]

    p = SearchPrompt("DB?", source=source)
    assert p.execute() == "pg"


def test_terminal_mode_basic(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "human")
    with patch("inquirer_ai.prompts.search.Application") as mock_app_cls:
        mock_app_cls.return_value.run.return_value = "Banana"
        p = SearchPrompt("Pick a fruit", source=_source)
        assert p.execute() == "Banana"


def test_terminal_mode_abort(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "human")
    with patch("inquirer_ai.prompts.search.Application") as mock_app_cls:
        mock_app_cls.return_value.run.return_value = None
        p = SearchPrompt("Pick a fruit", source=_source)
        with pytest.raises(PromptAbortedError):
            p.execute()


# --- Async source tests ---


async def _async_source(term: str) -> list[str]:
    if not term:
        return ALL_ITEMS
    return [item for item in ALL_ITEMS if term.lower() in item.lower()]


def test_agent_mode_async_source(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": "Cherry"}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = SearchPrompt("Pick a fruit", source=_async_source)
    result = p.execute()

    assert result == "Cherry"
    prompt_data = parse_prompt_from_stdout(stdout)
    assert prompt_data["type"] == "search"
    assert prompt_data["searchable"] is True
    assert len(prompt_data["choices"]) == 5


def test_agent_dict_async_source_shows_initial_choices():
    p = SearchPrompt("Pick", source=_async_source)
    d = p._to_agent_dict()
    names = [c["name"] for c in d["choices"]]
    assert names == ALL_ITEMS


@pytest.mark.asyncio
async def test_agent_mode_async_source_with_execute_async(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": "Apple"}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = SearchPrompt("Pick a fruit", source=_async_source)
    result = await p.execute_async()

    assert result == "Apple"
    prompt_data = parse_prompt_from_stdout(stdout)
    assert prompt_data["type"] == "search"
    assert len(prompt_data["choices"]) == 5

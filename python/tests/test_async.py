"""Tests for async execute_async() and async convenience functions."""

import io
import json

import pytest

import inquirer_ai
from inquirer_ai.exceptions import ValidationError
from inquirer_ai.prompts.text import TextPrompt
from tests.conftest import parse_prompt_from_stdout


@pytest.fixture(autouse=True)
def _agent_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")


def _make_stdin(*answers: object) -> io.StringIO:
    lines = [json.dumps({"answer": a}) + "\n" for a in answers]
    return io.StringIO("".join(lines))


@pytest.mark.asyncio
async def test_execute_async_basic(monkeypatch: pytest.MonkeyPatch) -> None:
    stdin = _make_stdin("hello")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = TextPrompt("Enter name")
    result = await p.execute_async()

    assert result == "hello"
    prompt_data = parse_prompt_from_stdout(stdout)
    assert prompt_data["type"] == "input"
    assert prompt_data["message"] == "Enter name"


@pytest.mark.asyncio
async def test_execute_async_with_default(monkeypatch: pytest.MonkeyPatch) -> None:
    stdin = _make_stdin(None)
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = TextPrompt("Name", default="world")
    result = await p.execute_async()

    assert result == "world"


@pytest.mark.asyncio
async def test_execute_async_with_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    stdin = _make_stdin("  Hello  ")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = TextPrompt("Name", filter=lambda v: v.strip().lower())
    result = await p.execute_async()

    assert result == "hello"


@pytest.mark.asyncio
async def test_execute_async_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    stdin = _make_stdin("ab")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = TextPrompt("Name", validate=lambda v: len(v) >= 3 or "Too short")
    with pytest.raises(ValidationError, match="Too short"):
        await p.execute_async()


@pytest.mark.asyncio
async def test_text_async(monkeypatch: pytest.MonkeyPatch) -> None:
    stdin = _make_stdin("alice")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    result = await inquirer_ai.text_async("What is your name?")
    assert result == "alice"


@pytest.mark.asyncio
async def test_confirm_async(monkeypatch: pytest.MonkeyPatch) -> None:
    stdin = _make_stdin(True)
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    result = await inquirer_ai.confirm_async("Continue?")
    assert result is True


@pytest.mark.asyncio
async def test_confirm_async_false(monkeypatch: pytest.MonkeyPatch) -> None:
    stdin = _make_stdin(False)
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    result = await inquirer_ai.confirm_async("Continue?")
    assert result is False


@pytest.mark.asyncio
async def test_select_async(monkeypatch: pytest.MonkeyPatch) -> None:
    stdin = _make_stdin("b")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    result = await inquirer_ai.select_async("Pick one", choices=["a", "b", "c"])
    assert result == "b"


@pytest.mark.asyncio
async def test_checkbox_async(monkeypatch: pytest.MonkeyPatch) -> None:
    stdin = _make_stdin(["x", "z"])
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    result = await inquirer_ai.checkbox_async("Pick some", choices=["x", "y", "z"])
    assert result == ["x", "z"]


@pytest.mark.asyncio
async def test_password_async(monkeypatch: pytest.MonkeyPatch) -> None:
    stdin = _make_stdin("secret123")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    result = await inquirer_ai.password_async("Password?")
    assert result == "secret123"


@pytest.mark.asyncio
async def test_number_async(monkeypatch: pytest.MonkeyPatch) -> None:
    stdin = _make_stdin(42)
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    result = await inquirer_ai.number_async("Pick a number")
    assert result == 42

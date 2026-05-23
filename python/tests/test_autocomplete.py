import io
import json

from inquirer_ai.prompts.autocomplete import AutocompletePrompt
from tests.conftest import parse_prompt_from_stdout


def test_agent_mode_basic(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": "python"}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = AutocompletePrompt("Pick a language", choices=["python", "javascript", "rust"])
    result = p.execute()

    assert result == "python"
    prompt_data = parse_prompt_from_stdout(stdout)
    assert prompt_data["type"] == "autocomplete"
    assert prompt_data["message"] == "Pick a language"


def test_agent_mode_accepts_non_choice(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": "haskell"}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = AutocompletePrompt("Pick a language", choices=["python", "javascript", "rust"])
    result = p.execute()

    assert result == "haskell"


def test_agent_mode_default(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": None}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = AutocompletePrompt("Pick a language", choices=["python", "javascript"], default="python")
    result = p.execute()

    assert result == "python"


def test_agent_dict_includes_choices():
    p = AutocompletePrompt("Pick a language", choices=["python", "javascript", "rust"])
    d = p._to_agent_dict()

    assert d["type"] == "autocomplete"
    assert d["choices"] == ["python", "javascript", "rust"]
    assert d["message"] == "Pick a language"


def test_terminal_mode(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "human")
    monkeypatch.setattr("inquirer_ai.prompts.autocomplete.pt_prompt", lambda *args, **kwargs: "rust")

    p = AutocompletePrompt("Pick a language", choices=["python", "javascript", "rust"])
    result = p.execute()

    assert result == "rust"

import io
import json

from inquirer_ai.prompts.path import PathPrompt
from tests.conftest import parse_prompt_from_stdout


def test_agent_mode_basic(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": "/home/user/file.txt"}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = PathPrompt("Select a file")
    result = p.execute()

    assert result == "/home/user/file.txt"
    prompt_data = parse_prompt_from_stdout(stdout)
    assert prompt_data["type"] == "path"
    assert prompt_data["message"] == "Select a file"


def test_agent_mode_default(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": None}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = PathPrompt("Select a file", default="/tmp")
    result = p.execute()

    assert result == "/tmp"
    prompt_data = parse_prompt_from_stdout(stdout)
    assert prompt_data["default"] == "/tmp"


def test_agent_dict_includes_options(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    p = PathPrompt("Select a directory", only_directories=True)
    d = p._to_agent_dict()
    assert d["only_directories"] is True
    assert d["type"] == "path"

    p2 = PathPrompt("Select a file")
    d2 = p2._to_agent_dict()
    assert d2["only_directories"] is False


def test_terminal_mode(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "human")
    monkeypatch.setattr(
        "inquirer_ai.prompts.path.pt_prompt",
        lambda *args, **kwargs: "/etc/hosts",
    )
    p = PathPrompt("Select a file")
    assert p.execute() == "/etc/hosts"

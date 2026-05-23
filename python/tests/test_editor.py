import io
import json
from unittest.mock import patch

from inquirer_ai.prompts.editor import EditorPrompt
from tests.conftest import parse_prompt_from_stdout


def test_agent_mode_basic(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": "Hello world\nLine 2"}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = EditorPrompt("Enter text")
    result = p.execute()

    assert result == "Hello world\nLine 2"
    prompt_data = parse_prompt_from_stdout(stdout)
    assert prompt_data["type"] == "editor"
    assert prompt_data["postfix"] == ".txt"


def test_agent_mode_default(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": None}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = EditorPrompt("Enter text", default="default text")
    assert p.execute() == "default text"


def test_agent_mode_custom_postfix(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = io.StringIO(json.dumps({"answer": "code"}) + "\n")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    p = EditorPrompt("Enter code", postfix=".py")
    assert p.execute() == "code"
    prompt_data = parse_prompt_from_stdout(stdout)
    assert prompt_data["postfix"] == ".py"


def test_terminal_mode(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "human")
    with patch("inquirer_ai.prompts.editor.subprocess.run") as mock_run:
        mock_run.return_value = None

        def fake_open(path, *args, **kwargs):
            class FakeFile:
                def read(self):
                    return "edited content"

                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    pass

            return FakeFile()

        with patch("builtins.open", fake_open), patch("inquirer_ai.prompts.editor.os.unlink"):
            p = EditorPrompt("Edit")
            assert p.execute() == "edited content"

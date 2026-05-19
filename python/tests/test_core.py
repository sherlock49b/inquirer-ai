import io
import json

from inquirer_ai.core import prompt


def _make_stdin(*answers) -> io.StringIO:
    lines = [json.dumps({"answer": a}) + "\n" for a in answers]
    return io.StringIO("".join(lines))


def test_prompt_multiple_questions(monkeypatch):
    monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
    stdin = _make_stdin("Alice", True, "pg")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    questions = [
        {"type": "input", "name": "username", "message": "Enter name"},
        {"type": "confirm", "name": "ok", "message": "Proceed?"},
        {
            "type": "select",
            "name": "db",
            "message": "Choose DB",
            "choices": ["pg", "mysql"],
        },
    ]
    answers = prompt(questions)

    assert answers == {"username": "Alice", "ok": True, "db": "pg"}

    lines = stdout.getvalue().strip().split("\n")
    assert len(lines) == 3
    assert json.loads(lines[0])["type"] == "input"
    assert json.loads(lines[1])["type"] == "confirm"
    assert json.loads(lines[2])["type"] == "select"

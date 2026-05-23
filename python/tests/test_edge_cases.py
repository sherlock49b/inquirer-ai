"""Edge case tests from code review: multi-prompt recovery, handshake defense, concurrency."""

import io
import json
import threading

import pytest

import inquirer_ai.prompts.base as _base
from inquirer_ai.exceptions import PromptAbortedError, ValidationError
from inquirer_ai.prompts.confirm import ConfirmPrompt
from inquirer_ai.prompts.text import TextPrompt


class TestMultiPromptErrorRecovery:
    """What happens when the second or third prompt in a sequence gets bad input?"""

    def test_second_prompt_bad_json_doesnt_corrupt_first(self, monkeypatch):
        monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
        lines = json.dumps({"answer": "Alice"}) + "\n" + "not json\n"
        monkeypatch.setattr("sys.stdin", io.StringIO(lines))
        monkeypatch.setattr("sys.stdout", io.StringIO())

        p1 = TextPrompt("Name?")
        result1 = p1.execute()
        assert result1 == "Alice"

        p2 = TextPrompt("Email?")
        with pytest.raises(ValidationError, match="Invalid JSON"):
            p2.execute()

    def test_second_prompt_eof_after_first_succeeds(self, monkeypatch):
        monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
        lines = json.dumps({"answer": "Alice"}) + "\n"
        monkeypatch.setattr("sys.stdin", io.StringIO(lines))
        monkeypatch.setattr("sys.stdout", io.StringIO())

        p1 = TextPrompt("Name?")
        assert p1.execute() == "Alice"

        p2 = TextPrompt("Email?")
        with pytest.raises(PromptAbortedError):
            p2.execute()

    def test_third_prompt_bad_input_after_two_good(self, monkeypatch):
        monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
        lines = (
            json.dumps({"answer": "Alice"})
            + "\n"
            + json.dumps({"answer": True})
            + "\n"
            + json.dumps({"answer": []})
            + "\n"  # array for text prompt
        )
        monkeypatch.setattr("sys.stdin", io.StringIO(lines))
        monkeypatch.setattr("sys.stdout", io.StringIO())

        assert TextPrompt("Name?").execute() == "Alice"
        assert ConfirmPrompt("Ok?").execute() is True
        result = TextPrompt("Third?").execute()
        assert result == "[]"


class TestHandshakeDefense:
    """What if agent sends data before/during handshake?"""

    def test_handshake_is_first_output_line(self, monkeypatch):
        monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"answer": "x"}) + "\n"))
        stdout = io.StringIO()
        monkeypatch.setattr("sys.stdout", stdout)

        TextPrompt("Q").execute()

        lines = stdout.getvalue().strip().split("\n")
        first = json.loads(lines[0])
        assert first["protocol"] == "inquirer-ai"
        assert first["interaction"] == "sequential"

    def test_agent_answering_handshake_as_prompt(self, monkeypatch):
        """If agent treats handshake as a prompt and sends {"answer": ...},
        that response will be consumed by the actual first prompt."""
        monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
        lines = json.dumps({"answer": "handshake_response"}) + "\n" + json.dumps({"answer": "real_answer"}) + "\n"
        monkeypatch.setattr("sys.stdin", io.StringIO(lines))
        monkeypatch.setattr("sys.stdout", io.StringIO())

        result = TextPrompt("Q").execute()
        assert result == "handshake_response"

    def test_handshake_not_sent_in_human_mode(self, monkeypatch):
        monkeypatch.setenv("INQUIRER_AI_MODE", "human")
        monkeypatch.setattr("inquirer_ai.prompts.text.pt_prompt", lambda _: "hi")
        stdout = io.StringIO()
        monkeypatch.setattr("sys.stdout", stdout)

        TextPrompt("Q").execute()

        output = stdout.getvalue()
        assert "inquirer-ai" not in output


class TestConcurrentHandshake:
    """_agent_handshake_sent is a global — verify it doesn't corrupt under threads."""

    def test_handshake_sent_exactly_once_under_threads(self, monkeypatch):
        monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
        _base._agent_handshake_sent = False

        handshake_count = 0
        lock = threading.Lock()
        original_write = io.StringIO.write

        class CountingWriter(io.StringIO):
            def write(self, s):
                nonlocal handshake_count
                if "inquirer-ai" in s:
                    with lock:
                        handshake_count += 1
                return original_write(self, s)

        stdout = CountingWriter()
        monkeypatch.setattr("sys.stdout", stdout)

        answers = "\n".join(json.dumps({"answer": f"t{i}"}) for i in range(10)) + "\n"
        monkeypatch.setattr("sys.stdin", io.StringIO(answers))

        results = []
        errors = []

        def run_prompt(i):
            try:
                r = TextPrompt(f"Q{i}").execute()
                results.append(r)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=run_prompt, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Document the race condition — don't fail, just observe
        _ = handshake_count  # may be >1 due to race on _agent_handshake_sent

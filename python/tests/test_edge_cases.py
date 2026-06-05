"""Edge case tests from code review: multi-prompt recovery, handshake defense, concurrency."""

import io
import json

import pytest

import inquirer_ai.prompts.base as _base
from inquirer_ai.exceptions import PromptAbortedError, ValidationError
from inquirer_ai.prompts.confirm import ConfirmPrompt
from inquirer_ai.prompts.text import TextPrompt


class TestMultiPromptErrorRecovery:
    """What happens when the second or third prompt in a sequence gets bad input?"""

    def test_second_prompt_bad_json_doesnt_corrupt_first(self, monkeypatch):
        monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
        # The second prompt exhausts its unified 3-attempt budget on bad JSON (R1).
        lines = json.dumps({"answer": "Alice"}) + "\n" + "not json\n" * 3
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
        assert first["kind"] == "handshake"
        assert first["interaction"] == "sequential"

    def test_agent_answering_handshake_as_prompt(self, monkeypatch):
        """If agent treats handshake as a prompt and sends {"answer": ...},
        that response will be pushed back and consumed by the actual first prompt."""
        monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
        lines = json.dumps({"answer": "handshake_response"}) + "\n" + json.dumps({"answer": "real_answer"}) + "\n"
        monkeypatch.setattr("sys.stdin", io.StringIO(lines))
        monkeypatch.setattr("sys.stdout", io.StringIO())

        result = TextPrompt("Q").execute()
        assert result == "handshake_response"

    def test_handshake_not_sent_in_human_mode(self, monkeypatch):
        monkeypatch.setenv("INQUIRER_AI_MODE", "human")
        monkeypatch.setattr("inquirer_ai.prompts.text.pt_prompt", lambda _, **kw: "hi")
        stdout = io.StringIO()
        monkeypatch.setattr("sys.stdout", stdout)

        TextPrompt("Q").execute()

        output = stdout.getvalue()
        assert "inquirer-ai" not in output


class TestHandshakeIdempotency:
    """The agent handshake is emitted exactly once per process. The protocol is
    sequential by contract (one prompt at a time over one stream), so the real
    invariant is idempotency across calls — the handshake must not repeat on
    every prompt — and ``_reset_agent_handshake`` must re-arm it for a new session.
    (Thread-safety of the global is out of contract; concurrent prompting is not
    a supported transport. See the handshake-race note in the test-flight run.)
    """

    @staticmethod
    def _count_kind(output: str, kind: str) -> int:
        count = 0
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(msg, dict) and msg.get("kind") == kind:
                count += 1
        return count

    def test_handshake_sent_exactly_once_across_sequential_prompts(self, monkeypatch):
        monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
        _base._reset_agent_handshake()

        answers = "".join(json.dumps({"answer": f"t{i}"}) + "\n" for i in range(3))
        monkeypatch.setattr("sys.stdin", io.StringIO(answers))
        stdout = io.StringIO()
        monkeypatch.setattr("sys.stdout", stdout)

        results = [TextPrompt(f"Q{i}").execute() for i in range(3)]
        output = stdout.getvalue()

        assert results == ["t0", "t1", "t2"]  # every prompt answered
        assert self._count_kind(output, "handshake") == 1  # once, not per-prompt
        assert self._count_kind(output, "prompt") == 3  # each prompt still announced

    def test_reset_rearms_handshake(self, monkeypatch):
        monkeypatch.setenv("INQUIRER_AI_MODE", "agent")

        def run_once(answer: str) -> str:
            monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"answer": answer}) + "\n"))
            out = io.StringIO()
            monkeypatch.setattr("sys.stdout", out)
            TextPrompt("Q").execute()
            return out.getvalue()

        _base._reset_agent_handshake()
        assert self._count_kind(run_once("a"), "handshake") == 1  # first session: handshake
        assert self._count_kind(run_once("b"), "handshake") == 0  # same session: not repeated
        _base._reset_agent_handshake()
        assert self._count_kind(run_once("c"), "handshake") == 1  # after reset: re-armed

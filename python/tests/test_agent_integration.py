"""Subprocess-based integration tests for the agent JSON line protocol."""

import json
import subprocess
import sys
import textwrap


def _run_agent_script(script: str, stdin_lines: list[dict[str, object]]) -> list[dict[str, object]]:
    stdin_payload = "\n".join(json.dumps(line) for line in stdin_lines) + "\n"
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(script)],
        input=stdin_payload,
        capture_output=True,
        text=True,
        env={"INQUIRER_AI_MODE": "agent", "PATH": ""},
        timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Script failed:\nstdout: {result.stdout}\nstderr: {result.stderr}")
    prompts: list[dict[str, object]] = []
    for line in result.stdout.strip().splitlines():
        prompts.append(json.loads(line))
    return prompts


class TestTextAgentProtocol:
    def test_basic_text(self):
        script = """\
        import inquirer_ai
        answer = inquirer_ai.text("What is your name?")
        import json, sys
        sys.stdout.write(json.dumps({"result": answer}) + "\\n")
        """
        prompts = _run_agent_script(script, [{"answer": "Alice"}])
        assert prompts[0]["type"] == "input"
        assert prompts[0]["message"] == "What is your name?"
        assert prompts[1]["result"] == "Alice"

    def test_text_with_default(self):
        script = """\
        import inquirer_ai
        answer = inquirer_ai.text("Name?", default="Bob")
        import json, sys
        sys.stdout.write(json.dumps({"result": answer}) + "\\n")
        """
        prompts = _run_agent_script(script, [{"answer": None}])
        assert prompts[0]["default"] == "Bob"
        assert prompts[1]["result"] == "Bob"


class TestConfirmAgentProtocol:
    def test_confirm_yes(self):
        script = """\
        import inquirer_ai
        answer = inquirer_ai.confirm("Continue?")
        import json, sys
        sys.stdout.write(json.dumps({"result": answer}) + "\\n")
        """
        prompts = _run_agent_script(script, [{"answer": True}])
        assert prompts[0]["type"] == "confirm"
        assert prompts[0]["message"] == "Continue?"
        assert prompts[1]["result"] is True

    def test_confirm_no(self):
        script = """\
        import inquirer_ai
        answer = inquirer_ai.confirm("Continue?")
        import json, sys
        sys.stdout.write(json.dumps({"result": answer}) + "\\n")
        """
        prompts = _run_agent_script(script, [{"answer": False}])
        assert prompts[1]["result"] is False

    def test_confirm_string_coercion(self):
        script = """\
        import inquirer_ai
        answer = inquirer_ai.confirm("Continue?")
        import json, sys
        sys.stdout.write(json.dumps({"result": answer}) + "\\n")
        """
        prompts = _run_agent_script(script, [{"answer": "yes"}])
        assert prompts[1]["result"] is True


class TestSelectAgentProtocol:
    def test_select_choices_in_prompt(self):
        script = """\
        import inquirer_ai
        answer = inquirer_ai.select("Pick one", choices=["a", "b", "c"])
        import json, sys
        sys.stdout.write(json.dumps({"result": answer}) + "\\n")
        """
        prompts = _run_agent_script(script, [{"answer": "b"}])
        assert prompts[0]["type"] == "select"
        assert prompts[0]["choices"] == [
            {"name": "a", "value": "a"},
            {"name": "b", "value": "b"},
            {"name": "c", "value": "c"},
        ]
        assert prompts[1]["result"] == "b"

    def test_select_by_name(self):
        script = """\
        import inquirer_ai
        from inquirer_ai import Choice
        answer = inquirer_ai.select("Pick", choices=[Choice("Alpha", 1), Choice("Beta", 2)])
        import json, sys
        sys.stdout.write(json.dumps({"result": answer}) + "\\n")
        """
        prompts = _run_agent_script(script, [{"answer": "Alpha"}])
        assert prompts[1]["result"] == 1


class TestCheckboxAgentProtocol:
    def test_checkbox_multi_select(self):
        script = """\
        import inquirer_ai
        answer = inquirer_ai.checkbox("Pick some", choices=["x", "y", "z"])
        import json, sys
        sys.stdout.write(json.dumps({"result": answer}) + "\\n")
        """
        prompts = _run_agent_script(script, [{"answer": ["x", "z"]}])
        assert prompts[0]["type"] == "checkbox"
        assert prompts[1]["result"] == ["x", "z"]

    def test_checkbox_empty_selection(self):
        script = """\
        import inquirer_ai
        answer = inquirer_ai.checkbox("Pick some", choices=["x", "y"])
        import json, sys
        sys.stdout.write(json.dumps({"result": answer}) + "\\n")
        """
        prompts = _run_agent_script(script, [{"answer": []}])
        assert prompts[1]["result"] == []


class TestFilterAndValidate:
    def test_filter_applied(self):
        script = """\
        import inquirer_ai
        answer = inquirer_ai.text("Name?", filter=str.upper)
        import json, sys
        sys.stdout.write(json.dumps({"result": answer}) + "\\n")
        """
        prompts = _run_agent_script(script, [{"answer": "alice"}])
        assert prompts[1]["result"] == "ALICE"

    def test_validation_failure_raises(self):
        script = """\
        import inquirer_ai, sys
        try:
            inquirer_ai.text("Name?", validate=lambda v: len(v) >= 3 or "Too short")
        except inquirer_ai.ValidationError as e:
            sys.stdout.write('{"error": "' + str(e) + '"}\\n')
        """
        prompts = _run_agent_script(script, [{"answer": "ab"}])
        assert "Too short" in prompts[-1].get("error", "")


class TestMultiPromptSequence:
    def test_two_prompts_in_sequence(self):
        script = """\
        import inquirer_ai, json, sys
        name = inquirer_ai.text("Name?")
        ok = inquirer_ai.confirm("Sure?")
        sys.stdout.write(json.dumps({"name": name, "ok": ok}) + "\\n")
        """
        prompts = _run_agent_script(script, [{"answer": "Eve"}, {"answer": True}])
        assert prompts[0]["type"] == "input"
        assert prompts[1]["type"] == "confirm"
        assert prompts[2] == {"name": "Eve", "ok": True}

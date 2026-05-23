from __future__ import annotations

import os
import subprocess
import tempfile
from typing import Any

from inquirer_ai.exceptions import EditorError
from inquirer_ai.prompts.base import BasePrompt


class EditorPrompt(BasePrompt[str]):
    def __init__(self, message: str, *, postfix: str = ".txt", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)
        self.postfix = postfix

    @property
    def prompt_type(self) -> str:
        return "editor"

    def _validate_answer(self, value: Any) -> str:
        if value is None:
            return self.default if self.default is not None else ""
        return str(value)

    def _to_agent_dict(self) -> dict[str, Any]:
        d = super()._to_agent_dict()
        d["postfix"] = self.postfix
        return d

    def _execute_terminal(self) -> str:
        editor = os.environ.get("VISUAL") or os.environ.get("EDITOR", "vi")
        with tempfile.NamedTemporaryFile(suffix=self.postfix, mode="w+", delete=False) as f:
            if self.default:
                f.write(self.default)
            f.flush()
            tmp_path = f.name

        try:
            subprocess.run([editor, tmp_path], check=True)
            with open(tmp_path) as f:
                return f.read()
        except FileNotFoundError:
            raise EditorError(f"Editor not found: {editor!r}. Set $VISUAL or $EDITOR.") from None
        except subprocess.CalledProcessError as e:
            raise EditorError(f"Editor exited with code {e.returncode}") from None
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

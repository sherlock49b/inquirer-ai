"""Search-specific async and concurrency tests.

Covers sync/async source functions in agent mode, edge cases (empty results,
special characters, exceptions), the ThreadPoolExecutor bridge for nested
event loops, and property-based fuzzing of the source pipeline.
"""

from __future__ import annotations

import asyncio
import io
import json
import string

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from inquirer_ai.choice import Choice, parse_choice
from inquirer_ai.prompts.search import SearchPrompt
from tests.conftest import parse_prompt_from_stdout

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ALL_ITEMS = ["Apple", "Banana", "Cherry", "Date", "Elderberry"]


def _sync_source(term: str) -> list[str]:
    if not term:
        return ALL_ITEMS
    return [item for item in ALL_ITEMS if term.lower() in item.lower()]


async def _async_source(term: str) -> list[str]:
    if not term:
        return ALL_ITEMS
    return [item for item in ALL_ITEMS if term.lower() in item.lower()]


def _empty_source(term: str) -> list[str]:
    return []


async def _async_empty_source(term: str) -> list[str]:
    return []


def _raising_source(term: str) -> list[str]:
    raise RuntimeError("source exploded")


async def _async_raising_source(term: str) -> list[str]:
    raise RuntimeError("async source exploded")


def _make_stdin(*answers: object) -> io.StringIO:
    lines = [json.dumps({"answer": a}) + "\n" for a in answers]
    return io.StringIO("".join(lines))


# ---------------------------------------------------------------------------
# 1. Sync source in agent mode
# ---------------------------------------------------------------------------


class TestSyncSourceAgentMode:
    def test_sync_source_basic(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
        stdin = _make_stdin("Banana")
        stdout = io.StringIO()
        monkeypatch.setattr("sys.stdin", stdin)
        monkeypatch.setattr("sys.stdout", stdout)

        p = SearchPrompt("Pick a fruit", source=_sync_source)
        result = p.execute()

        assert result == "Banana"
        prompt_data = parse_prompt_from_stdout(stdout)
        assert prompt_data["type"] == "search"
        assert prompt_data["searchable"] is True
        assert len(prompt_data["choices"]) == len(ALL_ITEMS)

    def test_sync_source_agent_dict_choices(self) -> None:
        p = SearchPrompt("Pick", source=_sync_source)
        d = p._to_agent_dict()
        names = [c["name"] for c in d["choices"]]
        assert names == ALL_ITEMS

    def test_sync_source_with_filter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
        stdin = _make_stdin("cherry")
        stdout = io.StringIO()
        monkeypatch.setattr("sys.stdin", stdin)
        monkeypatch.setattr("sys.stdout", stdout)

        p = SearchPrompt("Pick", source=_sync_source, filter=lambda v: v.upper())
        assert p.execute() == "CHERRY"


# ---------------------------------------------------------------------------
# 2. Async source in agent mode (ThreadPoolExecutor bridge)
# ---------------------------------------------------------------------------


class TestAsyncSourceAgentMode:
    def test_async_source_basic(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
        stdin = _make_stdin("Cherry")
        stdout = io.StringIO()
        monkeypatch.setattr("sys.stdin", stdin)
        monkeypatch.setattr("sys.stdout", stdout)

        p = SearchPrompt("Pick a fruit", source=_async_source)
        result = p.execute()

        assert result == "Cherry"
        prompt_data = parse_prompt_from_stdout(stdout)
        assert prompt_data["type"] == "search"
        assert prompt_data["searchable"] is True
        assert len(prompt_data["choices"]) == len(ALL_ITEMS)

    def test_async_source_agent_dict_choices(self) -> None:
        p = SearchPrompt("Pick", source=_async_source)
        d = p._to_agent_dict()
        names = [c["name"] for c in d["choices"]]
        assert names == ALL_ITEMS

    @pytest.mark.asyncio
    async def test_async_source_execute_async(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
        stdin = _make_stdin("Apple")
        stdout = io.StringIO()
        monkeypatch.setattr("sys.stdin", stdin)
        monkeypatch.setattr("sys.stdout", stdout)

        p = SearchPrompt("Pick a fruit", source=_async_source)
        result = await p.execute_async()

        assert result == "Apple"
        prompt_data = parse_prompt_from_stdout(stdout)
        assert prompt_data["type"] == "search"
        assert len(prompt_data["choices"]) == len(ALL_ITEMS)


# ---------------------------------------------------------------------------
# 3. Source with empty results
# ---------------------------------------------------------------------------


class TestEmptyResults:
    def test_sync_empty_source_agent_dict(self) -> None:
        p = SearchPrompt("Pick", source=_empty_source)
        d = p._to_agent_dict()
        assert d["choices"] == []

    def test_async_empty_source_agent_dict(self) -> None:
        p = SearchPrompt("Pick", source=_async_empty_source)
        d = p._to_agent_dict()
        assert d["choices"] == []

    def test_sync_empty_source_refresh_filtered(self) -> None:
        p = SearchPrompt("Pick", source=_empty_source)
        p._filtered = []
        p._cursor = 0
        p._refresh_filtered("anything")
        assert p._filtered == []
        assert p._cursor == 0

    def test_async_empty_source_refresh_filtered(self) -> None:
        p = SearchPrompt("Pick", source=_async_empty_source)
        p._filtered = []
        p._cursor = 0
        p._refresh_filtered("anything")
        assert p._filtered == []
        assert p._cursor == 0


# ---------------------------------------------------------------------------
# 4. Source with special characters
# ---------------------------------------------------------------------------


class TestSpecialCharacters:
    @pytest.mark.parametrize(
        "items",
        [
            ["café", "üñîçödë", "☃❤\U0001f600"],
            ["\t\ttabs", "new\nline", "carriage\rreturn"],
            ["a" * 500, "b" * 1000],
            ["", " ", "  "],
            ["\x00null\x01byte", "\x1b[31mred\x1b[0m"],
        ],
        ids=["unicode", "control-chars", "long-strings", "whitespace", "ansi-escape"],
    )
    def test_special_char_source_agent_dict(self, items: list[str]) -> None:
        def source(term: str) -> list[str]:
            return items

        p = SearchPrompt("Pick", source=source)
        d = p._to_agent_dict()
        # Non-empty items should produce choices; empty strings produce choices too
        # (Choice.from_raw("") creates Choice(name="", value=""))
        assert len(d["choices"]) == len(items)
        # Verify JSON-serializable
        json.dumps(d, ensure_ascii=False)

    @pytest.mark.parametrize(
        "items",
        [
            ["café", "üñîçödë", "☃❤\U0001f600"],
            ["\t\ttabs", "new\nline", "carriage\rreturn"],
            ["a" * 500, "b" * 1000],
        ],
        ids=["unicode", "control-chars", "long-strings"],
    )
    def test_special_char_async_source_agent_dict(self, items: list[str]) -> None:
        async def source(term: str) -> list[str]:
            return items

        p = SearchPrompt("Pick", source=source)
        d = p._to_agent_dict()
        assert len(d["choices"]) == len(items)
        json.dumps(d, ensure_ascii=False)

    def test_unicode_source_in_agent_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("INQUIRER_AI_MODE", "agent")
        stdin = _make_stdin("☃")
        stdout = io.StringIO()
        monkeypatch.setattr("sys.stdin", stdin)
        monkeypatch.setattr("sys.stdout", stdout)

        def source(term: str) -> list[str]:
            return ["☃", "❤", "\U0001f600"]

        p = SearchPrompt("Pick", source=source)
        result = p.execute()
        assert result == "☃"


# ---------------------------------------------------------------------------
# 5. Property-based (hypothesis) tests
# ---------------------------------------------------------------------------


# Strategies
_choice_text = st.text(min_size=0, max_size=50, alphabet=st.characters(codec="utf-8"))
_search_term = st.text(min_size=0, max_size=30, alphabet=string.printable)


class TestPropertyBased:
    @given(
        items=st.lists(_choice_text, min_size=0, max_size=20),
        term=_search_term,
    )
    @settings(max_examples=200)
    def test_sync_source_never_crashes(self, items: list[str], term: str) -> None:
        """Source returning arbitrary strings should never crash parse_choice."""

        def source(t: str) -> list[str]:
            return items

        p = SearchPrompt("q", source=source)
        raw_choices = p._call_source_sync(term)
        assert isinstance(raw_choices, list)
        parsed = [c for raw in raw_choices if isinstance((c := parse_choice(raw)), Choice) and not c.disabled]
        assert all(isinstance(c, Choice) for c in parsed)

    @given(
        items=st.lists(_choice_text, min_size=0, max_size=20),
        term=_search_term,
    )
    @settings(max_examples=200)
    def test_async_source_never_crashes(self, items: list[str], term: str) -> None:
        """Async source returning arbitrary strings should never crash."""

        async def source(t: str) -> list[str]:
            return items

        p = SearchPrompt("q", source=source)
        raw_choices = p._call_source_sync(term)
        assert isinstance(raw_choices, list)
        parsed = [c for raw in raw_choices if isinstance((c := parse_choice(raw)), Choice) and not c.disabled]
        assert all(isinstance(c, Choice) for c in parsed)

    @given(
        items=st.lists(_choice_text, min_size=0, max_size=15),
    )
    @settings(max_examples=100)
    def test_agent_dict_choices_json_serializable(self, items: list[str]) -> None:
        """Agent dict from any source output should always be JSON-serializable."""

        def source(t: str) -> list[str]:
            return items

        p = SearchPrompt("q", source=source)
        d = p._to_agent_dict()
        serialized = json.dumps(d, ensure_ascii=False)
        parsed = json.loads(serialized)
        assert parsed["type"] == "search"
        assert isinstance(parsed["choices"], list)

    @given(
        items=st.lists(_choice_text, min_size=0, max_size=10),
    )
    @settings(max_examples=100)
    def test_refresh_filtered_resets_cursor(self, items: list[str]) -> None:
        """_refresh_filtered should always reset cursor to 0."""

        def source(t: str) -> list[str]:
            return items

        p = SearchPrompt("q", source=source)
        p._cursor = 999
        p._filtered = []
        p._refresh_filtered("test")
        assert p._cursor == 0


# ---------------------------------------------------------------------------
# 6. ThreadPoolExecutor bridge (nested event loop)
# ---------------------------------------------------------------------------


class TestThreadPoolExecutorBridge:
    def test_async_source_from_running_loop(self) -> None:
        """When there IS a running event loop, the bridge should use
        ThreadPoolExecutor to run the async source in a separate thread."""
        call_count = 0

        async def counting_source(term: str) -> list[str]:
            nonlocal call_count
            call_count += 1
            return ["result"]

        p = SearchPrompt("q", source=counting_source)

        async def run_in_loop() -> list[str]:
            # We are inside a running loop here; _call_source_sync must
            # use the ThreadPoolExecutor branch.
            return p._call_source_sync("")  # type: ignore[return-value]

        result = asyncio.run(run_in_loop())
        assert result == ["result"]
        assert call_count == 1

    def test_async_source_without_running_loop(self) -> None:
        """When there is no running event loop, _call_source_sync should
        use asyncio.run directly."""

        async def source(term: str) -> list[str]:
            return ["direct"]

        p = SearchPrompt("q", source=source)
        result = p._call_source_sync("")
        assert result == ["direct"]

    def test_sync_source_passthrough(self) -> None:
        """Sync source should be called directly, no loop involvement."""

        def source(term: str) -> list[str]:
            return ["sync"]

        p = SearchPrompt("q", source=source)
        result = p._call_source_sync("")
        assert result == ["sync"]

    @pytest.mark.asyncio
    async def test_call_source_async_with_async_source(self) -> None:
        """_call_source_async should await the async source directly."""

        async def source(term: str) -> list[str]:
            return ["awaited"]

        p = SearchPrompt("q", source=source)
        result = await p._call_source_async("")
        assert result == ["awaited"]

    @pytest.mark.asyncio
    async def test_call_source_async_with_sync_source(self) -> None:
        """_call_source_async should call sync source directly."""

        def source(term: str) -> list[str]:
            return ["sync-in-async"]

        p = SearchPrompt("q", source=source)
        result = await p._call_source_async("")
        assert result == ["sync-in-async"]

    def test_bridge_agent_dict_from_running_loop(self) -> None:
        """_to_agent_dict calls _call_source_sync internally; verify it
        works correctly when called from inside a running event loop."""

        async def source(term: str) -> list[str]:
            return ["alpha", "beta"]

        p = SearchPrompt("q", source=source)

        async def run_in_loop() -> dict:
            return p._to_agent_dict()

        d = asyncio.run(run_in_loop())
        assert d["type"] == "search"
        assert len(d["choices"]) == 2


# ---------------------------------------------------------------------------
# 7. Source raising exception
# ---------------------------------------------------------------------------


class TestSourceExceptions:
    def test_sync_raising_source_propagates(self) -> None:
        p = SearchPrompt("q", source=_raising_source)
        with pytest.raises(RuntimeError, match="source exploded"):
            p._call_source_sync("")

    def test_async_raising_source_propagates(self) -> None:
        p = SearchPrompt("q", source=_async_raising_source)
        with pytest.raises(RuntimeError, match="async source exploded"):
            p._call_source_sync("")

    def test_sync_raising_source_in_agent_dict(self) -> None:
        p = SearchPrompt("q", source=_raising_source)
        with pytest.raises(RuntimeError, match="source exploded"):
            p._to_agent_dict()

    def test_async_raising_source_in_agent_dict(self) -> None:
        p = SearchPrompt("q", source=_async_raising_source)
        with pytest.raises(RuntimeError, match="async source exploded"):
            p._to_agent_dict()

    def test_sync_raising_source_in_refresh_filtered(self) -> None:
        p = SearchPrompt("q", source=_raising_source)
        p._filtered = []
        p._cursor = 0
        with pytest.raises(RuntimeError, match="source exploded"):
            p._refresh_filtered("")

    @pytest.mark.asyncio
    async def test_async_raising_source_via_call_source_async(self) -> None:
        p = SearchPrompt("q", source=_async_raising_source)
        with pytest.raises(RuntimeError, match="async source exploded"):
            await p._call_source_async("")

    def test_raising_source_from_running_loop(self) -> None:
        """Exception from async source should propagate through the
        ThreadPoolExecutor bridge."""

        async def bad_source(term: str) -> list[str]:
            raise RuntimeError("bridge boom")

        p = SearchPrompt("q", source=bad_source)

        async def run_in_loop() -> None:
            p._call_source_sync("")

        with pytest.raises(RuntimeError, match="bridge boom"):
            asyncio.run(run_in_loop())

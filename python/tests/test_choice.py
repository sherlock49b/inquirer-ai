import pytest

from inquirer_ai.choice import Choice


def test_from_string():
    c = Choice.from_raw("hello")
    assert c.name == "hello"
    assert c.value == "hello"


def test_from_dict_with_name_and_value():
    c = Choice.from_raw({"name": "PostgreSQL", "value": "pg"})
    assert c.name == "PostgreSQL"
    assert c.value == "pg"


def test_from_dict_name_only():
    c = Choice.from_raw({"name": "MySQL"})
    assert c.name == "MySQL"
    assert c.value == "MySQL"


def test_from_choice_instance():
    original = Choice(name="test", value=42)
    c = Choice.from_raw(original)
    assert c is original


def test_from_invalid_type():
    with pytest.raises(TypeError):
        Choice.from_raw(123)  # type: ignore[arg-type]


def test_to_dict():
    c = Choice(name="PostgreSQL", value="pg")
    assert c.to_dict() == {"name": "PostgreSQL", "value": "pg"}

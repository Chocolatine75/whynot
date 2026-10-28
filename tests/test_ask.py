"""ask_json: validated answers, repair with feedback, no guessing."""

import pytest

from fakes import ScriptedChat
from whynot.agents.ask import AgentError, Invalid, ask_json
from whynot.jsonio import JSONExtractError, extract_json


def positive(data):
    if not isinstance(data, dict) or not isinstance(data.get("n"), int) or data["n"] <= 0:
        raise Invalid("'n' must be a positive integer")
    return data["n"]


def test_valid_first_time():
    chat = ScriptedChat(['Sure! ```json\n{"n": 3}\n```'])
    a = ask_json(chat, [{"role": "user", "content": "q"}], positive, module="m", model="x")
    assert (a.value, a.attempts, a.usd) == (3, 1, 0.01)


def test_repair_sends_the_error_back():
    chat = ScriptedChat(['{"n": -1}', "not json", '{"n": 2}'])
    a = ask_json(chat, [{"role": "user", "content": "q"}], positive, module="m", model="x", repairs=2)
    assert a.value == 2 and a.attempts == 3 and a.usd == pytest.approx(0.03)
    second = chat.calls[1]["messages"]
    assert second[-2] == {"role": "assistant", "content": '{"n": -1}'}
    assert "'n' must be a positive integer" in second[-1]["content"]


def test_gives_up_with_every_error_and_the_spend():
    chat = ScriptedChat(['{"n": 0}', '{"n": 0}'])
    with pytest.raises(AgentError) as exc:
        ask_json(chat, [{"role": "user", "content": "q"}], positive, module="m", model="x", repairs=1)
    assert len(exc.value.errors) == 2 and exc.value.usd == pytest.approx(0.02)


@pytest.mark.parametrize("text, expected", [
    ('{"a": 1}', {"a": 1}),
    ('noise {"a": {"b": 2}} more', {"a": {"b": 2}}),
    ("```\n[1, 2]\n```", [1, 2]),
    ('thinking {not json} then ```json\n{"ok": true}\n```', {"ok": True}),
])
def test_extract_json(text, expected):
    assert extract_json(text) == expected


def test_extract_json_fails_cleanly():
    with pytest.raises(JSONExtractError):
        extract_json("no json at all")

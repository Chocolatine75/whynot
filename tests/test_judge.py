"""The simple-judge baseline: strict answers, retries, cache, failures recorded, never guessed."""

from types import SimpleNamespace as NS

import pytest

from whynot.sim.feed import FeedItem
from whynot.sim.viewer import ViewerCache
from whynot.validate.judge import Judge, build_messages, parse


class Model:
    viewer_model = "muse-spark-open"

    def __init__(self, answers):
        self.answers = answers  # ad text -> list of answers, consumed in order
        self.calls = []

    def viewer_chat(self, messages, *, module, **kwargs):
        self.calls.append((module, kwargs))
        content = messages[0]["content"]
        text = content if isinstance(content, str) else content[0]["text"]
        key = next(k for k in self.answers if k in text)
        return NS(text=self.answers[key].pop(0), cost=NS(usd=0.01))


def item(i, body, image=None):
    return FeedItem(str(i), "Brand", "", body, image_url=image)


@pytest.mark.parametrize("bad", ['{"score": 11}', '{"score": 0}', '{"score": 7.5}', '{"score": "7"}',
                                 '{"score": true}', '[7]', "seven", '{"why": "x"}'])
def test_parse_refuses_anything_but_an_integer_1_to_10(bad):
    with pytest.raises(ValueError):
        parse(bad)


def test_parse_accepts_fenced_json():
    assert parse('Sure:\n```json\n{"score": 8, "why": "clear offer"}\n```') == (8, "clear offer")


def test_image_is_sent_with_the_text_only_when_present():
    assert isinstance(build_messages(item(1, "hi"))[0]["content"], str)
    parts = build_messages(item(2, "hi", image="data:image/jpeg;base64,AAAA"))[0]["content"]
    assert parts[1] == {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,AAAA"}}
    assert "(image below)" in parts[0]["text"]


def test_judge_retries_once_then_records_the_failure_and_caches_valid_answers(tmp_path):
    model = Model({"good": ['{"score": 9, "why": "strong"}'], "flaky": ["oops", '{"score": 3}'],
                   "broken": ["no", "still no"]})
    judge = Judge(model, cache=ViewerCache(tmp_path))
    out = judge.run([item(1, "good"), item(2, "flaky"), item(3, "broken")])
    assert out.scores == {"1": 9.0, "2": 3.0} and set(out.failures) == {"3"}
    assert out.usd == pytest.approx(0.05)  # 1 + 2 + 2 calls
    assert all(module == "judge" and kw["reasoning_effort"] == "low" for module, kw in model.calls)

    again = Judge(Model({}), cache=ViewerCache(tmp_path)).run([item(1, "good"), item(2, "flaky")])
    assert again.scores == {"1": 9.0, "2": 3.0} and again.usd == 0 and again.cache_hits == 2

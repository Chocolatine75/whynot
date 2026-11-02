"""Picture and voice tell one story: lines own their shots, shots last as long as their line, the same cast in
every photo, and no other language unless the app is about it."""

import json
from dataclasses import replace

import pytest

from test_trends import CTX, DIALOGUE, GOOD, check, check_selling, selling_brief
from whynot.agents.ask import Invalid
from whynot.agents.trend_brief import Line, Shot, make_validator, other_languages, retime, storyboard_problems, write
from whynot.create.trends import BY_ID

WHATSAPP = replace(CTX, app_name="WhatsApp Messenger", store_text="Simple. Reliable. Private. Free calls with up to "
                   "32 people, on mobile and desktop, even on slower connections.")


def lines_brief(lines):
    return {**{k: v for k, v in GOOD.items() if k != "voice"}, "lines": json.loads(json.dumps(lines))}


def shots(*beats):
    return [Shot("photo", "", 1.0, "still", "none", b) for b in beats]


# --- the storyboard rule ---------------------------------------------------------------------

def test_a_storyboard_where_every_line_owns_its_shots():
    assert storyboard_problems([Line("me", "a", "en", shots=(1, 2)), Line("narrator", "b", "en", shots=(3,))],
                               shots("trend", "twist", "demo", "cta")) == []


@pytest.mark.parametrize(("lines", "error"), [
    ([Line("me", "a", "en")], "needs 'shots'"),
    ([Line("me", "a", "en", shots=(1, 3))], "in a row"),
    ([Line("me", "a", "en", shots=(1, 9))], "in a row"),
    ([Line("me", "a", "en", shots=(1, 2)), Line("me", "b", "en", shots=(2,))], "already has a line"),
    ([Line("me", "a", "en", shots=(1,))], "have no line"),  # shots 2 and 3 are silent
    ([Line("me", "a", "en", shots=(1, 2, 3))], "speaks over"),  # the creator over the app's demo
    ([Line("narrator", "a", "en", shots=(1, 2, 3))], "speaks over"),  # the brand over the story
])
def test_storyboard_problems(lines, error):
    problems = storyboard_problems(lines, shots("trend", "twist", "demo", "cta"))
    assert any(error in p for p in problems), problems


def test_a_plain_voice_over_is_still_accepted_without_a_storyboard():
    assert check(GOOD).lines[0].shots == ()  # the first scripts re-render as they were


def test_a_brief_with_lines_must_be_storyboarded_and_cast():
    d = lines_brief(DIALOGUE)
    for x in d["lines"]:
        del x["shots"]
    with pytest.raises(Invalid, match="needs 'shots'"):
        check(d)
    d = lines_brief(DIALOGUE)
    del d["cast"]
    with pytest.raises(Invalid, match="'cast'"):
        check(d)
    d["cast"] = "Minh and his phone at the counter"
    with pytest.raises(Invalid, match="'cast' mentions 'phone'"):
        check(d)


def test_the_narrator_is_the_brand():
    d = selling_brief()
    assert check_selling(d).lines[-1].speaker == "narrator"
    d["lines"][-1]["text"] = "i love linguaapp"
    with pytest.raises(Invalid, match="never says 'i'"):
        check_selling(d)


# --- languages -------------------------------------------------------------------------------

def test_other_languages_only_when_the_app_is_about_them():
    assert other_languages(CTX, "en") == ["vi"]  # a Vietnamese app
    assert other_languages(WHATSAPP, "en") == []  # a messaging app: everyone speaks English


def test_a_messaging_app_ad_refuses_a_vietnamese_line():
    validate = make_validator(WHATSAPP, BY_ID["tell_me_without"], "heritage_learner", "southern_accent", 3,
                              has_mascot=False)
    with pytest.raises(Invalid, match="spoken in en only; write the line in en"):
        validate(lines_brief(DIALOGUE))


class Recorder:
    def __init__(self):
        self.prompt = ""

    def chat(self, messages, **kw):
        self.prompt = messages[0]["content"]
        raise RuntimeError("stop after the prompt")


def test_the_prompt_offers_no_other_language_to_a_messaging_app():
    model = Recorder()
    with pytest.raises(RuntimeError):
        write(model, WHATSAPP, BY_ID["tell_me_without"], persona="heritage_learner", angle="southern_accent",
              screens=["a", "b", "c"], has_mascot=False)
    assert "no other language anywhere" in model.prompt and "Vietnamese (code vi" not in model.prompt
    assert "cà phê" not in model.prompt and "southern voice" not in model.prompt  # no VietBuddy examples left
    assert "STORYBOARD" in model.prompt and '"cast"' in model.prompt
    with pytest.raises(RuntimeError):
        write(model, CTX, BY_ID["tell_me_without"], persona="heritage_learner", angle="southern_accent",
              screens=["a", "b", "c"], has_mascot=False)
    assert "Vietnamese (code vi" in model.prompt  # the Vietnamese app keeps its native voices


# --- timing ----------------------------------------------------------------------------------

def test_shots_last_as_long_as_their_line():
    b = check_selling(selling_brief())
    measured = [2.5, 3.0, 1.1, 6.0]  # seconds of each line in the audio, gap included
    t = retime(b, measured)
    for x, total in zip(t.lines, measured, strict=True):
        assert sum(t.shots[k - 1].seconds for k in x.shots) == pytest.approx(total, abs=0.01)
    first, second = b.lines[0].shots
    assert t.shots[first - 1].seconds / t.shots[second - 1].seconds == pytest.approx(
        b.shots[first - 1].seconds / b.shots[second - 1].seconds, rel=0.01)  # proportions kept
    assert t.shots[-1].seconds == b.shots[-1].seconds  # the cta keeps its time
    assert retime(b, measured[:2]) == b  # unknown timing: unchanged
    assert retime(check(GOOD), [3.0]) == check(GOOD)  # a plain voice-over has no storyboard to follow

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
    assert storyboard_problems([Line("me", "a", "en", shots=(1, 2)), Line("narrator", "b", "en", shots=(3, 4))],
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
    measured = [2.5, 3.0, 1.1, 7.0]  # seconds of each line in the audio, gap included
    t = retime(b, measured)
    for x, total in zip(t.lines, measured, strict=True):
        assert sum(t.shots[k - 1].seconds for k in x.shots) == pytest.approx(total, abs=0.01)
    first, second = b.lines[0].shots
    assert t.shots[first - 1].seconds / t.shots[second - 1].seconds == pytest.approx(
        b.shots[first - 1].seconds / b.shots[second - 1].seconds, rel=0.01)  # proportions kept
    assert retime(b, measured[:2]) == b  # unknown timing: unchanged
    assert retime(check(GOOD), [3.0]) == check(GOOD)  # a plain voice-over has no storyboard to follow


# --- realism, motion, honesty ------------------------------------------------------------------

from whynot.agency.trend_video import final_check, short_brand  # noqa: E402
from whynot.agents.trend_brief import photo_problem  # noqa: E402


@pytest.mark.parametrize(("prompt", "refused"), [
    ("Rosa holding her phone to her ear, screen facing away, laughing", None),  # the phone is in the story
    ("Leo typing on the back of the phone, from behind the phone", None),
    ("Rosa staring at her phone", "phone"),  # its screen could show a generated interface
    ("the WhatsApp app open on a laptop", "app"),
    ("a neon sign over the bar", "sign"),
])
def test_a_phone_in_hand_but_never_its_screen(prompt, refused):
    assert photo_problem(prompt) == refused


def test_screens_come_alive_with_a_valid_motion():
    d = selling_brief()
    d["shots"][5]["ui"] = "grid"
    d["shots"][5]["grid"] = [2, 3]
    d["shots"][6]["ui"] = "rows"
    b = check_selling(d)
    assert (b.shots[5].ui, b.shots[5].grid, b.shots[6].ui) == ("grid", (2, 3), "rows")
    from whynot.agents.trend_brief import TrendBrief
    assert TrendBrief.from_json(json.loads(json.dumps(b.to_json()))) == b
    d["shots"][5]["grid"] = [9, 9]
    with pytest.raises(Invalid, match="'grid'"):
        check_selling(d)
    d["shots"][5]["ui"] = "explode"
    with pytest.raises(Invalid, match="'ui' must be one of"):
        check_selling(d)


def test_the_brand_never_claims_an_absolute():
    d = selling_brief()
    d["lines"][3]["text"] = "calls and texts stay private always, free to download"
    with pytest.raises(Invalid, match="'always'"):
        check_selling(d)


def test_the_brand_is_the_name_people_say():
    assert short_brand({"name": "WhatsApp Messenger", "seller": "WhatsApp Inc."}) == "WhatsApp"
    assert short_brand({"name": "VietBuddy: Learn Vietnamese", "seller": "Lingo Ltd"}) == "VietBuddy"
    assert short_brand({"name": "Flighty – Live Flight Tracker", "seller": None}) == "Flighty"


class Ears:
    """Muse Voice Transcribe on the final mix."""

    def __init__(self, heard):
        self.heard = heard

    def transcribe(self, wav, **kw):
        if isinstance(self.heard, Exception):
            raise self.heard
        return self.heard


def test_the_final_mix_is_checked_by_ear_and_by_meter(tmp_path, monkeypatch):
    import whynot.agency.trend_video as tv

    monkeypatch.setattr(tv, "to_wav16k", lambda path: b"wav")
    b = check_selling(selling_brief())
    said = " ".join(x.text for x in b.lines if x.language == "en")
    good = final_check(Ears(said), tmp_path / "v.mp4", b, "English", {"lufs": -14.1, "true_peak": -1.6})
    assert good["flags"] == [] and good["word_error_rate"] < 0.1  # emotion tags are not heard
    looped = final_check(Ears(said + " " + said), tmp_path / "v.mp4", b, "English", {"lufs": -21.6, "true_peak": -0.2})
    assert any("off the captions" in f for f in looped["flags"])
    assert any("LUFS" in f for f in looped["flags"]) and any("true peak" in f for f in looped["flags"])
    broken = final_check(Ears(RuntimeError("down")), tmp_path / "v.mp4", b, "English", None)
    assert broken["flags"] == ["final transcription failed: RuntimeError"]


def test_the_narrator_says_one_thing_in_its_own_words():
    d = selling_brief()
    # 25 words: a list, not one thing
    d["lines"][3]["text"] = ("linguaapp has a southern voice and a northern voice and short lessons for travel and "
                             "food and family and work and school, free to download")
    with pytest.raises(Invalid, match="ONE feature"):
        check_selling(d)
    claim = CTX.strategy.claims[0].text
    d["lines"][3]["text"] = claim
    if len(claim.split()) <= 22:
        with pytest.raises(Invalid, match="word for word"):
            check_selling(d)


def test_the_same_screen_is_never_shown_twice_in_a_row():
    d = selling_brief()
    d["shots"][6]["screen"] = d["shots"][5]["screen"]  # two demo shots of the same screen back to back
    with pytest.raises(Invalid, match="same screen"):
        check_selling(d)


def test_a_run_of_app_shots_keeps_one_phone():
    from whynot.create.trend_render import build_props

    b = check_selling(selling_brief())
    images = {i: f"s{i}.png" for i, s in enumerate(b.shots) if s.visual in ("photo", "screen")}
    props = build_props(b, palette=["#FFFFFF", "#111111", "#00EB6E", "#EEEEEE"], app_name="X", images=images,
                        icon=None, rating=None, rating_count=None, audio=None, sfx={})
    screens = [i for i, s in enumerate(b.shots) if s.visual == "screen"]
    assert screens == [4, 5, 6]
    assert "continues" not in props["shots"][4]  # the phone enters here...
    assert props["shots"][5]["continues"] and props["shots"][6]["continues"]  # ...and stays for the next screens

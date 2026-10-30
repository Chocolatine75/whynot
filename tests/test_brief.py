"""Video briefs: the storyboard is checked like any ad copy, and can never fake the product."""

import json

import pytest

from fakes import ScriptedChat
from strategy_fixture import ADS, APP, COUNTRIES, strategy_json
from whynot.agents.archetypes import Archetype, Pick
from whynot.agents.ask import AgentError, Invalid
from whynot.agents.brief import END_CARD_SECONDS, VideoBrief, describe_screens, make_validator, write_brief
from whynot.agents.director import Context
from whynot.agents.strategist import Sources
from whynot.agents.strategist import make_validator as strategy_validator

STRATEGY = strategy_validator(Sources.build(APP, ADS), COUNTRIES)(strategy_json())
CTX = Context(STRATEGY, APP.name, APP.description, ("Rival Lingo",), ("#F5FAFF", "#0B1D33", "#1E6FD9"), "s.png")
PICK = Pick("transformation:app_screen", "heritage_learner", "southern_accent", 8, 7, 9, "Shows the app.")
ARCH = Archetype("transformation:app_screen", "transformation", "app_screen", ["1", "2"], ["A", "B"], {}, {}, 0.8,
                 [{"ad_id": "1", "hook": "Talk to grandma", "promise": "Real talk", "visual": "phone",
                   "overlays": ["Speak now"], "days": 120}])
GOOD = {"id": "grandma_call", "hook": "Your grandma speaks Southern",
        "scenes": [{"kind": "scene", "prompt": "A sunny family kitchen in Saigon, warm light", "overlay":
                    "Family dinner, every Sunday", "motion": "zoom_in", "seconds": 3},
                   {"kind": "screen", "screen": 2, "overlay": "Pick the Southern voice", "motion": "scroll",
                    "seconds": 4},
                   {"kind": "text", "text": "Understand her, finally", "overlay": "Listen first, then speak",
                    "motion": "pop", "seconds": 3}],
        "cta": "Start free", "narration": "She speaks Southern. Your app should too.", "music": "inspiring"}


def check(data, n=3):
    return make_validator(CTX, PICK, n)(data)


def test_a_good_brief_is_typed_and_timed():
    b = check(GOOD)
    assert isinstance(b, VideoBrief) and b.seconds == 10 + END_CARD_SECONDS
    assert b.scenes[1].screen == 2 and b.persona == "heritage_learner"
    assert VideoBrief.from_json(json.loads(json.dumps(b.to_json()))) == b


def scene(i, **patch):
    data = json.loads(json.dumps(GOOD))
    data["scenes"][i].update(patch)
    return data


@pytest.mark.parametrize("data, error", [
    (scene(0, prompt="A woman holding a phone with the app open"), "phone"),
    (scene(0, prompt="Kitchen with a big logo on the wall"), "logo"),
    (scene(1, screen=7), "screenshot number"),
    (scene(1, kind="text", text="Listen"), "real app"),
    (scene(2, seconds=9), "seconds"),
    (scene(2, motion="spin"), "motion"),
    ({**GOOD, "hook": "Learn Vietnamese in 10 minutes a day"}, "number"),
    ({**GOOD, "hook": "Better than Rival Lingo"}, "competitor"),
    ({**GOOD, "cta": "Download the app right now please"}, "cta"),
    ({**GOOD, "music": "techno"}, "music"),
    ({**GOOD, "hook": "Speak like home 🎉"}, "emoji"),
    ({**GOOD, "scenes": GOOD["scenes"][:2]}, "3 to 4"),
])
def test_bad_briefs_are_refused_with_the_reason(data, error):
    with pytest.raises(Invalid, match=error):
        check(data)


def test_total_length_must_fit_a_reel():
    long = json.loads(json.dumps(GOOD))
    long["scenes"].append({"kind": "screen", "screen": 1, "overlay": "Start today", "motion": "still",
                           "seconds": 4.5})
    for s in long["scenes"]:
        s["seconds"] = 4.5
    with pytest.raises(Invalid, match="lasts"):
        check(long)


def test_write_brief_repairs_then_succeeds():
    model = ScriptedChat([json.dumps(scene(0, prompt="A phone on a table")), json.dumps(GOOD)])
    answer = write_brief(model, CTX, PICK, ARCH, ["home", "voice picker", "chat"])
    assert answer.value.id == "grandma_call" and answer.attempts == 2
    prompt = model.calls[0]["messages"][0]["content"]
    assert "Talk to grandma" in prompt and "2. voice picker" in prompt


def test_describe_screens_needs_one_description_per_screenshot():
    model = ScriptedChat([json.dumps({"screens": ["home"]}), json.dumps({"screens": ["home", "chat"]})])
    answer = describe_screens(model, "App", ["data:image/png;base64,AA", "data:image/png;base64,BB"])
    assert answer.value == ["home", "chat"]
    with pytest.raises(AgentError):
        describe_screens(ScriptedChat(lambda m, mod: "{}"), "App", ["data:x"])

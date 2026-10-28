"""Creative director: invented facts, competitor names, emoji, policy breaches and duplicates are rejected;
valid templates compose into ads that pass every guard."""

import copy
import json

import pytest
from PIL import Image, ImageDraw

from director_fixture import director_json
from fakes import ScriptedChat
from strategy_fixture import ADS, APP, COUNTRIES, strategy_json
from whynot.agents.ask import AgentError, Invalid
from whynot.agents.director import Context, build_prompt, make_validator, write_templates
from whynot.agents.strategist import Sources
from whynot.agents.strategist import make_validator as strategy_validator
from whynot.create.composer import compose
from whynot.create.guards import publishable, run_guards

STRATEGY = strategy_validator(Sources.build(APP, ADS), COUNTRIES)(strategy_json())
CTX = Context(STRATEGY, APP.name, APP.description, ("Rival Lingo", "Other App"),
              ("#F5FAFF", "#0B1D33", "#1E6FD9"), "screen_1.png")
ANGLES = [a.id for a in STRATEGY.angles]
VALIDATE = make_validator(CTX, ANGLES)


def answer(**changes):
    d = director_json()
    t = d["templates"][0]
    for path, value in changes.items():
        keys = path.split("__")
        target = t
        for k in keys[:-1]:
            target = target[k]
        target[keys[-1]] = value
    return d


def screenshot():
    img = Image.new("RGBA", (1290, 2796), (250, 250, 250, 255))
    d = ImageDraw.Draw(img)
    for y in range(200, 2600, 300):
        d.rounded_rectangle((100, y, 1190, y + 200), radius=40, fill=(30, 111, 217, 255))
    return img


def test_valid_answer_becomes_templates_tied_to_the_strategy():
    templates = VALIDATE(director_json())
    assert [t.id for t in templates] == [f"{a}_v1" for a in ANGLES]
    t = templates[0]
    assert t.persona == "heritage_learner" and t.evidence["refs"] == ["review:102"]
    assert t.genes["cta"] == ["INSTALL_MOBILE_APP", "LEARN_MORE"]
    assert t.text("cta", "INSTALL_MOBILE_APP") == "Start free"
    assert t.text("proof", "none") == "" and t.space_size() == 2 * 2 * 2 * 2 * 1 * 2


def test_every_variant_of_every_template_composes_and_passes_all_guards():
    asset = screenshot()
    for t in VALIDATE(director_json()):
        for genome in t.sample(8, seed=1):
            comp = compose(t, genome, asset)
            results = run_guards(t, comp, asset)
            assert publishable(results), (t.id, genome, {k: r.detail for k, r in results.items() if not r.passed})


@pytest.mark.parametrize("changes, msg", [
    ({"hooks__family": "Join 50,000 learners"}, "not in any verified claim"),
    ({"bodys__short": "Rated 4.9 by teachers"}, "not in any verified claim"),
    ({"hooks__family": "Better than Rival Lingo"}, "names a competitor"),
    ({"hooks__family": "Talk with family 🇻🇳"}, "cannot draw"),
    ({"hooks__family": "Are you lonely abroad?"}, "personal attribute"),
    ({"bodys__story": "Fluency guaranteed."}, "absolute claim"),
    ({"hooks__family": "x" * 71}, "max 70"),
    ({"titles__main": "y" * 41}, "max 40"),
    ({"ctas": {"BUY_NOW": "Buy"}}, "must be one of"),
    ({"angle": "ghost"}, "is not one of"),
    ({"claims_used": ["award"]}, "claims_used"),
    ({"first_shots": ["video"]}, "first_shots"),
    ({"hooks": {"only": "One hook"}}, "2 to 3"),
])
def test_bad_copy_is_rejected_with_the_reason(changes, msg):
    with pytest.raises(Invalid, match=msg):
        VALIDATE(answer(**changes))


def test_numbers_from_verified_claims_are_allowed():
    ctx = Context(STRATEGY, APP.name, APP.description + " 5 minutes a day.", (), CTX.palette, "s.png")
    ok = answer(hooks__family="5 minutes a day")
    assert make_validator(ctx, ANGLES)(ok)[0].text("hook", "family") == "5 minutes a day"


def test_reworded_concepts_and_missing_angles_are_rejected():
    d = director_json()
    d["templates"][1]["concept"] = d["templates"][0]["concept"] + " Really."
    with pytest.raises(Invalid, match="same concept"):
        VALIDATE(d)
    d = director_json(angles=("southern_accent",))
    with pytest.raises(Invalid, match="no template for angles"):
        VALIDATE(d)
    d = director_json()
    d["templates"].append(copy.deepcopy(d["templates"][0]))
    with pytest.raises(Invalid, match="second template"):
        VALIDATE(d)


def test_prompt_contains_only_verified_claims_and_rules():
    p = build_prompt(CTX, ANGLES)
    assert "- accents: Choose a Northern or Southern accent" in p and "Never name competitors" in p
    assert "southern_accent (persona heritage_learner, objection none, not used by competitors)" in p


def test_write_templates_repairs_then_succeeds():
    bad = answer(hooks__family="Join 10,000 happy learners")
    chat = ScriptedChat([json.dumps(bad), json.dumps(director_json())])
    out = write_templates(chat, CTX, ANGLES)
    assert out.attempts == 2 and len(out.value) == 4
    assert "'10,000'" in chat.calls[1]["messages"][-1]["content"]


def test_write_templates_never_returns_unverified_copy():
    chat = ScriptedChat([json.dumps(answer(hooks__family="Trusted by 1 million"))] * 3)
    with pytest.raises(AgentError):
        write_templates(chat, CTX, ANGLES)

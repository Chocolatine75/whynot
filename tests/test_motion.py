"""Motion ads: a static ad brought to life for Reels and Stories, from its own copy, screens and facts ($0)."""

import json

from PIL import Image

from whynot.create.motion import build_props, key_words, make_motion
from whynot.create.templates import Template

CONTENT = {"review": {"text": "The voices sound like my family.", "rating": 5, "review": "9"},
           "benefits": ["Five-minute lessons", "Free to start"], "objection": {"text": "No time", "objection": "o"}}


def template(content=CONTENT) -> Template:
    return Template.from_dict({
        "id": "demo_en_v1", "concept": "c", "persona": "p", "objection": "o",
        "fixed": {"brand": {"name": "Demo", "palette": ["#FFF8EE", "#1B1B1F", "#E4572E", "#FFE3D3"]},
                  "product": {"asset": "ui-1.png", "second": "ui-2.png"}, "content": content, "language": "en"},
        "genes": {"format": ["portrait"], "layout": ["review_card", "two_screens", "split"],
                  "style": ["light", "brand"], "hook": ["h"], "proof": ["p"], "cta": ["c"]},
        "copy": {"hook": {"h": "No time to learn Vietnamese?"}, "proof": {"p": "Rated 4.8"},
                 "cta": {"c": "Start free"}}})


def genome(**kw):
    return {"format": "portrait", "layout": "review_card", "style": "light", "hook": "h", "proof": "p", "cta": "c",
            **kw}


def test_props_carry_the_ads_own_copy_screens_and_facts():
    p = build_props(template(), genome(), screen="screen.png", icon="icon.png")
    assert (p["headline"], p["cta"], p["proof"], p["layout"]) == ("No time to learn Vietnamese?", "Start free",
                                                                   "Rated 4.8", "review_card")
    assert p["content"]["review"] == {"text": "The voices sound like my family.", "rating": 5}  # the quote as is
    assert p["durationInFrames"] == 210 and p["screen"] == "screen.png" and "second" not in p
    assert p["keyWords"] == key_words("No time to learn Vietnamese?") == 1


def test_on_the_brand_colour_the_accent_is_never_the_background():
    p = build_props(template(), genome(style="brand"), screen="s.png")
    assert p["base"] == "#E4572E" and p["look"]["accent"] != p["base"] and p["ink"] != p["base"]


def test_every_planned_ad_gets_its_motion_version_listed(tmp_path):
    run = tmp_path / "run"
    (run / "templates").mkdir(parents=True)
    (run / "assets").mkdir()
    (run / "ads").mkdir()
    t = template()
    import yaml
    (run / "templates" / f"{t.id}.yaml").write_text(yaml.safe_dump(t.to_dict()))
    for name in ("ui-1.png", "ui-2.png", "icon.png"):
        Image.new("RGB", (40, 80)).save(run / "assets" / name)
    rows = [{"variant_id": "v1", "template_id": t.id, "genome": genome()},
            {"variant_id": "v2", "template_id": t.id, "genome": genome(layout="two_screens")}]
    (run / "variants.json").write_text(json.dumps(rows))
    (run / "plan.json").write_text(json.dumps({"ad_sets": [{"ads": [{"variant_id": "v1"}, {"variant_id": "v2"}]}]}))
    calls = []

    def render(comp, props, files, out):
        calls.append((comp, props, set(files), out.name))
        return {"seconds": 7.0, "frames": 210}

    done = make_motion(run, render=render, say=lambda m: None)
    assert [d["video"] for d in done] == ["ads/v1.motion.mp4", "ads/v2.motion.mp4"]
    assert calls[0][0] == "StaticMotion" and calls[0][2] == {"screen.png", "icon.png"}
    assert calls[1][2] == {"screen.png", "second.png", "icon.png"} and calls[1][1]["second"] == "second.png"
    assert json.loads((run / "motion.json").read_text())["usd"] == 0.0
    assert len(make_motion(run, render=render, limit=1, say=lambda m: None)) == 1

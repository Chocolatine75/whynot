"""E5-2: ten layouts × five styles × three formats, each guarded; verified facts only; text never overflows."""

import io

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from PIL import Image, ImageDraw

from strategy_fixture import APP, strategy_json
from whynot.agents.strategist import Strategy
from whynot.create.composer import (
    DECORS,
    FORMATS,
    LAYOUTS,
    NEEDS,
    SAFE,
    STYLES,
    ComposeError,
    compose,
    hex_to_rgb,
    layouts_for,
    styles_for,
)
from whynot.create.content import MAX_QUOTE, verified_content
from whynot.create.guards import publishable, run_guards
from whynot.create.templates import Template

CONTENT = {"review": {"text": "I finally understand my mother-in-law when she talks fast.", "rating": 5},
           "number": {"value": "4.8", "label": "Rated 4.8 on the App Store"},
           "benefits": ["Real voices from the North and the South", "Five-minute lessons", "Free to start"],
           "objection": {"text": "I never have time to study"}}
PALETTE = ["#FFF8EE", "#1B1B1F", "#E4572E", "#FFE3D3"]
NEW_FORMATS = ["square", "portrait", "story"]


def phone(colour=(30, 120, 200, 255)) -> Image.Image:
    img = Image.new("RGBA", (400, 868), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, 399, 867), radius=60, fill=colour)
    for i in range(0, 868, 40):
        d.rectangle((40, i, 360, i + 15), fill=(250, 250, 250, 255))
    return img


def other_phone() -> Image.Image:
    return phone((40, 160, 90, 255))


def template(hook="No time to learn Vietnamese?", proof="Rated 4.8 on the App Store", cta="Start free",
             content=CONTENT, palette=PALETTE, layouts=LAYOUTS, styles=STYLES, decors=("none",)) -> Template:
    return Template.from_dict({
        "id": "demo_v1", "concept": "Five minutes a day", "persona": "p1", "objection": "o1",
        "fixed": {"brand": {"name": "Demo", "palette": palette}, "product": {"asset": "x.png"}, "content": content},
        "genes": {"format": NEW_FORMATS, "layout": list(layouts), "style": list(styles), "decor": list(decors),
                  "hook": ["h"],
                  "proof": ["p"], "cta": ["c"]},
        "copy": {"hook": {"h": hook}, "proof": {"p": proof}, "cta": {"c": cta}}})


def png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def test_every_layout_style_and_format_composes_and_passes_every_guard():
    t, asset, second = template(), phone(), other_phone()
    assert t.space_size() == 165
    for g in t.genomes():
        comp = compose(t, g, asset, second)
        assert comp.image.size == FORMATS[g["format"]]
        results = run_guards(t, comp, asset)  # pixels untouched, palette, legible, not over the screen, policy
        assert publishable(results), (g, {k: r.detail for k, r in results.items() if not r.passed})


def test_the_same_inputs_always_give_the_same_picture():
    t, asset = template(), phone()
    for layout in LAYOUTS:
        g = {"format": "portrait", "layout": layout, "style": "shape", "decor": "none", "hook": "h", "proof": "p",
             "cta": "c"}
        assert png(compose(t, g, asset, other_phone()).image) == png(compose(t, g, asset, other_phone()).image)


def test_every_layout_and_style_looks_different():
    t, asset = template(), phone()
    base = {"format": "square", "style": "light", "hook": "h", "proof": "p", "cta": "c"}
    assert len({png(compose(t, {**base, "layout": x, "decor": "none"}, asset, other_phone()).image)
                for x in LAYOUTS}) == len(LAYOUTS)
    base = {"format": "square", "layout": "split", "hook": "h", "proof": "p", "cta": "c"}
    assert len({png(compose(t, {**base, "style": s, "decor": "none"}, asset).image) for s in STYLES}) == len(STYLES)


def test_stories_keep_text_out_of_the_zones_meta_covers():
    t, asset = template(), phone()
    top, bottom = SAFE["story"]
    for layout in LAYOUTS:
        comp = compose(t, {"format": "story", "layout": layout, "style": "light", "decor": "none", "hook": "h",
                           "proof": "p", "cta": "c"}, asset, other_phone())
        for x in comp.texts:
            assert x.box[1] >= top and x.box[3] <= 1920 - bottom, (layout, x.role, x.box)


def test_a_layout_needs_its_verified_fact():
    assert layouts_for({}) == [x for x in LAYOUTS if x not in NEEDS and x != "two_screens"]
    assert set(layouts_for(CONTENT, second_screen=True)) == set(LAYOUTS)
    t = template(content={})
    with pytest.raises(ComposeError, match="needs a verified review"):
        compose(t, {"format": "square", "layout": "review_card", "style": "light", "decor": "none", "hook": "h",
                    "proof": "p", "cta": "c"}, phone())


def test_styles_without_readable_text_are_not_offered():
    pale = [hex_to_rgb(c) for c in ("#FFFFFF", "#DDDDDD", "#EEEEEE")]
    assert "dark" not in styles_for(pale) and styles_for(pale)  # never empty
    assert set(styles_for([hex_to_rgb(c) for c in PALETTE])) == set(STYLES)


def test_old_templates_still_draw_as_before():
    t = Template.from_dict({"id": "old_v1", "concept": "c", "persona": "p", "objection": "o",
                            "fixed": {"brand": {"name": "B", "palette": PALETTE[:3]}, "product": {"asset": "x"}},
                            "genes": {"format": ["static_1080"], "hook": ["h"], "first_shot": ["app_screen",
                                                                                               "result_card"],
                                      "cta": ["c"]},
                            "copy": {"hook": {"h": "Hello there"}, "cta": {"c": "Start"}}})
    a, b = (compose(t, {"format": "static_1080", "hook": "h", "first_shot": s, "cta": "c"}, phone())
            for s in ("app_screen", "result_card"))
    assert a.image.size == (1080, 1080) and png(a.image) != png(b.image)
    assert a.product.box[0] >= 600  # split: the screen on the right
    assert b.product.box[3] == 1080  # rising: the screen cut by the bottom edge


LANGS = st.sampled_from([
    "Learn", "Vietnamese", "five", "minutes", "Sprachkenntnisse", "Donaudampfschifffahrt", "Grüße", "überall",
    "日本語", "を", "学ぶ", "毎日", "five-minute", "lessons", "?", "talk", "with", "family", "Ça", "marche"])


@settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(words=st.lists(LANGS, min_size=1, max_size=40), layout=st.sampled_from(LAYOUTS),
       fmt=st.sampled_from(NEW_FORMATS))
def test_property_text_of_any_length_fits_or_is_refused_never_drawn_wrong(words, layout, fmt):
    """German compounds, Japanese without spaces, a single word or a paragraph: the ad is either refused with a
    clear reason, or every text sits inside the canvas and off the screen."""
    t = template(hook=" ".join(words))
    g = {"format": fmt, "layout": layout, "style": "light", "decor": "none", "hook": "h", "proof": "p", "cta": "c"}
    try:
        comp = compose(t, g, phone(), other_phone())
    except ComposeError as exc:
        assert "does not fit" in str(exc) or "cannot draw" in str(exc)
        return
    w, h = comp.image.size
    for x in comp.texts:
        assert x.box[0] >= 0 and x.box[1] >= 0 and x.box[2] <= w and x.box[3] <= h
    assert run_guards(t, comp, phone())["text_legible"].passed, comp.texts


# --- the verified facts, taken by code --------------------------------------------------------------------------

def test_facts_come_from_the_store_reviews_and_the_strategy_word_for_word():
    s = Strategy.from_json(strategy_json())
    c = verified_content(s, APP, "southern_accent", "en")
    quote = c["review"]["text"]
    review = next(r for r in APP.reviews if r.id == c["review"]["review"])
    assert quote in review.text and review.rating >= 4 and len(quote) <= MAX_QUOTE
    assert review.id == "102"  # the review the angle itself cites comes first
    assert all(b in {x.text for x in s.claims} for b in c.get("benefits", []))
    if "number" in c:
        assert c["number"]["label"] in {x.text for x in s.claims} and c["number"]["value"] in c["number"]["label"]


def test_the_objection_layout_uses_the_strategys_own_answer():
    s = Strategy.from_json(strategy_json())
    c = verified_content(s, APP, "listen_first", "en")
    o = s.objection("speech_recognition")
    assert c["objection"] == {"text": o.text, "objection": o.id}  # never the copywriter's instruction (answer)


def test_a_long_objection_keeps_its_first_clause_whole():
    from dataclasses import replace

    from whynot.create.content import objection
    s = Strategy.from_json(strategy_json())
    long = "Vietnamese tones scare me, the audio sounds too fast, and I do not want whole sentences thrown at me"
    s = replace(s, objections=[replace(o, text=long) for o in s.objections])
    assert objection(s, s.objections[0].id)["text"] == "Vietnamese tones scare me"


def test_no_fact_for_ads_in_another_language():
    assert verified_content(Strategy.from_json(strategy_json()), APP, "southern_accent", "fr") == {}


def test_a_quote_is_never_cut_and_low_ratings_are_never_quoted():
    from dataclasses import replace

    from whynot.create.content import review_quote
    from whynot.ingest.appstore import Review
    long = "This sentence is far too long to be shown whole on an ad, " * 4
    app = replace(APP, reviews=[Review("1", 5, "t", long.strip(), "1", "2026-10-01"),
                                Review("2", 2, "t", "Terrible app but the voices are nice to hear.", "1",
                                       "2026-10-01")])
    assert review_quote(app, ["review:1", "review:2"]) is None


# --- decors and two screens ------------------------------------------------------------------------------------

def test_every_decor_in_every_layout_and_format_passes_every_guard_and_never_touches_text():
    t = template(decors=DECORS, styles=("light",))
    asset, second = phone(), other_phone()
    for g in t.genomes():
        comp = compose(t, g, asset, second)
        results = run_guards(t, comp, asset)
        assert publishable(results), (g, {k: r.detail for k, r in results.items() if not r.passed})
        if g["decor"] != "none":  # the decor colour never sits under a text box
            plain = compose(t, {**g, "decor": "none"}, asset, second).image
            for x in comp.texts:
                inner = (x.box[0] + 2, x.box[1] + 2, x.box[2] - 2, x.box[3] - 2)
                if x.bg == comp.fills[0]:  # text on the background (not on a card)
                    assert comp.image.crop(inner).tobytes() == plain.crop(inner).tobytes(), (g, x.role)


def test_decors_make_the_same_ad_look_different():
    t = template(decors=DECORS)
    g = {"format": "portrait", "layout": "rising", "style": "light", "hook": "h", "proof": "p", "cta": "c"}
    assert len({png(compose(t, {**g, "decor": d}, phone()).image) for d in DECORS}) == len(DECORS)


def test_two_screens_shows_two_real_screens_and_checks_both():
    t, asset, second = template(decors=DECORS), phone(), other_phone()
    g = {"format": "portrait", "layout": "two_screens", "style": "light", "decor": "panel", "hook": "h",
         "proof": "p", "cta": "c"}
    comp = compose(t, g, asset, second)
    assert len(comp.extra_products) == 1 and publishable(run_guards(t, comp, asset))
    box = comp.extra_products[0][0].box
    ImageDraw.Draw(comp.image).rectangle((box[0] + 60, box[1] + 60, box[0] + 64, box[1] + 64), fill=(255, 0, 0))
    r = run_guards(t, comp, asset)["product_pixels_unchanged"]
    assert r.passed is False and r.detail.startswith("second screen")
    with pytest.raises(ComposeError, match="second real screen"):
        compose(t, g, asset)

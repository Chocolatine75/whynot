"""Ad-policy rules and brand palette."""

import colorsys

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from PIL import Image, ImageDraw

from whynot.assets.brand import accent_from_icon, palette_from_icon
from whynot.create.composer import contrast_ratio, hex_to_rgb
from whynot.create.policy import check_ad, check_text, errors


@pytest.mark.parametrize("text, code", [
    ("Are you depressed? Try this app", "personal_attributes"),
    ("You're lonely and want to talk?", "personal_attributes"),
    ("Pay off your debt faster", "personal_attributes"),
    ("Meet other single women nearby", "personal_attributes"),
    ("Fluency guaranteed in 30 days", "absolute_claim"),
    ("The #1 app to learn Vietnamese", "absolute_claim"),
    ("100% results", "absolute_claim"),
    ("Tag a friend who needs this", "engagement_bait"),
    ("Like this if you love Vietnam", "engagement_bait"),
    ("LEARN VIETNAMESE TODAY", "shouting"),
    ("Start now!!!", "shouting"),
])
def test_policy_errors(text, code):
    found = errors(check_text(text, "headline"))
    assert found and found[0].code == code, check_text(text, "headline")


@pytest.mark.parametrize("text", [
    "Learn Vietnamese the way it sounds",
    "Five minutes a day on your commute",
    "Talk with your grandparents in their accent",
    "Free to start. Choose a Northern or Southern accent.",
    "Ready for your trip to Hanoi?",
    "Speak with your family",
    "IELTS practice in 10 minutes",
])
def test_ordinary_ad_copy_passes(text):
    assert errors(check_text(text, "body")) == []


def test_superlatives_are_warnings_and_fields_are_named():
    issues = check_ad({"headline": "The easiest way to learn", "body": "", "cta": "Tag a friend below"})
    assert [(i.field, i.severity) for i in issues] == [("headline", "warning"), ("cta", "error")]


def icon(colour, bg=(255, 255, 255)):
    img = Image.new("RGB", (512, 512), bg)
    ImageDraw.Draw(img).rounded_rectangle((40, 40, 472, 472), radius=90, fill=colour)
    return img


@pytest.mark.parametrize("colour", [(220, 38, 38), (22, 163, 74), (37, 99, 235), (234, 179, 8), (147, 51, 234)])
def test_palette_from_icon_has_readable_text(colour):
    bg, fg, accent, surface = (hex_to_rgb(c) for c in palette_from_icon(icon(colour)))
    assert contrast_ratio(fg, surface) >= 12
    assert max(abs(a - b) for a, b in zip(accent, colour, strict=True)) <= 60  # the brand colour, maybe darkened
    assert colorsys.rgb_to_hls(*(x / 255 for x in accent))[0] == pytest.approx(
        colorsys.rgb_to_hls(*(x / 255 for x in colour))[0], abs=0.03)  # same hue
    assert contrast_ratio(fg, bg) >= 12  # body text far above WCAG AA
    assert len({bg, fg, accent, surface}) == 4


def test_greyscale_icon_falls_back_to_a_neutral_accent():
    assert accent_from_icon(icon((128, 128, 128))) == (37, 99, 235)


@settings(max_examples=300)
@given(st.tuples(st.integers(0, 255), st.integers(0, 255), st.integers(0, 255)))
def test_any_icon_colour_gives_a_legible_button(colour):
    """Bug: a red icon gave button text at 4.43:1, so the legibility guard refused every ad."""
    bg, fg, accent, surface = (hex_to_rgb(c) for c in palette_from_icon(icon(colour)))
    assert max(contrast_ratio(accent, bg), contrast_ratio(accent, fg)) >= 4.5
    assert contrast_ratio(fg, bg) >= 12 and contrast_ratio(fg, surface) >= 12
    assert len({bg, fg, accent, surface}) == 4

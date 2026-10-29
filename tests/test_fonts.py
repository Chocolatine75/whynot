"""Ads in every supported language keep their accents (bug: French copy lost them on the Flighty run)."""

import pytest
from PIL import Image

from whynot.create import fonts
from whynot.create.composer import ComposeError, compose
from whynot.create.guards import publishable, run_guards
from whynot.create.templates import Template

COPY = {
    "fr": ("Retardé ? Voyez pourquoi, en direct.", "« C’est mon vol ! »", "Commencer"),
    "de": ("Verspätet? Sehen Sie den Grund – live.", "Größe zählt nicht", "Jetzt starten"),
    "es": ("¿Retrasado? Mira por qué, al momento.", "Niño, año, señal…", "Empezar"),
    "pl": ("Opóźniony? Zobacz dlaczego – na żywo.", "Łatwo i szybko", "Zacznij"),
}


def template(lang):
    hook, proof, cta = COPY[lang]
    return Template.from_dict({
        "id": f"t_{lang}", "concept": "c", "persona": "p", "objection": "o",
        "fixed": {"brand": {"name": "B", "palette": ["#F7F9FC", "#111827", "#1D4ED8"]}, "language": lang},
        "genes": {"format": ["static_1080"], "hook": ["h"], "proof": ["p"], "cta": ["INSTALL_MOBILE_APP"]},
        "copy": {"hook": {"h": hook}, "proof": {"p": proof}, "cta": {"INSTALL_MOBILE_APP": cta}},
    })


def screen():
    return Image.new("RGBA", (600, 1200), (30, 111, 217, 255))


def test_a_font_covering_every_language_is_available():
    assert fonts.default_font_path() is not None, "install a Latin font (DejaVu/Arial) or set WHYNOT_FONT"
    assert fonts.covers(fonts.load(40))


@pytest.mark.parametrize("lang", sorted(COPY))
def test_accented_ads_compose_and_pass_every_guard(lang):
    t = template(lang)
    comp = compose(t, next(t.genomes()), screen())
    assert comp.texts[0].text == COPY[lang][0]  # drawn exactly as written, accents included
    results = run_guards(t, comp, screen())
    assert publishable(results), {k: r.detail for k, r in results.items() if not r.passed}


def test_without_a_suitable_font_accents_are_refused_not_mangled(monkeypatch):
    monkeypatch.setattr(fonts, "_candidates", lambda bold=False: ["/nope/missing.ttf"])
    fonts.default_font_path.cache_clear()
    try:
        with pytest.raises(ComposeError, match="cannot draw"):
            t = template("fr")
            compose(t, next(t.genomes()), screen())
    finally:
        fonts.default_font_path.cache_clear()


def test_env_font_wins_when_it_covers_the_languages(monkeypatch):
    path = fonts.default_font_path()
    monkeypatch.setenv("WHYNOT_FONT", path)
    fonts.default_font_path.cache_clear()
    try:
        assert fonts._candidates()[0] == path and fonts.default_font_path() == path
    finally:
        fonts.default_font_path.cache_clear()


def test_bold_font_covers_every_language_too():
    assert fonts.covers(fonts.load(40, bold=True))

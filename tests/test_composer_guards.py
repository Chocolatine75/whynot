import io
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from whynot.create.composer import ComposeError, compose, contrast_ratio
from whynot.create.guards import MANDATORY, GuardResult, publishable, run_guards
from whynot.create.templates import Template, load_dir

EXAMPLES = Path(__file__).resolve().parents[1] / "templates" / "examples"


def phone_asset() -> Image.Image:
    """A fake app screen: opaque rounded phone with a pattern, transparent corners."""
    img = Image.new("RGBA", (400, 800), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, 399, 799), radius=60, fill=(30, 120, 200, 255))
    for i in range(0, 800, 40):
        d.rectangle((40, i, 360, i + 15), fill=(250, 250, 250, 255))
    return img


@pytest.fixture(scope="module")
def template():
    return load_dir(EXAMPLES)[0]


def png(img):
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def test_every_genome_composes_and_passes_guards(template):
    asset = phone_asset()
    for genome in template.genomes():
        comp = compose(template, genome, asset)
        assert comp.image.size == (1080, 1080)
        results = run_guards(template, comp, asset)
        failed = {k: r.detail for k, r in results.items() if r.passed is False}
        assert not failed, (genome, failed)
        assert results["policy_safe"].passed is True
        assert publishable(results)


def test_composition_is_deterministic(template):
    genome = next(template.genomes())
    assert png(compose(template, genome, phone_asset()).image) == png(compose(template, genome, phone_asset()).image)


def test_genes_change_the_ad(template):
    genomes = list(template.genomes())
    images = {png(compose(template, g, phone_asset()).image) for g in genomes[:6]}
    assert len(images) == 6


def test_pixel_guard_catches_painted_product(template):
    asset = phone_asset()
    comp = compose(template, next(template.genomes()), asset)
    left, top, *_ = comp.product.box
    ImageDraw.Draw(comp.image).rectangle((left + 100, top + 100, left + 110, top + 110), fill=(255, 0, 0))
    r = run_guards(template, comp, asset)["product_pixels_unchanged"]
    assert r.passed is False and "121 of" in r.detail


def test_pixel_guard_catches_a_different_asset(template):
    comp = compose(template, next(template.genomes()), phone_asset())
    other = phone_asset()
    ImageDraw.Draw(other).rectangle((100, 100, 300, 300), fill=(0, 200, 0, 255))
    assert run_guards(template, comp, other)["product_pixels_unchanged"].passed is False


def test_off_palette_and_low_contrast_are_caught(template):
    asset = phone_asset()
    data = template.to_dict()
    data["fixed"] = {**data["fixed"], "brand": {"name": "B", "palette": ["#FFFFFF", "#DDDDDD", "#EEEEEE"]}}
    pale = Template.from_dict(data)
    comp = compose(pale, next(pale.genomes()), asset)
    results = run_guards(pale, comp, asset)
    assert results["text_legible"].passed is False and "contrast" in results["text_legible"].detail
    comp.fills.append((1, 2, 3))
    assert run_guards(pale, comp, asset)["brand_palette"].passed is False


def test_mandatory_guards_run_even_if_the_template_lists_none(template):
    data = template.to_dict()
    data["guards"] = []
    t = Template.from_dict(data)
    results = run_guards(t, compose(t, next(t.genomes()), phone_asset()), phone_asset())
    assert set(results) == set(MANDATORY)
    assert publishable(results)


def test_publishable_needs_every_mandatory_guard_passed():
    ok = {g: GuardResult(g, True) for g in MANDATORY}
    assert publishable(ok)
    assert not publishable({k: v for k, v in ok.items() if k != "text_legible"})  # one missing
    assert not publishable({**ok, "policy_safe": GuardResult("policy_safe", None)})  # not checked
    assert not publishable({**ok, "brand_palette": GuardResult("brand_palette", False)})


def test_unsupported_format_and_overlong_text(template):
    data = template.to_dict()
    data["genes"] = {**data["genes"], "format": ["reel_6s"]}
    with pytest.raises(ComposeError, match="not supported"):
        t = Template.from_dict(data)
        compose(t, next(t.genomes()), phone_asset())
    data = template.to_dict()
    data["copy"] = {**data["copy"], "hook": {"question": "word " * 200}}
    t = Template.from_dict(data)
    g = {**next(t.genomes()), "hook": "question"}
    with pytest.raises(ComposeError, match="does not fit"):
        compose(t, g, phone_asset())


def test_contrast_ratio_extremes():
    assert contrast_ratio((0, 0, 0), (255, 255, 255)) == pytest.approx(21.0)
    assert contrast_ratio((10, 10, 10), (10, 10, 10)) == pytest.approx(1.0)


def test_missing_glyphs_are_refused(template):
    data = template.to_dict()
    data["copy"] = {**data["copy"], "proof": {**data["copy"]["proof"], "rating_badge": "★ 4.8"}}
    t = Template.from_dict(data)
    g = {**next(t.genomes()), "proof": "rating_badge"}
    with pytest.raises(ComposeError, match="cannot draw"):
        compose(t, g, phone_asset())


# --- each guard failure path ---------------------------------------------------------

def test_pixel_guard_catches_a_one_level_change_in_one_channel(template):
    """Bug: diffs were converted to grey first, so (1, 0, 0) rounded to 0 and passed."""
    asset = phone_asset()
    comp = compose(template, next(template.genomes()), asset)
    left, top, right, bottom = comp.product.box
    x, y = (left + right) // 2, (top + bottom) // 2
    r, g, b = comp.image.getpixel((x, y))
    comp.image.putpixel((x, y), ((r + 1) % 256, g, b))
    result = run_guards(template, comp, asset)["product_pixels_unchanged"]
    assert result.passed is False and result.detail.startswith("1 of")


def test_pixel_guard_without_product_or_opaque_pixels(template):
    asset = phone_asset()
    comp = compose(template, next(template.genomes()), asset)
    transparent = Image.new("RGBA", asset.size, (0, 0, 0, 0))
    assert "no fully opaque" in run_guards(template, comp, transparent)["product_pixels_unchanged"].detail
    comp.product = None
    assert run_guards(template, comp, asset)["product_pixels_unchanged"].detail == "no product placed"


def test_legibility_guard_failure_paths(template):
    from dataclasses import replace

    comp = compose(template, next(template.genomes()), phone_asset())
    headline = comp.texts[0]
    comp.texts = [
        replace(headline, font_size=20),                          # too small
        replace(headline, box=(-10, 0, 100, 50)),                 # outside the canvas
        replace(headline, box=comp.product.box),                  # over the product
    ]
    detail = run_guards(template, comp, phone_asset())["text_legible"].detail
    assert "20px < 28px" in detail and "outside the canvas" in detail and "overlaps the product" in detail

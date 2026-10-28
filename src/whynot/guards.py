"""Guards: checks every composed ad must pass before it can be tested or published.

- product_pixels_unchanged: the real product/app-screen pixels in the ad are
  exactly the asset after the composer's one declared resize (no generated or
  painted-over product pixels; R8 in TARGETS.md);
- text_legible: WCAG contrast (≥ 4.5, ≥ 3 for the large headline), a minimum
  font size, text inside the canvas and not over the product;
- brand_palette: every colour the composer painted with is in the brand palette;
- policy_safe: Meta ad-policy check; needs a model, reported as not checked here.

A guard returns passed=True/False, or None when it was not checked. An ad is
publishable only if every guard of its template passed (None blocks too).
"""

from dataclasses import dataclass

from PIL import Image, ImageChops

from whynot.composer import Box, Brand, Composition, contrast_ratio, resize_asset
from whynot.templates import Template

MIN_CONTRAST = 4.5
MIN_CONTRAST_LARGE = 3.0  # WCAG large text
LARGE_TEXT_PX = 48
MIN_FONT_PX = 28  # on a 1080 px canvas


@dataclass(frozen=True)
class GuardResult:
    name: str
    passed: bool | None  # None = not checked
    detail: str = ""


def _overlap(a: Box, b: Box) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def product_pixels_unchanged(comp: Composition, asset: Image.Image) -> GuardResult:
    name = "product_pixels_unchanged"
    if comp.product is None:
        return GuardResult(name, False, "no product placed")
    expected = resize_asset(asset, comp.product.size)
    opaque = expected.getchannel("A").point(lambda a: 255 if a == 255 else 0)
    n_opaque = opaque.histogram()[255]
    if n_opaque == 0:
        return GuardResult(name, False, "asset has no fully opaque pixels to check")
    actual = comp.image.crop(comp.product.box).convert("RGB")
    diff = ImageChops.difference(actual, expected.convert("RGB")).convert("L")
    changed = ImageChops.multiply(diff.point(lambda d: 255 if d else 0), opaque)
    n_changed = changed.histogram()[255]
    if n_changed:
        return GuardResult(name, False, f"{n_changed} of {n_opaque} product pixels changed")
    return GuardResult(name, True, f"{n_opaque} opaque product pixels identical")


def text_legible(comp: Composition) -> GuardResult:
    name = "text_legible"
    w, h = comp.image.size
    problems = []
    for t in comp.texts:
        need = MIN_CONTRAST_LARGE if t.font_size >= LARGE_TEXT_PX else MIN_CONTRAST
        ratio = contrast_ratio(t.fg, t.bg)
        if ratio < need:
            problems.append(f"{t.role}: contrast {ratio:.2f} < {need}")
        if t.font_size < MIN_FONT_PX:
            problems.append(f"{t.role}: {t.font_size}px < {MIN_FONT_PX}px")
        if t.box[0] < 0 or t.box[1] < 0 or t.box[2] > w or t.box[3] > h:
            problems.append(f"{t.role}: outside the canvas")
        if comp.product and _overlap(t.box, comp.product.box):
            problems.append(f"{t.role}: overlaps the product")
    if problems:
        return GuardResult(name, False, "; ".join(problems))
    return GuardResult(name, True, f"{len(comp.texts)} text elements legible")


def brand_palette(comp: Composition, brand: Brand) -> GuardResult:
    name = "brand_palette"
    off = [c for c in comp.fills if c not in brand.palette]
    if off:
        return GuardResult(name, False, f"colours outside the palette: {off}")
    return GuardResult(name, True, "all colours from the brand palette")


def run_guards(template: Template, comp: Composition, asset: Image.Image) -> dict[str, GuardResult]:
    brand = Brand.from_fixed(template.fixed)
    checks = {
        "product_pixels_unchanged": lambda: product_pixels_unchanged(comp, asset),
        "text_legible": lambda: text_legible(comp),
        "brand_palette": lambda: brand_palette(comp, brand),
        "policy_safe": lambda: GuardResult("policy_safe", None, "needs the policy model; not checked"),
    }
    return {g: checks[g]() for g in template.guards}


def publishable(results: dict[str, GuardResult]) -> bool:
    return all(r.passed is True for r in results.values())

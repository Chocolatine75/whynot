"""Guards: checks every composed ad must pass before it can be tested or published.

- product_pixels_unchanged: the real product/app-screen pixels in the ad are
  exactly the asset after the composer's declared transform (resize, crop at the
  canvas edge, rounded corners; no generated or painted-over pixels; R8);
- text_legible: WCAG contrast (≥ 4.5, ≥ 3 for the large headline), a minimum
  font size, text inside the canvas and not over the product;
- brand_palette: every colour the composer painted with is in the brand palette;
- policy_safe: rule-based Meta ad-policy check on the text drawn in the ad
  (`create/policy.py`: personal attributes, absolute claims, engagement bait,
  shouting). The ad's primary text is checked by the creative director.

A guard returns passed=True/False, or None when it was not checked. Every guard
in `MANDATORY` runs on every ad, whatever the template lists. An ad is
publishable only if every guard that ran passed (None blocks too).
"""

from dataclasses import dataclass

from PIL import Image, ImageChops

from whynot.create import policy
from whynot.create.composer import Box, Brand, Composition, contrast_ratio, product_pixels
from whynot.create.templates import KNOWN_GUARDS, Template

MANDATORY = frozenset(KNOWN_GUARDS)  # all of them, for now

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
    expected = product_pixels(asset, comp.product)
    opaque = expected.getchannel("A").point(lambda a: 255 if a == 255 else 0)
    n_opaque = opaque.histogram()[255]
    if n_opaque == 0:
        return GuardResult(name, False, "asset has no fully opaque pixels to check")
    actual = comp.image.crop(comp.product.box).convert("RGB")
    r, g, b = ImageChops.difference(actual, expected.convert("RGB")).split()
    # max over channels: converting to grey would round a 1-level change in one channel to 0
    diff = ImageChops.lighter(ImageChops.lighter(r, g), b)
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


def policy_safe(comp: Composition) -> GuardResult:
    issues = policy.check_ad({f"{t.role}_{i}": t.text for i, t in enumerate(comp.texts)})
    errs = policy.errors(issues)
    if errs:
        return GuardResult("policy_safe", False, "; ".join(f"{e.field}: {e.message}" for e in errs))
    warnings = [i.message for i in issues if i.severity == "warning"]
    detail = "rule-based check passed" + (f" (warnings: {warnings})" if warnings else "")
    return GuardResult("policy_safe", True, detail)


def run_guards(template: Template, comp: Composition, asset: Image.Image) -> dict[str, GuardResult]:
    brand = Brand.from_fixed(template.fixed)
    checks = {
        "product_pixels_unchanged": lambda: product_pixels_unchanged(comp, asset),
        "text_legible": lambda: text_legible(comp),
        "brand_palette": lambda: brand_palette(comp, brand),
        "policy_safe": lambda: policy_safe(comp),
    }
    names = sorted(MANDATORY | set(template.guards))
    return {g: checks[g]() for g in names}


def publishable(results: dict[str, GuardResult]) -> bool:
    return set(results) >= MANDATORY and all(r.passed is True for r in results.values())

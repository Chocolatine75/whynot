"""Deterministic ad composition: template + genome + real assets → image.

Code, not generation: the same inputs always give the same pixels. The product
or app-screen asset is pasted after one declared resize, and nothing is drawn
over it, so `guards.product_pixels_unchanged` can verify it exactly.

v0 supports the `static_1080` format (1080×1080). Reels come later (ffmpeg).
Layout: hook headline on top, product in the middle (on an accent card when
first_shot is `result_card`), optional proof line, CTA button at the bottom.
"""

from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from whynot.create.templates import Genome, Template

SIZE = 1080
MARGIN = 60
SUPPORTED_FORMATS = {"static_1080"}

RGB = tuple[int, int, int]
Box = tuple[int, int, int, int]  # left, top, right, bottom


class ComposeError(ValueError):
    pass


@dataclass(frozen=True)
class Brand:
    name: str
    palette: list[RGB]  # [background, foreground, accent, ...]
    font: str | None = None  # path to a .ttf; Pillow's default font otherwise

    @classmethod
    def from_fixed(cls, fixed: dict) -> "Brand":
        b = fixed.get("brand") or {}
        palette = [hex_to_rgb(c) for c in b.get("palette", [])]
        if len(palette) < 3:
            raise ComposeError("brand palette needs at least 3 colours: background, foreground, accent")
        if len(set(palette)) != len(palette):
            raise ComposeError("brand palette has duplicate colours")
        return cls(name=str(b.get("name", "")), palette=palette, font=b.get("font"))


@dataclass(frozen=True)
class TextElement:
    role: str  # headline | proof | cta
    text: str
    box: Box
    fg: RGB
    bg: RGB
    font_size: int


@dataclass(frozen=True)
class ProductElement:
    box: Box  # where the resized asset was pasted
    size: tuple[int, int]  # resized asset size


@dataclass
class Composition:
    image: Image.Image
    texts: list[TextElement] = field(default_factory=list)
    product: ProductElement | None = None
    fills: list[RGB] = field(default_factory=list)  # every colour the composer painted with


def hex_to_rgb(value: str) -> RGB:
    v = str(value).lstrip("#")
    if len(v) != 6:
        raise ComposeError(f"bad colour {value!r}")
    try:
        return (int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16))
    except ValueError:
        raise ComposeError(f"bad colour {value!r}") from None


def relative_luminance(c: RGB) -> float:
    def ch(x: int) -> float:
        s = x / 255
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(x) for x in c)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: RGB, b: RGB) -> float:
    """WCAG contrast ratio, 1 to 21."""
    la, lb = sorted((relative_luminance(a), relative_luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def best_text_colour(bg: RGB, palette: list[RGB]) -> RGB:
    return max((c for c in palette if c != bg), key=lambda c: contrast_ratio(c, bg))


def fit_product(asset_size: tuple[int, int], box: Box) -> tuple[tuple[int, int], Box]:
    """Size and position of the asset fitted (aspect kept, centred) in a box."""
    w, h = asset_size
    bw, bh = box[2] - box[0], box[3] - box[1]
    scale = min(bw / w, bh / h)
    nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
    left = box[0] + (bw - nw) // 2
    top = box[1] + (bh - nh) // 2
    return (nw, nh), (left, top, left + nw, top + nh)


def resize_asset(asset: Image.Image, size: tuple[int, int]) -> Image.Image:
    """The only transform applied to product pixels (guards replay it)."""
    return asset.convert("RGBA").resize(size, Image.Resampling.LANCZOS)


def _font(brand: Brand, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    from whynot.create import fonts
    return fonts.load(size, brand.font)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, width: int) -> list[str]:
    lines: list[str] = []
    for word in text.split():
        if lines and draw.textlength(f"{lines[-1]} {word}", font=font) <= width:
            lines[-1] = f"{lines[-1]} {word}"
        else:
            lines.append(word)
    return lines


def missing_glyphs(font, text: str) -> list[str]:
    """Characters the font would draw as the empty 'missing glyph' box."""
    notdef = font.getmask("\U0010fffd")
    ref = (notdef.size, bytes(notdef))
    out = []
    for ch in sorted(set(text) - {" "}):
        m = font.getmask(ch)
        if (m.size, bytes(m)) == ref:
            out.append(ch)
    return out


def _draw_text(draw, brand: Brand, text: str, box: Box, fg: RGB, *, max_size: int, min_size: int) -> int:
    """Largest font size (≤ max_size) whose wrapped text fits the box; centred."""
    width, height = box[2] - box[0], box[3] - box[1]
    missing = missing_glyphs(_font(brand, max_size), text)
    if missing:
        raise ComposeError(f"font cannot draw {missing} in {text!r}")
    for size in range(max_size, min_size - 1, -2):
        font = _font(brand, size)
        lines = _wrap(draw, text, font, width)
        line_h = round(size * 1.2)
        too_wide = any(draw.textlength(line, font=font) > width for line in lines)
        if not too_wide and line_h * len(lines) <= height:
            y = box[1] + (height - line_h * len(lines)) // 2
            for line in lines:
                x = box[0] + (width - draw.textlength(line, font=font)) / 2
                draw.text((x, y), line, font=font, fill=fg)
                y += line_h
            return size
    raise ComposeError(f"text does not fit its box even at {min_size}px: {text!r}")


def compose(template: Template, genome: Genome, product_asset: str | Path | Image.Image) -> Composition:
    template.check(genome)
    if genome["format"] not in SUPPORTED_FORMATS:
        raise ComposeError(f"format {genome['format']!r} not supported yet (v0: {sorted(SUPPORTED_FORMATS)})")
    brand = Brand.from_fixed(template.fixed)
    bg, fg, accent = brand.palette[:3]
    asset = product_asset if isinstance(product_asset, Image.Image) else Image.open(product_asset)

    image = Image.new("RGB", (SIZE, SIZE), bg)
    draw = ImageDraw.Draw(image)
    comp = Composition(image=image, fills=[bg])

    headline_box: Box = (MARGIN, MARGIN, SIZE - MARGIN, 300)
    headline = template.text("hook", genome["hook"]).strip()
    if not headline:
        raise ComposeError(f"{template.id}: empty headline for hook {genome['hook']!r}")
    size = _draw_text(draw, brand, headline, headline_box, fg, max_size=88, min_size=40)
    comp.texts.append(TextElement("headline", headline, headline_box, fg, bg, size))
    comp.fills.append(fg)

    product_box: Box = (240, 330, 840, 860)
    if genome.get("first_shot") == "result_card":
        draw.rounded_rectangle((200, 320, 880, 870), radius=36, fill=accent)
        comp.fills.append(accent)
        product_box = (260, 360, 820, 830)
    size_px, pasted = fit_product(asset.size, product_box)
    resized = resize_asset(asset, size_px)
    image.paste(resized, pasted[:2], resized)
    comp.product = ProductElement(box=pasted, size=size_px)

    proof = template.text("proof", genome["proof"]) if "proof" in genome else ""
    if proof:
        proof_box: Box = (MARGIN, 880, SIZE - MARGIN, 945)
        size = _draw_text(draw, brand, proof, proof_box, fg, max_size=44, min_size=28)
        comp.texts.append(TextElement("proof", proof, proof_box, fg, bg, size))

    cta = template.text("cta", genome["cta"]).strip()
    if not cta:
        raise ComposeError(f"{template.id}: empty call to action")
    button: Box = (300, 960, 780, 1040)
    cta_fg = best_text_colour(accent, brand.palette)
    draw.rounded_rectangle(button, radius=40, fill=accent)
    if accent not in comp.fills:
        comp.fills.append(accent)
    inner: Box = (button[0] + 20, button[1] + 8, button[2] - 20, button[3] - 8)
    size = _draw_text(draw, brand, cta, inner, cta_fg, max_size=44, min_size=28)
    comp.texts.append(TextElement("cta", cta, inner, cta_fg, accent, size))
    if cta_fg not in comp.fills:
        comp.fills.append(cta_fg)
    return comp

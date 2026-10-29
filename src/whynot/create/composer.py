"""Deterministic ad composition: template + genome + real assets → image.

Code, not generation: the same inputs always give the same pixels. The product
or app screen goes through one declared transform (`prepare_product`: resize,
optional crop at the canvas edge, rounded corners) and nothing is drawn over
it, so `guards.product_pixels_unchanged` replays the transform and checks every
opaque pixel exactly.

Style, between Apple and Meta: generous white space, a soft vertical gradient,
a large bold headline, the real screen large with rounded corners and a soft
shadow, a rounded "pill" button in the brand accent. Two layouts, chosen by the
`first_shot` gene:
- `app_screen` → split: text column on the left, the full screen on the right;
- `result_card` → rising: headline on top, the screen rising from the bottom edge.
Format: `static_1080` (1080×1080). Reels come later (ffmpeg).
"""

from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from whynot.create.templates import Genome, Template

SIZE = 1080
MARGIN = 64
SCREEN_RADIUS = 44  # rounded corners of the app screen, like a device display
SUPPORTED_FORMATS = {"static_1080"}

RGB = tuple[int, int, int]
Box = tuple[int, int, int, int]  # left, top, right, bottom


class ComposeError(ValueError):
    pass


@dataclass(frozen=True)
class Brand:
    name: str
    palette: list[RGB]  # [background, foreground, accent, surface?]: surface = gradient end (optional)
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
    box: Box  # where the prepared asset was pasted (visible part)
    size: tuple[int, int]  # size the asset was resized to (before cropping)
    visible: int  # rows kept from the top (= size[1] unless the canvas edge crops it)
    radius: int  # rounded-corner radius
    round_bottom: bool  # False when the bottom is cut by the canvas edge


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
    return asset.convert("RGBA").resize(size, Image.Resampling.LANCZOS)


def prepare_product(asset: Image.Image, size: tuple[int, int], *, visible: int | None = None, radius: int = 0,
                    round_bottom: bool = True) -> Image.Image:
    """The only transform applied to product pixels (guards replay it): resize, keep the top `visible` rows,
    round the corners (alpha only: colours of kept pixels are untouched)."""
    img = resize_asset(asset, size)
    if visible is not None and visible < img.height:
        img = img.crop((0, 0, img.width, visible))
    if radius > 0:
        mask = Image.new("L", img.size, 0)
        d = ImageDraw.Draw(mask)
        d.rounded_rectangle((0, 0, img.width - 1, img.height - 1), radius=radius, fill=255)
        if not round_bottom:
            d.rectangle((0, img.height // 2, img.width - 1, img.height - 1), fill=255)
        alpha = Image.composite(img.getchannel("A"), Image.new("L", img.size, 0), mask)
        img.putalpha(alpha)
    return img


def product_pixels(asset: Image.Image, element: ProductElement) -> Image.Image:
    return prepare_product(asset, element.size, visible=element.visible, radius=element.radius,
                           round_bottom=element.round_bottom)


def _font(brand: Brand, size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    from whynot.create import fonts
    return fonts.load(size, brand.font, bold=bold)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, width: int) -> list[str]:
    lines: list[str] = []
    for word in text.split():
        if lines and draw.textlength(f"{lines[-1]} {word}", font=font) <= width:
            lines[-1] = f"{lines[-1]} {word}"
        else:
            lines.append(word)
    return lines


def _balanced(draw: ImageDraw.ImageDraw, text: str, font, width: int) -> list[str]:
    """Same number of lines as a greedy wrap at `width`, but as even as possible (no lone last word)."""
    lines = _wrap(draw, text, font, width)
    if len(lines) < 2:
        return lines
    lo, hi = 1, width
    while lo < hi:  # narrowest width that keeps the line count
        mid = (lo + hi) // 2
        if len(_wrap(draw, text, font, mid)) <= len(lines) and all(
                draw.textlength(w, font=font) <= mid for w in text.split()):
            hi = mid
        else:
            lo = mid + 1
    return _wrap(draw, text, font, lo)


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


def _draw_text(draw, brand: Brand, text: str, box: Box, fg: RGB, *, max_size: int, min_size: int,
               bold: bool = False, align: str = "center", valign: str = "middle", leading: float = 1.15) -> int:
    """Largest font size (≤ max_size) whose wrapped text fits the box."""
    width, height = box[2] - box[0], box[3] - box[1]
    missing = missing_glyphs(_font(brand, max_size, bold=bold), text)
    if missing:
        raise ComposeError(f"font cannot draw {missing} in {text!r}")
    for size in range(max_size, min_size - 1, -2):
        font = _font(brand, size, bold=bold)
        lines = _balanced(draw, text, font, width)
        line_h = round(size * leading)
        too_wide = any(draw.textlength(line, font=font) > width for line in lines)
        if not too_wide and line_h * len(lines) <= height:
            y = box[1] + ((height - line_h * len(lines)) // 2 if valign == "middle" else 0)
            for line in lines:
                w = draw.textlength(line, font=font)
                x = box[0] + ((width - w) / 2 if align == "center" else 0)
                draw.text((x, y), line, font=font, fill=fg)
                y += line_h
            return size
    raise ComposeError(f"text does not fit its box even at {min_size}px: {text!r}")


def _background(bg: RGB, surface: RGB | None) -> Image.Image:
    top = Image.new("RGB", (SIZE, SIZE), bg)
    if surface is None:
        return top
    bottom = Image.new("RGB", (SIZE, SIZE), surface)
    ramp = Image.linear_gradient("L").resize((SIZE, SIZE))  # 0 at the top, 255 at the bottom
    return Image.composite(bottom, top, ramp)


def _shadow(image: Image.Image, box: Box, colour: RGB, *, radius: int, offset: int = 22, blur: int = 26,
            opacity: int = 70) -> Image.Image:
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle((box[0], box[1] + offset, box[2], box[3] + offset), radius=radius,
                                            fill=(*colour, opacity))
    layer = layer.filter(ImageFilter.GaussianBlur(blur))
    return Image.alpha_composite(image.convert("RGBA"), layer).convert("RGB")


def _pill(draw, brand: Brand, comp: "Composition", text: str, box: Box, accent: RGB) -> None:
    cta_fg = best_text_colour(accent, brand.palette)
    draw.rounded_rectangle(box, radius=(box[3] - box[1]) // 2, fill=accent)
    inner: Box = (box[0] + 28, box[1] + 10, box[2] - 28, box[3] - 10)
    size = _draw_text(draw, brand, text, inner, cta_fg, max_size=40, min_size=28, bold=True)
    comp.texts.append(TextElement("cta", text, inner, cta_fg, accent, size))
    for c in (accent, cta_fg):
        if c not in comp.fills:
            comp.fills.append(c)


def compose(template: Template, genome: Genome, product_asset: str | Path | Image.Image) -> Composition:
    template.check(genome)
    if genome["format"] not in SUPPORTED_FORMATS:
        raise ComposeError(f"format {genome['format']!r} not supported yet (v0: {sorted(SUPPORTED_FORMATS)})")
    brand = Brand.from_fixed(template.fixed)
    bg, fg, accent = brand.palette[:3]
    surface = brand.palette[3] if len(brand.palette) > 3 else None
    asset = product_asset if isinstance(product_asset, Image.Image) else Image.open(product_asset)
    headline = template.text("hook", genome["hook"]).strip()
    if not headline:
        raise ComposeError(f"{template.id}: empty headline for hook {genome['hook']!r}")
    cta = template.text("cta", genome["cta"]).strip()
    if not cta:
        raise ComposeError(f"{template.id}: empty call to action")
    proof = template.text("proof", genome["proof"]).strip() if "proof" in genome else ""
    rising = genome.get("first_shot") == "result_card"

    # 1. background, then the screen's shadow, then the screen (nothing is ever drawn over the screen)
    if rising:
        width = 560
        size_px = (width, max(1, round(asset.height * width / asset.width)))
        top = 430
        visible = min(size_px[1], SIZE - top)
        left = (SIZE - width) // 2
        box: Box = (left, top, left + width, top + visible)
        element = ProductElement(box, size_px, visible, SCREEN_RADIUS, round_bottom=visible == size_px[1])
    else:
        size_px, box = fit_product(asset.size, (600, 64, SIZE - 56, SIZE - 64))
        element = ProductElement(box, size_px, size_px[1], SCREEN_RADIUS, round_bottom=True)
    image = _shadow(_background(bg, surface), box, fg, radius=SCREEN_RADIUS)
    screen = product_pixels(asset, element)
    image.paste(screen, box[:2], screen)
    draw = ImageDraw.Draw(image)
    comp = Composition(image=image, product=element, fills=[bg] + ([surface] if surface else []) + [fg])

    # 2. text and button, never over the screen
    if rising:
        h_box: Box = (MARGIN, 56, SIZE - MARGIN, 236)
        size = _draw_text(draw, brand, headline, h_box, fg, max_size=72, min_size=40, bold=True)
        comp.texts.append(TextElement("headline", headline, h_box, fg, bg, size))
        y = 246
        if proof:
            p_box: Box = (MARGIN, y, SIZE - MARGIN, y + 52)
            size = _draw_text(draw, brand, proof, p_box, fg, max_size=34, min_size=28)
            comp.texts.append(TextElement("proof", proof, p_box, fg, bg, size))
            y += 60
        _pill(draw, brand, comp, cta, (SIZE // 2 - 190, y + 6, SIZE // 2 + 190, y + 92), accent)
    else:
        h_box = (MARGIN, 120, 560, 600)
        size = _draw_text(draw, brand, headline, h_box, fg, max_size=80, min_size=40, bold=True, align="left",
                          valign="top", leading=1.1)
        comp.texts.append(TextElement("headline", headline, h_box, fg, bg, size))
        if proof:
            p_box = (MARGIN, 640, 560, 760)
            size = _draw_text(draw, brand, proof, p_box, fg, max_size=36, min_size=28, align="left", valign="top")
            comp.texts.append(TextElement("proof", proof, p_box, fg, bg, size))
        _pill(draw, brand, comp, cta, (MARGIN, 860, MARGIN + 440, 956), accent)
    return comp

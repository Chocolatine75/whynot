"""Deterministic ad composition: template + genome + real assets → image.

Code, not generation: the same inputs always give the same pixels. The product
or app screen goes through one declared transform (`prepare_product`: resize,
optional crop at the canvas edge, rounded corners) and nothing is drawn over
it, so `guards.product_pixels_unchanged` replays the transform and checks every
opaque pixel exactly.

Style, between Apple and Meta: generous white space, a large bold headline, the real screen large with
rounded corners and a soft shadow, a rounded "pill" button. Three genes shape the picture (E5-2):
- `format`: square 1:1 (1080×1080, `static_1080` is its old name), portrait 4:5 (1080×1350, the feed),
  story 9:16 (1080×1920, Stories and Reels);
- `layout`: ten arrangements (LAYOUTS). Four of them show a verified fact the template carries in
  `fixed.content` (a real App Store review quoted word for word, a number from a verified claim, verified
  benefits, the customer's objection, answered by the ad's own headline): a template only offers them when it
  has that fact;
- `style`: light, dark, brand, gradient, shape. Every colour comes from the brand palette.
Templates without `layout` use the old `first_shot` gene (app_screen → split, result_card → rising).
"""

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from whynot.create.templates import Genome, Template

SIZE = 1080  # every format is 1080 px wide
MARGIN = 64
SCREEN_RADIUS = 44  # rounded corners of the app screen, like a device display
FORMATS = {"square": (1080, 1080), "portrait": (1080, 1350), "story": (1080, 1920), "static_1080": (1080, 1080)}
SUPPORTED_FORMATS = set(FORMATS)
LAYOUTS = ("split", "rising", "full_screen", "review_card", "before_after", "big_number", "benefits",
           "big_question", "comparison", "bold_text", "two_screens", "offer", "note")
DECORS = ("none", "panel", "diagonal", "circle")  # a shape of colour behind the phone, never under any text
STYLES = ("light", "dark", "brand", "gradient", "shape")
# layouts that show a verified fact: the `fixed.content` key they need
NEEDS = {"review_card": "review", "big_number": "number", "benefits": "benefits", "before_after": "objection",
         "comparison": "objection", "offer": "offer", "note": "benefits"}
LEGACY_LAYOUT = {"app_screen": "split", "result_card": "rising"}
# Stories/Reels draw the account name over the top and the reply bar and caption over the bottom: no text there
# (Meta's guidance: ~14 % top, ~20 % bottom). Other formats use the whole canvas.
SAFE = {"story": (250, 340)}

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
    extra_products: list[tuple[ProductElement, Image.Image]] = field(default_factory=list)  # a second real screen


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
               bold: bool = False, align: str = "center", valign: str = "middle", leading: float = 1.15,
               accent: RGB | None = None, accent_words: int = 0, dry: bool = False) -> int:
    """Largest font size (≤ max_size) whose wrapped text fits the box. With `accent`, the last `accent_words`
    words are drawn in that colour (the key words of a headline). `dry`: only find the size, draw nothing."""
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
            if dry:
                return size
            y = box[1] + ((height - line_h * len(lines)) // 2 if valign == "middle" else 0)
            total = sum(len(line.split()) for line in lines)
            first_accent = total - accent_words if accent else total
            n = 0
            for line in lines:
                w = draw.textlength(line, font=font)
                x = box[0] + ((width - w) / 2 if align == "center" else 0)
                for word in line.split():  # word by word, so key words can take the accent
                    draw.text((x, y), word, font=font, fill=accent if accent and n >= first_accent else fg)
                    x += draw.textlength(word + " ", font=font)
                    n += 1
                y += line_h
            return size
    raise ComposeError(f"text does not fit its box even at {min_size}px: {text!r}")


def layouts_for(content: dict | None, *, second_screen: bool = False) -> list[str]:
    """The layouts a template can offer: every free one, those whose verified fact it carries, and two screens
    when the app has a second real screen to show."""
    content = content or {}
    return [x for x in LAYOUTS if (x not in NEEDS or content.get(NEEDS[x])) and (x != "two_screens" or second_screen)]


def styles_for(palette: list[RGB]) -> list[str]:
    """The styles whose text reaches WCAG contrast with this palette (a style no text can be read on is not offered)."""
    out = []
    for s in STYLES:
        base, *_ = _style_colours(s, palette)
        if contrast_ratio(base, best_text_colour(base, palette)) >= 4.5:
            out.append(s)
    return out or ["light"]


def _lightest(palette: list[RGB]) -> RGB:
    return max(palette, key=relative_luminance)


def _darkest(palette: list[RGB]) -> RGB:
    return min(palette, key=relative_luminance)


def _style_colours(style: str, palette: list[RGB]) -> tuple[RGB, RGB | None, RGB | None]:
    """(base colour under the text, gradient end or None, shape colour or None)."""
    bg, fg, accent = palette[:3]
    surface = palette[3] if len(palette) > 3 else None
    if style == "dark":
        return _darkest(palette), None, None
    if style == "brand":
        return accent, None, None
    if style == "gradient":
        return bg, surface or next((c for c in palette if c not in (bg, fg, accent)), None), None
    if style == "shape":
        return bg, None, accent
    if style == "light":
        return _lightest(palette), None, None
    raise ComposeError(f"unknown style {style!r}; one of {list(STYLES)}")


def _background(size: tuple[int, int], bg: RGB, surface: RGB | None) -> Image.Image:
    top = Image.new("RGB", size, bg)
    if surface is None:
        return top
    bottom = Image.new("RGB", size, surface)
    ramp = Image.linear_gradient("L").resize(size)  # 0 at the top, 255 at the bottom
    return Image.composite(bottom, top, ramp)


def _shadow(image: Image.Image, box: Box, colour: RGB, *, radius: int, offset: int = 22, blur: int = 26,
            opacity: int = 70) -> Image.Image:
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle((box[0], box[1] + offset, box[2], box[3] + offset), radius=radius,
                                            fill=(*colour, opacity))
    layer = layer.filter(ImageFilter.GaussianBlur(blur))
    return Image.alpha_composite(image.convert("RGBA"), layer).convert("RGB")


class Canvas:
    """One ad being drawn. Layouts declare the screen and the text/shapes; `finish` paints them in order:
    background, the accent halo (style `shape`, never under any text), the screen's shadow, the screen (never
    drawn over), then text and shapes."""

    def __init__(self, brand: Brand, size: tuple[int, int], style: str, asset: Image.Image,
                 safe: tuple[int, int] = (0, 0), decor: str = "none"):
        if decor not in DECORS:
            raise ComposeError(f"unknown decor {decor!r}; one of {list(DECORS)}")
        self.decor = decor
        # layouts work in the safe area (height `h`, from `y0`); a screen rising from the bottom goes to the real edge
        self.brand, self.w, self.H, self.asset = brand, size[0], size[1], asset
        self.y0, self.h = safe[0], size[1] - safe[0] - safe[1]
        self.base, self.surface, self.shape = _style_colours(style, brand.palette)
        self.fg = best_text_colour(self.base, brand.palette)
        # the button: the accent, unless the background is the accent (brand style): then the strongest contrast
        self.button = brand.palette[2] if self.base != brand.palette[2] else self.fg
        # the phone frame: the darkest palette colour, or the lightest on a dark background (it must show)
        dark = _darkest(brand.palette)
        # the decor: a palette colour that stands out from the background (never the background itself)
        self.decor_colour = (self.button if self.button != self.base and contrast_ratio(self.button, self.base) >= 1.3
                             else self.other(self.base))
        under = self.decor_colour if decor != "none" else self.base
        self.frame = (dark if contrast_ratio(dark, under) >= 1.5 and contrast_ratio(dark, self.base) >= 1.5
                      else _lightest(brand.palette))
        self.screens: list[tuple[ProductElement, Image.Image]] = []
        self.second: Image.Image | None = None  # another real screen of the app, for `two_screens`
        self.comp = Composition(image=Image.new("RGB", size), fills=[self.base, self.fg]
                                + [c for c in (self.surface, self.shape) if c])
        self.element: ProductElement | None = None
        self.ops: list[tuple[Box, Callable[[ImageDraw.ImageDraw], None]]] = []  # (area it covers, how to paint)

    def at(self, box: Box) -> Box:
        """A box given in the safe area, on the canvas."""
        return (box[0], box[1] + self.y0, box[2], box[3] + self.y0)

    def fill(self, c: RGB) -> RGB:
        if c not in self.comp.fills:
            self.comp.fills.append(c)
        return c

    def other(self, *avoid: RGB) -> RGB:
        """A palette colour for a card, different from the background, with the best contrast for text on it."""
        options = [c for c in self.brand.palette if c not in avoid] or list(self.brand.palette)
        return max(options, key=lambda c: (contrast_ratio(c, best_text_colour(c, self.brand.palette)), c))

    def screen(self, box: Box, *, rising: bool = False, width: int | None = None,
               asset: Image.Image | None = None) -> Box:
        """Place a real screen: fitted in `box`, or `rising` from the bottom edge at `width` (cut by the edge).
        The first one placed is the ad's main screen; `asset` places another real screen of the app."""
        a = asset or self.asset
        box = self.at(box)
        if rising:
            assert width is not None
            size_px = (width, max(1, round(a.height * width / a.width)))
            top = box[1]
            visible = min(size_px[1], self.H - top)
            left = box[0] + (box[2] - box[0] - width) // 2
            pbox: Box = (left, top, left + width, top + visible)
            element = ProductElement(pbox, size_px, visible, SCREEN_RADIUS, round_bottom=visible == size_px[1])
        else:
            size_px, pbox = fit_product(a.size, box)
            element = ProductElement(pbox, size_px, size_px[1], SCREEN_RADIUS, round_bottom=True)
        self.screens.append((element, a))
        if self.element is None:
            self.element = element
        return pbox

    def text(self, role: str, text: str, box: Box, *, max_size: int, min_size: int = 28, bold: bool = False,
             align: str = "center", valign: str = "middle", leading: float = 1.15, fg: RGB | None = None,
             bg: RGB | None = None) -> None:
        ink, under = fg or self.fg, bg or self.base
        self.fill(ink)
        box = self.at(box)
        # a headline's key words (its last ones) in the button colour, when it reads well as large text
        words = len(text.split())
        key = min(3, max(1, words // 3)) if role == "headline" and words >= 3 else 0
        accent = self.button if key and self.button != ink and contrast_ratio(self.button, under) >= 3.0 else None

        def paint(d: ImageDraw.ImageDraw) -> None:
            size = _draw_text(d, self.brand, text, box, ink, max_size=max_size, min_size=min_size, bold=bold,
                              align=align, valign=valign, leading=leading, dry=True)
            use = accent if accent and size >= 48 else None  # the accent only on large text (WCAG ≥ 3)
            _draw_text(d, self.brand, text, box, ink, max_size=size, min_size=size, bold=bold, align=align,
                       valign=valign, leading=leading, accent=self.fill(use) if use else None, accent_words=key)
            self.comp.texts.append(TextElement(role, text, box, ink, under, size))
            if use:
                self.comp.texts.append(TextElement("headline_key", " ".join(text.split()[-key:]), box, use, under,
                                                   size))
        self.ops.append((box, paint))

    def pill(self, text: str, box: Box) -> None:
        accent = self.fill(self.button)
        cta_fg = self.fill(best_text_colour(accent, self.brand.palette))
        box = self.at(box)
        inner: Box = (box[0] + 28, box[1] + 10, box[2] - 28, box[3] - 10)

        def paint(d: ImageDraw.ImageDraw) -> None:
            d.rounded_rectangle(box, radius=(box[3] - box[1]) // 2, fill=accent)
            size = _draw_text(d, self.brand, text, inner, cta_fg, max_size=40, min_size=28, bold=True)
            self.comp.texts.append(TextElement("cta", text, inner, cta_fg, accent, size))
        self.ops.append((box, paint))

    def card(self, box: Box, colour: RGB, *, outline: bool = False) -> None:
        c = self.fill(colour)
        box = self.at(box)
        self.ops.append((box, lambda d: d.rounded_rectangle(box, radius=28, outline=c, width=4) if outline
                         else d.rounded_rectangle(box, radius=28, fill=c)))

    def stars(self, x: int, y: int, n: int, size: int = 40) -> None:
        """`n` five-point stars drawn as shapes (no glyph: every font draws them)."""
        colour = self.fill(self.button)
        y += self.y0
        polys = []
        for i in range(n):
            cx, cy, pts = x + i * (size + 10) + size // 2, y + size // 2, []
            for k in range(10):
                r = size / 2 if k % 2 == 0 else size / 5
                ang = math.pi / 2 + k * math.pi / 5
                pts.append((cx + r * math.cos(ang), cy - r * math.sin(ang)))
            polys.append(pts)

        def paint(d: ImageDraw.ImageDraw) -> None:
            for p in polys:
                d.polygon(p, fill=colour)
        self.ops.append(((x, y, x + n * (size + 10), y + size), paint))

    def mark(self, x: int, y: int, size: int, *, tick: bool, colour: RGB | None = None) -> None:
        """A drawn check mark (tick) or cross in a disc."""
        disc = self.fill(colour or self.button)
        ink = self.fill(best_text_colour(disc, self.brand.palette))
        w = max(4, size // 9)
        y += self.y0

        def paint(d: ImageDraw.ImageDraw) -> None:
            d.ellipse((x, y, x + size, y + size), fill=disc)
            if tick:
                d.line([(x + size * 0.27, y + size * 0.52), (x + size * 0.44, y + size * 0.68),
                        (x + size * 0.74, y + size * 0.34)], fill=ink, width=w, joint="curve")
            else:
                d.line([(x + size * 0.32, y + size * 0.32), (x + size * 0.68, y + size * 0.68)], fill=ink, width=w)
                d.line([(x + size * 0.68, y + size * 0.32), (x + size * 0.32, y + size * 0.68)], fill=ink, width=w)
        self.ops.append(((x, y, x + size, y + size), paint))

    def arrow(self, box: Box) -> None:
        """A right-pointing arrow filling `box` (before → after)."""
        colour = self.fill(self.button)
        x0, y0, x1, y1 = self.at(box)
        cy, t = (y0 + y1) // 2, max(6, (y1 - y0) // 6)
        head = (x1 - x0) // 3

        def paint(d: ImageDraw.ImageDraw) -> None:
            d.rectangle((x0, cy - t, x1 - head, cy + t), fill=colour)
            d.polygon([(x1 - head, y0), (x1, cy), (x1 - head, y1)], fill=colour)
        self.ops.append((box, paint))

    def finish(self) -> Composition:
        if self.element is None:
            raise ComposeError("layout placed no screen")
        image = _background((self.w, self.H), self.base, self.surface)
        boxes = [b for b, _ in self.ops]
        if self.decor != "none":
            self._decor(image, boxes)
        for element, _ in self.screens:
            pbox = element.box
            near = [_distance(pbox, b) for b in boxes]
            if self.shape:  # a halo of the accent around the screen, as wide as the space to the nearest text allows
                gap = min([HALO + BEZEL] + [d - 14 for d in near])
                if gap >= BEZEL + 8:
                    ImageDraw.Draw(image).rounded_rectangle(
                        (pbox[0] - gap, pbox[1] - gap, pbox[2] + gap, pbox[3] + gap), radius=SCREEN_RADIUS + gap,
                        fill=self.shape)
            # a phone frame around the screen (its own pixels stay untouched), as thick as the space allows
            bezel = max(0, min([BEZEL] + [d - 10 for d in near]))
            frame: Box = (pbox[0] - bezel, pbox[1] - bezel, pbox[2] + bezel, pbox[3] + bezel)
            image = _shadow(image, frame, self.fg, radius=SCREEN_RADIUS + bezel)
            if bezel:
                ImageDraw.Draw(image).rounded_rectangle(frame, radius=SCREEN_RADIUS + bezel,
                                                        fill=self.fill(self.frame))
        for element, asset in self.screens:  # the screens last: no other phone's frame or shadow over them
            pixels = product_pixels(asset, element)
            image.paste(pixels, element.box[:2], pixels)
        draw = ImageDraw.Draw(image)
        for _, paint in self.ops:
            paint(draw)
        self.comp.image, self.comp.product = image, self.element
        self.comp.extra_products = self.screens[1:]
        return self.comp

    def _decor(self, image: Image.Image, boxes: list[Box]) -> None:
        """A shape of colour behind the phones, inside the largest area around them that no text touches."""
        xs = [e.box for e, _ in self.screens]
        u: Box = (min(b[0] for b in xs) - BEZEL, min(b[1] for b in xs) - BEZEL,
                  max(b[2] for b in xs) + BEZEL, max(b[3] for b in xs) + BEZEL)
        r = [0, 0, self.w, self.H]
        for raw in sorted(boxes, key=lambda b: -_distance(u, b)):
            b = (raw[0] - 24, raw[1] - 24, raw[2] + 24, raw[3] + 24)
            if not (b[0] < r[2] and r[0] < b[2] and b[1] < r[3] and r[1] < b[3]):
                continue  # already outside the area
            cuts = []  # cut the area on one side of this text box, keeping the phones whole
            if b[2] <= u[0]:
                cuts.append([b[2], r[1], r[2], r[3]])
            if b[0] >= u[2]:
                cuts.append([r[0], r[1], b[0], r[3]])
            if b[3] <= u[1]:
                cuts.append([r[0], b[3], r[2], r[3]])
            if b[1] >= u[3]:
                cuts.append([r[0], r[1], r[2], b[1]])
            if not cuts:
                return  # a text box hugs the phone on every side: no decor
            r = max(cuts, key=lambda c: (c[2] - c[0]) * (c[3] - c[1]))
        x0, y0, x1, y1 = r
        if (x1 - x0) * (y1 - y0) < 1.4 * (u[2] - u[0]) * (u[3] - u[1]):
            return  # no room worth a decor
        mask = Image.new("L", image.size, 0)
        d = ImageDraw.Draw(mask)
        if self.decor == "panel":
            d.rounded_rectangle((x0, y0, x1, y1), radius=56, fill=255)
        elif self.decor == "diagonal":
            d.polygon([(x0, y0 + round((y1 - y0) * 0.38)), (x1, y0), (x1, y1), (x0, y1)], fill=255)
        else:  # circle: big, centred on the phones, kept inside the area
            cx, cy = (u[0] + u[2]) // 2, (u[1] + min(u[3], self.H)) // 2
            rad = round(max(u[2] - u[0], min(u[3], self.H) - u[1]) * 0.62)
            d.ellipse((cx - rad, cy - rad, cx + rad, cy + rad), fill=255)
            clip = Image.new("L", image.size, 0)
            ImageDraw.Draw(clip).rectangle((x0, y0, x1, y1), fill=255)
            mask = ImageChops.multiply(mask, clip)
        image.paste(self.fill(self.decor_colour), (0, 0), mask)


HALO = 40  # widest accent halo around the screen (style `shape`), px
BEZEL = 18  # phone frame around the screen, px


def _distance(a: Box, b: Box) -> int:
    """Gap between two boxes (0 when they touch or overlap)."""
    dx = max(b[0] - a[2], a[0] - b[2], 0)
    dy = max(b[1] - a[3], a[1] - b[3], 0)
    return max(dx, dy) if not (dx and dy) else min(dx, dy) + max(dx, dy)


def _layout(template: Template, genome: Genome) -> str:
    if "layout" in genome:
        return genome["layout"]
    return LEGACY_LAYOUT.get(genome.get("first_shot", "app_screen"), "split")


def compose(template: Template, genome: Genome, product_asset: str | Path | Image.Image,
            second_asset: str | Path | Image.Image | None = None) -> Composition:
    """The ad for this genome. `second_asset`: another real screen of the app (layout `two_screens`)."""
    template.check(genome)
    fmt = genome["format"]
    if fmt not in FORMATS:
        raise ComposeError(f"format {fmt!r} not supported (one of {sorted(FORMATS)})")
    layout, style = _layout(template, genome), genome.get("style", "gradient")
    if layout not in LAYOUTS:
        raise ComposeError(f"unknown layout {layout!r}; one of {list(LAYOUTS)}")
    content = template.fixed.get("content") or {}
    if layout in NEEDS and not content.get(NEEDS[layout]):
        raise ComposeError(f"layout {layout!r} needs a verified {NEEDS[layout]} in fixed.content")
    brand = Brand.from_fixed(template.fixed)
    asset = product_asset if isinstance(product_asset, Image.Image) else Image.open(product_asset)
    headline = template.text("hook", genome["hook"]).strip()
    if not headline:
        raise ComposeError(f"{template.id}: empty headline for hook {genome['hook']!r}")
    cta = template.text("cta", genome["cta"]).strip()
    if not cta:
        raise ComposeError(f"{template.id}: empty call to action")
    proof = template.text("proof", genome["proof"]).strip() if "proof" in genome else ""
    second = (second_asset if isinstance(second_asset, Image.Image) or second_asset is None
              else Image.open(second_asset))
    if layout == "two_screens" and second is None:
        raise ComposeError("layout 'two_screens' needs a second real screen")
    cv = Canvas(brand, FORMATS[fmt], style, asset, SAFE.get(fmt, (0, 0)), decor=genome.get("decor", "none"))
    cv.second = second
    DRAW[layout](cv, headline, proof, cta, content)
    return cv.finish()


# --- the ten layouts ---------------------------------------------------------------------------------------
# Each draws the screen first (nothing is drawn over it), then text and shapes in the space left. Positions
# are fractions of the canvas, so one layout works in the three formats. `tall` = portrait or story.

def _split(cv: Canvas, headline: str, proof: str, cta: str, content: dict) -> None:
    w, h = cv.w, cv.h
    cv.screen((600, MARGIN, w - 56, h - MARGIN))
    top = round(h * 0.11)
    cv.text("headline", headline, (MARGIN, top, 540, round(h * 0.56)), max_size=80, min_size=40, bold=True,
            align="left", valign="top", leading=1.1)
    if proof:
        cv.text("proof", proof, (MARGIN, round(h * 0.59), 540, round(h * 0.70)), max_size=36, align="left",
                valign="top")
    cv.pill(cta, (MARGIN, h - 220, MARGIN + 440, h - 124))


def _rising(cv: Canvas, headline: str, proof: str, cta: str, content: dict) -> None:
    w, h = cv.w, cv.h
    width = {1080: 600, 1350: 700, 1920: 780}.get(cv.H, 600)
    y = 56 + round(h * 0.17)
    after = y + (60 if proof else 0) + 98
    cv.screen((0, after + 40, w, h), rising=True, width=width)
    cv.text("headline", headline, (MARGIN, 56, w - MARGIN, y - 10), max_size=72, min_size=40, bold=True)
    if proof:
        cv.text("proof", proof, (MARGIN, y, w - MARGIN, y + 52), max_size=34)
        y += 60
    cv.pill(cta, (w // 2 - 190, y + 6, w // 2 + 190, y + 92))


def _full_screen(cv: Canvas, headline: str, proof: str, cta: str, content: dict) -> None:
    w, h = cv.w, cv.h
    band = round(h * 0.15)
    cv.screen((MARGIN, band + 40, w - MARGIN, h - 160))
    cv.text("headline", headline, (MARGIN, 40, w - MARGIN, band), max_size=64, min_size=36, bold=True)
    cv.pill(cta, (w // 2 - 200, h - 140, w // 2 + 200, h - 50))


def _review_card(cv: Canvas, headline: str, proof: str, cta: str, content: dict) -> None:
    """A real App Store review, quoted word for word, with its star rating (drawn), over the screen."""
    w, h = cv.w, cv.h
    review = content["review"]
    card_h = round(h * 0.36)
    card: Box = (MARGIN, 56, w - MARGIN, 56 + card_h)
    cv.screen((0, card[3] + 160, w, h), rising=True, width={1080: 560, 1350: 660, 1920: 760}.get(cv.H, 560))
    colour = cv.other(cv.base)
    cv.card(card, colour)
    n = max(1, min(5, int(review.get("rating", 5))))
    cv.stars(card[0] + 40, card[1] + 36, n)
    cv.text("quote", f"\"{review['text']}\"", (card[0] + 40, card[1] + 100, card[2] - 40, card[3] - 30),
            max_size=64, min_size=30, bold=True, align="left", valign="middle",
            fg=best_text_colour(colour, cv.brand.palette), bg=colour)
    cv.pill(cta, (w // 2 - 200, card[3] + 34, w // 2 + 200, card[3] + 120))


def _before_after(cv: Canvas, headline: str, proof: str, cta: str, content: dict) -> None:
    """The customer's objection (before) → the ad's headline (after), then the screen."""
    w, h = cv.w, cv.h
    obj = content["objection"]
    top, band = 56, round(h * 0.30)
    cv.screen((0, top + band + 160, w, h), rising=True, width={1080: 560, 1350: 660, 1920: 760}.get(cv.H, 560))
    left: Box = (MARGIN, top, 470, top + band)
    cv.card(left, cv.fg, outline=True)
    cv.text("before", str(obj["text"]), (left[0] + 28, left[1] + 24, left[2] - 28, left[3] - 24),
            max_size=48, min_size=28)
    cv.arrow((492, top + band // 2 - 36, 588, top + band // 2 + 36))
    cv.text("headline", headline, (610, top, w - MARGIN, top + band), max_size=60, min_size=32, bold=True,
            align="left")
    cv.pill(cta, (w // 2 - 200, top + band + 40, w // 2 + 200, top + band + 126))


def _big_number(cv: Canvas, headline: str, proof: str, cta: str, content: dict) -> None:
    """A number from a verified claim, very large, the claim itself under it."""
    w, h = cv.w, cv.h
    num = content["number"]
    nb = round(h * 0.22)
    cv.screen((0, 56 + nb + 240, w, h), rising=True, width={1080: 560, 1350: 660, 1920: 760}.get(cv.H, 560))
    cv.text("number", str(num["value"]), (MARGIN, 40, w - MARGIN, 40 + nb), max_size=240, min_size=80, bold=True,
            fg=cv.fg)
    cv.text("label", str(num["label"]), (MARGIN, 48 + nb, w - MARGIN, 48 + nb + 100), max_size=40, min_size=28)
    cv.pill(cta, (w // 2 - 200, 56 + nb + 110, w // 2 + 200, 56 + nb + 196))


def _benefits(cv: Canvas, headline: str, proof: str, cta: str, content: dict) -> None:
    """The headline and up to three verified benefits with drawn ticks, the screen on the right."""
    w, h = cv.w, cv.h
    cv.screen((620, MARGIN, w - 56, h - MARGIN))
    y = round(h * 0.08)
    hb = round(h * 0.26)
    cv.text("headline", headline, (MARGIN, y, 580, y + hb), max_size=64, min_size=36, bold=True, align="left",
            valign="top", leading=1.1)
    y += hb + 20
    row = round((h - 260 - y) / 3)
    for i, b in enumerate(content["benefits"][:3]):
        cv.mark(MARGIN, y + 8, 48, tick=True)
        cv.text(f"benefit_{i}", str(b), (MARGIN + 70, y, 580, y + row - 12), max_size=36, min_size=28,
                align="left", valign="top")
        y += row
    cv.pill(cta, (MARGIN, h - 210, MARGIN + 420, h - 120))


def _big_question(cv: Canvas, headline: str, proof: str, cta: str, content: dict) -> None:
    """The hook very large in the middle, the screen small at the bottom."""
    w, h = cv.w, cv.h
    qb = round(h * 0.34)
    cv.screen((0, 56 + qb + 150, w, h), rising=True, width={1080: 520, 1350: 620, 1920: 720}.get(cv.H, 520))
    cv.text("headline", headline, (MARGIN, 56, w - MARGIN, 56 + qb), max_size=120, min_size=48, bold=True,
            leading=1.05)
    cv.pill(cta, (w // 2 - 190, 56 + qb + 30, w // 2 + 190, 56 + qb + 114))


def _comparison(cv: Canvas, headline: str, proof: str, cta: str, content: dict) -> None:
    """Two cards: the objection (cross) and the ad's headline answering it (tick), then the screen."""
    w, h = cv.w, cv.h
    obj = content["objection"]
    top, ch = 56, round(h * 0.30)
    cv.screen((0, top + ch + 160, w, h), rising=True, width={1080: 560, 1350: 660, 1920: 760}.get(cv.H, 560))
    left: Box = (MARGIN, top, w // 2 - 14, top + ch)
    right: Box = (w // 2 + 14, top, w - MARGIN, top + ch)
    cv.card(left, cv.fg, outline=True)
    colour = cv.other(cv.base)
    cv.card(right, colour)
    cv.mark(left[0] + 24, left[1] + 24, 48, tick=False, colour=cv.fg)
    cv.mark(right[0] + 24, right[1] + 24, 48, tick=True)
    cv.text("before", str(obj["text"]), (left[0] + 24, left[1] + 92, left[2] - 24, left[3] - 24), max_size=52,
            min_size=28, align="left", valign="middle")
    on = best_text_colour(colour, cv.brand.palette)
    cv.text("headline", headline, (right[0] + 24, right[1] + 92, right[2] - 24, right[3] - 24),
            max_size=52, min_size=28, bold=True, align="left", valign="middle", fg=on, bg=colour)
    cv.pill(cta, (w // 2 - 200, top + ch + 40, w // 2 + 200, top + ch + 126))


def _bold_text(cv: Canvas, headline: str, proof: str, cta: str, content: dict) -> None:
    """Text first, like a post: the hook very large on top, a big screen rising at the bottom right."""
    w, h = cv.w, cv.h
    text_bottom = round(h * 0.50)
    cv.screen((w // 2 - 20, text_bottom + 40, w - 40, h), rising=True,
              width={1080: 440, 1350: 500, 1920: 560}.get(cv.H, 440))
    cv.text("headline", headline, (MARGIN, 64, w - MARGIN, text_bottom), max_size=140, min_size=48,
            bold=True, align="left", valign="top", leading=1.02)
    cv.pill(cta, (MARGIN, h - 180, MARGIN + 400, h - 90))


def _two_screens(cv: Canvas, headline: str, proof: str, cta: str, content: dict) -> None:
    """Two real screens of the app side by side, the second set lower, under the headline."""
    w, h = cv.w, cv.h
    hb = round(h * 0.17)
    top = 56 + hb + 130
    width = {1080: 380, 1350: 420, 1920: 460}.get(cv.H, 380)
    cv.screen((w // 2 - width - 30, top, w // 2 - 30, h), rising=True, width=width)
    assert cv.second is not None
    cv.screen((w // 2 + 30, top + 90, w // 2 + width + 30, h), rising=True, width=width, asset=cv.second)
    cv.text("headline", headline, (MARGIN, 56, w - MARGIN, 56 + hb), max_size=72, min_size=40, bold=True)
    cv.pill(cta, (w // 2 - 200, 56 + hb + 20, w // 2 + 200, 56 + hb + 104))


def _offer(cv: Canvas, headline: str, proof: str, cta: str, content: dict) -> None:
    """The offer first (the most winning format on Meta), only as the store page states it: "Free to download"."""
    w, h = cv.w, cv.h
    ob = round(h * 0.26)
    cv.screen((0, 56 + ob + 250, w, h), rising=True, width={1080: 520, 1350: 620, 1920: 720}.get(cv.H, 520))
    cv.text("offer", str(content["offer"]), (MARGIN, 40, w - MARGIN, 40 + ob), max_size=170, min_size=60, bold=True,
            leading=1.0, fg=cv.button if contrast_ratio(cv.button, cv.base) >= 3 else cv.fg)
    cv.text("headline", headline, (MARGIN, 52 + ob, w - MARGIN, 52 + ob + 110), max_size=46, min_size=28, bold=True)
    cv.pill(cta, (w // 2 - 200, 56 + ob + 130, w // 2 + 200, 56 + ob + 216))


def _note(cv: Canvas, headline: str, proof: str, cta: str, content: dict) -> None:
    """A phone note in the brand's voice: the headline as its title, verified benefits as ticked items."""
    w, h = cv.w, cv.h
    nb = round(h * 0.44)
    card: Box = (MARGIN, 48, w - MARGIN, 48 + nb)
    cv.screen((0, card[3] + 140, w, h), rising=True, width={1080: 440, 1350: 540, 1920: 660}.get(cv.H, 440))
    paper = cv.other(cv.base)
    ink = best_text_colour(paper, cv.brand.palette)
    cv.card(card, paper)
    cv.text("headline", headline, (card[0] + 44, card[1] + 36, card[2] - 44, card[1] + 36 + round(nb * 0.34)),
            max_size=58, min_size=32, bold=True, align="left", valign="top", fg=ink, bg=paper)
    items = content["benefits"][:3]
    top = card[1] + 60 + round(nb * 0.34)
    row = max(60, (card[3] - 30 - top) // max(1, len(items)))
    for i, b in enumerate(items):
        y = top + i * row
        cv.mark(card[0] + 44, y + 6, 44, tick=True)
        cv.text(f"item_{i}", str(b), (card[0] + 108, y, card[2] - 44, y + row - 8), max_size=38, min_size=28,
                align="left", valign="top", fg=ink, bg=paper)
    cv.pill(cta, (w // 2 - 200, card[3] + 30, w // 2 + 200, card[3] + 116))


DRAW = {"offer": _offer, "note": _note, "two_screens": _two_screens, "split": _split, "rising": _rising,
        "full_screen": _full_screen,
        "review_card": _review_card,
        "before_after": _before_after, "big_number": _big_number, "benefits": _benefits,
        "big_question": _big_question, "comparison": _comparison, "bold_text": _bold_text}

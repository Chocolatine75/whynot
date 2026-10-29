"""Brand palette from the app icon: deterministic, no model.

The accent is the icon's most frequent saturated colour; background and
foreground are a near-white and a near-black tinted with it, so text always
has strong contrast. The composer and guards check legibility again.
"""

import colorsys

from PIL import Image

RGB = tuple[int, int, int]


def _hex(c: RGB) -> str:
    return "#{:02X}{:02X}{:02X}".format(*c)


def _tint(accent: RGB, lightness: float, saturation: float) -> RGB:
    h, _, _ = colorsys.rgb_to_hls(*(x / 255 for x in accent))
    r, g, b = colorsys.hls_to_rgb(h, lightness, saturation)
    return (round(r * 255), round(g * 255), round(b * 255))


def accent_from_icon(icon: Image.Image, *, colours: int = 8) -> RGB:
    small = icon.convert("RGB").resize((64, 64), Image.Resampling.LANCZOS)
    quant = small.quantize(colors=colours, method=Image.Quantize.MEDIANCUT)
    palette = quant.getpalette() or []
    counts = sorted(quant.getcolors() or [], reverse=True)  # (count, index), most frequent first
    best: tuple[float, RGB] | None = None
    for count, index in counts:
        assert isinstance(index, int)
        c = (palette[3 * index], palette[3 * index + 1], palette[3 * index + 2])
        _, light, sat = colorsys.rgb_to_hls(*(x / 255 for x in c))
        if 0.2 <= light <= 0.8 and sat >= 0.35:
            score = count * sat
            if best is None or score > best[0]:
                best = (score, c)
    if best is None:  # greyscale icon: a neutral dark blue
        return (37, 99, 235)
    return best[1]


def _contrast(a: RGB, b: RGB) -> float:
    def lum(c: RGB) -> float:
        def ch(x: int) -> float:
            v = x / 255
            return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
        return 0.2126 * ch(c[0]) + 0.7152 * ch(c[1]) + 0.0722 * ch(c[2])
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def readable_accent(accent: RGB, background: RGB, foreground: RGB, *, minimum: float = 4.6) -> RGB:
    """The accent, darkened or lightened as little as possible (same hue) until button text on it
    (background or foreground colour) reaches WCAG AA. Bright reds/oranges/yellows need this."""
    def ok(c: RGB) -> bool:
        return max(_contrast(c, background), _contrast(c, foreground)) >= minimum
    if ok(accent):
        return accent
    h, light, sat = colorsys.rgb_to_hls(*(x / 255 for x in accent))
    for step in range(1, 100):
        for candidate_l in (light - step / 100, light + step / 100):
            if 0.0 <= candidate_l <= 1.0:
                r, g, b = colorsys.hls_to_rgb(h, candidate_l, sat)
                c = (round(r * 255), round(g * 255), round(b * 255))
                if ok(c) and c not in (background, foreground):
                    return c
    return foreground  # unreachable in practice: black/white extremes always pass


def palette_from_icon(icon: Image.Image) -> list[str]:
    """[background, foreground, accent, surface] as hex, for `fixed.brand.palette`.
    Background and surface are the two ends of the soft vertical gradient (a near-white tint of the brand).
    Guaranteed: body text ≥ 12:1 on both ends, button text ≥ 4.6:1 on the accent."""
    accent = accent_from_icon(icon)
    background = _tint(accent, 0.985, 0.5)
    surface = _tint(accent, 0.93, 0.55)
    foreground = _tint(accent, 0.11, 0.35)
    return [_hex(background), _hex(foreground), _hex(readable_accent(accent, background, foreground)), _hex(surface)]

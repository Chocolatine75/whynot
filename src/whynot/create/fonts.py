"""The font ads are drawn with: one that covers every Latin language we write ads in.

Pillow's built-in font cannot draw "é", "ß", "ñ" or "—", which forced French,
German or Spanish copy to lose its accents. Resolution order:
1. `WHYNOT_FONT` (path to a .ttf/.otf);
2. a font shipped in `assets/fonts/` (first .ttf/.otf, sorted);
3. well-known system fonts (Arial on macOS/Windows, DejaVu Sans on Linux);
4. Pillow's default (accented text is then refused by the glyph check, with a clear error).
A candidate is used only if it can draw every character in `REQUIRED`.
"""

import os
from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

REPO_FONTS = Path(__file__).resolve().parents[3] / "assets" / "fonts"
SYSTEM_BOLD_FONTS = (
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
)
SYSTEM_FONTS = (
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "C:/Windows/Fonts/arial.ttf",
)
# Accents and punctuation of the languages in create/locale.py.
REQUIRED = "éèêëàâäçîïôöùûüÿœæÉÀÇßñáíóúãõåøąćęłńśźżčěřšžůőűăîșț’‘“”«»—–…€"


def covers(font: ImageFont.FreeTypeFont, text: str = REQUIRED) -> bool:
    from whynot.create.composer import missing_glyphs  # avoid an import cycle
    return not missing_glyphs(font, text)


def _candidates(bold: bool = False) -> list[str]:
    paths: list[str] = []
    env = "WHYNOT_FONT_BOLD" if bold else "WHYNOT_FONT"
    if os.getenv(env):
        paths.append(os.environ[env])
    if REPO_FONTS.is_dir():
        files = [p for p in sorted(REPO_FONTS.iterdir()) if p.suffix.lower() in {".ttf", ".otf"}]
        paths += [str(p) for p in files if ("bold" in p.stem.lower()) == bold]
    return paths + list(SYSTEM_BOLD_FONTS if bold else SYSTEM_FONTS)


@lru_cache(maxsize=2)
def default_font_path(bold: bool = False) -> str | None:
    """Path of the first candidate that draws every required character, or None.
    Bold falls back to the regular font when no bold one is found."""
    if bold:
        found = _first_covering(_candidates(bold=True))
        return found or default_font_path(False)
    return _first_covering(_candidates())


def _first_covering(candidates: list[str]) -> str | None:
    for path in candidates:
        if not Path(path).is_file():
            continue
        try:
            font = ImageFont.truetype(path, 40)
        except OSError:
            continue
        if covers(font):
            return path
    return None


def load(size: int, path: str | None = None, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    chosen = path or default_font_path(bold)
    if chosen:
        return ImageFont.truetype(chosen, size)
    return ImageFont.load_default(size=size)

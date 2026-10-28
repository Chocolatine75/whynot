"""Parse SAM 3.1 output.

SAM 3.1 streams special-token text, one box and one mask per match:

    <|box;x1=12;y1=40;x2=300;y2=320;w=320;h=334;c=0.93|>
    <|mask;x=0;y=0;c=0.93;data=<H>,<W>,<enc><base85 payload>|>

Box corners are in source pixels; w/h are the source frame size. The mask raster
is H x W, smaller than the frame. Decoding the mask payload and mapping it back to
the frame is not documented yet (see docs/META_APIS.md): this module only parses
the records; mask decoding comes once verified on a real image.
"""

import re
from dataclasses import dataclass

# A record starts at "<|box;" or "<|mask;". The base85 mask payload may itself
# contain "|>", so a record ends at the last "|>" before the next record start.
_START = re.compile(r"<\|(box|mask);")


class SamParseError(ValueError):
    pass


@dataclass
class Box:
    x1: int
    y1: int
    x2: int
    y2: int
    frame_w: int
    frame_h: int
    confidence: float | None = None


@dataclass
class MaskRecord:
    height: int
    width: int
    encoding: str  # "~" lossless (default) or "!" one-bit
    payload: str  # base85
    confidence: float | None = None


def _fields(body: str) -> dict[str, str]:
    """Split `k=v;k=v` but keep `data=` (which may contain ';' in base85) whole."""
    head, sep, data = body.partition("data=")
    fields = dict(part.split("=", 1) for part in head.strip(";").split(";") if "=" in part)
    if sep:
        fields["data"] = data
    return fields


def _records(text: str) -> list[tuple[str, str]]:
    starts = list(_START.finditer(text))
    out = []
    for i, m in enumerate(starts):
        end_limit = starts[i + 1].start() if i + 1 < len(starts) else len(text)
        segment = text[m.end():end_limit]
        close = segment.rfind("|>")
        if close < 0:
            raise SamParseError(f"unterminated {m.group(1)} record at offset {m.start()}")
        out.append((m.group(1), segment[:close]))
    return out


def parse(text: str) -> tuple[list[Box], list[MaskRecord]]:
    boxes: list[Box] = []
    masks: list[MaskRecord] = []
    for kind, body in _records(text):
        f = _fields(body)
        try:
            conf = float(f["c"]) if "c" in f else None
            if kind == "box":
                box = Box(int(f["x1"]), int(f["y1"]), int(f["x2"]), int(f["y2"]), int(f["w"]), int(f["h"]), conf)
                if not (0 <= box.x1 <= box.x2 <= box.frame_w and 0 <= box.y1 <= box.y2 <= box.frame_h):
                    raise SamParseError(f"box outside its frame: {box}")
                boxes.append(box)
            else:
                h, w, rest = f["data"].split(",", 2)
                if not rest:
                    raise SamParseError("mask record without payload")
                masks.append(MaskRecord(int(h), int(w), rest[:1], rest[1:], conf))
        except (KeyError, ValueError) as exc:
            if isinstance(exc, SamParseError):
                raise
            raise SamParseError(f"malformed {kind} record: {exc!r}") from None
    return boxes, masks

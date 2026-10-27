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

_RECORD = re.compile(r"<\|(box|mask);(.*?)\|>", re.DOTALL)


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


def parse(text: str) -> tuple[list[Box], list[MaskRecord]]:
    boxes: list[Box] = []
    masks: list[MaskRecord] = []
    for kind, body in _RECORD.findall(text):
        f = _fields(body)
        conf = float(f["c"]) if "c" in f else None
        if kind == "box":
            boxes.append(Box(int(f["x1"]), int(f["y1"]), int(f["x2"]), int(f["y2"]),
                             int(f["w"]), int(f["h"]), conf))
        else:
            h, w, rest = f["data"].split(",", 2)
            masks.append(MaskRecord(int(h), int(w), rest[:1], rest[1:], conf))
    return boxes, masks

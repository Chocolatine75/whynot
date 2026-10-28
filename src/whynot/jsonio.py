"""Extract a JSON value from a model answer (fences, prose around it)."""

import json
import re
from typing import Any


class JSONExtractError(ValueError):
    pass


def extract_json(text: str) -> Any:
    """The outermost JSON object (or array) in `text`.

    Tries the whole answer, then a fenced block, then the span from the first
    opening to the last closing bracket.
    """
    candidates = [text.strip()]
    fenced = re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL)
    candidates += [f.strip() for f in fenced]
    for open_c, close_c in (("{", "}"), ("[", "]")):
        start, end = text.find(open_c), text.rfind(close_c)
        if 0 <= start < end:
            candidates.append(text[start:end + 1])
    last_error = "no JSON in the answer"
    for c in candidates:
        if not c:
            continue
        try:
            return json.loads(c)
        except json.JSONDecodeError as exc:
            last_error = f"invalid JSON: {exc}"
    raise JSONExtractError(last_error)

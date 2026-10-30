"""Recorded model answers ("cassettes"): pay for a model answer once, replay it for free.

`ModelClient` consults a `Cassette` on every chat call, by mode (`WHYNOT_CASSETTE`):

- `off` (default): every call goes to the API;
- `record`: calls go to the API and each answer is saved;
- `replay`: answers come from disk only. The network is never touched, and a
  request with no recording fails loudly (`CassetteMissing`) instead of
  silently calling, and paying for, the API.

A recording is keyed by a hash of (model, messages, call parameters), so any
change to a prompt, a feed, an image or `reasoning_effort` is a different key.
Only the answer text, finish reason and token usage are stored, never the
request: prompts can be long and can hold partner data. Known secrets and
token-shaped strings are scrubbed from the answer before it is written.

Where recordings go: `WHYNOT_CASSETTE_DIR` (default `tests/cassettes/`, which
is committed). Record partner runs into `data/private/` instead.
"""

import hashlib
import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

MODES = ("off", "record", "replay")
# Meta user / system tokens start with EAA; `access_token=` covers tokens in URLs.
_TOKEN_SHAPES = re.compile(r"EAA[A-Za-z0-9]{20,}|(?<=access_token=)[^&\s\"']+")
REDACTED = "[REDACTED]"


class CassetteMissing(RuntimeError):
    """Replay mode found no recording for a request: record it first (WHYNOT_CASSETTE=record)."""


def request_key(model: str, messages: list[dict[str, Any]], params: dict[str, Any]) -> str:
    """Stable id of a request: same model, messages and parameters → same key, whatever the dict order."""
    blob = json.dumps({"model": model, "messages": messages, "params": params}, sort_keys=True,
                      ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:32]


def scrub(text: str, secrets: tuple[str | None, ...] = ()) -> str:
    """`text` without the given secret values and without anything shaped like a Meta token."""
    for secret in secrets:
        if secret:
            text = text.replace(secret, REDACTED)
    return _TOKEN_SHAPES.sub(REDACTED, text)


@dataclass(frozen=True)
class Recording:
    model: str
    module: str  # which part of whynot made the call, for humans reading the folder
    text: str
    finish_reason: str | None
    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0


class Cassette:
    """A folder of recordings, one JSON file per request key. Writes are atomic, so threads can share it."""

    def __init__(self, folder: Path, mode: str = "off", *, secrets: tuple[str | None, ...] = ()):
        if mode not in MODES:
            raise ValueError(f"cassette mode must be one of {MODES}, got {mode!r}")
        self.folder = Path(folder)
        self.mode = mode
        self._secrets = secrets

    @property
    def replaying(self) -> bool:
        return self.mode == "replay"

    @property
    def recording(self) -> bool:
        return self.mode == "record"

    def path(self, key: str) -> Path:
        return self.folder / f"{key}.json"

    def get(self, key: str) -> Recording | None:
        p = self.path(key)
        if not p.exists():
            return None
        data = json.loads(p.read_text(encoding="utf-8"))
        return Recording(**{k: v for k, v in data.items() if k in Recording.__dataclass_fields__})

    def load(self, key: str, *, model: str, module: str) -> Recording:
        """The recording for `key`, or `CassetteMissing` with what to do about it."""
        rec = self.get(key)
        if rec is None:
            raise CassetteMissing(f"no recording for {module} call to {model} (key {key}) in {self.folder}: "
                                  "run once with WHYNOT_CASSETTE=record")
        return rec

    def put(self, key: str, rec: Recording) -> Path:
        clean = Recording(**{**asdict(rec), "text": scrub(rec.text, self._secrets)})
        self.folder.mkdir(parents=True, exist_ok=True)
        body = json.dumps({"key": key, **asdict(clean)}, indent=1, ensure_ascii=False) + "\n"
        fd, tmp = tempfile.mkstemp(dir=self.folder, prefix=".tmp-", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(body)
        os.replace(tmp, self.path(key))  # readers never see half a file
        return self.path(key)

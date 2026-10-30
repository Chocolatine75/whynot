"""ElevenLabs: the voice-over (with per-character timing, for word-by-word captions) and the music bed.

Meta's hackathon models have no text-to-speech, so audio comes from ElevenLabs; every word it says was
written and checked by our agents (the brief's narration), and Muse Voice Transcribe listens back to
check it (`audio/captions.py`).

Both calls are cached on disk by a hash of the request: a voice or a track is generated once, then reused
across reruns. The API key travels only in the `xi-api-key` header and is redacted from every error.
"""

import base64
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

API = "https://api.elevenlabs.io/v1"
DEFAULT_VOICE = "21m00Tcm4TlvDq8ikWAM"  # a premade voice available on every account ("Rachel")
VOICE_MODEL = "eleven_multilingual_v2"  # handles every language we advertise in
MUSIC_PROMPTS = {
    "upbeat": "Upbeat modern pop instrumental for a mobile app ad, bright synths, light drums, feel-good",
    "calm": "Calm warm acoustic instrumental, soft piano and guitar, gentle, for a mobile app ad",
    "playful": "Playful quirky instrumental, pizzicato and marimba, light percussion, for a mobile app ad",
    "inspiring": "Inspiring cinematic instrumental, building piano and strings, hopeful, for a mobile app ad",
    "dramatic": "Dramatic tense instrumental, pulsing bass and drums, cinematic hits, for a mobile app ad",
}

SFX_PROMPTS = {  # one short effect per cut type, generated once and reused by every video
    "whoosh": "Fast whoosh transition swoosh, short, punchy, for a social video cut",
    "pop": "Short cartoon pop bubble sound, bright, satisfying",
    "ding": "Bright notification ding, single chime, clean",
    "record_scratch": "Vinyl record scratch, comedic stop, short",
    "bass_drop": "Deep cinematic bass drop hit with sub boom, short",
}


class ElevenLabsError(RuntimeError):
    pass


@dataclass(frozen=True)
class Voice:
    mp3: Path
    characters: list[str]
    starts: list[float]
    ends: list[float]

    @property
    def seconds(self) -> float:
        return self.ends[-1] if self.ends else 0.0


class ElevenLabs:
    def __init__(self, api_key: str, cache: Path, *, http: httpx.Client | None = None, base_url: str = API):
        if not api_key:
            raise ElevenLabsError("no ElevenLabs key: set ELEVENLABS_API_KEY in .env")
        self.key = api_key
        self.cache = Path(cache)
        self.http = http or httpx.Client(timeout=180)
        self.base = base_url

    def _post(self, path: str, body: dict[str, Any], **params: Any) -> httpx.Response:
        try:
            r = self.http.post(f"{self.base}{path}", json=body, params=params or None,
                               headers={"xi-api-key": self.key, "Content-Type": "application/json"})
        except httpx.HTTPError as exc:
            raise ElevenLabsError(f"request failed: {exc}".replace(self.key, "[REDACTED]")) from None
        if r.status_code >= 400:
            raise ElevenLabsError(f"HTTP {r.status_code}: {r.text[:300]}".replace(self.key, "[REDACTED]"))
        return r

    @staticmethod
    def _key(kind: str, body: dict[str, Any]) -> str:
        return hashlib.sha256(json.dumps({"kind": kind, **body}, sort_keys=True).encode()).hexdigest()[:24]

    def voice(self, text: str, *, voice_id: str = DEFAULT_VOICE, model_id: str = VOICE_MODEL,
              seed: int = 7) -> Voice:
        """The narration as an MP3 plus the start/end time of every character."""
        body = {"text": text, "model_id": model_id, "seed": seed,
                "voice_settings": {"stability": 0.45, "similarity_boost": 0.8, "style": 0.25, "speed": 1.05}}
        key = self._key(f"voice:{voice_id}", body)
        mp3, meta = self.cache / f"voice-{key}.mp3", self.cache / f"voice-{key}.json"
        if not (mp3.exists() and meta.exists()):
            data = self._post(f"/text-to-speech/{voice_id}/with-timestamps", body).json()
            al = data.get("alignment") or data.get("normalized_alignment")
            if not data.get("audio_base64") or not al:
                raise ElevenLabsError("no audio or no alignment in the answer")
            self.cache.mkdir(parents=True, exist_ok=True)
            mp3.write_bytes(base64.b64decode(data["audio_base64"]))
            meta.write_text(json.dumps({"characters": al["characters"],
                                        "starts": al["character_start_times_seconds"],
                                        "ends": al["character_end_times_seconds"]}))
        m = json.loads(meta.read_text())
        return Voice(mp3, m["characters"], m["starts"], m["ends"])

    def music(self, mood: str, seconds: float) -> Path:
        """An instrumental bed for the mood, `seconds` long (rounded up to the second, min 3 s)."""
        if mood not in MUSIC_PROMPTS:
            raise ValueError(f"unknown mood {mood!r}")
        body = {"prompt": MUSIC_PROMPTS[mood], "music_length_ms": max(3000, int(seconds + 0.999) * 1000),
                "force_instrumental": True}
        path = self.cache / f"music-{self._key('music', body)}.mp3"
        if not path.exists():
            r = self._post("/music", body)
            if not r.content:
                raise ElevenLabsError("empty music answer")
            self.cache.mkdir(parents=True, exist_ok=True)
            path.write_bytes(r.content)
        return path

    def sfx(self, name: str) -> Path:
        """A short sound effect for a cut (`SFX_PROMPTS`), generated once."""
        if name not in SFX_PROMPTS:
            raise ValueError(f"unknown sound effect {name!r}")
        body = {"text": SFX_PROMPTS[name], "duration_seconds": 1.0, "prompt_influence": 0.6}
        path = self.cache / f"sfx-{name}-{self._key('sfx', body)}.mp3"
        if not path.exists():
            r = self._post("/sound-generation", body)
            if not r.content:
                raise ElevenLabsError("empty sound effect answer")
            self.cache.mkdir(parents=True, exist_ok=True)
            path.write_bytes(r.content)
        return path

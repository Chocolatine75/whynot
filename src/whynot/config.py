"""Settings read from the environment (.env at the repo root)."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    model_api_key: str | None
    model_base_url: str
    baseten_api_key: str | None
    baseten_base_url: str
    baseten_model: str
    cost_log: Path
    fb_token: str | None = None
    fb_api_version: str = "v26.0"
    viewer_backend: str = "meta"  # "meta" (Muse Spark on the Meta API) or "baseten" (Muse Spark Open)
    viewer_model: str = "muse-spark-1.3"  # used when viewer_backend == "meta"
    autonomy_level: str = "dry_run"  # dry_run | propose | autopilot (see autopilot.py)
    # Marketing API (publishing). Sandbox and live are separate accounts and tokens on purpose.
    meta_token: str | None = None
    meta_ad_account_id: str | None = None
    meta_sandbox_token: str | None = None
    meta_sandbox_ad_account_id: str | None = None
    meta_page_id: str | None = None
    meta_app_id: str | None = None
    max_daily_ad_spend_eur: float = 0.0  # hard cap; 0 = no live spend
    cassette_mode: str = "off"  # off | record | replay (see cassette.py)
    cassette_dir: Path = REPO_ROOT / "tests" / "cassettes"
    viewer_cache_dir: Path | None = None  # cached viewer answers (see sim/viewer.py); None = no cache
    elevenlabs_api_key: str | None = None  # voice-over and music (Meta has no text-to-speech model)
    elevenlabs_voice_id: str | None = None


def _clean(value: str | None) -> str:
    """Env value without an inline comment (`VALUE   # note`)."""
    return (value or "").split("#", 1)[0].strip()


def _float(name: str, default: float) -> float:
    raw = _clean(os.getenv(name))
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        raise ValueError(f"{name} must be a number, got {raw!r}") from None


def _viewer_cache_dir(raw: str) -> Path | None:
    """WHYNOT_VIEWER_CACHE: a folder, "off" to disable, or empty for the default data/cache/viewers."""
    if raw.lower() == "off":
        return None
    return Path(raw) if raw else REPO_ROOT / "data" / "cache" / "viewers"


def load_settings() -> Settings:
    load_dotenv(REPO_ROOT / ".env")
    return Settings(
        model_api_key=os.getenv("MODEL_API_KEY") or None,
        model_base_url=os.getenv("META_MODEL_BASE_URL", "https://api.meta.ai/v1"),
        baseten_api_key=os.getenv("BASETEN_API_KEY") or None,
        baseten_base_url=os.getenv("BASETEN_BASE_URL", "https://inference.baseten.co/v1"),
        baseten_model=os.getenv("BASETEN_MODEL", "meta-models/muse-spark-open-1026"),
        cost_log=Path(os.getenv("WHYNOT_COST_LOG") or REPO_ROOT / "outputs" / "costs.jsonl"),
        fb_token=os.getenv("FB_TOKEN") or None,
        fb_api_version=os.getenv("FB_API_VERSION", "v26.0"),
        viewer_backend=os.getenv("VIEWER_BACKEND", "meta"),
        viewer_model=os.getenv("VIEWER_MODEL", "muse-spark-1.3"),
        autonomy_level=_clean(os.getenv("AUTONOMY_LEVEL")) or "dry_run",
        meta_token=_clean(os.getenv("META_ACCESS_TOKEN")) or None,
        meta_ad_account_id=_clean(os.getenv("META_AD_ACCOUNT_ID")) or None,
        meta_sandbox_token=_clean(os.getenv("META_SANDBOX_TOKEN")) or None,
        meta_sandbox_ad_account_id=_clean(os.getenv("META_SANDBOX_AD_ACCOUNT_ID")) or None,
        meta_page_id=_clean(os.getenv("META_PAGE_ID")) or None,
        meta_app_id=_clean(os.getenv("META_APP_ID")) or None,
        max_daily_ad_spend_eur=_float("MAX_DAILY_AD_SPEND_EUR", 0.0),
        cassette_mode=_clean(os.getenv("WHYNOT_CASSETTE")) or "off",
        cassette_dir=Path(_clean(os.getenv("WHYNOT_CASSETTE_DIR")) or REPO_ROOT / "tests" / "cassettes"),
        elevenlabs_api_key=_clean(os.getenv("ELEVENLABS_API_KEY")) or None,
        elevenlabs_voice_id=_clean(os.getenv("ELEVENLABS_VOICE_ID")) or None,
        viewer_cache_dir=_viewer_cache_dir(_clean(os.getenv("WHYNOT_VIEWER_CACHE"))),
    )

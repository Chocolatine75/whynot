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
    max_daily_ad_spend_eur: float = 0.0  # hard cap; 0 = no live spend


def load_settings() -> Settings:
    load_dotenv(REPO_ROOT / ".env")
    return Settings(
        model_api_key=os.getenv("MODEL_API_KEY") or None,
        model_base_url=os.getenv("META_MODEL_BASE_URL", "https://api.meta.ai/v1"),
        baseten_api_key=os.getenv("BASETEN_API_KEY") or None,
        baseten_base_url=os.getenv("BASETEN_BASE_URL", "https://inference.baseten.co/v1"),
        baseten_model=os.getenv("BASETEN_MODEL", "meta-models/muse-spark-open"),
        cost_log=Path(os.getenv("WHYNOT_COST_LOG") or REPO_ROOT / "outputs" / "costs.jsonl"),
        fb_token=os.getenv("FB_TOKEN") or None,
        fb_api_version=os.getenv("FB_API_VERSION", "v26.0"),
        viewer_backend=os.getenv("VIEWER_BACKEND", "meta"),
        viewer_model=os.getenv("VIEWER_MODEL", "muse-spark-1.3"),
        autonomy_level=(os.getenv("AUTONOMY_LEVEL") or "dry_run").split("#")[0].strip(),
        max_daily_ad_spend_eur=float((os.getenv("MAX_DAILY_AD_SPEND_EUR") or "0").split("#")[0].strip()),
    )
